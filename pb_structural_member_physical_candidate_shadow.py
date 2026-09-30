"""Shadow-only source-owned physical structural geometry candidates.

This module preserves neutral physical geometry propositions. It does not
create structural members, assign semantic roles, bind structural definitions,
prove scope completeness, or publish quantities.

Candidates are reconstructed only from exact SHA-verified source bytes and
must be backed by producer-owned native PDF visible-segment observations from
the same immutable revision/snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Mapping, Optional, Sequence

import fitz

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_source_observation_authority import (
    ObservationSelector,
    SOURCE_HASH_MISMATCH,
)
from pb_source_visibility_authority import (
    NATIVE_PDF_VISIBLE_SEGMENT,
    SourceVisibilityProducer,
)
from pb_vector_geometry_v130 import extract_native_page


STRUCTURAL_PHYSICAL_CANDIDATE_SHADOW_SCHEMA_VERSION = "1.0.0"

COMPACT_MEMBER_SYMBOL_CANDIDATE = "compact_member_symbol_candidate"
VERTICAL_PROFILE_CANDIDATE = "vertical_profile_candidate"
OUTLINED_VERTICAL_PROFILE_CANDIDATE = (
    "outlined_vertical_profile_candidate"
)

STRUCTURAL_PHYSICAL_CANDIDATE_SHADOW_RESOLVED = (
    "structural_physical_candidate_shadow_resolved"
)
STRUCTURAL_PHYSICAL_CANDIDATE_SHADOW_EMPTY = (
    "structural_physical_candidate_shadow_empty"
)
STRUCTURAL_PHYSICAL_CANDIDATE_SHADOW_SOURCE_UNAVAILABLE = (
    "structural_physical_candidate_shadow_source_unavailable"
)
STRUCTURAL_PHYSICAL_CANDIDATE_SHADOW_PAGE_UNAVAILABLE = (
    "structural_physical_candidate_shadow_page_unavailable"
)
STRUCTURAL_PHYSICAL_CANDIDATE_SHADOW_VISIBLE_SOURCE_CONFLICT = (
    "structural_physical_candidate_shadow_visible_source_conflict"
)


@dataclass(frozen=True)
class StructuralPhysicalGeometryCandidate:
    candidate_id: str
    candidate_class: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    view_id: None
    source_partition_id: str
    source_observation_ids: tuple[str, ...]
    source_primitive_refs: tuple[str, ...]
    path_index: int
    item_indices: tuple[int, ...]
    geometry_kind: str
    bbox: tuple[float, float, float, float]
    width: float
    height: float
    orientation: str
    fill_present: bool
    stroke_present: bool
    stroke_width: Optional[float]
    layer_present: bool
    dashes_present: bool
    schema_version: str = STRUCTURAL_PHYSICAL_CANDIDATE_SHADOW_SCHEMA_VERSION


@dataclass(frozen=True)
class StructuralPhysicalCandidateShadowResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_ids: tuple[str, ...]
    candidates: tuple[StructuralPhysicalGeometryCandidate, ...]
    schema_version: str = STRUCTURAL_PHYSICAL_CANDIDATE_SHADOW_SCHEMA_VERSION


def _blocked(
    *,
    status: EvidenceResolutionStatus,
    reason: str,
    published=None,
    page_ids: Sequence[str] = (),
) -> StructuralPhysicalCandidateShadowResult:
    revision = getattr(published, "revision", None)
    snapshot = getattr(published, "snapshot", None)
    return StructuralPhysicalCandidateShadowResult(
        status=status,
        reason_codes=(str(reason),),
        document_id="" if revision is None else str(revision.document_id),
        revision_id="" if revision is None else str(revision.revision_id),
        source_sha256="" if revision is None else str(revision.source_sha256),
        snapshot_id="" if snapshot is None else str(snapshot.snapshot_id),
        page_ids=tuple(str(page) for page in page_ids),
        candidates=(),
    )


def _finite_bbox(
    values: Sequence[object],
) -> Optional[tuple[float, float, float, float]]:
    if len(values) < 4:
        return None
    try:
        x0, y0, x1, y1 = (float(values[index]) for index in range(4))
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (x0, y0, x1, y1)):
        return None
    left, right = sorted((x0, x1))
    top, bottom = sorted((y0, y1))
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def _bbox_from_segments(
    segments: Sequence[Mapping[str, object]],
) -> Optional[tuple[float, float, float, float]]:
    xs: list[float] = []
    ys: list[float] = []
    for segment in segments:
        try:
            points = (
                float(segment["x1"]),
                float(segment["y1"]),
                float(segment["x2"]),
                float(segment["y2"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
        if not all(math.isfinite(value) for value in points):
            return None
        xs.extend((points[0], points[2]))
        ys.extend((points[1], points[3]))
    if not xs or not ys:
        return None
    return _finite_bbox((min(xs), min(ys), max(xs), max(ys)))


def _graphic_tuple(
    value: object,
) -> Optional[tuple[float, ...]]:
    if value is None:
        return None
    try:
        result = tuple(float(item) for item in value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(item) for item in result):
        return None
    return result


def _line_path_is_axis_aligned_rectangle(
    segments: Sequence[Mapping[str, object]],
) -> bool:
    if len(segments) != 4:
        return False
    bbox = _bbox_from_segments(segments)
    if bbox is None:
        return False
    x0, y0, x1, y1 = bbox
    tolerance = max(1e-6, max(x1 - x0, y1 - y0) * 1e-7)
    expected = {
        ("h", round(y0 / tolerance), round(x0 / tolerance), round(x1 / tolerance)),
        ("h", round(y1 / tolerance), round(x0 / tolerance), round(x1 / tolerance)),
        ("v", round(x0 / tolerance), round(y0 / tolerance), round(y1 / tolerance)),
        ("v", round(x1 / tolerance), round(y0 / tolerance), round(y1 / tolerance)),
    }
    actual = set()
    for segment in segments:
        x_start = float(segment["x1"])
        y_start = float(segment["y1"])
        x_end = float(segment["x2"])
        y_end = float(segment["y2"])
        if abs(y_start - y_end) <= tolerance:
            left, right = sorted((x_start, x_end))
            actual.add(
                (
                    "h",
                    round(((y_start + y_end) / 2.0) / tolerance),
                    round(left / tolerance),
                    round(right / tolerance),
                )
            )
        elif abs(x_start - x_end) <= tolerance:
            top, bottom = sorted((y_start, y_end))
            actual.add(
                (
                    "v",
                    round(((x_start + x_end) / 2.0) / tolerance),
                    round(top / tolerance),
                    round(bottom / tolerance),
                )
            )
        else:
            return False
    return actual == expected


def _candidate_class(
    *,
    width: float,
    height: float,
    fill_present: bool,
    exact_outline: bool,
    scale_ref: float,
) -> Optional[str]:
    if width <= 0.0 or height <= 0.0 or scale_ref <= 0.0:
        return None

    aspect = max(width, height) / min(width, height)
    min_side = scale_ref * 0.00035
    max_side = scale_ref * 0.02

    if (
        fill_present
        and min_side <= width <= max_side
        and min_side <= height <= max_side
        and aspect <= 1.20
        and exact_outline
    ):
        return COMPACT_MEMBER_SYMBOL_CANDIDATE

    if height / width < 3.0:
        return None

    if exact_outline and not fill_present:
        return OUTLINED_VERTICAL_PROFILE_CANDIDATE
    return VERTICAL_PROFILE_CANDIDATE


def _candidate_record(
    *,
    candidate_class: str,
    published,
    page_id: str,
    source_refs: Sequence[str],
    observation_ids: Sequence[str],
    path_index: int,
    item_indices: Sequence[int],
    geometry_kind: str,
    bbox: tuple[float, float, float, float],
    fill_present: bool,
    stroke_present: bool,
    stroke_width: Optional[float],
    layer_present: bool,
    dashes_present: bool,
) -> StructuralPhysicalGeometryCandidate:
    x0, y0, x1, y1 = bbox
    width = x1 - x0
    height = y1 - y0
    refs = tuple(sorted(set(str(ref) for ref in source_refs)))
    observations = tuple(
        sorted(set(str(observation_id) for observation_id in observation_ids))
    )
    items = tuple(sorted(set(int(index) for index in item_indices)))
    payload = {
        "document_id": published.revision.document_id,
        "revision_id": published.revision.revision_id,
        "source_sha256": published.revision.source_sha256,
        "snapshot_id": published.snapshot.snapshot_id,
        "page_id": str(page_id),
        "candidate_class": str(candidate_class),
        "source_observation_ids": observations,
        "source_primitive_refs": refs,
        "path_index": int(path_index),
        "item_indices": items,
        "geometry_kind": str(geometry_kind),
        "bbox": tuple(round(float(value), 8) for value in bbox),
    }
    return StructuralPhysicalGeometryCandidate(
        candidate_id=stable_contract_id(
            "structural_physical_geometry_candidate_shadow_v1",
            payload,
            digest_chars=32,
        ),
        candidate_class=str(candidate_class),
        document_id=str(published.revision.document_id),
        revision_id=str(published.revision.revision_id),
        source_sha256=str(published.revision.source_sha256),
        snapshot_id=str(published.snapshot.snapshot_id),
        page_id=str(page_id),
        view_id=None,
        source_partition_id=f"page:{page_id}",
        source_observation_ids=observations,
        source_primitive_refs=refs,
        path_index=int(path_index),
        item_indices=items,
        geometry_kind=str(geometry_kind),
        bbox=tuple(float(value) for value in bbox),
        width=float(width),
        height=float(height),
        orientation="vertical" if height > width else "compact",
        fill_present=bool(fill_present),
        stroke_present=bool(stroke_present),
        stroke_width=(
            None if stroke_width is None else float(stroke_width)
        ),
        layer_present=bool(layer_present),
        dashes_present=bool(dashes_present),
    )


def _compile_native_page_candidates(
    *,
    native: Mapping[str, object],
    published,
    page_id: str,
    visible_refs: Mapping[str, str],
) -> tuple[StructuralPhysicalGeometryCandidate, ...]:
    try:
        page_width = float(native["width"])
        page_height = float(native["height"])
    except (KeyError, TypeError, ValueError):
        return ()
    if (
        not math.isfinite(page_width)
        or not math.isfinite(page_height)
        or page_width <= 0.0
        or page_height <= 0.0
    ):
        return ()
    scale_ref = max(1.0, min(page_width, page_height))

    raw_segments = tuple(
        segment
        for segment in (native.get("segments") or ())  # type: ignore[union-attr]
        if isinstance(segment, Mapping)
    )
    visible_segments: list[Mapping[str, object]] = []
    for segment in raw_segments:
        raw_id = str(segment.get("id") or "").strip()
        if not raw_id:
            continue
        ref = f"visible:segment:{raw_id}"
        if ref in visible_refs:
            visible_segments.append(segment)

    by_path: dict[int, list[Mapping[str, object]]] = {}
    for segment in visible_segments:
        try:
            path_index = int(segment.get("path_index"))
        except (TypeError, ValueError):
            continue
        by_path.setdefault(path_index, []).append(segment)

    candidates: list[StructuralPhysicalGeometryCandidate] = []
    rect_keys: set[tuple[int, int]] = set()

    for rect in tuple(native.get("rects") or ()):  # type: ignore[union-attr]
        if not isinstance(rect, Mapping):
            continue
        try:
            path_index = int(rect.get("path_index"))
            item_index = int(rect.get("item_index"))
        except (TypeError, ValueError):
            continue
        bbox = _finite_bbox(tuple(rect.get("bbox") or ()))
        if bbox is None:
            continue

        refs = tuple(
            f"visible:segment:d{path_index}i{item_index}e{edge}"
            for edge in range(4)
        )
        if any(ref not in visible_refs for ref in refs):
            continue

        rect_keys.add((path_index, item_index))
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        candidate_class = _candidate_class(
            width=width,
            height=height,
            fill_present=rect.get("fill_present") is True,
            exact_outline=True,
            scale_ref=scale_ref,
        )
        if candidate_class is None:
            continue

        stroke_width = (
            float(rect.get("width"))
            if rect.get("width_present") is True
            and rect.get("width") is not None
            else None
        )
        candidates.append(
            _candidate_record(
                candidate_class=candidate_class,
                published=published,
                page_id=page_id,
                source_refs=refs,
                observation_ids=tuple(visible_refs[ref] for ref in refs),
                path_index=path_index,
                item_indices=(item_index,),
                geometry_kind="native_rect_item",
                bbox=bbox,
                fill_present=rect.get("fill_present") is True,
                stroke_present=rect.get("stroke_present") is True,
                stroke_width=stroke_width,
                layer_present=rect.get("layer_present") is True,
                dashes_present=rect.get("dashes_present") is True,
            )
        )

    for path_index, rows in sorted(by_path.items()):
        line_rows = [
            row
            for row in rows
            if str(row.get("kind") or "") == "line"
        ]
        if len(line_rows) < 2:
            continue
        # A native rectangle item already has stronger item-level identity and
        # was considered above. Do not duplicate it as a generic path.
        if any(
            (path_index, int(row.get("item_index"))) in rect_keys
            for row in rows
            if row.get("item_index") is not None
        ):
            continue

        bbox = _bbox_from_segments(line_rows)
        if bbox is None:
            continue
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        exact_outline = _line_path_is_axis_aligned_rectangle(line_rows)
        first = line_rows[0]
        candidate_class = _candidate_class(
            width=width,
            height=height,
            fill_present=first.get("fill_present") is True,
            exact_outline=exact_outline,
            scale_ref=scale_ref,
        )
        if candidate_class is None:
            continue

        refs = tuple(
            f"visible:segment:{str(row.get('id') or '').strip()}"
            for row in line_rows
            if str(row.get("id") or "").strip()
        )
        if not refs or any(ref not in visible_refs for ref in refs):
            continue
        item_indices = tuple(
            int(row.get("item_index"))
            for row in line_rows
            if row.get("item_index") is not None
        )
        stroke_width = (
            float(first.get("width"))
            if first.get("width_present") is True
            and first.get("width") is not None
            else None
        )
        candidates.append(
            _candidate_record(
                candidate_class=candidate_class,
                published=published,
                page_id=page_id,
                source_refs=refs,
                observation_ids=tuple(visible_refs[ref] for ref in refs),
                path_index=path_index,
                item_indices=item_indices,
                geometry_kind=(
                    "native_line_rectangle_path"
                    if exact_outline
                    else "native_line_path"
                ),
                bbox=bbox,
                fill_present=first.get("fill_present") is True,
                stroke_present=first.get("stroke_present") is True,
                stroke_width=stroke_width,
                layer_present=first.get("layer_present") is True,
                dashes_present=first.get("dashes_present") is True,
            )
        )

    return tuple(sorted(candidates, key=lambda row: row.candidate_id))


def compile_structural_physical_candidate_shadow(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    revision_id: str,
    source_bytes: bytes,
    page_ids: Sequence[str] | None = None,
) -> StructuralPhysicalCandidateShadowResult:
    """Compile neutral physical geometry candidates from exact source bytes."""

    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError(
            "source_visibility_producer must be producer-owned "
            "SourceVisibilityProducer"
        )
    if not isinstance(source_bytes, bytes):
        raise TypeError("source_bytes must be immutable bytes")

    published = source_visibility_producer.published_snapshot_for_revision(
        str(revision_id)
    )
    if published is None:
        return _blocked(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason=STRUCTURAL_PHYSICAL_CANDIDATE_SHADOW_SOURCE_UNAVAILABLE,
        )

    actual_sha = hashlib.sha256(source_bytes).hexdigest()
    if actual_sha != str(published.revision.source_sha256):
        return _blocked(
            status=EvidenceResolutionStatus.CONFLICT,
            reason=SOURCE_HASH_MISMATCH,
            published=published,
        )

    decoded_pages = {
        str(int(page)) for page in published.coverage.decoded_pages
    }
    if page_ids is None:
        selected_pages = tuple(sorted(decoded_pages, key=int))
    else:
        selected_pages = tuple(
            sorted(
                {
                    str(page).strip()
                    for page in page_ids
                    if str(page).strip()
                },
                key=int,
            )
        )
        if (
            not selected_pages
            or any(page not in decoded_pages for page in selected_pages)
        ):
            return _blocked(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason=STRUCTURAL_PHYSICAL_CANDIDATE_SHADOW_PAGE_UNAVAILABLE,
                published=published,
                page_ids=selected_pages,
            )

    visibility = source_visibility_producer.authority()
    visible_by_page: dict[str, dict[str, str]] = {
        page: {} for page in selected_pages
    }
    for observation_id in published.visible_observation_ids:
        result = visibility.resolve(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        observation = result.observation
        if result.status is EvidenceResolutionStatus.CONFLICT:
            return _blocked(
                status=EvidenceResolutionStatus.CONFLICT,
                reason=STRUCTURAL_PHYSICAL_CANDIDATE_SHADOW_VISIBLE_SOURCE_CONFLICT,
                published=published,
                page_ids=selected_pages,
            )
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or observation is None
            or observation.observation_kind != NATIVE_PDF_VISIBLE_SEGMENT
            or observation.page_id not in visible_by_page
        ):
            continue
        visible_by_page[observation.page_id][
            observation.source_primitive_ref
        ] = observation.observation_id

    candidates: list[StructuralPhysicalGeometryCandidate] = []
    pdf = fitz.open(stream=source_bytes, filetype="pdf")
    try:
        for page_id in selected_pages:
            page = pdf.load_page(int(page_id) - 1)
            native = extract_native_page(page)
            candidates.extend(
                _compile_native_page_candidates(
                    native=native,
                    published=published,
                    page_id=page_id,
                    visible_refs=visible_by_page.get(page_id, {}),
                )
            )
    finally:
        pdf.close()

    ordered = tuple(sorted(candidates, key=lambda row: row.candidate_id))
    return StructuralPhysicalCandidateShadowResult(
        status=(
            EvidenceResolutionStatus.CORROBORATED
            if ordered
            else EvidenceResolutionStatus.ABSTAINED
        ),
        reason_codes=(
            STRUCTURAL_PHYSICAL_CANDIDATE_SHADOW_RESOLVED
            if ordered
            else STRUCTURAL_PHYSICAL_CANDIDATE_SHADOW_EMPTY,
        ),
        document_id=str(published.revision.document_id),
        revision_id=str(published.revision.revision_id),
        source_sha256=str(published.revision.source_sha256),
        snapshot_id=str(published.snapshot.snapshot_id),
        page_ids=selected_pages,
        candidates=ordered,
    )


__all__ = [
    "COMPACT_MEMBER_SYMBOL_CANDIDATE",
    "OUTLINED_VERTICAL_PROFILE_CANDIDATE",
    "STRUCTURAL_PHYSICAL_CANDIDATE_SHADOW_SCHEMA_VERSION",
    "STRUCTURAL_PHYSICAL_CANDIDATE_SHADOW_RESOLVED",
    "STRUCTURAL_PHYSICAL_CANDIDATE_SHADOW_EMPTY",
    "STRUCTURAL_PHYSICAL_CANDIDATE_SHADOW_SOURCE_UNAVAILABLE",
    "STRUCTURAL_PHYSICAL_CANDIDATE_SHADOW_PAGE_UNAVAILABLE",
    "STRUCTURAL_PHYSICAL_CANDIDATE_SHADOW_VISIBLE_SOURCE_CONFLICT",
    "VERTICAL_PROFILE_CANDIDATE",
    "StructuralPhysicalGeometryCandidate",
    "StructuralPhysicalCandidateShadowResult",
    "compile_structural_physical_candidate_shadow",
]
