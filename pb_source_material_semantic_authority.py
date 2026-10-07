"""Producer-owned material schedule and finish-semantic authority.

This module lifts material/finish schedule semantics onto the same immutable
source lineage used by physical PlanReader authorities. It does not create a
physical surface or publish a quantity.

Definitions are admitted only from authenticated SCHEDULE / LEGEND /
SPECIFICATION viewports produced by the source PDF. Drawing occurrences are
admitted only inside independently authenticated non-schedule viewports and
only for codes already confirmed by the schedule universe.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

import fitz
from PIL import Image, ImageOps

from pb_drawing_evidence_binding import DrawingViewClassifier, DrawingViewType
from pb_material_schedule_v1222 import (
    SCHEDULE_WORDS,
    _compatible_descriptions,
    _defined_codes_in_text,
    parse_schedule_text,
    semantic_finish_from_schedule_entry,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_pdf_text_integrity_authority import (
    TEXT_CLIP_STATE_UNRESOLVED,
    TEXT_GLYPH_MAPPING_UNVERIFIED,
)
from pb_portable_raster_ocr_authority import TesseractOCRBackend
from pb_raster_text_corroboration_authority import (
    RASTER_TEXT_CORROBORATION_DPIS,
    RasterTextCorroborationProducer,
    RasterTextCorroborationSelector,
    _lossless_rotate,
    _producer_owned_ocr_target,
    normalize_reading,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    SegmentedViewport,
    ViewportSegmentationStatus,
    is_authoritative_derived_viewport,
    is_segment_page_viewports_product,
    segment_page_viewports,
    validate_non_overlapping_viewports,
)

SOURCE_MATERIAL_SEMANTIC_SCHEMA_VERSION = "1.0.0"

SOURCE_MATERIAL_DEFINITION_RESOLVED = "source_material_definition_resolved"
SOURCE_MATERIAL_DEFINITION_UNAVAILABLE = "source_material_definition_unavailable"
SOURCE_MATERIAL_DEFINITION_CONFLICT = "source_material_definition_conflict"
SOURCE_MATERIAL_SCOPE_RESOLVED = "source_material_occurrence_scope_resolved"
SOURCE_MATERIAL_SCOPE_UNAVAILABLE = "source_material_occurrence_scope_unavailable"
SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE = "source_material_source_integrity_failure"
SOURCE_MATERIAL_VIEWPORT_UNAUTHENTICATED = "source_material_viewport_unauthenticated"

_SCHEDULE_VIEW_TYPES = frozenset(
    {
        DrawingViewType.SCHEDULE.value,
        DrawingViewType.LEGEND.value,
        DrawingViewType.SPECIFICATION.value,
    }
)


def _is_explicit_non_material_schedule(viewport: SegmentedViewport) -> bool:
    """Exclude source-proven door/window schedules from material semantics.

    These schedules are legitimate semantic tables, but they do not define the
    material-finish dictionary owned by this producer. An unreadable door or
    window schedule therefore must not poison otherwise complete finish
    schedules, legends or specifications. Ambiguous/general semantic sources
    remain fail-closed.
    """
    if viewport.view_type != DrawingViewType.SCHEDULE.value:
        return False
    label = " ".join(
        str(viewport.label or "").strip().casefold().replace(".", "").split()
    )
    return label.startswith(
        (
            "door schedule",
            "window schedule",
            "schedule of doors",
            "schedule of windows",
        )
    )


_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_MATERIAL_LINE_OCR_BLANK_MARGIN_MM = 1.0


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


@dataclass(frozen=True)
class SourceMaterialDefinitionSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    code: str

    def __post_init__(self) -> None:
        for name in ("document_id", "revision_id", "source_sha256", "snapshot_id", "code"):
            _required(getattr(self, name), name)

    @property
    def key(self) -> tuple[str, str, str, str, str]:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.code.strip().upper(),
        )


@dataclass(frozen=True)
class SourceMaterialOccurrenceSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "viewport_id",
        ):
            _required(getattr(self, name), name)

    @property
    def key(self) -> tuple[str, str, str, str, str, str]:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            self.viewport_id,
        )


@dataclass(frozen=True)
class SourceMaterialDefinitionRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    code: str
    description: str
    substrate: str
    finish: str
    semantic_finish: str
    source_definition_ids: tuple[str, ...]
    source_page_ids: tuple[str, ...]
    source_viewport_ids: tuple[str, ...]
    schema_version: str = SOURCE_MATERIAL_SEMANTIC_SCHEMA_VERSION


@dataclass(frozen=True)
class SourceMaterialDefinitionResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[SourceMaterialDefinitionRecord] = None
    schema_version: str = SOURCE_MATERIAL_SEMANTIC_SCHEMA_VERSION


@dataclass(frozen=True)
class SourceMaterialOccurrenceRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    code: str
    semantic_finish: str
    definition_record_id: str
    bbox_pdf_pts: tuple[float, float, float, float]
    raw_text: str
    source_evidence_id: str
    source_text_observation_ids: tuple[str, ...] = ()
    schema_version: str = SOURCE_MATERIAL_SEMANTIC_SCHEMA_VERSION


@dataclass(frozen=True)
class SourceMaterialOccurrenceScopeResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    scope_complete: bool
    records: tuple[SourceMaterialOccurrenceRecord, ...]
    schema_version: str = SOURCE_MATERIAL_SEMANTIC_SCHEMA_VERSION


def _definition_blocked(
    status: EvidenceResolutionStatus,
    *reasons: str,
) -> SourceMaterialDefinitionResult:
    return SourceMaterialDefinitionResult(
        status=status,
        reason_codes=tuple(dict.fromkeys(r for r in reasons if r)),
        record=None,
    )


def _scope_blocked(
    status: EvidenceResolutionStatus,
    *reasons: str,
) -> SourceMaterialOccurrenceScopeResult:
    return SourceMaterialOccurrenceScopeResult(
        status=status,
        reason_codes=tuple(dict.fromkeys(r for r in reasons if r)),
        scope_complete=False,
        records=(),
    )


def _viewport_is_authoritative(
    viewport: SegmentedViewport,
    *,
    sibling_non_overlapping: bool,
) -> bool:
    return bool(
        viewport.bounding_box is not None
        and (
            viewport.status == ViewportSegmentationStatus.RESOLVED.value
            or (
                sibling_non_overlapping
                and is_authoritative_derived_viewport(viewport)
            )
        )
    )


@dataclass(frozen=True)
class _TrustedTextWord:
    observation_id: str
    page_id: str
    source_partition_id: str
    text: str
    bbox: tuple[float, float, float, float]
    block_no: int
    line_no: int
    word_no: int
    trusted: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class _TrustedScheduleBlock:
    page_id: str
    source_partition_id: str
    block_no: int
    scope_id: str
    text: str
    line_evidence: Mapping[str, tuple[str, ...]]


def _is_material_schedule_title(value: object) -> bool:
    text = " ".join(str(value or "").strip().casefold().split())
    if not text or not any(token in text for token in SCHEDULE_WORDS):
        return False
    return (
        DrawingViewClassifier.classify_text(str(value or "")).value
        == DrawingViewType.SCHEDULE.value
    )


def _trusted_native_material_schedule_blocks(
    words: Sequence[_TrustedTextWord],
) -> tuple[_TrustedScheduleBlock, ...]:
    """Return only complete trusted native blocks headed by a material schedule.

    This is an independent source-ownership route for schedules whose outer
    vector frame is ambiguous. It never chooses a competing rectangle. The PDF
    text structure itself must put exactly one qualified material/finish
    schedule title at the first line of one source partition/block, followed by
    contiguous complete trusted rows in that same block.
    """

    grouped: dict[tuple[str, int], list[_TrustedTextWord]] = {}
    for word in words:
        if not word.source_partition_id:
            continue
        grouped.setdefault(
            (word.source_partition_id, int(word.block_no)),
            [],
        ).append(word)

    out: list[_TrustedScheduleBlock] = []
    for (partition_id, block_no), block_words in sorted(grouped.items()):
        if not block_words or any(not word.trusted for word in block_words):
            continue
        by_line: dict[int, list[_TrustedTextWord]] = {}
        for word in block_words:
            by_line.setdefault(int(word.line_no), []).append(word)
        line_numbers = sorted(by_line)
        if len(line_numbers) < 2:
            continue
        if line_numbers != list(range(line_numbers[0], line_numbers[-1] + 1)):
            continue

        lines: list[tuple[str, tuple[str, ...]]] = []
        valid = True
        for line_no in line_numbers:
            line_words = sorted(
                by_line[line_no],
                key=lambda row: (row.word_no, row.bbox[0], row.observation_id),
            )
            word_numbers = [int(row.word_no) for row in line_words]
            if (
                not word_numbers
                or len(set(word_numbers)) != len(word_numbers)
                or word_numbers
                != list(range(word_numbers[0], word_numbers[-1] + 1))
            ):
                valid = False
                break
            text = " ".join(
                row.text.strip() for row in line_words if row.text.strip()
            ).strip()
            if not text:
                valid = False
                break
            lines.append(
                (
                    text,
                    tuple(row.observation_id for row in line_words),
                )
            )
        if not valid or len(lines) < 2:
            continue
        title_indices = [
            index
            for index, (text, _ids) in enumerate(lines)
            if _is_material_schedule_title(text)
        ]
        if title_indices != [0]:
            continue

        page_ids = {word.page_id for word in block_words}
        if len(page_ids) != 1:
            continue
        page_id = next(iter(page_ids))
        scope_id = stable_contract_id(
            "source_material_native_schedule_block",
            {
                "page_id": page_id,
                "source_partition_id": partition_id,
                "block_no": block_no,
                "title": lines[0][0],
                "observation_ids": tuple(
                    observation_id
                    for _text, observation_ids in lines
                    for observation_id in observation_ids
                ),
            },
            digest_chars=32,
        )
        out.append(
            _TrustedScheduleBlock(
                page_id=page_id,
                source_partition_id=partition_id,
                block_no=block_no,
                scope_id=scope_id,
                text="\n".join(text for text, _ids in lines),
                line_evidence=MappingProxyType(
                    {text: ids for text, ids in lines}
                ),
            )
        )
    return tuple(out)


def _bbox_fully_inside(
    inner: Sequence[float],
    outer: Sequence[float],
    *,
    tolerance: float = 1e-6,
) -> bool:
    return (
        float(inner[0]) >= float(outer[0]) - tolerance
        and float(inner[1]) >= float(outer[1]) - tolerance
        and float(inner[2]) <= float(outer[2]) + tolerance
        and float(inner[3]) <= float(outer[3]) + tolerance
    )


def _bbox_intersects(
    left: Sequence[float],
    right: Sequence[float],
    *,
    tolerance: float = 1e-6,
) -> bool:
    return not (
        float(left[2]) <= float(right[0]) + tolerance
        or float(right[2]) <= float(left[0]) + tolerance
        or float(left[3]) <= float(right[1]) + tolerance
        or float(right[3]) <= float(left[1]) + tolerance
    )


def _trusted_words_by_page(
    source: SourceVisibilityProducer,
    published: object,
) -> dict[str, tuple[_TrustedTextWord, ...]]:
    """Resolve the producer-owned PDF text-integrity receipt for every word."""

    authority = source.text_integrity_authority()
    rows: dict[str, list[_TrustedTextWord]] = {}
    for observation_id in tuple(
        getattr(published, "text_observation_ids", ()) or ()
    ):
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=str(observation_id),
        )
        result = authority.resolve_text(selector)
        receipt = result.receipt
        if receipt is None:
            # Published text ids are producer-owned and must always carry their
            # receipt. Treat a missing receipt as a source-integrity failure
            # rather than silently dropping a word.
            raise RuntimeError(SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE)
        try:
            bbox = tuple(float(value) for value in receipt.geometry)
        except (TypeError, ValueError):
            raise RuntimeError(SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE)
        if (
            len(bbox) != 4
            or bbox[2] <= bbox[0]
            or bbox[3] <= bbox[1]
        ):
            raise RuntimeError(SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE)
        page_id = str(receipt.page_id)
        trusted_text = (
            str(result.trusted_text)
            if (
                result.status is EvidenceResolutionStatus.CORROBORATED
                and result.trusted_text is not None
            )
            else None
        )
        reason_codes = tuple(result.reason_codes or ())
        trusted = trusted_text is not None

        rows.setdefault(page_id, []).append(
            _TrustedTextWord(
                observation_id=str(observation_id),
                page_id=page_id,
                source_partition_id=str(receipt.source_partition_id or ""),
                text=str(trusted_text or receipt.raw_text or ""),
                bbox=bbox,
                block_no=int(receipt.block_no or 0),
                line_no=int(receipt.line_no or 0),
                word_no=int(receipt.word_no or 0),
                trusted=trusted,
                reason_codes=reason_codes,
            )
        )
    return {
        page_id: tuple(
            sorted(
                values,
                key=lambda row: (
                    row.block_no,
                    row.line_no,
                    row.word_no,
                    row.bbox,
                    row.observation_id,
                ),
            )
        )
        for page_id, values in rows.items()
    }


def _recover_admissible_viewport_words(
    *,
    source: SourceVisibilityProducer,
    published: object,
    raster: RasterTextCorroborationProducer,
    words: Sequence[_TrustedTextWord],
    viewport: SegmentedViewport,
) -> tuple[_TrustedTextWord, ...]:
    """Recover only admissible words owned by one authenticated viewport.

    This deliberately avoids document-wide OCR. Words outside the viewport,
    crossing its boundary, or blocked for any reason other than the existing
    glyph/clip pair are returned unchanged and remain fail-closed downstream.
    """
    assert viewport.bounding_box is not None
    authority = source.text_integrity_authority()
    admissible = {
        TEXT_GLYPH_MAPPING_UNVERIFIED,
        TEXT_CLIP_STATE_UNRESOLVED,
    }
    recovered: list[_TrustedTextWord] = []
    for word in words:
        if (
            word.trusted
            or not _bbox_fully_inside(word.bbox, viewport.bounding_box)
        ):
            recovered.append(word)
            continue
        reason_set = set(word.reason_codes)
        if (
            TEXT_GLYPH_MAPPING_UNVERIFIED not in reason_set
            or not reason_set.issubset(admissible)
        ):
            recovered.append(word)
            continue
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=word.observation_id,
        )
        native = authority.resolve_text(selector)
        receipt = native.receipt
        if (
            native.status is not EvidenceResolutionStatus.ABSTAINED
            or receipt is None
            or bool(receipt.trusted)
            or tuple(native.reason_codes or ()) != tuple(word.reason_codes)
            or tuple(receipt.reason_codes or ()) != tuple(word.reason_codes)
        ):
            recovered.append(word)
            continue
        raster_result = raster.publish(
            RasterTextCorroborationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=word.observation_id,
            )
        )
        if (
            raster_result.status is EvidenceResolutionStatus.CORROBORATED
            and raster_result.record is not None
            and str(raster_result.corroborated_text or "").strip()
        ):
            recovered.append(
                _TrustedTextWord(
                    observation_id=word.observation_id,
                    page_id=word.page_id,
                    source_partition_id=word.source_partition_id,
                    text=str(raster_result.corroborated_text),
                    bbox=word.bbox,
                    block_no=word.block_no,
                    line_no=word.line_no,
                    word_no=word.word_no,
                    trusted=True,
                    reason_codes=tuple(
                        dict.fromkeys(
                            (*word.reason_codes, "raster_text_corroborated")
                        )
                    ),
                )
            )
        else:
            recovered.append(word)
    return tuple(recovered)


def _single_isolated_material_line_reading(
    backend,
    image: Image.Image,
    *,
    dpi: int,
) -> Optional[str]:
    """Read one already-isolated producer-owned source material line."""
    if backend is None or not backend.is_available():
        return None
    if type(backend) is TesseractOCRBackend:
        try:
            import pytesseract

            command = backend._resolved_cmd()
            if not command:
                return None
            pytesseract.pytesseract.tesseract_cmd = command
            raw = pytesseract.image_to_string(image, config="--psm 7")
        except Exception:
            return None
        readings = tuple(
            normalize_reading(line)
            for line in str(raw or "").splitlines()
            if normalize_reading(line)
        )
        return readings[0] if len(readings) == 1 else None
    try:
        lines = tuple(backend.extract_lines(image, dpi=int(dpi)))
    except Exception:
        return None
    readings = tuple(
        normalize_reading(getattr(line, "text", ""))
        for line in lines
        if normalize_reading(getattr(line, "text", ""))
    )
    return readings[0] if len(readings) == 1 else None


def _recover_admissible_viewport_lines(
    *,
    source: SourceVisibilityProducer,
    published: object,
    raster: RasterTextCorroborationProducer,
    words: Sequence[_TrustedTextWord],
    viewport: SegmentedViewport,
) -> tuple[_TrustedTextWord, ...]:
    """Corroborate exact native lines when per-word OCR remains unresolved.

    This is deliberately the same narrow evidence class used by source-room
    labels: every unresolved word must be producer-owned native text blocked
    only by glyph mapping and optional clip-state ownership; the producer-owned
    raster targets for that exact native line are unioned; and two independent
    renders must both read exactly the native whole line.
    """
    assert viewport.bounding_box is not None
    backend = getattr(raster, "_backend", None)
    if backend is None or not backend.is_available():
        return tuple(words)

    grouped: dict[tuple[int, int], list[_TrustedTextWord]] = {}
    for word in words:
        if (
            _bbox_fully_inside(word.bbox, viewport.bounding_box)
            and word.text.strip()
        ):
            grouped.setdefault((word.block_no, word.line_no), []).append(word)

    replacements: dict[str, _TrustedTextWord] = {}
    text_authority = source.text_integrity_authority()
    source_authority = source._producer.authority()
    admissible = {
        TEXT_GLYPH_MAPPING_UNVERIFIED,
        TEXT_CLIP_STATE_UNRESOLVED,
    }

    for key in sorted(grouped):
        line = sorted(
            grouped[key],
            key=lambda row: (row.word_no, row.bbox[0], row.observation_id),
        )
        if not line or all(word.trusted for word in line):
            continue
        word_numbers = [word.word_no for word in line]
        if (
            len(set(word_numbers)) != len(word_numbers)
            or word_numbers != list(range(word_numbers[0], word_numbers[-1] + 1))
        ):
            continue
        claim = normalize_reading(
            " ".join(word.text.strip() for word in line if word.text.strip())
        )
        if not claim:
            continue

        targets: list[tuple[float, float, float, float]] = []
        rotations: set[int] = set()
        source_partitions: set[str] = set()
        source_page_ids: set[str] = set()
        line_valid = True

        for word in line:
            selector = ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=word.observation_id,
            )
            text_result = text_authority.resolve_text(selector)
            receipt = text_result.receipt
            if (
                receipt is None
                or tuple(float(value) for value in receipt.geometry)
                != tuple(float(value) for value in word.bbox)
                or str(receipt.page_id) != str(word.page_id)
            ):
                line_valid = False
                break

            if word.trusted:
                if (
                    text_result.status is not EvidenceResolutionStatus.CORROBORATED
                    or not text_result.trusted_text
                    or normalize_reading(text_result.trusted_text)
                    != normalize_reading(word.text)
                ):
                    line_valid = False
                    break
            else:
                receipt_reasons = tuple(receipt.reason_codes or ())
                reason_set = set(receipt_reasons)
                if (
                    text_result.status is not EvidenceResolutionStatus.ABSTAINED
                    or bool(receipt.trusted)
                    or TEXT_GLYPH_MAPPING_UNVERIFIED not in reason_set
                    or not reason_set.issubset(admissible)
                    or tuple(text_result.reason_codes or ()) != receipt_reasons
                    or tuple(word.reason_codes) != receipt_reasons
                ):
                    line_valid = False
                    break

            source_result = source_authority.resolve(selector)
            observation = source_result.observation
            if (
                source_result.status is not EvidenceResolutionStatus.CORROBORATED
                or observation is None
                or observation.observation_kind != "native_pdf_word"
                or observation.origin_kind != "native"
                or observation.viewport_id is not None
                or observation.document_id != published.revision.document_id
                or observation.revision_id != published.revision.revision_id
                or observation.source_sha256 != published.revision.source_sha256
                or str(observation.page_id) != str(word.page_id)
                or tuple(float(value) for value in observation.geometry)
                != tuple(float(value) for value in word.bbox)
                or normalize_reading(observation.raw_text)
                != normalize_reading(word.text)
            ):
                line_valid = False
                break

            raster_bbox, rotation = _producer_owned_ocr_target(
                source._producer,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                page_id=str(observation.page_id),
                receipt=receipt,
                word_bbox=tuple(float(value) for value in word.bbox),
                raw_text=str(observation.raw_text),
            )
            targets.append(raster_bbox)
            rotations.add(int(rotation))
            source_partitions.add(str(observation.source_partition_id))
            source_page_ids.add(str(observation.page_id))

        if (
            not line_valid
            or len(rotations) != 1
            or len(source_partitions) != 1
            or len(source_page_ids) != 1
            or not targets
        ):
            continue

        rotation = next(iter(rotations))
        source_partition_id = next(iter(source_partitions))
        source_page_id = next(iter(source_page_ids))
        raster_bbox = (
            min(value[0] for value in targets),
            min(value[1] for value in targets),
            max(value[2] for value in targets),
            max(value[3] for value in targets),
        )

        readings: list[str] = []
        parent_ids: set[tuple[str, str, str]] = set()
        for dpi in RASTER_TEXT_CORROBORATION_DPIS:
            try:
                png_bytes, page_parent = source._producer.render_native_page_png(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    page_id=source_page_id,
                    dpi=float(dpi),
                    clip_pt=raster_bbox,
                )
            except Exception:
                line_valid = False
                break
            if (
                page_parent.document_id != published.revision.document_id
                or page_parent.revision_id != published.revision.revision_id
                or page_parent.source_sha256 != published.revision.source_sha256
                or str(page_parent.source_partition_id) != source_partition_id
                or str(page_parent.page_id) != source_page_id
            ):
                line_valid = False
                break
            parent_ids.add(
                (
                    str(page_parent.observation_id),
                    str(page_parent.source_partition_id),
                    str(page_parent.page_id),
                )
            )
            try:
                rendered = Image.open(io.BytesIO(png_bytes)).convert("RGB")
                normalized = _lossless_rotate(rendered, rotation)
            except Exception:
                line_valid = False
                break
            margin_px = max(
                1,
                int(
                    round(
                        float(dpi)
                        * _MATERIAL_LINE_OCR_BLANK_MARGIN_MM
                        / 25.4
                    )
                ),
            )
            isolated = ImageOps.expand(
                normalized,
                border=margin_px,
                fill="white",
            )
            reading = _single_isolated_material_line_reading(
                backend,
                isolated,
                dpi=int(dpi),
            )
            if reading is None or normalize_reading(reading) != claim:
                line_valid = False
                break
            readings.append(reading)

        if (
            not line_valid
            or len(parent_ids) != 1
            or len(readings) != len(RASTER_TEXT_CORROBORATION_DPIS)
            or len({normalize_reading(value) for value in readings}) != 1
        ):
            continue

        for word in line:
            replacements[word.observation_id] = _TrustedTextWord(
                observation_id=word.observation_id,
                page_id=word.page_id,
                source_partition_id=word.source_partition_id,
                text=word.text,
                bbox=word.bbox,
                block_no=word.block_no,
                line_no=word.line_no,
                word_no=word.word_no,
                trusted=True,
                reason_codes=tuple(
                    dict.fromkeys(
                        (*word.reason_codes, "raster_text_line_corroborated")
                    )
                ),
            )

    return tuple(
        replacements.get(word.observation_id, word)
        for word in words
    )


def _trusted_lines_for_viewport(
    words: Sequence[_TrustedTextWord],
    viewport: SegmentedViewport,
) -> tuple[
    tuple[tuple[str, tuple[float, float, float, float], tuple[str, ...]], ...],
    bool,
    tuple[str, ...],
]:
    """Return only integrity-proven text wholly owned by one viewport.

    Any untrusted word inside the viewport, or any word crossing the viewport
    boundary, makes the text scope incomplete. This prevents corrupted text
    from becoming schedule/finish authority merely because nearby words were
    readable.
    """

    assert viewport.bounding_box is not None
    grouped: dict[
        tuple[int, int],
        list[_TrustedTextWord],
    ] = {}
    reasons: list[str] = []
    complete = True

    for word in words:
        if not _bbox_intersects(word.bbox, viewport.bounding_box):
            continue
        if not _bbox_fully_inside(word.bbox, viewport.bounding_box):
            complete = False
            reasons.append(SOURCE_MATERIAL_VIEWPORT_UNAUTHENTICATED)
            reasons.append("text_crosses_viewport_boundary")
            continue
        if not word.trusted:
            complete = False
            reasons.append(SOURCE_MATERIAL_VIEWPORT_UNAUTHENTICATED)
            reasons.extend(word.reason_codes)
            continue
        if not word.text.strip():
            continue
        grouped.setdefault((word.block_no, word.line_no), []).append(word)

    output = []
    for key in sorted(grouped):
        line_words = sorted(
            grouped[key],
            key=lambda row: (row.word_no, row.bbox[0], row.observation_id),
        )
        text = " ".join(row.text.strip() for row in line_words if row.text.strip()).strip()
        if not text:
            continue
        output.append(
            (
                text,
                (
                    min(row.bbox[0] for row in line_words),
                    min(row.bbox[1] for row in line_words),
                    max(row.bbox[2] for row in line_words),
                    max(row.bbox[3] for row in line_words),
                ),
                tuple(row.observation_id for row in line_words),
            )
        )
    return (
        tuple(output),
        complete,
        tuple(dict.fromkeys(reason for reason in reasons if reason)),
    )


class SourceMaterialSemanticAuthority:
    def __init__(
        self,
        definition_results: Mapping[
            tuple[str, str, str, str, str], SourceMaterialDefinitionResult
        ],
        occurrence_results: Mapping[
            tuple[str, str, str, str, str, str], SourceMaterialOccurrenceScopeResult
        ],
        definition_scope_blockers: Optional[
            Mapping[tuple[str, str, str, str], tuple[str, ...]]
        ] = None,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("SourceMaterialSemanticAuthority is producer-owned")
        self._definition_results = MappingProxyType(dict(definition_results))
        self._occurrence_results = MappingProxyType(dict(occurrence_results))
        self._definition_scope_blockers = MappingProxyType(
            dict(definition_scope_blockers or {})
        )

    def resolve_definition(
        self,
        selector: SourceMaterialDefinitionSelector,
    ) -> SourceMaterialDefinitionResult:
        if type(selector) is not SourceMaterialDefinitionSelector:
            raise TypeError("selector must be SourceMaterialDefinitionSelector")
        resolved = self._definition_results.get(selector.key)
        if resolved is not None:
            return resolved
        scope_blockers = self._definition_scope_blockers.get(selector.key[:4])
        if scope_blockers:
            return _definition_blocked(
                EvidenceResolutionStatus.ABSTAINED,
                *scope_blockers,
            )
        return _definition_blocked(
            EvidenceResolutionStatus.ABSTAINED,
            SOURCE_MATERIAL_DEFINITION_UNAVAILABLE,
        )

    def resolve_occurrences(
        self,
        selector: SourceMaterialOccurrenceSelector,
    ) -> SourceMaterialOccurrenceScopeResult:
        if type(selector) is not SourceMaterialOccurrenceSelector:
            raise TypeError("selector must be SourceMaterialOccurrenceSelector")
        return self._occurrence_results.get(
            selector.key,
            _scope_blocked(
                EvidenceResolutionStatus.ABSTAINED,
                SOURCE_MATERIAL_SCOPE_UNAVAILABLE,
            ),
        )


class SourceMaterialSemanticProducer:
    def __init__(
        self,
        source_visibility_producer: SourceVisibilityProducer,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("Use from_source_visibility_producer()")
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        self._source = source_visibility_producer
        self._raster = RasterTextCorroborationProducer.from_source_visibility_producer(
            source_visibility_producer
        )
        self._definition_results: dict[
            tuple[str, str, str, str, str], SourceMaterialDefinitionResult
        ] = {}
        self._occurrence_results: dict[
            tuple[str, str, str, str, str, str], SourceMaterialOccurrenceScopeResult
        ] = {}
        self._definition_scope_blockers: dict[
            tuple[str, str, str, str], tuple[str, ...]
        ] = {}
        self._published_revisions: set[str] = set()

    @classmethod
    def from_source_visibility_producer(
        cls,
        source_visibility_producer: SourceVisibilityProducer,
    ) -> "SourceMaterialSemanticProducer":
        return cls(source_visibility_producer, _seal=_PRODUCER_SEAL)

    def authority(self) -> SourceMaterialSemanticAuthority:
        return SourceMaterialSemanticAuthority(
            self._definition_results,
            self._occurrence_results,
            self._definition_scope_blockers,
            _seal=_AUTHORITY_SEAL,
        )

    def published_occurrence_results(
        self,
    ) -> tuple[SourceMaterialOccurrenceScopeResult, ...]:
        """Return immutable source-owned occurrence scopes in deterministic order."""
        return tuple(
            self._occurrence_results[key]
            for key in sorted(self._occurrence_results)
        )

    def _source_bytes(self, revision_id: str) -> tuple[object, Optional[bytes]]:
        published = self._source.published_snapshot_for_revision(revision_id)
        if published is None:
            return None, None
        source_bytes = self._source._producer._store.source_bytes_by_revision.get(
            str(revision_id)
        )
        if source_bytes is None:
            return published, None
        if hashlib.sha256(source_bytes).hexdigest() != published.revision.source_sha256:
            raise RuntimeError(SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE)
        return published, bytes(source_bytes)

    def publish(self, revision_id: str) -> SourceMaterialSemanticAuthority:
        revision_id = _required(revision_id, "revision_id")
        if revision_id in self._published_revisions:
            return self.authority()

        published, source_bytes = self._source_bytes(revision_id)
        if published is None or source_bytes is None:
            self._published_revisions.add(revision_id)
            return self.authority()

        lineage = {
            "document_id": str(published.revision.document_id),
            "revision_id": str(published.revision.revision_id),
            "source_sha256": str(published.revision.source_sha256),
            "snapshot_id": str(published.snapshot.snapshot_id),
        }
        decoded_pages = {int(value) for value in published.coverage.decoded_pages}
        raw_definitions: dict[str, list[dict[str, object]]] = {}
        drawing_viewports: list[
            tuple[int, SegmentedViewport, tuple[_TrustedTextWord, ...]]
        ] = []
        schedule_universe_complete = True
        schedule_universe_reasons: list[str] = []
        trusted_words = _trusted_words_by_page(
            self._source,
            published,
        )
        raster = self._raster

        pdf = fitz.open(stream=source_bytes, filetype="pdf")
        try:
            for page_number in sorted(decoded_pages):
                if page_number < 1 or page_number > pdf.page_count:
                    continue
                page = pdf.load_page(page_number - 1)
                page_words = trusted_words.get(str(page_number), ())

                # A native source text block headed by a qualified material
                # schedule title is independently usable for definitions even
                # when competing outer vector frames leave the schedule
                # viewport ambiguous. No drawing occurrence is minted from this
                # route; it owns schedule semantics only.
                for schedule_block in _trusted_native_material_schedule_blocks(
                    page_words
                ):
                    line_evidence = dict(schedule_block.line_evidence)
                    for item in parse_schedule_text(
                        schedule_block.text,
                        page_id=page_number,
                        page_label=f"page:{page_number}",
                    ):
                        code = str(item.get("code") or "").strip().upper()
                        if not code:
                            continue
                        raw = dict(item)
                        raw["source_viewport_id"] = ""
                        raw["source_block_id"] = schedule_block.scope_id
                        contributing_lines = tuple(
                            item.get("source_lines")
                            or (str(item.get("source_line") or ""),)
                        )
                        raw["source_text_observation_ids"] = tuple(
                            dict.fromkeys(
                                observation_id
                                for source_line in contributing_lines
                                for observation_id in line_evidence.get(
                                    str(source_line),
                                    (),
                                )
                            )
                        )
                        raw_definitions.setdefault(code, []).append(raw)

                viewports = tuple(
                    segment_page_viewports(page, page_number=page_number)
                )
                if (
                    not viewports
                    or any(
                        not is_segment_page_viewports_product(viewport)
                        for viewport in viewports
                    )
                ):
                    continue
                sibling_non_overlapping = validate_non_overlapping_viewports(viewports)
                authoritative = tuple(
                    viewport
                    for viewport in viewports
                    if _viewport_is_authoritative(
                        viewport,
                        sibling_non_overlapping=sibling_non_overlapping,
                    )
                )
                for viewport in authoritative:
                    if _is_explicit_non_material_schedule(viewport):
                        continue
                    scoped_words = _recover_admissible_viewport_words(
                        source=self._source,
                        published=published,
                        raster=raster,
                        words=page_words,
                        viewport=viewport,
                    )
                    scoped_words = _recover_admissible_viewport_lines(
                        source=self._source,
                        published=published,
                        raster=raster,
                        words=scoped_words,
                        viewport=viewport,
                    )
                    lines, text_complete, text_reasons = _trusted_lines_for_viewport(
                        scoped_words,
                        viewport,
                    )
                    if viewport.view_type in _SCHEDULE_VIEW_TYPES:
                        if not text_complete or not lines:
                            schedule_universe_complete = False
                            schedule_universe_reasons.append(
                                SOURCE_MATERIAL_VIEWPORT_UNAUTHENTICATED
                            )
                            schedule_universe_reasons.extend(text_reasons)
                            if not lines:
                                schedule_universe_reasons.append(
                                    "schedule_viewport_has_no_trusted_text"
                                )
                            continue
                        text = "\n".join(line[0] for line in lines)
                        line_evidence = {
                            line[0]: line[2]
                            for line in lines
                        }
                        for item in parse_schedule_text(
                            text,
                            page_id=page_number,
                            page_label=f"page:{page_number}",
                        ):
                            code = str(item.get("code") or "").strip().upper()
                            if not code:
                                continue
                            raw = dict(item)
                            raw["source_viewport_id"] = viewport.view_id
                            contributing_lines = tuple(
                                item.get("source_lines")
                                or (str(item.get("source_line") or ""),)
                            )
                            raw["source_text_observation_ids"] = tuple(
                                dict.fromkeys(
                                    observation_id
                                    for source_line in contributing_lines
                                    for observation_id in line_evidence.get(
                                        str(source_line),
                                        (),
                                    )
                                )
                            )
                            raw_definitions.setdefault(code, []).append(raw)
                    else:
                        if not text_complete:
                            scope_selector = SourceMaterialOccurrenceSelector(
                                **lineage,
                                page_id=str(page_number),
                                viewport_id=viewport.view_id,
                            )
                            self._occurrence_results[scope_selector.key] = _scope_blocked(
                                EvidenceResolutionStatus.ABSTAINED,
                                SOURCE_MATERIAL_VIEWPORT_UNAUTHENTICATED,
                                *text_reasons,
                            )
                            continue
                        drawing_viewports.append(
                            (page_number, viewport, scoped_words)
                        )

            if not schedule_universe_complete:
                blocked_reasons = tuple(
                    dict.fromkeys(
                        (
                            SOURCE_MATERIAL_VIEWPORT_UNAUTHENTICATED,
                            *(
                                reason
                                for reason in schedule_universe_reasons
                                if reason
                            ),
                        )
                    )
                )
                self._definition_scope_blockers[
                    (
                        lineage["document_id"],
                        lineage["revision_id"],
                        lineage["source_sha256"],
                        lineage["snapshot_id"],
                    )
                ] = blocked_reasons
                for code in sorted(raw_definitions):
                    selector = SourceMaterialDefinitionSelector(
                        **lineage,
                        code=code,
                    )
                    self._definition_results[selector.key] = _definition_blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        *blocked_reasons,
                    )
                for page_number, viewport, _page_words in drawing_viewports:
                    scope_selector = SourceMaterialOccurrenceSelector(
                        **lineage,
                        page_id=str(page_number),
                        viewport_id=viewport.view_id,
                    )
                    self._occurrence_results[scope_selector.key] = _scope_blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        SOURCE_MATERIAL_SCOPE_UNAVAILABLE,
                        *blocked_reasons,
                    )
                self._published_revisions.add(revision_id)
                return self.authority()

            confirmed_dictionary: dict[str, dict[str, object]] = {}
            for code, items in sorted(raw_definitions.items()):
                representative = items[0]
                conflicting = [
                    item
                    for item in items[1:]
                    if not _compatible_descriptions(
                        representative.get("description"),
                        item.get("description"),
                    )
                ]
                substrate_names = {
                    str(item.get("substrate") or "").strip()
                    for item in items
                    if str(item.get("substrate") or "").strip()
                }
                finish_names = {
                    str(item.get("finish") or "").strip()
                    for item in items
                    if str(item.get("finish") or "").strip()
                }
                status = (
                    EvidenceResolutionStatus.CONFLICT
                    if (
                        conflicting
                        or len(substrate_names) > 1
                        or len(finish_names) > 1
                    )
                    else EvidenceResolutionStatus.CORROBORATED
                )
                selector = SourceMaterialDefinitionSelector(
                    **lineage,
                    code=code,
                )
                if status is EvidenceResolutionStatus.CONFLICT:
                    self._definition_results[selector.key] = _definition_blocked(
                        status,
                        SOURCE_MATERIAL_DEFINITION_CONFLICT,
                    )
                    continue

                entry = {
                    "code": code,
                    "description": str(representative.get("description") or ""),
                    "substrate": next(iter(substrate_names)) if substrate_names else "",
                    "finish": next(iter(finish_names)) if finish_names else "",
                    "status": "Confirmed",
                }
                semantic_finish = semantic_finish_from_schedule_entry(entry)
                source_id_rows: list[str] = []
                for item in items:
                    evidence_payload = {
                        **lineage,
                        "page_id": str(item.get("page_id") or ""),
                        "viewport_id": str(item.get("source_viewport_id") or ""),
                        "code": code,
                        "source_line": str(item.get("source_line") or ""),
                        "source_text_observation_ids": tuple(
                            item.get("source_text_observation_ids") or ()
                        ),
                    }
                    source_block_id = str(
                        item.get("source_block_id") or ""
                    ).strip()
                    if source_block_id:
                        evidence_payload["source_block_id"] = source_block_id
                    source_id_rows.append(
                        stable_contract_id(
                            "source_material_definition_evidence",
                            evidence_payload,
                            digest_chars=32,
                        )
                    )
                source_ids = tuple(sorted(source_id_rows))
                payload = {
                    **lineage,
                    "code": code,
                    "description": entry["description"],
                    "substrate": entry["substrate"],
                    "finish": entry["finish"],
                    "semantic_finish": semantic_finish,
                    "source_definition_ids": source_ids,
                }
                record = SourceMaterialDefinitionRecord(
                    record_id=stable_contract_id(
                        "source_material_definition",
                        payload,
                        digest_chars=32,
                    ),
                    document_id=lineage["document_id"],
                    revision_id=lineage["revision_id"],
                    source_sha256=lineage["source_sha256"],
                    snapshot_id=lineage["snapshot_id"],
                    code=code,
                    description=str(entry["description"]),
                    substrate=str(entry["substrate"]),
                    finish=str(entry["finish"]),
                    semantic_finish=semantic_finish,
                    source_definition_ids=source_ids,
                    source_page_ids=tuple(
                        sorted({str(item.get("page_id") or "") for item in items})
                    ),
                    source_viewport_ids=tuple(
                        sorted(
                            {
                                str(item.get("source_viewport_id") or "").strip()
                                for item in items
                                if str(
                                    item.get("source_viewport_id") or ""
                                ).strip()
                            }
                        )
                    ),
                )
                self._definition_results[selector.key] = SourceMaterialDefinitionResult(
                    status=EvidenceResolutionStatus.CORROBORATED,
                    reason_codes=(SOURCE_MATERIAL_DEFINITION_RESOLVED,),
                    record=record,
                )
                confirmed_dictionary[code] = {
                    **entry,
                    "semantic_finish": semantic_finish,
                    "record": record,
                }

            for page_number, viewport, page_words in drawing_viewports:
                scope_selector = SourceMaterialOccurrenceSelector(
                    **lineage,
                    page_id=str(page_number),
                    viewport_id=viewport.view_id,
                )
                records: list[SourceMaterialOccurrenceRecord] = []
                seen: set[tuple[str, tuple[float, float, float, float], str]] = set()
                dictionary_for_scan = {
                    code: dict(entry)
                    for code, entry in confirmed_dictionary.items()
                }
                lines, text_complete, text_reasons = _trusted_lines_for_viewport(
                    page_words,
                    viewport,
                )
                if not text_complete:
                    self._occurrence_results[scope_selector.key] = _scope_blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        SOURCE_MATERIAL_VIEWPORT_UNAUTHENTICATED,
                        *text_reasons,
                    )
                    continue
                for raw_text, bbox, text_observation_ids in lines:
                    for code in _defined_codes_in_text(raw_text, dictionary_for_scan):
                        entry = confirmed_dictionary.get(code)
                        if entry is None:
                            continue
                        definition = entry["record"]
                        assert isinstance(definition, SourceMaterialDefinitionRecord)
                        semantic_finish = str(entry.get("semantic_finish") or "")
                        if not semantic_finish:
                            continue
                        normalized_bbox = tuple(round(float(v), 6) for v in bbox)
                        dedup_key = (code, normalized_bbox, raw_text)
                        if dedup_key in seen:
                            continue
                        seen.add(dedup_key)
                        evidence_payload = {
                            **lineage,
                            "page_id": str(page_number),
                            "viewport_id": viewport.view_id,
                            "code": code,
                            "bbox": normalized_bbox,
                            "raw_text": raw_text,
                            "source_text_observation_ids": tuple(
                                text_observation_ids
                            ),
                        }
                        evidence_id = stable_contract_id(
                            "source_material_occurrence_evidence",
                            evidence_payload,
                            digest_chars=32,
                        )
                        record_payload = {
                            **evidence_payload,
                            "definition_record_id": definition.record_id,
                            "semantic_finish": semantic_finish,
                            "source_evidence_id": evidence_id,
                        }
                        records.append(
                            SourceMaterialOccurrenceRecord(
                                record_id=stable_contract_id(
                                    "source_material_occurrence",
                                    record_payload,
                                    digest_chars=32,
                                ),
                                document_id=lineage["document_id"],
                                revision_id=lineage["revision_id"],
                                source_sha256=lineage["source_sha256"],
                                snapshot_id=lineage["snapshot_id"],
                                page_id=str(page_number),
                                viewport_id=viewport.view_id,
                                code=code,
                                semantic_finish=semantic_finish,
                                definition_record_id=definition.record_id,
                                bbox_pdf_pts=normalized_bbox,
                                raw_text=raw_text,
                                source_evidence_id=evidence_id,
                                source_text_observation_ids=tuple(
                                    text_observation_ids
                                ),
                            )
                        )
                # `lines` is already emitted in deterministic producer-owned
                # native block/line order. Preserve that source order here:
                # `record_id` is identity, not an ordering key, and adding
                # legitimate provenance must not reshuffle published output.
                self._occurrence_results[scope_selector.key] = (
                    SourceMaterialOccurrenceScopeResult(
                        status=EvidenceResolutionStatus.CORROBORATED,
                        reason_codes=(SOURCE_MATERIAL_SCOPE_RESOLVED,),
                        scope_complete=True,
                        records=tuple(records),
                    )
                )
        finally:
            pdf.close()

        self._published_revisions.add(revision_id)
        return self.authority()


__all__ = [
    "SOURCE_MATERIAL_DEFINITION_CONFLICT",
    "SOURCE_MATERIAL_DEFINITION_RESOLVED",
    "SOURCE_MATERIAL_DEFINITION_UNAVAILABLE",
    "SOURCE_MATERIAL_SCOPE_RESOLVED",
    "SOURCE_MATERIAL_SCOPE_UNAVAILABLE",
    "SOURCE_MATERIAL_SEMANTIC_SCHEMA_VERSION",
    "SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE",
    "SOURCE_MATERIAL_VIEWPORT_UNAUTHENTICATED",
    "SourceMaterialDefinitionRecord",
    "SourceMaterialDefinitionResult",
    "SourceMaterialDefinitionSelector",
    "SourceMaterialOccurrenceRecord",
    "SourceMaterialOccurrenceScopeResult",
    "SourceMaterialOccurrenceSelector",
    "SourceMaterialSemanticAuthority",
    "SourceMaterialSemanticProducer",
]
