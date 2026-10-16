"""Source-only native PDF paint evidence: never create a physical wall."""
from copy import deepcopy
import hashlib

import fitz
import pytest

from tools.diag_gpt2_original_native_ink_vs_w2 import (
    inspect_native_ink_against_w2,
)


def _source(lines):
    doc = fitz.open()
    page = doc.new_page(width=220, height=180)
    for start, end in lines:
        page.draw_line(fitz.Point(*start), fitz.Point(*end), width=0.3)
    original = doc.tobytes()
    ids = tuple(f"d{i}i0" for i in range(len(page.get_drawings())))
    doc.close()
    return original, ids


def _report(original, wall_source_ids, *, edge=((10, 10), (60, 10))):
    sha = hashlib.sha256(original).hexdigest()
    candidates = [{
        "wall_id": f"w{i}",
        "source_primitive_ids": list(ids),
        "source_edge_fragments": [{
            "edge_id": f"split_{i}",
            "geometry": (10, 10, 60, 10),
            "source_primitive_ids": list(ids),
        }],
    } for i, ids in enumerate(wall_source_ids)]
    return {
        "source_sha256": sha, "source_snapshot_preserved": True,
        "new_commercial_quantities": [],
        "scopes": [{
            "source_sha256": sha, "revision_id": "observed-revision",
            "snapshot_id": "observed-snapshot", "page_id": "1",
            "decision_scope_id": "observed-viewport",
            "w4_scope_complete": False, "source_room_face_record_count": 0,
            "competing_source_edges": [{
                "face_id": "unresolved-face",
                "competing_planar_edge": edge,
                "candidate_walls": candidates,
            }],
        }],
    }


def _status(value):
    return value["scopes"][0]["edges"][0]["indexed_native_ink_status"]


def test_two_real_original_native_ink_owners_do_not_elect_a_wall():
    original, ids = _source([
        ((10, 10), (60, 10)), ((10, 10), (60, 10))
    ])
    report = _report(original, ((ids[0],), (ids[1],)))
    before = deepcopy(report)
    out = inspect_native_ink_against_w2(report, original)
    assert _status(out) == "original_pdf_distinct_w4_candidates_have_native_ink"
    assert report == before
    assert out["native_ink_independently_read_from_source_pdf"]
    assert out["new_commercial_quantities"] == []
    assert not out["physical_wall_or_room_authority_granted"]
    assert not out["frozen_benchmark_scored"]


def test_shared_original_native_path_across_w4_candidates_is_not_two_walls():
    original, ids = _source([((10, 10), (60, 10))])
    # The same original native item survives in two W4 graph candidates.
    out = inspect_native_ink_against_w2(
        _report(original, ((ids[0],), (ids[0],))), original,
    )
    e, = out["scopes"][0]["edges"]
    assert e["indexed_native_ink_status"] == "original_pdf_w4_candidates_share_same_native_ink"
    assert e["shared_original_native_source_ids"] == [ids[0]]
    assert len(e["w4_candidate_original_ink_evidence"]) == 2
    assert all(not c["physical_wall_equivalence_granted"]
               for c in e["w4_candidate_original_ink_evidence"])
    assert not e["source_room_boundary_closed"]


def test_orthogonal_original_ink_is_not_horizontal_span_witness():
    original, ids = _source([
        ((10, 10), (60, 10)), ((20, 5), (20, 70))
    ])
    out = inspect_native_ink_against_w2(
        _report(original, ((ids[0],), (ids[1],))), original,
    )
    assert _status(out) == "original_pdf_one_w4_candidate_has_native_ink"
    candidates = out["scopes"][0]["edges"][0]["w4_candidate_original_ink_evidence"]
    assert candidates[0]["direct_indexed_native_ink_witness"] is True
    assert candidates[1]["direct_indexed_native_ink_witness"] is False


def test_actual_gap_cannot_be_infilled_by_snapped_edges():
    original, ids = _source([
        ((10, 10), (30, 10)), ((31, 10), (60, 10))
    ])
    out = inspect_native_ink_against_w2(
        _report(original, ((ids[0],), (ids[1],)),
                edge=((29, 10), (32, 10))), original,
    )
    assert _status(out) == "original_pdf_no_indexed_candidate_native_ink_span"
    assert not out["scopes"][0]["edges"][0]["source_room_boundary_closed"]


def test_original_native_ink_witness_survives_where_w2_splits_drop_edge():
    original, ids = _source([
        ((10, 10), (60, 10)), ((20, 5), (20, 70))
    ])
    report = _report(original, ((ids[0],), (ids[1],)),
                     edge=((29, 10), (40, 10)))
    # Original source item really crosses 29..40, but surviving W2 split
    # fragment on that candidate ends at 30. This is source-vs-W2 LOSS,
    # not permission to invent a wall or alter the original source.
    report["scopes"][0]["competing_source_edges"][0]["candidate_walls"][0][
        "source_edge_fragments"
    ][0]["geometry"] = (10, 10, 30, 10)
    report["scopes"][0]["competing_source_edges"][0]["candidate_walls"][1][
        "source_edge_fragments"
    ][0]["geometry"] = (20, 5, 20, 70)
    result = inspect_native_ink_against_w2(report, original)
    a, b = result["scopes"][0]["edges"][0]["w4_candidate_original_ink_evidence"]
    assert a["direct_indexed_native_ink_witness"] is True
    assert a["same_edge_surviving_w2_full_span_supported"] is False
    assert a["first_source_vs_w2_divergence"] == (
        "original_native_ink_spans_edge_but_surviving_w2_does_not"
    )
    assert b["direct_indexed_native_ink_witness"] is False
    assert b["same_edge_surviving_w2_full_span_supported"] is False
    assert b["first_source_vs_w2_divergence"] == "source_and_surviving_w2_span_agree"
    assert not result["physical_wall_or_room_authority_granted"]


def test_missing_native_source_id_causes_unavailable_not_false():
    original, ids = _source([((10, 10), (60, 10))])
    out = inspect_native_ink_against_w2(
        _report(original, ((ids[0],), ("d987654i0",))), original,
    )
    assert _status(out) == "original_pdf_native_ink_unavailable"
    row = out["scopes"][0]["edges"][0]["w4_candidate_original_ink_evidence"][1]
    assert row["direct_indexed_native_ink_witness"] is None


@pytest.mark.parametrize("transform", [
    lambda x, y: (x + 20, y + 15),
    lambda x, y: (150 - y, x + 20),
    lambda x, y: (2 * x, 2 * y),
])
def test_page_point_translation_rotation_scale_invariant(transform):
    a, b = transform(10, 10), transform(60, 10)
    original, ids = _source([(a, b), (transform(5, 60), transform(90, 70))])
    out = inspect_native_ink_against_w2(
        _report(original, ((ids[0],), (ids[1],)), edge=(a, b)), original,
    )
    assert _status(out) == "original_pdf_one_w4_candidate_has_native_ink"


def test_borrowed_source_pdf_and_replayed_scope_fail_closed():
    original, ids = _source([((10, 10), (60, 10))])
    report = _report(original, ((ids[0],), ("d9999i0",)))
    with pytest.raises(ValueError, match="source_sha_mismatch"):
        inspect_native_ink_against_w2(report, original + b"foreign")
    report["scopes"].append(deepcopy(report["scopes"][0]))
    with pytest.raises(ValueError, match="original_source_scope_replayed"):
        inspect_native_ink_against_w2(report, original)


def test_deterministic_repeated_read_and_candidate_order():
    original, ids = _source([
        ((10, 10), (60, 10)), ((20, 5), (20, 70)),
    ])
    report = _report(original, ((ids[0],), (ids[1],)))
    one = inspect_native_ink_against_w2(report, original)
    swapped = deepcopy(report)
    swapped["scopes"][0]["competing_source_edges"][0]["candidate_walls"].reverse()
    two = inspect_native_ink_against_w2(swapped, original)
    assert one == two
