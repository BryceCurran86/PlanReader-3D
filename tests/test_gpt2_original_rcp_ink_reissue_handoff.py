"""GPT2 original RCP compiler reissues ink from immutable source, never dict truth.

Synthetic, source-neutral adversarial tests. Not a real A120 F07 viewport
acceptance or a grant of ceiling square metres.
"""
from __future__ import annotations

from copy import deepcopy
from math import dist
from types import SimpleNamespace

import pytest

import pb_gpt2_original_source_geometry_bridge as module
import pb_cross_view_ceiling_finish_authority as ceiling_module


SHA = "a" * 64
BORDERS = ("d0i0", "d1i0", "d2i0", "d3i0")
FLOOR_EDGES = ("f0", "f1", "f2", "f3")
POLYGON = ((20., 20.), (120., 20.), (120., 120.), (20., 120.))


def _cross():
    return {
        "status": "original_source_ink_ring_translation_candidate",
        "geometric_ink_correspondence_only": True,
        "original_source_sha256": SHA,
        "original_floor_page": 7,
        "original_finish_page": 9,
        "original_floor_source_ids": FLOOR_EDGES,
        "original_finish_source_ids": BORDERS,
        "source_cross_sheet_translation_pdf_pts": [0., 0.],
        "source_floor_perimeter_polygon_pdf_pts": POLYGON,
        "source_finishes_perimeter_polygon_pdf_pts": POLYGON,
    }


def _floor():
    return {
        "status": "original_closed_ink_ring_candidates_only",
        "source_sha256": SHA,
        "page_1_based": 7,
        "original_native_edge_ids": FLOOR_EDGES,
        "native_candidate_ring_count": 1,
        "interior_stroke_intersections_and_overlaps": (),
        "native_components": ({
            "source_edge_ids": FLOOR_EDGES,
            "source_simple_ring_candidate": {
                "vertices_pdf_pts": POLYGON,
                "source_edge_ids": FLOOR_EDGES,
            },
        },),
    }


def _ink():
    return {
        "status": "original_rcp_source_ink_ceiling_polygon_candidate",
        "original_source_sha256": SHA,
        "original_document_id": "doc",
        "original_revision_id": "rev",
        "original_snapshot_id": "snap",
        "original_rcp_page": 9,
        "original_rcp_viewport_id": "source-p9-original-rcp",
        "source_boundary_graph": {"original_native_edge_ids": BORDERS},
        "original_grid_source_ink_candidates": (
            {"native_source_id": "d5i0"},
        ),
        "source_ceiling_ink_polygon_pdf_pts": (
            (20., 20.), (120., 20.), (120., 120.), (20., 120.),
        ),
    }


def _call(monkeypatch, ink=None, *, issued=None, error=None,
          cross=None, issued_floor=None, floor_error=None,
          issued_w4=None, issued_ceiling=None, native_room_lines=None,
          open_floor=None, issued_open_ancestry=None,
          painted_gap_inventory_complete=True):
    events = []
    actual = _ink() if issued is None else issued

    class Bridge(module.GPT2OriginalSourceGeometryBridge):
        def __init__(self):
            self._source = object()

        def _source_revision(self, revision_id, *, page_1_based):
            events.append(("original_source", revision_id, page_1_based))
            assert revision_id == "rev"
            assert page_1_based == 7
            return (
                SimpleNamespace(
                    revision=SimpleNamespace(
                        source_sha256=SHA, document_id="doc",
                    ),
                    snapshot=SimpleNamespace(snapshot_id="snap"),
                ), b"source-neutral-bytes",
            )

        def original_rcp_ink_graph(
            self, *, revision_id, page_1_based, viewport_id,
            source_boundary_edge_ids, original_source_grid_edge_ids=(),
        ):
            events.append((
                "reissue_ink", revision_id, page_1_based, viewport_id,
                source_boundary_edge_ids, original_source_grid_edge_ids,
            ))
            if error is not None:
                raise error
            return deepcopy(actual)

        def original_room_ink_graph(
            self, *, revision_id, page_1_based, original_source_edge_ids,
        ):
            events.append((
                "reissue_floor", revision_id, page_1_based,
                original_source_edge_ids,
            ))
            if floor_error is not None:
                raise floor_error
            return deepcopy(_floor() if issued_floor is None else issued_floor)

        def original_room_doorway_source_ancestry(self, **kwargs):
            events.append(("reissue_original_open_doorway",kwargs))
            return deepcopy(issued_open_ancestry)

    monkeypatch.setattr(
        module, "_original_doorway_gap_native_ink_inventory_complete",
        lambda *a, **k: (
            events.append(("replay_full_gap_ink",k.get("page_1_based")))
            or painted_gap_inventory_complete
        ),
    )

    monkeypatch.setattr(
        module, "audit_original_rcp_source_finish_occurrence",
        lambda *a, **k: (
            events.append(("material",)) or
            {"status": "original_rcp_material_in_ceiling_ink_candidate"}
        ),
    )
    monkeypatch.setattr(
        module, "audit_gpt2_w4_bound_original_floor",
        lambda *a, **k: events.append(("w4",)) or (
            {
                "status": "source_original_floor_W4_face_candidate_only",
                "w4_room_face_source_identity_proven": True,
                "source_w4_wall_ownership_authenticated": True,
            } if issued_w4 is None else issued_w4
        ),
    )
    monkeypatch.setattr(
        module, "audit_gpt2_w4_original_rcp_ceiling_handoff",
        lambda *a, **k: events.append(("ceiling_handoff",)) or (
            {
                "status": "original_A120_RCP_material_on_W4_room_candidate_for_GPT1",
                "new_firm_quantities": 0, "ceiling_quantity_m2_issued": False,
            } if issued_ceiling is None else issued_ceiling
        ),
    )

    def original_room_text_line(
        text="OFFICE", block=9,
        bbox=(26., 45., 46., 57.),
        observations=("office-obs",), receipts=("office-receipt",),
    ):
        return SimpleNamespace(
            page_id="9", source_partition_id="original-rcp-page9",
            block_no=block, line_no=0, text=text, bbox=bbox,
            observation_ids=observations, receipt_ids=receipts,
        )
    lines = (
        (original_room_text_line(),)
        if native_room_lines is None else native_room_lines
    )
    monkeypatch.setattr(
        ceiling_module, "_trusted_room_labels_for_pages",
        lambda *a, **k: events.append(("trusted_room_labels",)) or
            {"9": lines},
    )

    result = Bridge().original_rcp_ceiling_source_handoff_for_gpt1(
        revision_id="rev",
        original_floor_page_1_based=7,
        source_floor_rcp_correspondence=deepcopy(_cross() if cross is None else cross),
        original_rcp_ink=deepcopy(_ink() if ink is None else ink),
        original_rcp_material={
            "status": "original_rcp_material_in_ceiling_ink_candidate",
        },
        source_material_authority=None,
        source_definition_selector=None,
        source_occurrence_selector=None,
        original_ceiling_finish_code="GRID",
        canonical_rooms=SimpleNamespace(rooms=(
            SimpleNamespace(physical_room_id="OFFICE", room_label="OFFICE"),
        )),
        physical_room_id="OFFICE",
        original_floor_open_doorway_source=open_floor,
    )
    return result, events


def test_exact_reissued_ink_reaches_source_only_material_and_w4(monkeypatch):
    result, events = _call(monkeypatch)
    assert result["status"] == "source_W4_original_A120_ceiling_compilation_shadow_only"
    assert [item[0] for item in events] == [
        "original_source", "reissue_ink", "reissue_floor",
        "material", "w4", "ceiling_handoff", "trusted_room_labels",
    ]
    assert events[1][1:] == (
        "rev", 9, "source-p9-original-rcp", BORDERS, ("d5i0",),
    )
    assert result["source_ceiling_area_m2"] is None
    assert result["new_firm_quantities"] == 0


@pytest.mark.parametrize(("key", "wrong"), [
    ("source_ceiling_ink_polygon_pdf_pts", (
        (20., 20.), (125., 20.), (125., 120.), (20., 120.))),
    ("original_source_sha256", "b" * 64),
    ("original_document_id", "foreign-document"),
    ("original_revision_id", "foreign-revision"),
    ("original_snapshot_id", "foreign-snapshot"),
    ("original_rcp_viewport_id", "other-viewport"),
    ("original_rcp_page", 8),
    ("original_rcp_page", True),
    ("original_rcp_page", "9"),
    ("source_boundary_graph", {"original_native_edge_ids": BORDERS[:-1]}),
    ("source_boundary_graph", {"original_native_edge_ids": BORDERS + ("d0i0",)}),
    ("source_boundary_graph", {"original_native_edge_ids": ("d0i0", "d1i0", True)}),
    ("original_grid_source_ink_candidates", ({"native_source_id": "d0i0"},)),
    ("original_grid_source_ink_candidates", ({"native_source_id": "d5i0"}, {"native_source_id": "d5i0"})),
    ("original_grid_source_ink_candidates", ({"native_source_id": "forged"},)),
    ("original_grid_source_ink_candidates", None),
])
def test_copied_or_changed_original_rcp_receipt_abstains_before_material(
    monkeypatch, key, wrong,
):
    forged = _ink()
    forged[key] = wrong
    result, events = _call(monkeypatch, forged)
    assert result["status"] == "source_RCP_ink_issuer_not_replayable"
    assert result["first_failure"] == "original_A120_source_ink_not_reauthenticated"
    assert result["source_ceiling_area_m2"] is None
    assert result["new_firm_quantities"] == 0
    assert all(item[0] not in ("material", "w4", "ceiling_handoff") for item in events)


@pytest.mark.parametrize("failure", [
    ValueError("source_page_ink_missing"),
    RuntimeError("source_revision_stale"),
])
def test_original_pdf_reissue_exception_abstains_before_any_issuer(
    monkeypatch, failure,
):
    result, events = _call(monkeypatch, error=failure)
    assert result["status"] == "source_RCP_ink_issuer_not_replayable"
    assert [item[0] for item in events] == ["original_source", "reissue_ink"]
    assert result["new_firm_quantities"] == 0


def test_original_f07_viewport_abstention_cannot_be_called_positive(monkeypatch):
    result, events = _call(
        monkeypatch, issued={"status": "original_rcp_source_unavailable",
                            "first_failure": "original_F07_rcp_viewport_not_authenticated"},
    )
    assert result["status"] == "source_RCP_ink_issuer_not_replayable"
    assert not any(item[0] in ("material", "w4", "ceiling_handoff") for item in events)





def test_same_original_rcp_native_members_in_different_source_order_are_valid(
    monkeypatch,
):
    cross = _cross()
    cross["original_finish_source_ids"] = tuple(reversed(BORDERS))
    result, events = _call(monkeypatch, cross=cross)
    assert result["status"] == "source_W4_original_A120_ceiling_compilation_shadow_only"
    assert "reissue_floor" in [event[0] for event in events]
    assert result["new_firm_quantities"] == 0


def test_original_floor_source_ids_are_replayed_before_material_and_w4(monkeypatch):
    result, events = _call(monkeypatch)
    assert result["status"] == "source_W4_original_A120_ceiling_compilation_shadow_only"
    assert events[2] == ("reissue_floor", "rev", 7, FLOOR_EDGES)
    assert result["source_ceiling_area_m2"] is None


@pytest.mark.parametrize(("field", "bad"), [
    ("status", "unissued-caller-copy"),
    ("geometric_ink_correspondence_only", 1),
    ("original_floor_page", True),
    ("original_finish_page", "9"),
    ("original_floor_source_ids", FLOOR_EDGES[:-1]),
    ("original_floor_source_ids", FLOOR_EDGES + ("f0",)),
    ("original_finish_source_ids", BORDERS[:-1]),
    ("source_cross_sheet_translation_pdf_pts", [True, 0.]),
    ("source_cross_sheet_translation_pdf_pts", [float("nan"), 0.]),
    ("source_cross_sheet_translation_pdf_pts", ["0", 0.]),
    ("source_floor_perimeter_polygon_pdf_pts", (
        (20.,20.),(125.,20.),(125.,120.),(20.,120.),
    )),
    ("source_finishes_perimeter_polygon_pdf_pts", (
        (20.,20.),(125.,20.),(125.,120.),(20.,120.),
    )),
])
def test_unsealed_or_forged_floor_rcp_registration_abstains_before_material(
    monkeypatch, field, bad,
):
    fake = _cross()
    fake[field] = bad
    result, events = _call(monkeypatch, cross=fake)
    assert result["status"] == "source_floor_RCP_registration_issuer_not_replayable"
    assert result["first_failure"] == "original_floor_to_A120_ink_not_reauthenticated"
    assert all(x[0] not in ("material","w4","ceiling_handoff") for x in events)
    assert result["new_firm_quantities"] == 0


@pytest.mark.parametrize("mutation", [
    {"status": "original_source_branches_or_open_ends"},
    {"source_sha256": "b"*64},
    {"page_1_based": 11},
    {"native_components": ({
        "source_edge_ids": FLOOR_EDGES[:-1],
        "source_simple_ring_candidate": {
            "vertices_pdf_pts": POLYGON,
            "source_edge_ids": FLOOR_EDGES,
        },
    },)},
    {"native_components": ({
        "source_edge_ids": FLOOR_EDGES,
        "source_simple_ring_candidate": {
            "vertices_pdf_pts": POLYGON,
            "source_edge_ids": FLOOR_EDGES[:-1],
        },
    },)},
    {"original_native_edge_ids": FLOOR_EDGES[:-1]},
    {"original_native_edge_ids": FLOOR_EDGES + ("f0",)},
    {"original_native_edge_ids": tuple(reversed(FLOOR_EDGES)) + ("f5",)},
    {"native_candidate_ring_count": 0},
    {"interior_stroke_intersections_and_overlaps": ("false-wall-crossing",)},
    {"native_components": ()},
    {"native_components": ({
        "source_simple_ring_candidate": {
            "vertices_pdf_pts": ((20.,20.),(125.,20.),(125.,120.),(20.,120.))
        },
    },)},
])
def test_reissued_original_floor_page_graph_must_equal_claimed_source_ink(
    monkeypatch, mutation,
):
    fake = _floor()
    fake.update(mutation)
    result, events = _call(monkeypatch, issued_floor=fake)
    assert result["status"] == "source_floor_RCP_registration_issuer_not_replayable"
    assert "reissue_floor" in [event[0] for event in events]
    assert all(x[0] not in ("material","w4","ceiling_handoff") for x in events)
    assert result["new_firm_quantities"] == 0


def test_failed_private_source_floor_reissue_abstains_before_material(monkeypatch):
    result, events = _call(
        monkeypatch, floor_error=RuntimeError("unavailable-source-floor")
    )
    assert result["status"] == "source_floor_RCP_registration_issuer_not_replayable"
    assert "reissue_floor" in [event[0] for event in events]
    assert all(x[0] not in ("material","w4","ceiling_handoff") for x in events)
    assert result["source_ceiling_area_m2"] is None



@pytest.mark.parametrize("negative", [
    {"status": "original_W4_RCP_ceiling_handoff_abstained",
     "first_failure": "W4_published_face_polygon_or_ancestry_conflict",
     "new_firm_quantities": 0, "ceiling_quantity_m2_issued": False},
    {"status": "original_A120_RCP_material_on_W4_room_candidate_for_GPT1",
     "new_firm_quantities": 1, "ceiling_quantity_m2_issued": False},
    {"status": "original_A120_RCP_material_on_W4_room_candidate_for_GPT1",
     "new_firm_quantities": 0, "ceiling_quantity_m2_issued": True},
    {},
])
def test_nested_source_w4_ceiling_failure_cannot_make_positive_outer_compilation(
    monkeypatch, negative,
):
    result, events = _call(monkeypatch, issued_ceiling=negative)
    assert result["status"] == "source_W4_original_A120_ceiling_binding_unverified"
    assert result["new_firm_quantities"] == 0
    assert result["source_ceiling_area_m2"] is None
    assert [x[0] for x in events][-2:] == ["w4", "ceiling_handoff"]


@pytest.mark.parametrize("negative", [
    {"status":"original_source_w4_room_binding_abstained",
     "first_failure":"sealed_W4_room_face_issuer_missing"},
    {"status":"source_original_floor_W4_face_candidate_only",
     "w4_room_face_source_identity_proven":False,
     "source_w4_wall_ownership_authenticated":True},
    {"status":"source_original_floor_W4_face_candidate_only",
     "w4_room_face_source_identity_proven":True,
     "source_w4_wall_ownership_authenticated":False},
    {},
])
def test_missing_sealed_w4_physical_owner_abstains_before_ceiling_adapter(
    monkeypatch, negative,
):
    result, events = _call(monkeypatch, issued_w4=negative)
    assert result["status"] == "source_W4_original_A120_ceiling_binding_unverified"
    assert result["new_firm_quantities"] == 0
    assert result["source_ceiling_area_m2"] is None
    assert "ceiling_handoff" not in [x[0] for x in events]



@pytest.mark.parametrize("native_room_lines", [
    (),
    (SimpleNamespace(
        page_id="9", source_partition_id="original-rcp-page9",
        block_no=9, line_no=0, text="LAUNDRY",
        bbox=(26.,45.,46.,57.),
        observation_ids=("laundry-obs",), receipt_ids=("laundry-receipt",),
    ),),
    (SimpleNamespace(
        page_id="9", source_partition_id="original-rcp-page9",
        block_no=9, line_no=0, text="OFFICE",
        bbox=(150.,145.,165.,157.),
        observation_ids=("office-obs",), receipt_ids=("office-receipt",),
    ),),
    (SimpleNamespace(
        page_id="9", source_partition_id="original-rcp-page9",
        block_no=9, line_no=0, text="OFFICE",
        bbox=(26.,45.,46.,57.),
        observation_ids=(), receipt_ids=(),
    ),),
    (SimpleNamespace(
        page_id="9", source_partition_id="original-rcp-page9",
        block_no=9, line_no=0, text="OFFICE",
        bbox=(26.,45.,46.,57.),
        observation_ids=("office-obs","office-obs"),
        receipt_ids=("r1","r2"),
    ),),
])
def test_missing_foreign_outside_or_untrusted_rcp_room_text_never_owns_grid(
    monkeypatch, native_room_lines,
):
    result, events = _call(monkeypatch, native_room_lines=native_room_lines)
    assert result["status"] == "source_RCP_room_label_region_not_authenticated"
    assert result["new_firm_quantities"] == 0
    assert result["source_ceiling_area_m2"] is None
    assert "trusted_room_labels" in [v[0] for v in events]


def test_two_independently_issued_room_labels_inside_same_rcp_zone_abstain(
    monkeypatch,
):
    def line(block, text):
        return SimpleNamespace(
            page_id="9", source_partition_id="original-rcp-page9",
            block_no=block, line_no=0, text=text,
            bbox=(26.,45.,46.,57.),
            observation_ids=(f"{text}-{block}",),
            receipt_ids=(f"{text}-{block}-proof",),
        )
    result, _ = _call(
        monkeypatch, native_room_lines=(
            line(9, "OFFICE"),line(14, "OFFICE")
        ),
    )
    assert result["status"] == "source_RCP_room_label_region_not_authenticated"
    assert result["new_firm_quantities"] == 0


def test_source_closed_cross_block_office_label_is_candidate_only(monkeypatch):
    result, events = _call(monkeypatch)
    assert result["status"] == "source_W4_original_A120_ceiling_compilation_shadow_only"
    assert "trusted_room_labels" in [v[0] for v in events]
    assert result["original_rcp_room_label_text"] == "OFFICE"
    assert result["original_rcp_room_label_native_block_no"] == 9
    assert result["original_rcp_room_label_observation_ids"] == ("office-obs",)
    assert result["original_rcp_room_label_receipt_ids"] == ("office-receipt",)
    assert result["original_rcp_label_material_join_authority"] == (
        "source_closed_zone_independent_text"
    )
    assert result["new_firm_quantities"] == 0
    assert result["source_ceiling_area_m2"] is None



def test_original_office_service_note_is_not_second_room_label(monkeypatch):
    # On the actual A120 original, the real OFFICE block and
    # "REVIEW IN OFFICE AREA" block are both within the ink region.
    # A word-token match would incorrectly count two OFFICE labels.
    def line(block, text, oid):
        return SimpleNamespace(
            page_id="9", source_partition_id="original-rcp-page9",
            block_no=block, line_no=0, text=text,
            bbox=(26., 45., 46., 57.),
            observation_ids=(oid,), receipt_ids=(oid+"-receipt",),
        )
    result, events=_call(
        monkeypatch, native_room_lines=(
            line(9,"OFFICE","original-office-label"),
            line(212,"REVIEW IN OFFICE AREA","mechanical-review-note"),
        ),
    )
    assert result["status"] == "source_W4_original_A120_ceiling_compilation_shadow_only"
    assert result["original_rcp_room_label_native_block_no"] == 9
    assert result["original_rcp_room_label_observation_ids"] == (
        "original-office-label",
    )
    assert "trusted_room_labels" in [e[0] for e in events]
    assert result["new_firm_quantities"] == 0


def test_source_review_note_alone_does_not_mint_office_identity(monkeypatch):
    note=SimpleNamespace(
        page_id="9",source_partition_id="original-rcp-page9",
        block_no=212,line_no=0,text="REVIEW IN OFFICE AREA",
        bbox=(26.,45.,46.,57.),
        observation_ids=("note-text",),receipt_ids=("note-receipt",),
    )
    result,_=_call(monkeypatch,native_room_lines=(note,))
    assert result["status"] == "source_RCP_room_label_region_not_authenticated"
    assert result["new_firm_quantities"] == 0


OPEN_FLOOR_IDS = ("f0","f1","f2","f3","f4")
OPEN_SECOND_IDS = ("s0","s1","s2")


def _open_floor_graph():
    strokes=(
        ("f0",((20.,20.),(120.,20.))),
        ("f1",((20.,20.),(20.,120.))),
        ("f2",((120.,20.),(120.,120.))),
        ("f3",((20.,120.),(60.,120.))),
        ("f4",((80.,120.),(120.,120.))),
    )
    nodes=(
        ((20.,20.),2),((20.,120.),2),((60.,120.),1),
        ((80.,120.),1),((120.,20.),2),((120.,120.),2),
    )
    return {
        "status":"original_source_branches_or_open_ends",
        "source_sha256":SHA,
        "page_1_based":7,
        "original_native_edge_ids":OPEN_FLOOR_IDS,
        "native_candidate_ring_count":0,
        "interior_stroke_intersections_and_overlaps":(),
        "original_native_edges":tuple(
            {"source_id":ident,"endpoints_pdf_pts":coords,
             "source_ink_length_pdf_pt":dist(*coords)}
            for ident,coords in strokes
        ),
        "native_components":({
            "source_edge_ids":OPEN_FLOOR_IDS,
            "source_simple_ring_candidate":None,
            "source_branch_coordinates_pdf_pts":(),
            "source_open_endpoint_coordinates_pdf_pts":(
                (60.,120.),(80.,120.),
            ),
            "native_endpoint_degrees":tuple(
                {"point_pdf_pt":xy,"degree":degree}
                for xy,degree in nodes
            ),
        },),
    }


def _open_ancestry():
    return {
        "status":"original_doorway_all_printed_wall_strokes_match_candidate",
        "original_source_sha256":SHA,
        "source_document_id":"doc",
        "source_revision_id":"rev",
        "source_snapshot_id":"snap",
        "floor_source_graph":{"original_native_edge_ids":OPEN_FLOOR_IDS},
        "second_plan_source_graph":{"original_native_edge_ids":OPEN_SECOND_IDS},
    }


def _open_request(ancestry=None):
    return {
        "original_second_page_1_based":11,
        "original_second_source_edge_ids":OPEN_SECOND_IDS,
        "source_floor_to_second_translation_pdf_pts":(78.,0.),
        "claimed_reissued_ancestry":(
            _open_ancestry() if ancestry is None else ancestry
        ),
    }


def _call_with_open_floor(monkeypatch, *, graph=None, request=None, actual=None,
                          full_page_ink=True, cross=None):
    registered=_cross() if cross is None else cross
    registered["original_floor_source_ids"]=OPEN_FLOOR_IDS
    return _call(
        monkeypatch,cross=registered,
        issued_floor=_open_floor_graph() if graph is None else graph,
        open_floor=_open_request() if request is None else request,
        issued_open_ancestry=_open_ancestry() if actual is None else actual,
        painted_gap_inventory_complete=full_page_ink,
    )


def test_unchanged_original_open_floor_ring_to_closed_rcp_reaches_source_only_w4(
    monkeypatch,
):
    result,events=_call_with_open_floor(monkeypatch)
    assert result["status"]=="source_W4_original_A120_ceiling_compilation_shadow_only"
    assert "reissue_original_open_doorway" in [v[0] for v in events]
    assert [v[1] for v in events if v[0]=="replay_full_gap_ink"]==[7,11]
    assert result["source_ceiling_area_m2"] is None
    assert result["new_firm_quantities"]==0


def test_open_original_floor_d15_without_explicit_original_replay_abstains(
    monkeypatch,
):
    cross=_cross()
    cross["original_floor_source_ids"]=OPEN_FLOOR_IDS
    result,events=_call(
        monkeypatch,cross=cross,issued_floor=_open_floor_graph(),
    )
    assert result["status"]=="source_floor_RCP_registration_issuer_not_replayable"
    assert "material" not in [v[0] for v in events]
    assert result["new_firm_quantities"]==0


@pytest.mark.parametrize("kind",[
    "caller_ancestry_changed","original_ancestry_negative",
    "painted_gap_incomplete","wrong_other_page","fake_floor_source_ids",
])
def test_open_doorway_without_original_full_ink_and_competitor_proof_abstains(
    monkeypatch,kind,
):
    request=_open_request()
    actual=_open_ancestry()
    graph=_open_floor_graph()
    complete=True
    if kind=="caller_ancestry_changed":
        request["claimed_reissued_ancestry"]["source_snapshot_id"]="stale-snapshot"
    elif kind=="original_ancestry_negative":
        actual["status"]="original_doorway_source_endpoint_rival_conflict"
        request["claimed_reissued_ancestry"]["status"]=actual["status"]
    elif kind=="painted_gap_incomplete":
        complete=False
    elif kind=="wrong_other_page":
        request["original_second_page_1_based"]=9
    elif kind=="fake_floor_source_ids":
        graph["original_native_edges"][2]["source_id"]="unknown-edge"
    result,events=_call_with_open_floor(
        monkeypatch,graph=graph,request=request,actual=actual,
        full_page_ink=complete,
    )
    assert result["status"]=="source_floor_RCP_registration_issuer_not_replayable"
    assert "material" not in [v[0] for v in events]
    assert result["source_ceiling_area_m2"] is None
    assert result["new_firm_quantities"]==0
