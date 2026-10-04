from __future__ import annotations

from types import SimpleNamespace

import fitz
import pytest

import pb_physical_wall_candidate_authority as authority_module
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_physical_wall_source_metadata_shadow import (
    SOURCE_METADATA_DESCRIBED,
    SOURCE_METADATA_UNAVAILABLE,
    build_physical_wall_source_metadata_scope_table,
    unavailable_physical_wall_source_metadata_scope_table,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _segment(
    segment_id: str,
    *,
    x1: float = 0.0,
    y1: float = 0.0,
    x2: float = 100.0,
    y2: float = 0.0,
    width: float = 1.0,
    width_present: bool = True,
    stroke=(0.0, 0.0, 0.0),
    stroke_present: bool = True,
    fill=None,
    fill_present: bool = False,
    layer: str = "",
    layer_present: bool = False,
    dashes: str = "[] 0",
    dashes_present: bool = True,
):
    return {
        "id": segment_id,
        "kind": "line",
        "kind_present": True,
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "width": width,
        "width_present": width_present,
        "stroke": stroke,
        "stroke_present": stroke_present,
        "fill": fill,
        "fill_present": fill_present,
        "layer": layer,
        "layer_present": layer_present,
        "dashes": dashes,
        "dashes_present": dashes_present,
    }


def _record(wall_id: str, source_ids):
    return SimpleNamespace(
        wall_candidate_id=wall_id,
        physical_identity=SimpleNamespace(source_primitive_ids=tuple(source_ids)),
    )


def _table(records, segments):
    return build_physical_wall_source_metadata_scope_table(
        records=records,
        source_segments=segments,
        page_id="1",
        decision_scope_id="wall-source:page-1",
    )


def test_descriptor_uses_existing_presence_and_attribute_status_vocabulary() -> None:
    segments = [
        _segment(
            "a",
            width=0.5,
            layer="A-WALL-EXT",
            layer_present=True,
            dashes="[] 0",
        ),
        _segment(
            "b",
            width=2.0,
            layer="DETAIL",
            layer_present=True,
            dashes="[3 2] 0",
        ),
    ]
    table = _table([_record("wall-a", ("a",)), _record("wall-b", ("b",))], segments)

    assert table.status == SOURCE_METADATA_DESCRIBED
    assert table.distinct_widths_pt == (0.5, 2.0)
    assert table.distinct_layer_values == ("A-WALL-EXT", "DETAIL")
    assert table.wall_named_layer_values == ("A-WALL-EXT",)
    assert table.distinct_dashes_values == ("[3 2] 0", "[] 0")

    left = table.descriptor_for("wall-a")
    right = table.descriptor_for("wall-b")
    assert left is not None and right is not None

    assert left.width_status == "agreed"
    assert left.layer_status == "agreed"
    assert left.dashes_status == "agreed"
    assert left.wall_named_layer_values == ("A-WALL-EXT",)
    assert left.drawing_relative_width_ranks[0].rank_ascending == 1
    assert left.drawing_relative_width_ranks[0].distinct_width_count == 2

    assert right.wall_named_layer_values == ()
    assert right.drawing_relative_width_ranks[0].rank_ascending == 2


def test_explicit_presence_flags_win_over_nonempty_sentinels() -> None:
    segment = _segment(
        "a",
        width=9.0,
        width_present=False,
        layer="A-WALL",
        layer_present=False,
        dashes="[9 9] 0",
        dashes_present=False,
        stroke=(1.0, 0.0, 0.0),
        stroke_present=False,
    )
    descriptor = _table([_record("wall-a", ("a",))], [segment]).descriptors[0]

    assert descriptor.width_status == "unknown"
    assert descriptor.width_values_pt == ()
    assert descriptor.drawing_relative_width_ranks == ()
    assert descriptor.layer_status == "unknown"
    assert descriptor.layer_values == ()
    assert descriptor.wall_named_layer_values == ()
    assert descriptor.dashes_status == "unknown"
    assert descriptor.dashes_values == ()
    assert descriptor.stroke_status == "unknown"
    assert descriptor.stroke_values == ()


def test_plural_source_conflicts_are_described_not_resolved() -> None:
    segments = [
        _segment(
            "a",
            width=0.7,
            layer="A-WALL",
            layer_present=True,
            dashes="[] 0",
        ),
        _segment(
            "b",
            width=2.2,
            layer="GLAZING",
            layer_present=True,
            dashes="[2 2] 0",
        ),
    ]
    descriptor = _table([_record("wall-ab", ("a", "b"))], segments).descriptors[0]

    assert descriptor.width_status == "conflict"
    assert descriptor.width_values_pt == (0.7, 2.2)
    assert descriptor.layer_status == "conflict"
    assert descriptor.layer_values == ("A-WALL", "GLAZING")
    assert descriptor.wall_named_layer_values == ("A-WALL",)
    assert descriptor.dashes_status == "conflict"
    assert descriptor.dashes_values == ("[2 2] 0", "[] 0")


def test_width_rank_is_drawing_relative_not_candidate_only() -> None:
    segments = [
        _segment("candidate", width=2.0),
        _segment("other-thin", width=0.25),
        _segment("other-middle", width=1.0),
    ]
    descriptor = _table([_record("wall", ("candidate",))], segments).descriptors[0]

    assert descriptor.width_values_pt == (2.0,)
    rank = descriptor.drawing_relative_width_ranks[0]
    assert rank.rank_ascending == 3
    assert rank.distinct_width_count == 3


def test_missing_source_primitive_is_reported_without_manufacturing_metadata() -> None:
    descriptor = _table(
        [_record("wall", ("present", "missing"))],
        [_segment("present", width=1.0)],
    ).descriptors[0]

    assert descriptor.source_primitive_ids == ("missing", "present")
    assert descriptor.matched_source_primitive_ids == ("present",)
    assert descriptor.missing_source_primitive_ids == ("missing",)
    assert descriptor.source_record_count == 1
    assert descriptor.width_values_pt == (1.0,)


def test_scope_table_is_input_order_and_coordinate_invariant() -> None:
    records = [_record("z", ("z",)), _record("a", ("a",))]
    segments = [
        _segment("z", x1=100, y1=50, x2=200, y2=50, width=3.0, layer="Z", layer_present=True),
        _segment("a", x1=10, y1=20, x2=90, y2=20, width=1.0, layer="A-WALL", layer_present=True),
    ]
    baseline = _table(records, segments)

    shuffled = _table(list(reversed(records)), list(reversed(segments)))
    assert shuffled == baseline

    translated = [
        dict(segment, x1=segment["x1"] + 137.0, y1=segment["y1"] - 41.0,
             x2=segment["x2"] + 137.0, y2=segment["y2"] - 41.0)
        for segment in segments
    ]
    assert _table(records, translated) == baseline


def test_uniform_width_scaling_preserves_ordinal_rank_pattern() -> None:
    records = [_record("a", ("a",)), _record("b", ("b",))]
    segments = [
        _segment("a", width=0.5),
        _segment("middle", width=1.0),
        _segment("b", width=2.0),
    ]
    scaled = [dict(segment, width=float(segment["width"]) * 10.0) for segment in segments]

    first = _table(records, segments)
    second = _table(records, scaled)

    first_ranks = {
        row.wall_candidate_id: tuple(rank.rank_ascending for rank in row.drawing_relative_width_ranks)
        for row in first.descriptors
    }
    second_ranks = {
        row.wall_candidate_id: tuple(rank.rank_ascending for rank in row.drawing_relative_width_ranks)
        for row in second.descriptors
    }
    assert first_ranks == second_ranks == {"a": (1,), "b": (3,)}


def test_layer_wall_descriptor_is_case_insensitive_substring_only() -> None:
    table = _table(
        [
            _record("a", ("a",)),
            _record("b", ("b",)),
            _record("c", ("c",)),
        ],
        [
            _segment("a", layer="wall", layer_present=True),
            _segment("b", layer="A-WaLl-HATCH", layer_present=True),
            _segment("c", layer="STRUCTURAL", layer_present=True),
        ],
    )
    assert table.wall_named_layer_values == ("A-WaLl-HATCH", "wall")
    assert table.descriptor_for("a").wall_named_layer_values == ("wall",)
    assert table.descriptor_for("b").wall_named_layer_values == ("A-WaLl-HATCH",)
    assert table.descriptor_for("c").wall_named_layer_values == ()


def test_unavailable_scope_table_never_claims_empty_metadata_as_evidence() -> None:
    table = unavailable_physical_wall_source_metadata_scope_table(
        page_id="3",
        decision_scope_id="scope",
        reason_code="synthetic_failure",
    )
    assert table.status == SOURCE_METADATA_UNAVAILABLE
    assert table.reason_code == "synthetic_failure"
    assert table.descriptors == ()
    assert table.distinct_widths_pt == ()
    assert table.descriptor_for("anything") is None


def _pdf_bytes(*, ocg: bool = False) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=320.0, height=240.0)
        layer_xref = doc.add_ocg("A-WALL-TEST", on=True) if ocg else 0
        widths = (0.5, 1.0, 2.0, 3.0)
        for index, width in enumerate(widths):
            y = 50.0 + index * 40.0
            kwargs = {
                "color": (0.0, 0.0, 0.0),
                "width": width,
            }
            if ocg:
                kwargs["oc"] = layer_xref
            if index == 2:
                kwargs["dashes"] = "[3 2] 0"
            page.draw_line((40.0, y), (280.0, y), **kwargs)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _resolve(payload: bytes, *, method: str):
    source = SourceVisibilityProducer(
        producer_method=method,
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="metadata-shadow-source",
        source_bytes=payload,
        source_locator="memory://metadata-shadow-source.pdf",
    )
    authority = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source,
        page_ids=("1",),
    ).authority()
    selector = PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        decision_scope_id="wall-source:page-1",
    )
    return authority.resolve_scope(selector)


def _legacy_surface(result):
    return (
        result.status,
        result.scope_complete,
        result.records,
        result.source_observation_ids,
        result.document_id,
        result.revision_id,
        result.source_sha256,
        result.snapshot_id,
        result.page_id,
        result.decision_scope_id,
        result.reason_codes,
        result.equivalence,
        result.proposition,
        result.scope_kind,
        result.viewport_id,
        result.viewport_bbox,
        result.viewport_view_type,
        result.viewport_status,
        result.viewport_boundary_source,
        result.viewport_producer_fingerprint,
        result.viewport_sibling_set_fingerprint,
        result.scope_boundary_observation_ids,
        result.ambiguous_source_observation_ids,
        result.schema_version,
        result.boundary_evaluation,
    )


def test_shadow_failure_cannot_change_legacy_wall_scope_surface(monkeypatch) -> None:
    payload = _pdf_bytes()
    baseline = _resolve(payload, method="metadata-shadow-failure-containment")
    assert baseline.status is EvidenceResolutionStatus.CORROBORATED
    assert baseline.source_metadata_table is not None
    assert baseline.source_metadata_table.status == SOURCE_METADATA_DESCRIBED

    def boom(**_kwargs):
        raise RuntimeError("synthetic")

    monkeypatch.setattr(
        authority_module,
        "build_physical_wall_source_metadata_scope_table",
        boom,
    )
    degraded = _resolve(payload, method="metadata-shadow-failure-containment")

    assert degraded.source_metadata_table is not None
    assert degraded.source_metadata_table.status == SOURCE_METADATA_UNAVAILABLE
    assert degraded.source_metadata_table.reason_code == "source_metadata_shadow_error:RuntimeError"
    assert _legacy_surface(degraded) == _legacy_surface(baseline)


def test_real_pdf_ocg_mixed_width_and_dash_metadata_reaches_scope_table() -> None:
    result = _resolve(_pdf_bytes(ocg=True), method="metadata-shadow-ocg")

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.records
    table = result.source_metadata_table
    assert table is not None
    assert table.status == SOURCE_METADATA_DESCRIBED
    assert table.candidate_count == len(result.records)

    assert len(table.distinct_widths_pt) >= 4
    for expected in (0.5, 1.0, 2.0, 3.0):
        assert any(abs(value - expected) < 1e-5 for value in table.distinct_widths_pt)

    assert "A-WALL-TEST" in table.distinct_layer_values
    assert "A-WALL-TEST" in table.wall_named_layer_values
    assert any("3" in value and "2" in value for value in table.distinct_dashes_values)
    assert any(
        "A-WALL-TEST" in descriptor.layer_values
        for descriptor in table.descriptors
    )


def test_scope_table_contains_no_support_or_opposition_fields() -> None:
    table = _table([_record("wall", ("a",))], [_segment("a")])
    descriptor = table.descriptors[0]

    forbidden = {
        "support",
        "supports",
        "opposition",
        "oppose",
        "confidence",
        "score",
        "classification",
        "promotion",
        "threshold",
    }
    names = set(vars(table)) | set(vars(descriptor))
    assert not any(any(token in name.lower() for token in forbidden) for name in names)
