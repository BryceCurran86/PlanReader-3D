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

from dataclasses import dataclass, replace
import hashlib
import io
import math
import re
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
from pb_migration_provider_envelope import ProviderContext
from pb_pdf_text_integrity_authority import (
    TEXT_CLIP_STATE_UNRESOLVED,
    TEXT_GLYPH_MAPPING_UNVERIFIED,
)
from pb_portable_raster_ocr_authority import TesseractOCRBackend
from pb_raster_text_corroboration_authority import (
    RASTER_TEXT_CORROBORATION_DPIS,
    RasterTextCorroborationProducer,
    RasterTextCorroborationResult,
    RasterTextCorroborationSelector,
    _lossless_rotate,
    _producer_owned_ocr_target,
    normalize_reading,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_migration_adapter import adapt_f07_viewport_to_migration
from pb_viewport_segmentation import (
    SegmentedViewport,
    ViewportSegmentationStatus,
    is_authoritative_derived_viewport,
    is_segment_page_viewports_product,
    segment_page_viewports,
    segment_source_page_viewports,
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
SOURCE_MATERIAL_SCOPE_INCOMPLETE = "source_material_occurrence_scope_incomplete"
SOURCE_MATERIAL_BOUNDED_PLAN_SCOPE = "source_material_bounded_plan_occurrence_scope"

_SCHEDULE_VIEW_TYPES = frozenset(
    {
        DrawingViewType.SCHEDULE.value,
        DrawingViewType.LEGEND.value,
        DrawingViewType.SPECIFICATION.value,
    }
)


_NONMATERIAL_GRID_DRAWING_TITLE = re.compile(
    r"^\s*GRID\s+(?:(?:SET\s*OUT|SETOUT|LAYOUT)\s+PLAN|"
    r"PLAN\s+(?:SET\s*OUT|SETOUT))\s*$",
    re.IGNORECASE,
)


def _source_owned_material_codes_in_line(
    raw_text: object,
    dictionary: Mapping[str, object],
) -> tuple[str, ...]:
    """Do not confuse an independently named drafting grid view with GRID finish.

    A complete GRID SETOUT/LAYOUT PLAN title is not a finish placement even
    when a *different* schedule authenticates GRID as a material code. Other
    line content is delegated unchanged to the established exact-token
    extractor. This is a negative lexical gate, not positive material authority.
    """
    text = str(raw_text or "")
    codes = _defined_codes_in_text(text, dictionary)
    if _NONMATERIAL_GRID_DRAWING_TITLE.fullmatch(text):
        return tuple(code for code in codes if code != "GRID")
    return tuple(codes)


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
_MATERIAL_WORD_OCR_BLANK_MARGIN_MM = 0.4
_MATERIAL_WORD_OCR_GAP_MM = 1.2
# Fixed before reading OCR output, for EVERY source-native material row line.
# The 300-DPI word path is unchanged. Small CAD fonts and vector quotation
# marks need distinct native-line raster views; never retry a failed view at
# a different scale or choose a scale from the OCR/native text result.
_MATERIAL_NATIVE_LINE_OCR_DPIS = (450, 600)


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
    source_text_corroboration_record_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceMaterialOccurrenceScopeResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    scope_complete: bool
    records: tuple[SourceMaterialOccurrenceRecord, ...]
    schema_version: str = SOURCE_MATERIAL_SEMANTIC_SCHEMA_VERSION
    source_viewport_ownership_id: str = ""
    unresolved_source_text_observation_ids: tuple[str, ...] = ()


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
    # The source receipt universe is not a collection to stringify/deduplicate.
    # Two replays of one PDF word cannot become two finish occurrences.
    original_observations = getattr(published, "text_observation_ids", ()) or ()
    if (
        type(original_observations) not in (tuple, list)
        or any(type(value) is not str or not value or value != value.strip()
               for value in original_observations)
        or len(set(original_observations)) != len(original_observations)
    ):
        raise RuntimeError(SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE)
    for observation_id in original_observations:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = authority.resolve_text(selector)
        receipt = result.receipt
        if receipt is None:
            # Published text ids are producer-owned and must always carry their
            # receipt. Treat a missing receipt as a source-integrity failure
            # rather than silently dropping a word.
            raise RuntimeError(SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE)
        # The source material text authority is a consumer, not an owner of
        # document identity or native word ordinals. Never str()/int()-cast a
        # forged parent, foreign revision or fractional PDF block index into
        # a new source-owned finish occurrence.
        if (
            type(receipt.parent_observation_id) is not str
            or receipt.parent_observation_id != observation_id
            or type(receipt.document_id) is not str
            or receipt.document_id != published.revision.document_id
            or type(receipt.revision_id) is not str
            or receipt.revision_id != published.revision.revision_id
            or type(receipt.source_sha256) is not str
            or receipt.source_sha256 != published.revision.source_sha256
            or type(receipt.page_id) is not str
            or not receipt.page_id or receipt.page_id != receipt.page_id.strip()
            or type(receipt.source_partition_id) is not str
            or type(receipt.raw_text) is not str
            or any(
                v is not None and (type(v) is not int or v < 0)
                for v in (receipt.block_no, receipt.line_no, receipt.word_no)
            )
        ):
            raise RuntimeError(SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE)
        # Text/glyph geometry is an original producer source receipt, never
        # a user-entered or JSON-coerced coordinate. NaN/Inf passes ordered
        # bbox comparisons and can cross a viewport trust boundary silently.
        original_bbox = receipt.geometry
        if (
            type(original_bbox) not in (tuple, list)
            or len(original_bbox) != 4
            or any(type(value) not in (int, float) for value in original_bbox)
        ):
            raise RuntimeError(SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE)
        try:
            bbox = tuple(float(value) for value in original_bbox)
        except (TypeError, ValueError, OverflowError) as exc:
            raise RuntimeError(SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE) from exc
        if (
            not all(math.isfinite(value) for value in bbox)
            or bbox[2] <= bbox[0]
            or bbox[3] <= bbox[1]
        ):
            raise RuntimeError(SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE)
        page_id = receipt.page_id
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
                observation_id=observation_id,
                page_id=page_id,
                source_partition_id=receipt.source_partition_id,
                text=str(trusted_text or receipt.raw_text),
                bbox=bbox,
                block_no=receipt.block_no if receipt.block_no is not None else 0,
                line_no=receipt.line_no if receipt.line_no is not None else 0,
                word_no=receipt.word_no if receipt.word_no is not None else 0,
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
    render_dpis: tuple[int, int] = RASTER_TEXT_CORROBORATION_DPIS,
) -> tuple[_TrustedTextWord, ...]:
    """Corroborate exact native lines when per-word OCR remains unresolved.

    This is deliberately the same narrow evidence class used by source-room
    labels: every unresolved word must be producer-owned native text blocked
    only by glyph mapping and optional clip-state ownership; the producer-owned
    raster targets for that exact native line are unioned; and two independent
    renders must both read exactly the native whole line.
    """
    assert viewport.bounding_box is not None
    # Reject caller-controlled / malformed profiles. Native rows select one
    # fixed source-independent profile before any OCR; a failed reading never
    # switches the profile, and all other viewport paths stay at 300/450.
    if render_dpis not in (
        RASTER_TEXT_CORROBORATION_DPIS,
        _MATERIAL_NATIVE_LINE_OCR_DPIS,
    ):
        return tuple(words)
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
                native_exact = (
                    text_result.status is EvidenceResolutionStatus.CORROBORATED
                    and bool(text_result.trusted_text)
                    and normalize_reading(text_result.trusted_text)
                    == normalize_reading(word.text)
                )
                raster_exact = False
                if (
                    not native_exact
                    and "raster_text_corroborated" in set(word.reason_codes)
                ):
                    raster_result = raster.publish(
                        RasterTextCorroborationSelector(
                            document_id=published.revision.document_id,
                            revision_id=published.revision.revision_id,
                            source_sha256=published.revision.source_sha256,
                            snapshot_id=published.snapshot.snapshot_id,
                            observation_id=word.observation_id,
                        )
                    )
                    raster_exact = (
                        raster_result.status
                        is EvidenceResolutionStatus.CORROBORATED
                        and raster_result.record is not None
                        and normalize_reading(
                            str(raster_result.corroborated_text or "")
                        )
                        == normalize_reading(word.text)
                    )
                if not native_exact and not raster_exact:
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
        full_line_exact = True
        for dpi in render_dpis:
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
            if render_dpis == _MATERIAL_NATIVE_LINE_OCR_DPIS:
                # Native material blocks already have a producer-owned exact
                # source glyph boundary. Do not place invented white pixels
                # around that source view: they change OCR's punctuation and
                # character segmentation. This fixed path is selected BEFORE
                # either DPI is read, never because one reading failed.
                isolated = normalized
            else:
                # Preserve the existing non-native viewport-line behavior.
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
                full_line_exact = False
            else:
                readings.append(reading)

        verified_reason = "raster_text_line_corroborated"
        verified = (
            line_valid
            and full_line_exact
            and len(parent_ids) == 1
            and len(readings) == len(render_dpis)
            and len({normalize_reading(value) for value in readings}) == 1
        )

        # Schedule ruling lines can be rendered between otherwise exact native
        # words and be mistaken by OCR for punctuation (for example "=").
        # If the source-owned whole-line raster does not read exactly, make one
        # stricter fallback view from the already-validated producer-owned word
        # clips only.  The native word order is fixed by source word_no; no OCR
        # token is inserted, deleted, corrected or fuzzy-matched.  Both DPI
        # composites must still read the exact native line.
        if line_valid and not verified:
            composite_readings: list[str] = []
            composite_parent_ids: set[tuple[str, str, str]] = set()
            composite_valid = True
            for dpi in render_dpis:
                word_images: list[Image.Image] = []
                for target in targets:
                    try:
                        png_bytes, page_parent = source._producer.render_native_page_png(
                            document_id=published.revision.document_id,
                            revision_id=published.revision.revision_id,
                            source_sha256=published.revision.source_sha256,
                            snapshot_id=published.snapshot.snapshot_id,
                            page_id=source_page_id,
                            dpi=float(dpi),
                            clip_pt=target,
                        )
                    except Exception:
                        composite_valid = False
                        break
                    if (
                        page_parent.document_id != published.revision.document_id
                        or page_parent.revision_id != published.revision.revision_id
                        or page_parent.source_sha256 != published.revision.source_sha256
                        or str(page_parent.source_partition_id) != source_partition_id
                        or str(page_parent.page_id) != source_page_id
                    ):
                        composite_valid = False
                        break
                    composite_parent_ids.add(
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
                        composite_valid = False
                        break
                    word_margin_px = max(
                        1,
                        int(
                            round(
                                float(dpi)
                                * _MATERIAL_WORD_OCR_BLANK_MARGIN_MM
                                / 25.4
                            )
                        ),
                    )
                    word_images.append(
                        ImageOps.expand(
                            normalized,
                            border=word_margin_px,
                            fill="white",
                        )
                    )
                if not composite_valid or not word_images:
                    break
                gap_px = max(
                    2,
                    int(
                        round(
                            float(dpi)
                            * _MATERIAL_WORD_OCR_GAP_MM
                            / 25.4
                        )
                    ),
                )
                height = max(image.height for image in word_images)
                width = (
                    sum(image.width for image in word_images)
                    + gap_px * (len(word_images) - 1)
                )
                composite = Image.new("RGB", (width, height), "white")
                offset_x = 0
                for word_image in word_images:
                    offset_y = max(0, (height - word_image.height) // 2)
                    composite.paste(word_image, (offset_x, offset_y))
                    offset_x += word_image.width + gap_px
                reading = _single_isolated_material_line_reading(
                    backend,
                    composite,
                    dpi=int(dpi),
                )
                if reading is None or normalize_reading(reading) != claim:
                    composite_valid = False
                    break
                composite_readings.append(reading)

            verified = (
                composite_valid
                and len(composite_parent_ids) == 1
                and len(composite_readings) == len(render_dpis)
                and len(
                    {normalize_reading(value) for value in composite_readings}
                ) == 1
            )
            if verified:
                verified_reason = "raster_text_line_word_composite_corroborated"

        if not verified:
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
                        (*word.reason_codes, verified_reason)
                    )
                ),
            )

    return tuple(
        replacements.get(word.observation_id, word)
        for word in words
    )




def _native_block_line_rows(
    words: Sequence[_TrustedTextWord],
) -> tuple[
    tuple[str, tuple[str, ...], tuple[float, float, float, float]], ...
]:
    by_line: dict[int, list[_TrustedTextWord]] = {}
    for word in words:
        by_line.setdefault(int(word.line_no), []).append(word)
    rows = []
    for line_no in sorted(by_line):
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
            return ()
        text = " ".join(
            row.text.strip() for row in line_words if row.text.strip()
        ).strip()
        if not text:
            return ()
        rows.append(
            (
                text,
                tuple(row.observation_id for row in line_words),
                (
                    min(row.bbox[0] for row in line_words),
                    min(row.bbox[1] for row in line_words),
                    max(row.bbox[2] for row in line_words),
                    max(row.bbox[3] for row in line_words),
                ),
            )
        )
    return tuple(rows)


def _material_definition_candidate(
    words: Sequence[_TrustedTextWord],
) -> Optional[tuple[str, dict[str, object]]]:
    """Recognise one code-cell + semantic-description native block.

    This function only identifies a block worth authenticating.  Publication
    still requires every word in the block to clear source-text integrity.
    """

    lines = _native_block_line_rows(words)
    if not lines:
        return None
    combined = " ".join(row[0] for row in lines).strip()
    if not combined:
        return None

    parsed = parse_schedule_text(
        combined,
        page_id=int(words[0].page_id) if words else 0,
        page_label=f"page:{words[0].page_id}" if words else "",
    )
    candidates = []
    for item in parsed:
        code = str(item.get("code") or "").strip().upper()
        if not code:
            continue
        entry = {
            "status": "Confirmed",
            "code": code,
            "description": str(item.get("description") or ""),
            "substrate": str(item.get("substrate") or ""),
            "finish": str(item.get("finish") or ""),
        }
        if semantic_finish_from_schedule_entry(entry):
            candidates.append((code, dict(item)))
    if len(candidates) != 1:
        return None
    return candidates[0]


def _native_multirow_material_definition_candidates(
    words: Sequence[_TrustedTextWord],
) -> tuple[
    tuple[str, int, tuple[_TrustedTextWord, ...], str, dict[str, object]], ...
]:
    """Opt-in CAD-exported multi-code material-legend source row ownership.

    One native text block can encode code, description, code, description in
    distinct original source lines. A whole-block parser rightfully abstains
    because many codes occur. Independently issue CANDIDATE rows only when
    a code occupies its own complete source line and is followed by one or
    more *original immediately subsequent* native description lines.
    Ambiguous repeated codes, broken word ordinals or missing semantics
    abstain. Every returned row holds ONLY its original source word IDs.
    Producer visibility, schedule-title and raster gates still apply later.
    """
    import re

    grouped = _group_native_material_block_words(words)
    candidates = []
    code_pattern = re.compile(r"^[A-Z]{2,4}(?:\d{1,4})?$")
    stopwords = frozenset({"CODE", "TYPE", "ROOM", "WALL", "FLOOR", "DOOR", "NOTE", "FIRE"})
    for (partition_id, block_no), block_words in sorted(grouped.items()):
        line_records: list[tuple[int, tuple[_TrustedTextWord, ...]]] = []
        by_line: dict[int, list[_TrustedTextWord]] = {}
        for word in block_words:
            by_line.setdefault(int(word.line_no), []).append(word)
        for line_id in sorted(by_line):
            members = tuple(sorted(by_line[line_id], key=lambda w: (w.word_no, w.bbox[0], w.observation_id)))
            indexes = [int(w.word_no) for w in members]
            if (not indexes or len(set(indexes)) != len(indexes)
                    or indexes != list(range(indexes[0], indexes[-1] + 1))):
                line_records = []
                break
            line_records.append((line_id, members))
        if not line_records:
            continue
        code_rows = []
        for pos, (line_id, line_words) in enumerate(line_records):
            if len(line_words) != 1:
                continue
            token = line_words[0].text.strip()
            if code_pattern.fullmatch(token) and token not in stopwords:
                code_rows.append((pos, token))
        if len(code_rows) < 2:
            continue  # Existing one-code-block path owns such rows.
        codes = [token for _, token in code_rows]
        for pos, code in code_rows:
            if codes.count(code) != 1:
                continue
            end = next((other for other, _ in code_rows if other > pos), len(line_records))
            # A valid source row has an immediately adjacent description; a
            # code must never borrow material semantics across a missing line.
            if pos + 1 >= end or line_records[pos + 1][0] != line_records[pos][0] + 1:
                continue
            if any(line_records[i + 1][0] != line_records[i][0] + 1
                   for i in range(pos, end - 1)):
                continue
            owned = tuple(
                word for _, members in line_records[pos:end] for word in members
            )
            candidate = _material_definition_candidate(owned)
            if candidate is None or candidate[0] != code:
                continue
            candidates.append((partition_id, block_no, owned, candidate[0], candidate[1]))
    return tuple(candidates)


def _raw_material_definition_candidates(
    words: Sequence[_TrustedTextWord],
) -> tuple[
    tuple[str, int, tuple[_TrustedTextWord, ...], str, dict[str, object]], ...
]:
    grouped: dict[tuple[str, int], list[_TrustedTextWord]] = {}
    for word in words:
        if not word.source_partition_id:
            continue
        grouped.setdefault(
            (word.source_partition_id, int(word.block_no)),
            [],
        ).append(word)

    out = []
    for (partition_id, block_no), block_words in sorted(grouped.items()):
        ordered = tuple(
            sorted(
                block_words,
                key=lambda row: (
                    row.line_no,
                    row.word_no,
                    row.bbox[0],
                    row.observation_id,
                ),
            )
        )
        candidate = _material_definition_candidate(ordered)
        if candidate is None:
            continue
        code, item = candidate
        out.append((partition_id, block_no, ordered, code, item))
    return tuple(out)


def _native_block_bbox(
    words: Sequence[_TrustedTextWord],
) -> tuple[float, float, float, float]:
    return (
        min(word.bbox[0] for word in words),
        min(word.bbox[1] for word in words),
        max(word.bbox[2] for word in words),
        max(word.bbox[3] for word in words),
    )


def _recover_native_material_block(
    *,
    source: SourceVisibilityProducer,
    published: object,
    raster: RasterTextCorroborationProducer,
    block_words: Sequence[_TrustedTextWord],
) -> tuple[_TrustedTextWord, ...]:
    if not block_words:
        return ()
    # Both downstream recovery paths skip already trusted native words, and
    # the line path cannot change an all-trusted source block. Preserve the
    # exact original receipts without constructing OCR targets or backends.
    if all(word.trusted for word in block_words):
        return tuple(block_words)
    bbox = _native_block_bbox(block_words)
    try:
        page_number = int(block_words[0].page_id)
    except (TypeError, ValueError):
        return ()
    viewport = SegmentedViewport(
        view_id=f"native_material_block:{block_words[0].source_partition_id}:{block_words[0].block_no}",
        page_number=page_number,
        view_type=DrawingViewType.SCHEDULE.value,
        label="NATIVE MATERIAL DEFINITION BLOCK",
        title_bbox=bbox,
        bounding_box=bbox,
        status=ViewportSegmentationStatus.RESOLVED.value,
        boundary_source="native_text_block",
        confidence=1.0,
    )
    recovered = _recover_admissible_viewport_words(
        source=source,
        published=published,
        raster=raster,
        words=block_words,
        viewport=viewport,
    )
    return _recover_admissible_viewport_lines(
        source=source,
        published=published,
        raster=raster,
        words=recovered,
        viewport=viewport,
        render_dpis=_MATERIAL_NATIVE_LINE_OCR_DPIS,
    )


def _group_native_material_block_words(
    words: Sequence[_TrustedTextWord],
) -> dict[tuple[str, int], tuple[_TrustedTextWord, ...]]:
    """Group source-owned words without repeated tuple copying or sorting.

    Preserve per-block first-seen order and the original provenance-based
    total sort key. This only reorganizes immutable receipts: it never changes
    their trust, source partition, geometry or authentication status.
    """
    collected: dict[tuple[str, int], list[_TrustedTextWord]] = {}
    for word in words:
        if not word.source_partition_id:
            continue
        collected.setdefault(
            (word.source_partition_id, int(word.block_no)), []
        ).append(word)
    return {
        key: tuple(
            sorted(
                block_words,
                key=lambda row: (
                    row.line_no,
                    row.word_no,
                    row.bbox[0],
                    row.observation_id,
                ),
            )
        )
        for key, block_words in collected.items()
    }


def _trusted_native_material_schedule_cluster_blocks(
    *,
    source: SourceVisibilityProducer,
    published: object,
    raster: RasterTextCorroborationProducer,
    words: Sequence[_TrustedTextWord],
    source_native_multirow_material_shadow: bool = False,
) -> tuple[tuple[_TrustedScheduleBlock, ...], tuple[str, ...]]:
    """Authenticate split native material-definition rows under one schedule title.

    CAD exports often store the schedule title and each code/description row in
    separate native text blocks.  The older fallback required title + rows in
    one block, which cannot represent that source structure.  This route stays
    fail-closed: exactly one material-schedule title must authenticate, at least
    two semantic definition-row blocks must exist, the title and row cluster
    must overlap on one native axis, and each published row must independently
    authenticate every source word.
    """

    # Collect each native block in one pass. Rebuilding and sorting a tuple
    # for every word copies the existing prefix repeatedly (quadratic on
    # dense CAD-exported text blocks). The immutable, deterministic sorted
    # tuples are materialized once, after all producer-owned words are read.
    # Recovery below can invoke expensive source-registered raster OCR. The
    # complete native source candidate universe is a pure, deterministic
    # read-only scan and already required to contain >=2 rows by this lane.
    # Avoid *all* OCR work on impossible one-row/empty clusters while keeping
    # identical rejection semantics, even for an otherwise trusted title.
    if type(source_native_multirow_material_shadow) is not bool:
        raise ValueError("source_multirow_material_shadow_requires_explicit_bool")
    candidates = _raw_material_definition_candidates(words)
    if source_native_multirow_material_shadow:
        candidates = (*candidates, *_native_multirow_material_definition_candidates(words))
    if len(candidates) < 2:
        return (), ()

    grouped = _group_native_material_block_words(words)

    trusted_titles: list[
        tuple[tuple[float, float, float, float], tuple[str, ...], str, str]
    ] = []
    for block_words in grouped.values():
        raw_text = " ".join(row[0] for row in _native_block_line_rows(block_words))
        if not _is_material_schedule_title(raw_text):
            continue
        recovered = _recover_native_material_block(
            source=source,
            published=published,
            raster=raster,
            block_words=block_words,
        )
        if not recovered or any(not word.trusted for word in recovered):
            continue
        recovered_text = " ".join(
            row[0] for row in _native_block_line_rows(recovered)
        )
        if not _is_material_schedule_title(recovered_text):
            continue
        # A title authenticates only its own original source partition and
        # page; nearby rows from a separate CAD/export partition may not borrow
        # the title's proven observation IDs merely because boxes overlap.
        source_pages = {word.page_id for word in recovered}
        source_partitions = {word.source_partition_id for word in recovered}
        if len(source_pages) != 1 or len(source_partitions) != 1:
            continue
        trusted_titles.append(
            (
                _native_block_bbox(recovered),
                tuple(word.observation_id for word in recovered),
                next(iter(source_pages)),
                next(iter(source_partitions)),
            )
        )

    # The row-count prerequisite has already been checked before any OCR.
    # A missing/ambiguous material title remains fail-closed.
    if len(trusted_titles) != 1:
        return (), ()

    title_bbox, title_ids, title_page_id, title_partition_id = trusted_titles[0]
    owned_candidates = tuple(
        row for row in candidates
        if row[0] == title_partition_id
        and row[2]
        and all(
            word.page_id == title_page_id
            and word.source_partition_id == title_partition_id
            for word in row[2]
        )
    )
    blocked_codes: set[str] = {
        row[3] for row in candidates
        if row[0] != title_partition_id or not row[2]
        or any(
            word.page_id != title_page_id
            or word.source_partition_id != title_partition_id
            for word in row[2]
        )
    }
    if len(owned_candidates) < 2:
        return (), tuple(sorted({row[3] for row in candidates}))
    row_bbox = (
        min(_native_block_bbox(row[2])[0] for row in owned_candidates),
        min(_native_block_bbox(row[2])[1] for row in owned_candidates),
        max(_native_block_bbox(row[2])[2] for row in owned_candidates),
        max(_native_block_bbox(row[2])[3] for row in owned_candidates),
    )
    overlap_x = min(title_bbox[2], row_bbox[2]) - max(title_bbox[0], row_bbox[0])
    overlap_y = min(title_bbox[3], row_bbox[3]) - max(title_bbox[1], row_bbox[1])
    if overlap_x <= 0.0 and overlap_y <= 0.0:
        return (), tuple(sorted({row[3] for row in candidates}))

    blocks: list[_TrustedScheduleBlock] = []
    for partition_id, block_no, block_words, raw_code, _raw_item in owned_candidates:
        recovered = _recover_native_material_block(
            source=source,
            published=published,
            raster=raster,
            block_words=block_words,
        )
        if not recovered or any(not word.trusted for word in recovered):
            blocked_codes.add(raw_code)
            continue
        candidate = _material_definition_candidate(recovered)
        if candidate is None or candidate[0] != raw_code:
            blocked_codes.add(raw_code)
            continue
        code, item = candidate
        combined_line = f"{code} {str(item.get('description') or '').strip()}".strip()
        observation_ids = tuple(word.observation_id for word in recovered)
        page_ids = {word.page_id for word in recovered}
        partitions = {word.source_partition_id for word in recovered}
        if len(page_ids) != 1 or partitions != {partition_id}:
            blocked_codes.add(raw_code)
            continue
        page_id = next(iter(page_ids))
        scope_id = stable_contract_id(
            "source_material_native_schedule_cluster_row",
            {
                "page_id": page_id,
                "source_partition_id": partition_id,
                "block_no": block_no,
                "code": code,
                "title_observation_ids": title_ids,
                "row_observation_ids": observation_ids,
            },
            digest_chars=32,
        )
        blocks.append(
            _TrustedScheduleBlock(
                page_id=page_id,
                source_partition_id=partition_id,
                block_no=block_no,
                scope_id=scope_id,
                text=combined_line,
                line_evidence=MappingProxyType(
                    {combined_line: observation_ids}
                ),
            )
        )

    if len(blocks) < 2:
        blocked_codes.update(row[3] for row in candidates)
        return (), tuple(sorted(blocked_codes))
    return tuple(blocks), tuple(sorted(blocked_codes))


def _material_candidate_codes_with_untrusted_words(
    words: Sequence[_TrustedTextWord],
    viewport: SegmentedViewport,
) -> tuple[str, ...]:
    if viewport.bounding_box is None:
        return ()
    scoped = tuple(
        word
        for word in words
        if _bbox_fully_inside(word.bbox, viewport.bounding_box)
    )
    blocked = set()
    for _partition, _block_no, block_words, code, _item in _raw_material_definition_candidates(scoped):
        if any(not word.trusted for word in block_words):
            blocked.add(code)
    return tuple(sorted(blocked))

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


def _complete_source_plan_lines(
    words: Sequence[_TrustedTextWord], viewport: SegmentedViewport,
):
    """Keep complete original lines; never promote a readable line fragment."""
    assert viewport.bounding_box is not None
    _, complete, reasons = _trusted_lines_for_viewport(words, viewport)
    reasons = list(reasons)
    grouped = {}
    for word in words:
        grouped.setdefault(
            (word.source_partition_id, word.block_no, word.line_no), []
        ).append(word)
    lines = []
    unresolved = set()
    for line_words in grouped.values():
        if not any(_bbox_intersects(w.bbox, viewport.bounding_box) for w in line_words):
            continue
        line_words = sorted(line_words, key=lambda w: (w.word_no, w.observation_id))
        owned = all(
            _bbox_fully_inside(w.bbox, viewport.bounding_box) for w in line_words
        )
        indices = [w.word_no for w in line_words]
        consecutive = indices == list(range(len(indices)))
        if not owned or not consecutive or any(not w.trusted for w in line_words):
            complete = False
            unresolved.update(
                w.observation_id
                for w in line_words
                if not w.trusted or not owned or not consecutive
            )
            if not owned:
                reasons.append("source_material_native_line_crosses_viewport")
            if not consecutive:
                reasons.append("source_material_native_line_incomplete")
            continue
        text = " ".join(w.text.strip() for w in line_words if w.text.strip()).strip()
        if text:
            lines.append((
                text, _native_block_bbox(line_words),
                tuple(w.observation_id for w in line_words),
            ))
    return (
        tuple(lines), complete, tuple(dict.fromkeys(reasons)),
        tuple(sorted(unresolved)),
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
        _physical_plan_page_ids: tuple[str, ...] = (),
        _source_native_multirow_material_shadow: bool = False,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("Use from_source_visibility_producer()")
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        if type(_source_native_multirow_material_shadow) is not bool:
            raise ValueError("source_multirow_material_shadow_requires_explicit_bool")
        self._source_native_multirow_material_shadow = _source_native_multirow_material_shadow
        self._source = source_visibility_producer
        self._raster = RasterTextCorroborationProducer.from_source_visibility_producer(
            source_visibility_producer
        )
        self._physical_plan_page_ids = frozenset(_physical_plan_page_ids)
        self._plan_raster = (
            RasterTextCorroborationProducer.for_physical_plan_view_shadow(
                source_visibility_producer
            )
            if self._physical_plan_page_ids
            else None
        )
        self._plan_viewports: dict[tuple[str, str], SegmentedViewport] = {}
        self._plan_ownership_ids: dict[tuple[str, str], str] = {}
        self._plan_text_results: dict[
            tuple[str, str, str, str, str], RasterTextCorroborationResult
        ] = {}
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

    @classmethod
    def for_native_multirow_material_shadow(
        cls,
        source_visibility_producer: SourceVisibilityProducer,
    ) -> "SourceMaterialSemanticProducer":
        """Explicit opt-in original multi-code native CAD legend source path."""
        return cls(
            source_visibility_producer,
            _seal=_PRODUCER_SEAL,
            _source_native_multirow_material_shadow=True,
        )

    @classmethod
    def for_physical_plan_view_shadow(
        cls,
        source_visibility_producer: SourceVisibilityProducer,
        *,
        page_ids: Sequence[str],
    ) -> "SourceMaterialSemanticProducer":
        """Consume internally proven bounded views without commercial activation.

        An incomplete source text universe stays ABSTAINED, retaining only
        individually authenticated complete native material lines.
        """
        if not isinstance(page_ids, Sequence) or isinstance(page_ids, (str, bytes)) or not page_ids:
            raise ValueError("page_ids must be a non-empty sequence of canonical page IDs")
        if any(
            type(p) is not str or not p.isdecimal()
            or str(int(p)) != p or int(p) < 1
            for p in page_ids
        ):
            raise ValueError("page_ids must contain canonical positive page IDs")
        return cls(
            source_visibility_producer,
            _seal=_PRODUCER_SEAL,
            _physical_plan_page_ids=tuple(sorted(set(page_ids), key=int)),
        )

    def published_plan_viewports(self) -> tuple[SegmentedViewport, ...]:
        """Actual F.07 products consumed by this isolated producer."""
        return tuple(self._plan_viewports[k] for k in sorted(self._plan_viewports))

    def published_plan_text_corroboration_results(
        self,
    ) -> tuple[RasterTextCorroborationResult, ...]:
        """Retain positive and negative fixed-source OCR receipts for review."""
        return tuple(self._plan_text_results[k] for k in sorted(self._plan_text_results))

    def _recover_plan_material_words(self, published, words, viewport, dictionary):
        assert self._plan_raster is not None and viewport.bounding_box is not None
        grouped = {}
        for word in words:
            grouped.setdefault(
                (word.source_partition_id, word.block_no, word.line_no), []
            ).append(word)
        candidate_ids = set()
        for line in grouped.values():
            text = " ".join(w.text for w in sorted(line, key=lambda w: w.word_no))
            if (
                _source_owned_material_codes_in_line(text, dictionary)
                and all(_bbox_fully_inside(w.bbox, viewport.bounding_box) for w in line)
            ):
                candidate_ids.update(w.observation_id for w in line)
        recovered = []
        for word in words:
            if word.trusted or word.observation_id not in candidate_ids:
                recovered.append(word)
                continue
            selector = RasterTextCorroborationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=word.observation_id,
            )
            result = self._plan_raster.publish(selector)
            self._plan_text_results[selector.key] = result
            if (
                result.status is EvidenceResolutionStatus.CORROBORATED
                and result.record is not None
                and normalize_reading(result.corroborated_text) == normalize_reading(word.text)
            ):
                recovered.append(replace(
                    word, trusted=True,
                    reason_codes=(*word.reason_codes, "raster_text_corroborated"),
                ))
            else:
                recovered.append(word)
        return tuple(recovered)

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
        incomplete_definition_codes: set[str] = set()
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

                # Native source text can own schedule semantics either when
                # title + rows live in one block or when an independently
                # authenticated CAD export stores one schedule title plus a
                # strict cluster of split code/description row blocks.
                cluster_blocks, cluster_blocked_codes = (
                    _trusted_native_material_schedule_cluster_blocks(
                        source=self._source,
                        published=published,
                        raster=raster,
                        words=page_words,
                        **({"source_native_multirow_material_shadow": True}
                           if self._source_native_multirow_material_shadow else {}),
                    )
                )
                incomplete_definition_codes.update(cluster_blocked_codes)
                native_schedule_by_id = {
                    schedule_block.scope_id: schedule_block
                    for schedule_block in (
                        *_trusted_native_material_schedule_blocks(page_words),
                        *cluster_blocks,
                    )
                }
                native_schedule_blocks = tuple(
                    native_schedule_by_id[key]
                    for key in sorted(native_schedule_by_id)
                )
                for schedule_block in native_schedule_blocks:
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
                    segment_source_page_viewports(
                        self._source,
                        revision_id=revision_id,
                        page_id=str(page_number),
                        physical_plan_view_shadow=True,
                    )
                    if str(page_number) in self._physical_plan_page_ids
                    else segment_page_viewports(page, page_number=page_number)
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
                    if (
                        str(page_number) in self._physical_plan_page_ids
                        and viewport.provenance.get("source_owned_plan_view_proven") is True
                    ):
                        ids = tuple(v.view_id for v in viewports)
                        context = ProviderContext(
                            document_id=lineage["document_id"],
                            revision_id=lineage["revision_id"],
                            source_sha256=lineage["source_sha256"],
                            run_id="source-plan-material-shadow",
                            workspace_id="source-plan-material-shadow",
                            project_id="source-only",
                            current_revision_id=revision_id,
                            selected_pages=(page_number - 1,),
                            owned_viewport_ids=ids,
                            owned_page_numbers=(page_number,),
                            viewport_page_ownership=tuple((i, page_number) for i in ids),
                            evidence_snapshot_id=lineage["snapshot_id"],
                        )
                        adapted = adapt_f07_viewport_to_migration(
                            viewports, viewport_id=viewport.view_id,
                            context=context, page_no=page_number,
                        )
                        if adapted.abstained or adapted.blocking_reasons:
                            continue
                        key = (str(page_number), viewport.view_id)
                        self._plan_viewports[key] = viewport
                        self._plan_ownership_ids[key] = adapted.ownership_proof.ownership_id
                        drawing_viewports.append((page_number, viewport, page_words))
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
                            incomplete_definition_codes.update(
                                _material_candidate_codes_with_untrusted_words(
                                    scoped_words,
                                    viewport,
                                )
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

            blocked_reasons: tuple[str, ...] = ()
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
                # Preserve a fail-closed answer for codes that have no exact
                # authenticated definition result, without letting unrelated
                # unreadable schedule text erase independently authenticated
                # code rows.
                self._definition_scope_blockers[
                    (
                        lineage["document_id"],
                        lineage["revision_id"],
                        lineage["source_sha256"],
                        lineage["snapshot_id"],
                    )
                ] = blocked_reasons

            confirmed_dictionary: dict[str, dict[str, object]] = {}
            blocked_definition_codes: set[str] = set(incomplete_definition_codes)
            for code, items in sorted(raw_definitions.items()):
                selector = SourceMaterialDefinitionSelector(
                    **lineage,
                    code=code,
                )
                if code in incomplete_definition_codes:
                    blocked_definition_codes.add(code)
                    self._definition_results[selector.key] = _definition_blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        SOURCE_MATERIAL_VIEWPORT_UNAUTHENTICATED,
                        *blocked_reasons,
                    )
                    continue
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
                plan_key = (str(page_number), viewport.view_id)
                plan_shadow = plan_key in self._plan_ownership_ids
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
                unresolved_text_ids = ()
                relevant_blocked_codes = set(blocked_definition_codes)
                if plan_shadow:
                    relevant_blocked_codes.update(
                        key[-1] for key, result in self._definition_results.items()
                        if key[:4] == scope_selector.key[:4]
                        and result.status is not EvidenceResolutionStatus.CORROBORATED
                    )
                    page_words = self._recover_plan_material_words(
                        published, page_words, viewport,
                        {**dictionary_for_scan, **{c: {} for c in relevant_blocked_codes}},
                    )
                    lines, text_complete, text_reasons, unresolved_text_ids = _complete_source_plan_lines(page_words, viewport)
                else:
                    lines, text_complete, text_reasons = _trusted_lines_for_viewport(page_words, viewport)
                if not text_complete and not plan_shadow:
                    self._occurrence_results[scope_selector.key] = _scope_blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        SOURCE_MATERIAL_VIEWPORT_UNAUTHENTICATED,
                        *text_reasons,
                    )
                    continue
                if relevant_blocked_codes:
                    blocked_lookup = {
                        code: {}
                        for code in relevant_blocked_codes
                    }
                    if any(
                        _source_owned_material_codes_in_line(raw_text, blocked_lookup)
                        for raw_text, _bbox, _ids in lines
                    ):
                        if not plan_shadow:
                            self._occurrence_results[scope_selector.key] = _scope_blocked(
                                EvidenceResolutionStatus.ABSTAINED,
                                SOURCE_MATERIAL_SCOPE_UNAVAILABLE,
                                *blocked_reasons,
                            )
                            continue
                        text_complete = False
                        text_reasons = (*text_reasons, SOURCE_MATERIAL_SCOPE_UNAVAILABLE, *blocked_reasons)
                for raw_text, bbox, text_observation_ids in lines:
                    for code in _source_owned_material_codes_in_line(raw_text, dictionary_for_scan):
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
                        corroboration_ids = tuple(sorted(
                            result.record.record_id
                            for key, result in self._plan_text_results.items()
                            if plan_shadow and key[:4] == scope_selector.key[:4]
                            and key[-1] in text_observation_ids
                            and result.status is EvidenceResolutionStatus.CORROBORATED
                            and result.record is not None
                        ))
                        if corroboration_ids:
                            evidence_payload["source_text_corroboration_record_ids"] = corroboration_ids
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
                                source_text_corroboration_record_ids=corroboration_ids,
                            )
                        )
                records.sort(key=lambda row: row.record_id)
                self._occurrence_results[scope_selector.key] = (
                    SourceMaterialOccurrenceScopeResult(
                        status=(EvidenceResolutionStatus.CORROBORATED if text_complete else EvidenceResolutionStatus.ABSTAINED),
                        reason_codes=(
                            (SOURCE_MATERIAL_SCOPE_RESOLVED,) if not plan_shadow
                            else tuple(dict.fromkeys((
                                SOURCE_MATERIAL_BOUNDED_PLAN_SCOPE,
                                SOURCE_MATERIAL_SCOPE_RESOLVED if text_complete else SOURCE_MATERIAL_SCOPE_INCOMPLETE,
                                *text_reasons,
                            )))
                        ),
                        scope_complete=text_complete,
                        records=tuple(records),
                        source_viewport_ownership_id=self._plan_ownership_ids.get(plan_key, ""),
                        unresolved_source_text_observation_ids=unresolved_text_ids,
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
    "SOURCE_MATERIAL_SCOPE_INCOMPLETE",
    "SOURCE_MATERIAL_BOUNDED_PLAN_SCOPE",
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
