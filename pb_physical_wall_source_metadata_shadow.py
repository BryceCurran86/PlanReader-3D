"""Shadow-only source graphic-state descriptors for physical wall candidates.

This module joins already-produced physical wall candidate identities back to
producer-owned visible source primitives. It is deliberately descriptive:
stroke, fill, width, layer and dash metadata are reported exactly as source
provenance, with the existing primitive-lineage unknown/agreed/conflict
vocabulary and drawing-relative width ordering.

Nothing here classifies a segment as a wall or non-wall, changes topology,
filters candidates, assigns confidence, or publishes authority. In particular,
a layer name containing "wall" is exposed only as a literal descriptive subset
using the same case-insensitive substring convention already used by the
canonical wall evidence model; it is not support or opposition.

Drawing-relative width rank is ordinal only. Rank 1 is the smallest distinct
present width among all producer-owned visible source segments in the exact
scope passed by the wall authority. No numeric threshold or percentile is
introduced.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Optional, Sequence

from pb_wall_room_topology_primitive_lineage import (
    lineage_from_source_segments,
    source_record_from_segment,
)


PHYSICAL_WALL_SOURCE_METADATA_SCHEMA_VERSION = "1.0.0"
SOURCE_METADATA_DESCRIBED = "described"
SOURCE_METADATA_UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class DrawingRelativeWidthRank:
    """Ordinal position of one exact present source width inside its scope."""

    width_pt: float
    rank_ascending: int
    distinct_width_count: int


@dataclass(frozen=True)
class PhysicalWallSourceMetadataDescriptor:
    """Descriptive source graphic-state joined to one wall candidate."""

    wall_candidate_id: str
    source_primitive_ids: tuple[str, ...]
    matched_source_primitive_ids: tuple[str, ...]
    missing_source_primitive_ids: tuple[str, ...]
    source_record_count: int

    width_status: str
    width_values_pt: tuple[float, ...]
    drawing_relative_width_ranks: tuple[DrawingRelativeWidthRank, ...]
    width_present_source_record_count: int

    stroke_status: str
    stroke_values: tuple[object, ...]
    stroke_present_source_record_count: int

    fill_status: str
    fill_values: tuple[object, ...]
    fill_present_source_record_count: int

    layer_status: str
    layer_values: tuple[str, ...]
    wall_named_layer_values: tuple[str, ...]
    layer_present_source_record_count: int

    dashes_status: str
    dashes_values: tuple[str, ...]
    dashes_present_source_record_count: int

    schema_version: str = PHYSICAL_WALL_SOURCE_METADATA_SCHEMA_VERSION


@dataclass(frozen=True)
class PhysicalWallSourceMetadataScopeTable:
    """Shadow table for one exact physical-wall authority scope."""

    status: str
    reason_code: Optional[str]
    page_id: str
    decision_scope_id: str
    source_segment_count: int
    candidate_count: int

    distinct_widths_pt: tuple[float, ...]
    distinct_stroke_values: tuple[object, ...]
    distinct_fill_values: tuple[object, ...]
    distinct_layer_values: tuple[str, ...]
    wall_named_layer_values: tuple[str, ...]
    distinct_dashes_values: tuple[str, ...]

    descriptors: tuple[PhysicalWallSourceMetadataDescriptor, ...]
    schema_version: str = PHYSICAL_WALL_SOURCE_METADATA_SCHEMA_VERSION

    def descriptor_for(
        self, wall_candidate_id: str
    ) -> Optional[PhysicalWallSourceMetadataDescriptor]:
        key = str(wall_candidate_id)
        for descriptor in self.descriptors:
            if descriptor.wall_candidate_id == key:
                return descriptor
        return None


def _stable_value(value: Any) -> object:
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        return round(value, 9)
    if isinstance(value, int):
        return value
    if isinstance(value, (list, tuple)):
        return tuple(_stable_value(item) for item in value)
    if isinstance(value, Mapping):
        return tuple(
            sorted(
                (str(key), _stable_value(item))
                for key, item in value.items()
            )
        )
    return str(value)


def _unique_sorted(values: Sequence[object]) -> tuple[object, ...]:
    by_key: dict[str, object] = {}
    for value in values:
        stable = _stable_value(value)
        by_key.setdefault(repr(stable), stable)
    return tuple(by_key[key] for key in sorted(by_key))


def _present_values(
    records: Sequence[Mapping[str, Any]],
    field: str,
) -> tuple[object, ...]:
    values = [
        record.get(field)
        for record in records
        if bool(record.get(f"{field}_present"))
    ]
    return _unique_sorted(values)


def _present_count(records: Sequence[Mapping[str, Any]], field: str) -> int:
    return sum(1 for record in records if bool(record.get(f"{field}_present")))


def _finite_widths(records: Sequence[Mapping[str, Any]]) -> tuple[float, ...]:
    values: set[float] = set()
    for record in records:
        if not bool(record.get("width_present")):
            continue
        try:
            value = float(record.get("width"))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value):
            continue
        values.add(round(value, 9))
    return tuple(sorted(values))


def _scope_records(
    source_segments: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    return tuple(source_record_from_segment(segment) for segment in source_segments)


def _segments_by_id(
    source_segments: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[Mapping[str, Any], ...]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for segment in source_segments:
        raw_id = str(segment.get("id") or "").strip()
        if not raw_id:
            continue
        grouped.setdefault(raw_id, []).append(segment)
    return {key: tuple(values) for key, values in grouped.items()}


def _descriptor(
    *,
    record: object,
    segments_by_id: Mapping[str, Sequence[Mapping[str, Any]]],
    scope_widths: Sequence[float],
) -> PhysicalWallSourceMetadataDescriptor:
    wall_candidate_id = str(getattr(record, "wall_candidate_id"))
    identity = getattr(record, "physical_identity")
    source_primitive_ids = tuple(
        sorted(dict.fromkeys(str(item) for item in identity.source_primitive_ids))
    )

    matched_ids: list[str] = []
    missing_ids: list[str] = []
    matched_segments: list[Mapping[str, Any]] = []
    for source_id in source_primitive_ids:
        segments = tuple(segments_by_id.get(source_id, ()))
        if not segments:
            missing_ids.append(source_id)
            continue
        matched_ids.append(source_id)
        matched_segments.extend(segments)

    lineage = lineage_from_source_segments(tuple(matched_segments))
    source_records = tuple(lineage.get("source_records") or ())
    attribute_status = dict(lineage.get("attribute_status") or {})

    width_values = _finite_widths(source_records)
    rank_by_width = {
        round(float(width), 9): index + 1
        for index, width in enumerate(scope_widths)
    }
    width_ranks = tuple(
        DrawingRelativeWidthRank(
            width_pt=width,
            rank_ascending=rank_by_width[width],
            distinct_width_count=len(scope_widths),
        )
        for width in width_values
        if width in rank_by_width
    )

    stroke_values = _present_values(source_records, "stroke")
    fill_values = _present_values(source_records, "fill")
    layer_values = tuple(str(value) for value in _present_values(source_records, "layer"))
    dashes_values = tuple(str(value) for value in _present_values(source_records, "dashes"))
    wall_named_layers = tuple(
        value for value in layer_values if "wall" in value.lower()
    )

    return PhysicalWallSourceMetadataDescriptor(
        wall_candidate_id=wall_candidate_id,
        source_primitive_ids=source_primitive_ids,
        matched_source_primitive_ids=tuple(matched_ids),
        missing_source_primitive_ids=tuple(missing_ids),
        source_record_count=len(source_records),
        width_status=str(attribute_status.get("width") or "unknown"),
        width_values_pt=width_values,
        drawing_relative_width_ranks=width_ranks,
        width_present_source_record_count=_present_count(source_records, "width"),
        stroke_status=str(attribute_status.get("stroke") or "unknown"),
        stroke_values=stroke_values,
        stroke_present_source_record_count=_present_count(source_records, "stroke"),
        fill_status=str(attribute_status.get("fill") or "unknown"),
        fill_values=fill_values,
        fill_present_source_record_count=_present_count(source_records, "fill"),
        layer_status=str(attribute_status.get("layer") or "unknown"),
        layer_values=layer_values,
        wall_named_layer_values=wall_named_layers,
        layer_present_source_record_count=_present_count(source_records, "layer"),
        dashes_status=str(attribute_status.get("dashes") or "unknown"),
        dashes_values=dashes_values,
        dashes_present_source_record_count=_present_count(source_records, "dashes"),
    )


def build_physical_wall_source_metadata_scope_table(
    *,
    records: Sequence[object],
    source_segments: Sequence[Mapping[str, Any]],
    page_id: str,
    decision_scope_id: str,
) -> PhysicalWallSourceMetadataScopeTable:
    """Build a deterministic, non-authoritative graphic-state census."""

    segments = tuple(source_segments)
    scope_records = _scope_records(segments)
    scope_widths = _finite_widths(scope_records)
    segments_by_id = _segments_by_id(segments)

    descriptors = tuple(
        sorted(
            (
                _descriptor(
                    record=record,
                    segments_by_id=segments_by_id,
                    scope_widths=scope_widths,
                )
                for record in records
            ),
            key=lambda item: item.wall_candidate_id,
        )
    )

    scope_layers = tuple(str(value) for value in _present_values(scope_records, "layer"))
    return PhysicalWallSourceMetadataScopeTable(
        status=SOURCE_METADATA_DESCRIBED,
        reason_code=None,
        page_id=str(page_id),
        decision_scope_id=str(decision_scope_id),
        source_segment_count=len(segments),
        candidate_count=len(descriptors),
        distinct_widths_pt=scope_widths,
        distinct_stroke_values=_present_values(scope_records, "stroke"),
        distinct_fill_values=_present_values(scope_records, "fill"),
        distinct_layer_values=scope_layers,
        wall_named_layer_values=tuple(
            value for value in scope_layers if "wall" in value.lower()
        ),
        distinct_dashes_values=tuple(
            str(value) for value in _present_values(scope_records, "dashes")
        ),
        descriptors=descriptors,
    )


def unavailable_physical_wall_source_metadata_scope_table(
    *,
    page_id: str,
    decision_scope_id: str,
    reason_code: str,
) -> PhysicalWallSourceMetadataScopeTable:
    """Return an explicit unavailable shadow table without claiming absence."""

    return PhysicalWallSourceMetadataScopeTable(
        status=SOURCE_METADATA_UNAVAILABLE,
        reason_code=str(reason_code),
        page_id=str(page_id),
        decision_scope_id=str(decision_scope_id),
        source_segment_count=0,
        candidate_count=0,
        distinct_widths_pt=(),
        distinct_stroke_values=(),
        distinct_fill_values=(),
        distinct_layer_values=(),
        wall_named_layer_values=(),
        distinct_dashes_values=(),
        descriptors=(),
    )


__all__ = [
    "DrawingRelativeWidthRank",
    "PHYSICAL_WALL_SOURCE_METADATA_SCHEMA_VERSION",
    "PhysicalWallSourceMetadataDescriptor",
    "PhysicalWallSourceMetadataScopeTable",
    "SOURCE_METADATA_DESCRIBED",
    "SOURCE_METADATA_UNAVAILABLE",
    "build_physical_wall_source_metadata_scope_table",
    "unavailable_physical_wall_source_metadata_scope_table",
]
