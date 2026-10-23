"""Shadow compiler: corroborated native words, unique graphic block-bar scale, unique primitive-owned hosts.

Live text integrity, physical-scale FIRM, W7, and hosted-opening geometry are not modified.
Uncorroborated words stay invisible. Ties are never broken by nearest, first, or smallest.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_label_dimension_authority import parse_opening_label_dimensions
from pb_scale_block_bar_shadow import BlockScaleBarCandidate, detect_block_scale_bars

SOURCE_CORROBORATED_TEXT_SCALE_HOST_SCHEMA_VERSION = "1.0.0"

METHOD_DIRECT_OCR = "DIRECT_OCR"
METHOD_AMORTIZED_GLYPH = "AMORTIZED_GLYPH"
METHOD_TRUSTED_PDF_TEXT = "TRUSTED_PDF_TEXT"
_ADMITTED_METHODS = frozenset(
    {METHOD_DIRECT_OCR, METHOD_AMORTIZED_GLYPH, METHOD_TRUSTED_PDF_TEXT}
)

SOURCE_TEXT_UNUSABLE = "source_text_unusable"
GRAPHIC_SCALE_UNAVAILABLE = "graphic_scale_unavailable"
GRAPHIC_SCALE_CONFLICT = "graphic_scale_conflict"
GRAPHIC_SCALE_CANDIDATE = "graphic_scale_candidate"
OPENING_LABEL_UNAVAILABLE = "opening_label_from_corroborated_text_unavailable"
OPENING_LABEL_AMBIGUOUS = "opening_label_from_corroborated_text_ambiguous"
OPENING_LABEL_CANDIDATE = "opening_label_from_corroborated_text_candidate"
HOST_PRIMITIVE_UNMAPPED = "opening_host_primitive_unmapped"
HOST_PRIMITIVE_AMBIGUOUS = "opening_host_primitive_ambiguous"
HOST_PRIMITIVE_CANDIDATE = "opening_host_primitive_candidate"

_PPM_REL_TOL = 1e-6
_COORD_TOL = 1e-9


@dataclass(frozen=True)
class CorroboratedNativeWord:
    observation_id: str
    text: str
    bbox: Tuple[float, float, float, float]
    method: str

    def __post_init__(self) -> None:
        if not str(self.observation_id).strip():
            raise ValueError("observation_id must be non-empty")
        if not str(self.text):
            raise ValueError("text must be present")
        if self.method not in _ADMITTED_METHODS:
            raise ValueError("method is not an admitted corroboration")
        if len(self.bbox) != 4:
            raise ValueError("bbox must be x0,y0,x1,y1")
        x0, y0, x1, y1 = (float(v) for v in self.bbox)
        if x1 <= x0 or y1 <= y0:
            raise ValueError("bbox must be ordered")


@dataclass(frozen=True)
class ShadowHostWall:
    wall_candidate_id: str
    source_primitive_ids: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not str(self.wall_candidate_id).strip():
            raise ValueError("wall_candidate_id must be non-empty")


@dataclass(frozen=True)
class ShadowGateResult:
    status: EvidenceResolutionStatus
    reason_codes: Tuple[str, ...]
    payload: Mapping[str, object]
    schema_version: str = SOURCE_CORROBORATED_TEXT_SCALE_HOST_SCHEMA_VERSION
    shadow_only: bool = True
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False


def _abstain(reason: str, **payload: object) -> ShadowGateResult:
    return ShadowGateResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=(reason,),
        payload=dict(payload),
    )


def _conflict(reason: str, **payload: object) -> ShadowGateResult:
    return ShadowGateResult(
        status=EvidenceResolutionStatus.CONFLICT,
        reason_codes=(reason,),
        payload=dict(payload),
    )


def _candidate(reason: str, **payload: object) -> ShadowGateResult:
    return ShadowGateResult(
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=(reason,),
        payload=dict(payload),
    )


def admitted_corroborated_words(
    words: Sequence[CorroboratedNativeWord],
) -> Tuple[CorroboratedNativeWord, ...]:
    """Deterministic, input-order invariant admission of corroborated native words."""
    unique: dict[str, CorroboratedNativeWord] = {}
    for word in words:
        if type(word) is not CorroboratedNativeWord:
            raise TypeError("word must be CorroboratedNativeWord")
        prior = unique.get(word.observation_id)
        if prior is not None and prior != word:
            raise ValueError(f"conflicting corroboration for {word.observation_id}")
        unique[word.observation_id] = word
    return tuple(sorted(unique.values(), key=lambda item: item.observation_id))


def resolve_graphic_block_bar_scale(
    segments: Sequence[Mapping[str, object]],
    words: Sequence[CorroboratedNativeWord],
) -> ShadowGateResult:
    """Unique block-bar scale from corroborated numerals. Never FIRM."""
    admitted = admitted_corroborated_words(words)
    if not admitted:
        return _abstain(SOURCE_TEXT_UNUSABLE, candidate_count=0)
    report = detect_block_scale_bars(
        tuple(segments),
        tuple(
            {
                "id": word.observation_id,
                "text": word.text,
                "bbox": list(word.bbox),
            }
            for word in admitted
        ),
    )
    bars = tuple(report.candidates)
    if not bars:
        return _abstain(GRAPHIC_SCALE_UNAVAILABLE, candidate_count=0)
    ppm_groups: dict[str, list[BlockScaleBarCandidate]] = {}
    for bar in bars:
        key = f"{bar.points_per_mm:.12e}"
        ppm_groups.setdefault(key, []).append(bar)
    if len(ppm_groups) > 1:
        representative = tuple(sorted(ppm_groups))
        disagree = False
        base = float(representative[0])
        for other in representative[1:]:
            value = float(other)
            if abs(value - base) > _PPM_REL_TOL * max(abs(base), abs(value), 1.0):
                disagree = True
                break
        if disagree:
            return _conflict(
                GRAPHIC_SCALE_CONFLICT,
                candidate_count=len(bars),
                points_per_mm_values=tuple(sorted(float(k) for k in ppm_groups)),
            )
    chosen = sorted(bars, key=lambda bar: (bar.axis, bar.label_ids, bar.edge_segment_ids))[0]
    record_id = stable_contract_id(
        "source_block_bar_scale_shadow",
        {
            "axis": chosen.axis,
            "label_ids": chosen.label_ids,
            "edge_segment_ids": chosen.edge_segment_ids,
            "points_per_mm": chosen.points_per_mm,
        },
    )
    return _candidate(
        GRAPHIC_SCALE_CANDIDATE,
        record_id=record_id,
        points_per_mm=chosen.points_per_mm,
        physical_span_mm=chosen.physical_span_mm,
        span_pt=chosen.span_pt,
        axis=chosen.axis,
        label_ids=chosen.label_ids,
        scale_authority_granted=False,
        candidate_count=len(bars),
    )


def _bbox_intersects(
    left: Tuple[float, float, float, float],
    right: Tuple[float, float, float, float],
) -> bool:
    return (
        left[0] < right[2] - _COORD_TOL
        and right[0] < left[2] - _COORD_TOL
        and left[1] < right[3] - _COORD_TOL
        and right[1] < left[3] - _COORD_TOL
    )


def resolve_opening_label_from_corroborated_text(
    opening_bbox: Tuple[float, float, float, float],
    words: Sequence[CorroboratedNativeWord],
) -> ShadowGateResult:
    """Bind a figured opening label only when exactly one corroborated parse intersects the opening."""
    admitted = admitted_corroborated_words(words)
    if not admitted:
        return _abstain(SOURCE_TEXT_UNUSABLE)
    x0, y0, x1, y1 = (float(v) for v in opening_bbox)
    if x1 <= x0 or y1 <= y0:
        raise ValueError("opening_bbox must be ordered")
    box = (x0, y0, x1, y1)
    hits: dict[tuple[object, ...], tuple[str, ...]] = {}
    for word in admitted:
        if not _bbox_intersects(word.bbox, box):
            continue
        parsed = parse_opening_label_dimensions(word.text)
        if parsed is None or parsed.dimension_count == 0:
            continue
        key = (parsed.dimension_values_mm, parsed.semantic_kind)
        hits.setdefault(key, [])
        if word.observation_id not in hits[key]:
            hits[key] = tuple(sorted((*hits[key], word.observation_id)))
    if not hits:
        return _abstain(OPENING_LABEL_UNAVAILABLE, parseable_count=0)
    if len(hits) > 1:
        return _conflict(
            OPENING_LABEL_AMBIGUOUS,
            parseable_count=len(hits),
            keys=tuple(sorted(hits, key=lambda item: (item[0], str(item[1])))),
        )
    (values, kind), observation_ids = next(iter(hits.items()))
    return _candidate(
        OPENING_LABEL_CANDIDATE,
        dimension_values_mm=values,
        semantic_kind=kind,
        source_text_observation_ids=observation_ids,
        axis_order_resolved=False,
    )


def resolve_primitive_owned_opening_host(
    face_primitive_ids: Sequence[str],
    walls: Sequence[ShadowHostWall],
) -> ShadowGateResult:
    """Host band from unique source-primitive ownership. Page-wide ambiguity is not a veto."""
    faces = tuple(dict.fromkeys(str(item).strip() for item in face_primitive_ids if str(item).strip()))
    if len(faces) != 4:
        return _abstain(HOST_PRIMITIVE_UNMAPPED, face_count=len(faces))
    owners_by_primitive: dict[str, Tuple[str, ...]] = {face: () for face in faces}
    walls_by_id: dict[str, ShadowHostWall] = {}
    for wall in walls:
        if type(wall) is not ShadowHostWall:
            raise TypeError("wall must be ShadowHostWall")
        prior = walls_by_id.get(wall.wall_candidate_id)
        if prior is not None and prior != wall:
            raise ValueError(f"conflicting wall record {wall.wall_candidate_id}")
        walls_by_id[wall.wall_candidate_id] = wall
        owned = set(str(item).strip() for item in wall.source_primitive_ids if str(item).strip())
        for face in faces:
            if face in owned:
                owners_by_primitive[face] = tuple(
                    sorted(set(owners_by_primitive[face]) | {wall.wall_candidate_id})
                )
    missing = tuple(face for face, owners in sorted(owners_by_primitive.items()) if not owners)
    if missing:
        return _abstain(
            HOST_PRIMITIVE_UNMAPPED,
            unmapped_primitive_ids=missing,
        )
    contested = tuple(
        face
        for face, owners in sorted(owners_by_primitive.items())
        if len(owners) != 1
    )
    if contested:
        return _conflict(
            HOST_PRIMITIVE_AMBIGUOUS,
            contested_primitive_ids=contested,
            owners_by_primitive=dict(owners_by_primitive),
        )
    host_ids = tuple(sorted({owners_by_primitive[face][0] for face in faces}))
    if len(host_ids) not in (1, 2):
        return _conflict(
            HOST_PRIMITIVE_AMBIGUOUS,
            host_wall_ids=host_ids,
        )
    return _candidate(
        HOST_PRIMITIVE_CANDIDATE,
        host_wall_ids=host_ids,
        face_primitive_ids=faces,
        owners_by_primitive=dict(owners_by_primitive),
    )


def compile_corroborated_text_scale_host(
    *,
    segments: Sequence[Mapping[str, object]],
    words: Sequence[CorroboratedNativeWord],
    opening_bbox: Tuple[float, float, float, float],
    face_primitive_ids: Sequence[str],
    walls: Sequence[ShadowHostWall],
) -> ShadowGateResult:
    """First remaining gate on the shadow chain. Later gates are not evaluated after a block."""
    scale = resolve_graphic_block_bar_scale(segments, words)
    if scale.status is not EvidenceResolutionStatus.CANDIDATE:
        return scale
    label = resolve_opening_label_from_corroborated_text(opening_bbox, words)
    if label.status is not EvidenceResolutionStatus.CANDIDATE:
        return label
    host = resolve_primitive_owned_opening_host(face_primitive_ids, walls)
    if host.status is not EvidenceResolutionStatus.CANDIDATE:
        return host
    return _candidate(
        "corroborated_text_scale_host_candidate",
        scale=scale.payload,
        label=label.payload,
        host=host.payload,
        first_failing_authority=None,
    )


__all__ = (
    "CorroboratedNativeWord",
    "ShadowGateResult",
    "ShadowHostWall",
    "admitted_corroborated_words",
    "compile_corroborated_text_scale_host",
    "resolve_graphic_block_bar_scale",
    "resolve_opening_label_from_corroborated_text",
    "resolve_primitive_owned_opening_host",
)
