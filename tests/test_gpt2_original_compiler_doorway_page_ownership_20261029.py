"""GPT2 compiler original doorway ring page-pair source provenance.

These inspect a seam against stubbed *already-decoded* producer coverage;
they are not original PDF evidence and do not promote W4/FT/FIRM.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import pb_gpt2_original_source_geometry_bridge as compiler
from pb_gpt2_original_source_geometry_bridge import GPT2OriginalSourceGeometryBridge


SOURCE_SHA = "a" * 64


def _ring(page=7, *, status="source_jamb_bound_open_door_perimeter_candidate_only"):
    dx = 0 if page == 7 else 10
    return {
        "status": status,
        "original_source_sha256": SOURCE_SHA,
        "original_page_1_based": page,
        "original_source_perimeter_side_ids": ("d0i0", "d1i0", "d2i0"),
        "source_ink_ring_with_explicit_virtual_door_gap_pdf_pts": (
            (dx, 0), (dx, 100), (dx + 100, 100), (dx + 100, 0),
        ),
        "source_virtual_door_connector_pdf_pts": (
            (dx + 100, 0), (dx, 0),
        ),
        "source_only_native_polygon_area_pdf_pt2_not_m2": 10000.0,
        "source_jamb_roles_same_sha_rechecked": True,
        "source_wall_and_jamb_geometry_independently_recomputed": True,
    }


def _graph(page=7):
    dx = 0 if page == 7 else 10
    points = ((dx, 0), (dx, 100), (dx + 100, 100), (dx + 100, 0))
    return {
        "source_sha256": SOURCE_SHA,
        "page_1_based": page,
        "original_native_edge_ids": ("d0i0", "d1i0", "d2i0"),
        "original_native_edges": tuple(
            {"source_id": f"d{i}i0", "endpoints_pdf_pts": (points[i], points[i + 1])}
            for i in range(3)
        ),
        "native_components": ({
            "source_simple_ring_candidate": None,
            "native_endpoint_degrees": tuple(
                {"point_pdf_pt": p, "degree": 1 if i in (0, 3) else 2,
                 "original_source_edge_ids": (
                     (f"d{i}i0",) if i == 0 else
                     (f"d{i-1}i0",) if i == len(points) - 1 else
                     (f"d{i-1}i0", f"d{i}i0")
                 )}
                for i, p in enumerate(points)
            ),
        },),
        "interior_stroke_intersections_and_overlaps": (),
    }


def _invoke(monkeypatch, *, floor_page=7, finish_page=11,
            floor=None, finish=None):
    calls=[]
    def decoded_source(self, revision_id, *, page_1_based):
        calls.append(("decoded",page_1_based))
        assert revision_id=="original-rev"
        return SimpleNamespace(
            revision=SimpleNamespace(
                source_sha256=SOURCE_SHA,
                document_id="source-doc",
            ),
            snapshot=SimpleNamespace(snapshot_id="original-snapshot"),
        ), b"already-sealed-source-private-bytes"

    def candidate_registration(*args, **kwargs):
        calls.append(("source-geometric-issuer",))
        return {
            "status":"original_source_ink_ring_translation_candidate",
            "original_source_sha256":SOURCE_SHA,
            "new_firm_quantities":0,
        }

    def candidate_material(*args, **kwargs):
        calls.append(("source-material-issuer",))
        return {"status":"source_finished_floor_material_handoff_abstained",
                "new_firm_quantities":0}

    monkeypatch.setattr(
        GPT2OriginalSourceGeometryBridge,"_source_revision",decoded_source)
    def native_graph(self, *, revision_id, page_1_based, original_source_edge_ids):
        calls.append(("native-graph", page_1_based))
        assert revision_id == "original-rev"
        # The independent graph remains the original; forged caller IDs
        # must be rejected by the compiler rather than by this test stub.
        return _graph(page_1_based)

    monkeypatch.setattr(
        GPT2OriginalSourceGeometryBridge, "original_room_ink_graph", native_graph)
    monkeypatch.setattr(
        compiler,"audit_gpt2_original_doorway_bound_floor_finish_correspondence",
        candidate_registration)
    monkeypatch.setattr(
        compiler,"audit_gpt2_source_material_floor_handoff",candidate_material)
    bridge=object.__new__(GPT2OriginalSourceGeometryBridge)
    def run():
        return bridge.original_doorway_bound_floor_finish_handoff(
            revision_id="original-rev",
            floor_page_1_based=floor_page,
            finish_page_1_based=finish_page,
            original_floor_doorway_ring=_ring(7) if floor is None else floor,
            original_finish_doorway_ring=_ring(11) if finish is None else finish,
            independent_cross_sheet_registration={},
            original_translation_pdf_pts=(10.0,0.0),
            material_authority=None,
            source_definition_selector=None,
            source_occurrence_selector=None,
            source_finish_code="FT3",
        )
    return run,calls


@pytest.mark.parametrize("bad",[
    _ring(8), _ring(11), _ring("7"), _ring(True),
    _ring(7,status="caller-falsified-w4"), {"original_page_1_based":7},
    {"status":"source_jamb_bound_open_door_perimeter_candidate_only"},
    [],
])
def test_wrong_original_floor_page_or_missing_native_receipt_never_enters_issuer(
    monkeypatch,bad,
):
    run,calls=_invoke(monkeypatch,floor=bad)
    with pytest.raises(ValueError,match="original_source_doorway_compiler_page_receipt_conflict"):
        run()
    assert all(name[0]=="decoded" for name in calls)


@pytest.mark.parametrize("bad_sha",[None, "", "0" * 64, True, 1])
def test_matching_native_page_with_missing_or_forged_source_root_abstains_at_root_gate(
    monkeypatch, bad_sha,
):
    # A valid typed page/status reaches the separate immutable SHA gate;
    # this is not a page-receipt failure and must never call either issuer.
    floor = _ring(7)
    floor["original_source_sha256"] = bad_sha
    run, calls = _invoke(monkeypatch, floor=floor)
    with pytest.raises(
        ValueError, match="original_source_doorway_handoff_revision_root_conflict"
    ):
        run()
    assert calls == [("decoded", 7), ("decoded", 11)]


@pytest.mark.parametrize("bad",[
    _ring(7), _ring(12), _ring("11"), _ring(False),
    _ring(11,status="wrong-original-source-issuer"),
    {"status":"source_jamb_bound_open_door_perimeter_candidate_only",
     "original_page_1_based":11.0},
])
def test_wrong_original_finish_page_never_enters_issuer(monkeypatch,bad):
    run,calls=_invoke(monkeypatch,finish=bad)
    with pytest.raises(ValueError,match="original_source_doorway_compiler_page_receipt_conflict"):
        run()
    assert all(name[0]=="decoded" for name in calls)


def test_same_original_floor_and_finish_page_never_elects_correspondence(monkeypatch):
    run,calls=_invoke(monkeypatch,finish_page=7,finish=_ring(7))
    with pytest.raises(ValueError,match="original_source_doorway_distinct_pages_required"):
        run()
    assert all(name[0]=="decoded" for name in calls)


def test_valid_original_page_pair_reaches_source_only_issuers_but_never_firm(monkeypatch):
    run,calls=_invoke(monkeypatch)
    outcome=run()
    assert calls==[
        ("decoded",7),
        ("decoded",11),
        ("native-graph",7),
        ("native-graph",11),
        ("source-geometric-issuer",),
        ("source-material-issuer",),
    ]
    assert outcome["status"]=="original_source_doorway_bound_floor_finish_shadow_only"
    assert outcome["new_firm_quantities"]==0
    assert outcome["customer_floor_finish_area_issued"] is False
    assert outcome["source_virtual_door_connectors_are_structural"] is False
    assert outcome["original_source_sha256"]==SOURCE_SHA


@pytest.mark.parametrize("field, replacement", [
    ("source_jamb_roles_same_sha_rechecked", "yes"),
    ("source_wall_and_jamb_geometry_independently_recomputed", 1),
    ("original_source_perimeter_side_ids", ("d0i0", "d0i0", "d2i0")),
    ("original_source_perimeter_side_ids", ("d0i0", "d1i0", "d999i0")),
    ("source_ink_ring_with_explicit_virtual_door_gap_pdf_pts",
     ((0, 0), (0, 100), (100, 101), (100, 0))),
    ("source_virtual_door_connector_pdf_pts", ((100, 0), (1, 0))),
    ("source_only_native_polygon_area_pdf_pt2_not_m2", 12345.0),
    ("source_only_native_polygon_area_pdf_pt2_not_m2", 10**1000),
])
def test_copied_sha_page_cannot_bypass_reissued_original_native_perimeter(
    monkeypatch, field, replacement,
):
    forged = _ring(7)
    forged[field] = replacement
    run, calls = _invoke(monkeypatch, floor=forged)
    with pytest.raises(
        ValueError, match="original_source_doorway_compiler_native_perimeter_receipt_conflict"
    ):
        run()
    assert not any(name[0].endswith("issuer") for name in calls)


def test_original_graph_with_competing_open_perimeters_cannot_be_silently_selected(
    monkeypatch,
):
    run, calls = _invoke(monkeypatch)
    def competing_graph(self, *, revision_id, page_1_based, original_source_edge_ids):
        calls.append(("native-graph", page_1_based))
        graph = _graph(page_1_based)
        graph["native_components"] = (
            graph["native_components"][0], graph["native_components"][0]
        )
        return graph
    monkeypatch.setattr(
        GPT2OriginalSourceGeometryBridge, "original_room_ink_graph", competing_graph
    )
    with pytest.raises(
        ValueError, match="original_source_doorway_compiler_native_perimeter_receipt_conflict"
    ):
        run()
    assert not any(name[0].endswith("issuer") for name in calls)


def test_native_source_graph_exception_is_typed_compiler_abstention(monkeypatch):
    run, calls = _invoke(monkeypatch)
    def unavailable_graph(self, *, revision_id, page_1_based, original_source_edge_ids):
        raise ValueError("original_graph_nonorthogonal_or_zero_source_edge")
    monkeypatch.setattr(
        GPT2OriginalSourceGeometryBridge, "original_room_ink_graph", unavailable_graph
    )
    with pytest.raises(
        ValueError, match="original_source_doorway_compiler_native_perimeter_receipt_conflict"
    ):
        run()
    assert not any(name[0].endswith("issuer") for name in calls)


def test_real_generated_native_pdf_edges_are_reissued_before_compiler_candidate(
    monkeypatch,
):
    # A generated two-page PDF exercises the actual SHA/page-native graph
    # issuer; the source producer itself remains stubbed, and the result is
    # still a shadow-only candidate rather than original-client authority.
    import hashlib
    import fitz

    doc = fitz.open()
    for dx in (0, 10):
        page = doc.new_page(width=300, height=300)
        page.draw_line((40 + dx, 40), (40 + dx, 140))
        page.draw_line((40 + dx, 140), (140 + dx, 140))
        page.draw_line((140 + dx, 140), (140 + dx, 40))
    raw = doc.tobytes()
    doc.close()
    sha = hashlib.sha256(raw).hexdigest()
    floor = _ring(7)
    finish = _ring(11)
    for row, page in ((floor, 1), (finish, 2)):
        row["original_source_sha256"] = sha
        row["original_page_1_based"] = page
        dx = 0 if page == 1 else 10
        row["source_ink_ring_with_explicit_virtual_door_gap_pdf_pts"] = (
            (40 + dx, 40), (40 + dx, 140),
            (140 + dx, 140), (140 + dx, 40),
        )
        row["source_virtual_door_connector_pdf_pts"] = (
            (140 + dx, 40), (40 + dx, 40),
        )

    def sealed_revision(self, revision_id, *, page_1_based):
        assert revision_id == "native-test-rev"
        assert page_1_based in (1, 2)
        return SimpleNamespace(
            revision=SimpleNamespace(source_sha256=sha, document_id="native-test"),
            snapshot=SimpleNamespace(snapshot_id="native-snapshot"),
        ), raw

    calls = []
    monkeypatch.setattr(
        GPT2OriginalSourceGeometryBridge, "_source_revision", sealed_revision
    )
    monkeypatch.setattr(
        compiler, "audit_gpt2_original_doorway_bound_floor_finish_correspondence",
        lambda *args, **kwargs: calls.append("source-geometry") or
        {"status": "original_source_ink_ring_translation_candidate"},
    )
    monkeypatch.setattr(
        compiler, "audit_gpt2_source_material_floor_handoff",
        lambda *args, **kwargs: calls.append("source-material") or
        {"status": "source_finished_floor_material_handoff_abstained"},
    )
    bridge = object.__new__(GPT2OriginalSourceGeometryBridge)
    result = bridge.original_doorway_bound_floor_finish_handoff(
        revision_id="native-test-rev",
        floor_page_1_based=1,
        finish_page_1_based=2,
        original_floor_doorway_ring=floor,
        original_finish_doorway_ring=finish,
        independent_cross_sheet_registration={},
        original_translation_pdf_pts=(10.0, 0.0),
        material_authority=None,
        source_definition_selector=None,
        source_occurrence_selector=None,
        source_finish_code="FT3",
    )
    assert calls == ["source-geometry", "source-material"]
    assert result["new_firm_quantities"] == 0
    assert result["customer_floor_finish_area_issued"] is False
    assert hashlib.sha256(raw).hexdigest() == sha


def test_large_native_perimeter_id_membership_is_exact_and_fail_closed():
    # Source-neutral complexity regression: the full edge universe must be
    # checked without choosing an edge, and unhashable foreign IDs ABSTAIN.
    # This is NOT an original drawing, source-positive or commercial test.
    count = 512
    # The virtual closing connector must not cross the native perimeter.
    # The former diagonal staircase crossed its own connector, correctly
    # failing the new intersection veto rather than testing ID membership.
    # Keep 1,024 distinct edges but place the chain above its connector;
    # its last edge descends to the sole second doorway endpoint.
    points = [(0, 0)]
    height = count * 4
    for i in range(count):
        points.extend(((i + 1, height),
                       (i + 1, height + 1 if i < count - 1 else height - 1)))
    ids = tuple(f"d{i}i0" for i in range(2 * count))
    edges = tuple(
        {"source_id": ident,
         "endpoints_pdf_pts": (points[i], points[i + 1])}
        for i, ident in enumerate(ids)
    )
    area = abs(sum(
        a[0] * b[1] - b[0] * a[1]
        for a, b in zip(points, points[1:] + points[:1])
    )) / 2
    assert area > 0
    ring = {
        "original_source_sha256": SOURCE_SHA,
        "original_page_1_based": 7,
        "original_source_perimeter_side_ids": ids,
        "source_ink_ring_with_explicit_virtual_door_gap_pdf_pts": tuple(points),
        "source_virtual_door_connector_pdf_pts": (points[-1], points[0]),
        "source_only_native_polygon_area_pdf_pt2_not_m2": area,
        "source_jamb_roles_same_sha_rechecked": True,
        "source_wall_and_jamb_geometry_independently_recomputed": True,
    }
    graph = {
        "source_sha256": SOURCE_SHA,
        "page_1_based": 7,
        "original_native_edge_ids": tuple(sorted(ids)),
        "original_native_edges": edges,
        "native_components": ({
            "source_simple_ring_candidate": None,
            "native_endpoint_degrees": tuple(
                {"point_pdf_pt": point,
                 "degree": 1 if i in (0, len(points) - 1) else 2,
                 "original_source_edge_ids": (
                     (ids[i],) if i == 0 else
                     (ids[i-1],) if i == len(points) - 1 else
                     (ids[i-1], ids[i])
                 )}
                for i, point in enumerate(points)
            ),
        },),
        "interior_stroke_intersections_and_overlaps": (),
    }
    assert compiler._original_doorway_ring_matches_reissued_native_graph(
        ring, graph
    )
    for foreign_id in ("d999999i0", ["d0i0"], None):
        corrupted = dict(graph)
        corrupted_edges = list(edges)
        corrupted_edges[count] = {
            **corrupted_edges[count], "source_id": foreign_id
        }
        corrupted["original_native_edges"] = tuple(corrupted_edges)
        assert not compiler._original_doorway_ring_matches_reissued_native_graph(
            ring, corrupted
        )
    # No producer-owned receipt is mutated by the validation.
    assert graph["original_native_edges"] == edges
    assert ring["original_source_perimeter_side_ids"] == ids


@pytest.mark.parametrize("corruption", [
    "missing_interior", "duplicated_interior", "foreign_vertex",
    "false_interior_degree", "wrong_incident_source", "duplicate_source_owner",
    "missing_incident_source_ids",
])
def test_reissued_original_graph_requires_complete_native_endpoint_owners(corruption):
    # The independent graph's degree table must account for every native
    # endpoint AND every incident source edge; two open ends are insufficient.
    # No forged/malformed graph may reach the source-only geometry issuer.
    ring = _ring(7)
    graph = _graph(7)
    component = dict(graph["native_components"][0])
    rows = [dict(row) for row in component["native_endpoint_degrees"]]
    if corruption == "missing_interior":
        rows.pop(1)
    elif corruption == "duplicated_interior":
        rows.append(dict(rows[1]))
    elif corruption == "foreign_vertex":
        rows[1]["point_pdf_pt"] = (200, 200)
    elif corruption == "false_interior_degree":
        rows[1]["degree"] = 1
        rows[1]["original_source_edge_ids"] = ("d0i0",)
    elif corruption == "wrong_incident_source":
        rows[1]["original_source_edge_ids"] = ("d0i0", "d2i0")
    elif corruption == "duplicate_source_owner":
        rows[1]["original_source_edge_ids"] = ("d0i0", "d0i0")
    else:
        del rows[1]["original_source_edge_ids"]
    component["native_endpoint_degrees"] = tuple(rows)
    graph["native_components"] = (component,)
    assert not compiler._original_doorway_ring_matches_reissued_native_graph(
        ring, graph
    )
    # The genuine native edge and caller-ring inputs were not modified.
    assert ring == _ring(7)
    assert graph["original_native_edges"] == _graph(7)["original_native_edges"]


def test_native_endpoint_owner_receipt_is_order_independent():
    # Owner order is not physical evidence: a complete, differently ordered
    # native receipt remains a candidate, never a commercial quantity.
    ring = _ring(7)
    graph = _graph(7)
    component = dict(graph["native_components"][0])
    component["native_endpoint_degrees"] = tuple(
        {**row, "original_source_edge_ids": tuple(reversed(row["original_source_edge_ids"]))}
        for row in reversed(component["native_endpoint_degrees"])
    )
    graph["native_components"] = (component,)
    assert compiler._original_doorway_ring_matches_reissued_native_graph(ring, graph)


@pytest.mark.parametrize(
    "malformed_census",
    [None, False, 0, "", [], {}, [{"source_id": "d0i0"}]],
)
def test_native_overlap_census_must_be_explicit_and_complete(malformed_census):
    """A missing or untyped census cannot certify an unobstructed source ring."""
    graph = _graph()
    graph["interior_stroke_intersections_and_overlaps"] = malformed_census
    assert not compiler._original_doorway_ring_matches_reissued_native_graph(
        _ring(), graph
    )


def test_native_overlap_census_missing_field_and_component_proof_abstain():
    graph = _graph()
    assert compiler._original_doorway_ring_matches_reissued_native_graph(
        _ring(), graph
    )
    missing_census = {key: value for key, value in graph.items()
                      if key != "interior_stroke_intersections_and_overlaps"}
    assert not compiler._original_doorway_ring_matches_reissued_native_graph(
        _ring(), missing_census
    )
    missing_ring_field = dict(graph)
    component = dict(graph["native_components"][0])
    component.pop("source_simple_ring_candidate")
    missing_ring_field["native_components"] = (component,)
    assert not compiler._original_doorway_ring_matches_reissued_native_graph(
        _ring(), missing_ring_field
    )
    # The actual native producer's complete, explicitly empty tuple is valid.
    assert graph["interior_stroke_intersections_and_overlaps"] == ()
    assert graph["native_components"][0]["source_simple_ring_candidate"] is None
    assert compiler._original_doorway_ring_matches_reissued_native_graph(
        _ring(), graph
    )


@pytest.mark.parametrize("axis", ("x", "y"))
@pytest.mark.parametrize("sign", (-1, 1))
def test_oversized_float_native_doorway_graph_endpoint_abstains(axis, sign):
    """Matching reissued edges cannot authenticate imprecise PDF coordinates.

    The caller's ring and the independent native graph deliberately agree
    on an oversized float; agreement is not source endpoint identity.
    """
    assert compiler._original_doorway_ring_matches_reissued_native_graph(
        _ring(), _graph()
    )
    ring = _ring()
    graph = _graph()
    huge = float(sign * (2**53 + 2))

    def transformed(point):
        x, y = point
        return (
            huge if axis == "x" and x == 100 else x,
            huge if axis == "y" and y == 100 else y,
        )

    ring["source_ink_ring_with_explicit_virtual_door_gap_pdf_pts"] = tuple(
        transformed(p) for p in ring["source_ink_ring_with_explicit_virtual_door_gap_pdf_pts"]
    )
    ring["source_virtual_door_connector_pdf_pts"] = tuple(
        transformed(p) for p in ring["source_virtual_door_connector_pdf_pts"]
    )
    ring["source_only_native_polygon_area_pdf_pt2_not_m2"] = abs(huge) * 100.0
    graph["original_native_edges"] = tuple(
        {
            **edge,
            "endpoints_pdf_pts": tuple(
                transformed(p) for p in edge["endpoints_pdf_pts"]
            ),
        }
        for edge in graph["original_native_edges"]
    )
    graph["native_components"] = tuple(
        {
            **component,
            "native_endpoint_degrees": tuple(
                {**row, "point_pdf_pt": transformed(row["point_pdf_pt"])}
                for row in component["native_endpoint_degrees"]
            ),
        }
        for component in graph["native_components"]
    )
    assert not compiler._original_doorway_ring_matches_reissued_native_graph(
        ring, graph
    )


@pytest.mark.parametrize(
    "bad_root",
    [None, "", "A" * 64, "g" * 64, True, 1, 10 ** 1000],
)
def test_native_graph_verifier_rejects_matching_but_untrusted_source_roots(bad_root):
    """Two equally malformed SHA receipts cannot authenticate original ink."""
    ring, graph = _ring(7), _graph(7)
    ring["original_source_sha256"] = bad_root
    graph["source_sha256"] = bad_root
    assert compiler._original_doorway_ring_matches_reissued_native_graph(ring, graph) is False
    assert _ring(7)["original_source_sha256"] == SOURCE_SHA


@pytest.mark.parametrize(
    "bad_page",
    [None, False, True, 7.0, "7", "", 0, -7, 2**53 + 1, 10 ** 1000],
)
def test_native_graph_verifier_rejects_matching_but_aliased_source_pages(bad_page):
    """Native page identity is a literal positive integer, not numeric equality."""
    ring, graph = _ring(7), _graph(7)
    ring["original_page_1_based"] = bad_page
    graph["page_1_based"] = bad_page
    assert compiler._original_doorway_ring_matches_reissued_native_graph(ring, graph) is False



def test_native_graph_verifier_rejects_oversized_matching_page_roots_without_mutation():
    """Both equally impossible original-page roots must abstain without side effects."""
    ring, graph = _ring(7), _graph(7)
    ring["original_page_1_based"] = 2**53 + 1
    graph["page_1_based"] = 2**53 + 1
    before_ring, before_graph = repr(ring), repr(graph)
    assert compiler._original_doorway_ring_matches_reissued_native_graph(ring, graph) is False
    assert repr(ring) == before_ring
    assert repr(graph) == before_graph
    assert "new_firm_quantities" not in ring
    assert "customer_floor_finish_area_issued" not in graph

def test_native_graph_verifier_keeps_complete_original_root_positive_and_no_quantity():
    ring, graph = _ring(7), _graph(7)
    ring_before, graph_before = repr(ring), repr(graph)
    assert compiler._original_doorway_ring_matches_reissued_native_graph(ring, graph) is True
    assert repr(ring) == ring_before
    assert repr(graph) == graph_before
    assert "new_firm_quantities" not in graph
    assert "customer_floor_finish_area_issued" not in graph


def _native_chain_receipts_for_virtual_connector(points, *, reverse_rows=False):
    """Source-neutral open native chain, with an independently stated census."""
    ids = tuple(f"d{i}i0" for i in range(len(points) - 1))
    ring = _ring()
    ring["original_source_perimeter_side_ids"] = ids
    ring["source_ink_ring_with_explicit_virtual_door_gap_pdf_pts"] = points
    ring["source_virtual_door_connector_pdf_pts"] = (points[-1], points[0])
    ring["source_only_native_polygon_area_pdf_pt2_not_m2"] = abs(sum(
        a[0] * b[1] - b[0] * a[1]
        for a, b in zip(points, points[1:] + points[:1])
    )) / 2.0
    edges = tuple(
        {"source_id": ids[i], "endpoints_pdf_pts": (points[i], points[i + 1])}
        for i in range(len(ids))
    )
    degrees = tuple(
        {"point_pdf_pt": p,
         "degree": 1 if i in (0, len(points) - 1) else 2,
         "original_source_edge_ids": (
             (ids[0],) if i == 0 else
             (ids[-1],) if i == len(points) - 1 else
             (ids[i - 1], ids[i])
         )}
        for i, p in enumerate(points)
    )
    graph = _graph()
    graph["original_native_edge_ids"] = ids
    graph["original_native_edges"] = edges[::-1] if reverse_rows else edges
    graph["native_components"] = ({
        "source_simple_ring_candidate": None,
        "native_endpoint_degrees": degrees[::-1] if reverse_rows else degrees,
    },)
    graph["interior_stroke_intersections_and_overlaps"] = ()
    return ring, graph


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("translation", [(0, 0), (400, -700)])
@pytest.mark.parametrize("reverse_rows", [False, True])
def test_virtual_door_connector_crossing_native_walls_abstains_without_mutation(
    reverse, translation, reverse_rows,
):
    from copy import deepcopy

    # Every native edge forms a simple open orthogonal chain; the native
    # intersection census is empty and the virtual shoelace area is positive.
    # But closing last->first crosses THREE nonadjacent native wall strokes.
    points = (
        (0, 0), (0, -9), (12, -9), (12, -21),
        (4, -21), (4, -28), (6, -28), (6, -36),
    )
    if reverse:
        points = points[::-1]
    points = tuple((x + translation[0], y + translation[1]) for x, y in points)
    ring, graph = _native_chain_receipts_for_virtual_connector(
        points, reverse_rows=reverse_rows,
    )
    before = deepcopy((ring, graph))
    assert ring["source_only_native_polygon_area_pdf_pt2_not_m2"] > 0
    assert not compiler._original_doorway_ring_matches_reissued_native_graph(
        ring, graph,
    )
    assert (ring, graph) == before
    assert "new_firm_quantities" not in ring


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("translation", [(0, 0), (400, -700)])
@pytest.mark.parametrize("reverse_rows", [False, True])
def test_virtual_door_connector_preserves_uncrossed_native_chain_candidate(
    reverse, translation, reverse_rows,
):
    from copy import deepcopy

    # A split, genuine open wall chain has a single virtual doorway gap;
    # this negative-only guard must not reject its source-geometry candidate.
    points = ((0, 0), (0, 100), (50, 100), (100, 100), (100, 0))
    if reverse:
        points = points[::-1]
    points = tuple((x + translation[0], y + translation[1]) for x, y in points)
    ring, graph = _native_chain_receipts_for_virtual_connector(
        points, reverse_rows=reverse_rows,
    )
    before = deepcopy((ring, graph))
    assert compiler._original_doorway_ring_matches_reissued_native_graph(
        ring, graph,
    )
    assert (ring, graph) == before
    assert "new_firm_quantities" not in ring


def test_virtual_connector_collinear_overlap_is_not_only_an_endpoint_touch():
    from copy import deepcopy

    # The last endpoint lies on the first native edge. Even a forged empty
    # native-only crossing census cannot make the overlapping virtual closure
    # an authenticated simple room perimeter.
    points = ((0, 0), (10, 0), (10, 10), (0, 10), (0, 5), (5, 0))
    ring, graph = _native_chain_receipts_for_virtual_connector(points)
    before = deepcopy((ring, graph))
    assert ring["source_only_native_polygon_area_pdf_pt2_not_m2"] > 0
    assert not compiler._original_doorway_ring_matches_reissued_native_graph(
        ring, graph,
    )
    assert (ring, graph) == before
