"""Original-source counterpart receipts cannot mint physical second faces."""
from types import SimpleNamespace as N
from tools.diag_gpt2_abstained_face_counterparts import (
    inspect_unpublished_source_face_counterparts as audit,
)

ATOM = ((2., 0.), (8., 0.))


def face(name, *, edges=(), reason=None, polygon=()):
    return N(
        face_id=name,
        boundary_wall_edges=edges,
        reason=reason,
        polygon_pdf_pts=polygon,
    )


def test_original_published_and_withheld_source_are_not_second_side_proof():
    prior = face("face-original", edges=(("wall-A", ((0., 0.), (10., 0.))),))
    withheld = face(
        "face-withheld",
        edges=(("wall-A", ((0., 0.), (10., 0.))),),
        reason="source_face_wall_owner_ambiguous",
    )
    r = audit(
        N(records=(prior,), abstained_faces=(withheld,)),
        wall_id="wall-A", atomic_edge=ATOM,
        known_component_face_ids=("face-original",),
    )
    assert r["status"] == "original_face_source_candidates_only"
    assert r["matching_original_face_count"] == 2
    assert r["matching_withheld_face_receipts"][0]["withheld_reason"] == (
        "source_face_wall_owner_ambiguous"
    )
    assert r["second_physical_source_face_authenticated"] is False
    assert r["candidate_only_no_second_side_authority"] is True


def test_only_exact_original_wall_subedge_matches():
    r = audit(
        N(records=(face("other", edges=(("wall-B", ATOM),)),),
          abstained_faces=()),
        wall_id="wall-A", atomic_edge=ATOM,
    )
    assert r["matching_original_face_count"] == 0


def test_abstained_polygon_overlap_cannot_invent_wall_owner():
    other = face(
        "no-wall-receipt", reason="unknown_boundary",
        polygon=((0., 0.), (10., 0.), (10., 10.), (0., 10.)),
    )
    r = audit(
        N(records=(), abstained_faces=(other,)),
        wall_id="wall-A", atomic_edge=ATOM,
    )
    assert r["matching_withheld_face_receipts"] == []
    assert r["matching_withheld_polygon_geometry_only"][0][
        "no_authenticated_w4_owner_or_second_face"
    ]
    assert r["second_physical_source_face_authenticated"] is False


def test_conflicting_duplicate_original_face_id_fails_closed():
    a = face("same", edges=(("wall-A", ATOM),))
    r = audit(
        N(records=(a,), abstained_faces=(a,)),
        wall_id="wall-A", atomic_edge=ATOM,
    )
    assert r["status"] == "ambiguous_original_source_face_identity"
    assert not r["matching_published_face_receipts"]


def test_invalid_source_face_receipt_reports_negative():
    bad = face("bad", edges=(("wall-A", ((float("nan"), 0.), (10., 0.))),))
    r = audit(
        N(records=(), abstained_faces=(bad,)),
        wall_id="wall-A", atomic_edge=ATOM,
    )
    assert r["rejected_source_receipt_count"] == 1
    assert not r["all_matching_receipts_observed"]
    assert r["second_physical_source_face_authenticated"] is False


def test_oversize_and_invalid_query_are_not_complete():
    many = tuple(face(f"f{i}") for i in range(5001))
    r = audit(
        N(records=many, abstained_faces=()),
        wall_id="wall-A", atomic_edge=ATOM,
    )
    assert r["status"] == "face_source_universe_safety_bound"
    r = audit(
        N(records=(), abstained_faces=()),
        wall_id="wall-A", atomic_edge=((0., 0.), (0., 0.)),
    )
    assert r["status"] == "invalid_source_query"
