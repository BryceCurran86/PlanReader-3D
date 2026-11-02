"""GPT2 original RCP compiler reissues ink from immutable source, never dict truth.

Synthetic, source-neutral adversarial tests. Not a real A120 F07 viewport
acceptance or a grant of ceiling square metres.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

import pb_gpt2_original_source_geometry_bridge as module


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
        "source_sha256": SHA,
        "page_1_based": 7,
        "original_native_edge_ids": FLOOR_EDGES,
        "native_candidate_ring_count": 1,
        "interior_stroke_intersections_and_overlaps": (),
        "native_components": ({
            "source_simple_ring_candidate": {"vertices_pdf_pts": POLYGON},
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
          cross=None, issued_floor=None, floor_error=None):
    events = []
    actual = _ink() if issued is None else issued

    class Bridge(module.GPT2OriginalSourceGeometryBridge):
        def __init__(self):
            pass

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

    monkeypatch.setattr(
        module, "audit_original_rcp_source_finish_occurrence",
        lambda *a, **k: (
            events.append(("material",)) or
            {"status": "original_rcp_material_in_ceiling_ink_candidate"}
        ),
    )
    monkeypatch.setattr(
        module, "audit_gpt2_w4_bound_original_floor",
        lambda *a, **k: events.append(("w4",)) or {"status": "W4_test_only"},
    )
    monkeypatch.setattr(
        module, "audit_gpt2_w4_original_rcp_ceiling_handoff",
        lambda *a, **k: events.append(("ceiling_handoff",)) or
            {"new_firm_quantities": 0, "ceiling_quantity_m2_issued": False},
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
        canonical_rooms=(),
        physical_room_id="OFFICE",
    )
    return result, events


def test_exact_reissued_ink_reaches_source_only_material_and_w4(monkeypatch):
    result, events = _call(monkeypatch)
    assert result["status"] == "source_W4_original_A120_ceiling_compilation_shadow_only"
    assert [item[0] for item in events] == [
        "original_source", "reissue_ink", "reissue_floor",
        "material", "w4", "ceiling_handoff",
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
    {"source_sha256": "b"*64},
    {"page_1_based": 11},
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
