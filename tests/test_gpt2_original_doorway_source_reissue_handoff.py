"""The GPT2 floor-finish compiler must replay original doorway ink, not trust status.

Source-neutral adversarial handoff tests; no FIRM, customer or frozen score.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

import pb_gpt2_original_source_geometry_bridge as module

SHA = "a" * 64
FLOOR_IDS = ("d1i0", "d2i0", "d3i0", "d4i0", "d5i0")
FINISH_IDS = ("d11i0", "d12i0", "d13i0", "d14i0", "d15i0")


def _cross_sheet():
    return {
        "original_source_sha256": SHA,
        "original_floor_page": 7,
        "original_finish_page": 11,
        "source_real_door_ink_gap_virtual_closure_only": True,
        "original_floor_source_ids": FLOOR_IDS,
        "original_finish_source_ids": FINISH_IDS,
        "source_cross_sheet_translation_pdf_pts": [78.0, 0.0],
    }


def _original_ancestry():
    return {
        "status": "original_doorway_all_printed_wall_strokes_match_candidate",
        "original_source_sha256": SHA,
        "source_document_id": "original-document",
        "source_revision_id": "original-revision",
        "source_snapshot_id": "original-snapshot",
        "original_floor_page": 7,
        "original_other_plan_page": 11,
        "original_translation_pdf_pts": [78.0, 0.0],
        "floor_source_graph": {"original_native_edge_ids": FLOOR_IDS},
        "second_plan_source_graph": {"original_native_edge_ids": FINISH_IDS},
        "original_floor_unclosed_gap_endpoints_pdf_pts": [[1, 2], [3, 2]],
        "original_second_unclosed_gap_endpoints_pdf_pts": [[79, 2], [81, 2]],
    }


def _call(monkeypatch, *, cross=None, ancestry=None, actual=None,
          inventory_complete=True, reissue_error=None):
    calls = []
    class Bridge(module.GPT2OriginalSourceGeometryBridge):
        def __init__(self):
            pass

        def _source_revision(self, revision_id, *, page_1_based):
            calls.append(("source", page_1_based))
            assert revision_id == "original-revision"
            return SimpleNamespace(
                revision=SimpleNamespace(
                    source_sha256=SHA, document_id="original-document"),
                snapshot=SimpleNamespace(snapshot_id="original-snapshot"),
            ), b"sealed-source"

        def original_room_doorway_source_ancestry(self, **kwargs):
            calls.append(("source_reissue", kwargs))
            assert kwargs == {
                "revision_id": "original-revision",
                "original_floor_page_1_based": 7,
                "original_second_page_1_based": 11,
                "original_floor_source_edge_ids": FLOOR_IDS,
                "original_second_source_edge_ids": FINISH_IDS,
                "original_translation_pdf_pts": (78.0, 0.0),
            }
            if reissue_error is not None:
                raise reissue_error
            return deepcopy(_original_ancestry() if actual is None else actual)

    def material(*args, **kwargs):
        calls.append(("material",))
        return {"status": "source_owned_material_on_original_ink_ring_candidate"}

    def w4(*args, **kwargs):
        calls.append(("w4",))
        return {
            "status": "source_original_floor_W4_face_candidate_only",
            "w4_room_face_source_identity_proven": True,
            "source_w4_wall_ownership_authenticated": True,
            "original_revision_id": "original-revision",
        }

    def to_gpt1(*args, **kwargs):
        calls.append(("gpt1_shadow",))
        return {
            "status":"gpt2_W4_source_finished_floor_ready_for_GPT1_measurement",
            "floor_finish_quantity_granted": False,
            "new_firm_quantities":0,
        }

    def census(original_pdf_bytes, *, page_1_based, original_room_graph):
        calls.append(("source_ink_inventory", page_1_based))
        assert original_pdf_bytes == b"sealed-source"
        assert original_room_graph["original_native_edge_ids"] in (
            FLOOR_IDS, FINISH_IDS,
        )
        return inventory_complete

    monkeypatch.setattr(
        module, "_original_doorway_gap_native_ink_inventory_complete", census,
    )
    monkeypatch.setattr(module, "audit_gpt2_source_material_floor_handoff", material)
    monkeypatch.setattr(module, "audit_gpt2_w4_bound_original_floor", w4)
    monkeypatch.setattr(module, "audit_gpt2_w4_material_to_gpt1", to_gpt1)
    receipt = _cross_sheet() if cross is None else cross
    witness = _original_ancestry() if ancestry is None else ancestry
    result = Bridge().source_closed_original_ft_handoff_for_gpt1(
        revision_id="original-revision",
        original_floor_page_1_based=7,
        source_cross_sheet_receipt=receipt,
        source_material_receipt={
            "status": "source_owned_material_on_original_ink_ring_candidate"
        },
        source_material_authority=None,
        source_definition_selector=None,
        source_occurrence_selector=None,
        original_finish_code="FT3",
        canonical_rooms=(),
        physical_room_id="office",
        original_doorway_source_ancestry=witness,
    )
    return result, calls


def test_negative_original_doorway_receipt_replays_and_preserves_producer_first_gate(
    monkeypatch,
):
    negative=_original_ancestry()
    negative["status"]="original_doorway_source_endpoint_rival_conflict"
    negative["first_unclosed_gate"]="original_short_wall_stub_disagrees_across_sheets"
    result,calls=_call(monkeypatch,ancestry=negative,actual=negative)
    assert [entry[0] for entry in calls]==["source","source_reissue"]
    assert result["status"]=="source_original_doorway_ancestry_conflict"
    assert result["first_failure"]==negative["first_unclosed_gate"]
    assert result["original_doorway_reissue_attempted"] is True
    assert result["original_doorway_reissued_status"]==negative["status"]
    assert result["new_firm_quantities"]==0
    assert result["floor_finish_quantity_granted"] is False


def test_forged_positive_preserves_actual_reissued_negative_gate(monkeypatch):
    actual=_original_ancestry()
    actual["status"]="original_doorway_source_endpoint_rival_conflict"
    actual["first_unclosed_gate"]="original_short_wall_stub_disagrees_across_sheets"
    result,calls=_call(monkeypatch,actual=actual)
    assert [entry[0] for entry in calls]==["source","source_reissue"]
    assert result["first_failure"]=="original_doorway_caller_receipt_mismatch"
    assert result["original_doorway_reissued_status"]==actual["status"]
    assert result["original_doorway_reissued_first_unclosed_gate"]==(
        actual["first_unclosed_gate"]
    )
    assert result["new_firm_quantities"]==0


def test_invalid_caller_scope_does_not_masquerade_as_real_source_failure(
    monkeypatch,
):
    altered=_cross_sheet()
    altered["original_floor_page"]=8
    result,calls=_call(monkeypatch,cross=altered)
    assert [entry[0] for entry in calls]==["source"]
    assert result["first_failure"]=="original_doorway_caller_scope_invalid"
    assert result["original_doorway_reissue_attempted"] is False
    assert result["original_doorway_reissued_status"] is None
    assert result["new_firm_quantities"]==0


@pytest.mark.parametrize("error", [
    ValueError("unavailable_original_source"),
    RuntimeError("tampered_original_source"),
])
def test_original_reissue_exception_preserves_typed_failure_and_never_hits_issuer(
    monkeypatch, error,
):
    result, calls = _call(monkeypatch, reissue_error=error)
    assert [entry[0] for entry in calls] == ["source", "source_reissue"]
    assert result["status"] == "source_original_doorway_ancestry_conflict"
    assert result["first_failure"] == "original_doorway_original_reissue_failed"
    assert result["original_doorway_reissue_attempted"] is True
    assert result["original_doorway_reissued_status"] is None
    assert result["original_doorway_reissued_first_unclosed_gate"] is None
    assert result["floor_finish_quantity_granted"] is False
    assert result["new_firm_quantities"] == 0


def test_negative_caller_status_cannot_bypass_positive_original_replay(
    monkeypatch,
):
    forged=_original_ancestry()
    forged["status"]="original_doorway_source_endpoint_rival_conflict"
    result,calls=_call(monkeypatch,ancestry=forged)
    assert [entry[0] for entry in calls]==["source","source_reissue"]
    assert result["first_failure"]=="original_doorway_caller_receipt_mismatch"
    assert result["new_firm_quantities"]==0


def test_replayed_original_doorway_reaches_existing_source_only_w4_handoff(monkeypatch):
    result, calls = _call(monkeypatch)
    assert [x[0] for x in calls] == [
        "source", "source_reissue", "source_ink_inventory",
        "source_ink_inventory", "material", "w4", "gpt1_shadow"
    ]
    assert result["status"] == "source_W4_FT_handoff_shadow_only"
    assert result["floor_finish_quantity_granted"] is False
    assert result["new_firm_quantities"] == 0


@pytest.mark.parametrize("mutation", [
    lambda x: x.update(status="original_doorway_source_endpoint_rival_conflict"),
    lambda x: x.update(source_snapshot_id="other-snapshot"),
    lambda x: x.update(source_document_id="other-document"),
    lambda x: x.update(original_other_plan_page=9),
    lambda x: x.update(original_translation_pdf_pts=[77.0, 0.0]),
    lambda x: x["floor_source_graph"].update(original_native_edge_ids=("d99i0",)),
    lambda x: x["second_plan_source_graph"].update(original_native_edge_ids=()),
    lambda x: x.update(original_second_unclosed_gap_endpoints_pdf_pts=[[79.24, 2], [81, 2]]),
])
def test_forged_copied_status_or_changed_original_geometry_never_reaches_issuer(
    monkeypatch, mutation
):
    fake = _original_ancestry()
    mutation(fake)
    result, calls = _call(monkeypatch, ancestry=fake)
    assert result["status"] == "source_original_doorway_ancestry_conflict"
    assert result["floor_finish_quantity_granted"] is False
    assert result["new_firm_quantities"] == 0
    assert not any(x[0] in {"material", "w4", "gpt1_shadow"} for x in calls)


@pytest.mark.parametrize("change", [
    {"original_floor_source_ids": ("d1i0", "d1i0", "d2i0")},
    {"original_floor_source_ids": ("d1i0", ["d2i0"])},
    {"original_finish_source_ids": ("d11i0", {"path": "d12i0"})},
    {"original_finish_source_ids": ("d11i0", "d12i0", "d99i0")},
    {"original_floor_page": 8},
    {"original_floor_page": "7"},
    {"original_finish_page": True},
    {"original_finish_page": 7},
    {"source_cross_sheet_translation_pdf_pts": [78.24, 0.0]},
    {"source_cross_sheet_translation_pdf_pts": [float("nan"), 0.0]},
    {"source_cross_sheet_translation_pdf_pts": [True, 0.0]},
    {"source_cross_sheet_translation_pdf_pts": "78,0"},
])
def test_caller_altered_doorway_source_inventory_or_registration_abstains(
    monkeypatch, change
):
    source = _cross_sheet()
    source.update(change)
    result, calls = _call(monkeypatch, cross=source)
    assert result["status"] == "source_original_doorway_ancestry_conflict"
    assert not any(x[0] in {"material", "w4", "gpt1_shadow"} for x in calls)


def test_true_private_pdf_rival_reissued_as_conflict_cannot_be_forged_positive(monkeypatch):
    actual = _original_ancestry()
    actual["status"] = "original_doorway_source_endpoint_rival_conflict"
    actual["original_second_unclosed_gap_endpoints_pdf_pts"] = [
        [79.24, 2], [81, 2],
    ]
    result, calls = _call(monkeypatch, actual=actual)
    assert result["status"] == "source_original_doorway_ancestry_conflict"
    assert not any(x[0] in {"material", "w4", "gpt1_shadow"} for x in calls)


def test_immutable_maryborough_office_d15_mismatch_cannot_spoof_matching_ancestry(
    monkeypatch,
):
    """Original-positive test requires a private source path, never fixture data."""
    import hashlib
    import os
    from pathlib import Path

    from pb_source_visibility_authority import SourceVisibilityProducer

    configured = os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not configured:
        pytest.skip("owner-private original not configured; SOURCE NOT VERIFIED")
    original = Path(configured)
    assert original.is_file(), "configured private source not found"
    raw = original.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
    )
    source = SourceVisibilityProducer(
        producer_method="gpt2-private-d15-reissue-test", producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="original-maryborough-d15-negative",
        source_bytes=raw,
        source_locator="memory://immutable-private-original.pdf",
        page_ids=("7", "11"),
    )
    bridge = module.GPT2OriginalSourceGeometryBridge.from_source_visibility_producer(
        source
    )
    p7 = (
        "d52239i0", "d66216i0", "d53725i0", "d52622i0", "d52625i0",
    )
    p11 = (
        "d2657i0", "d3058i0", "d2931i0", "d2842i0", "d2845i0",
    )
    authentic = bridge.original_room_doorway_source_ancestry(
        revision_id=published.revision.revision_id,
        original_floor_page_1_based=7, original_second_page_1_based=11,
        original_floor_source_edge_ids=p7, original_second_source_edge_ids=p11,
        original_translation_pdf_pts=(78.0, 0.0),
    )
    assert authentic["status"] == "original_doorway_source_endpoint_rival_conflict"
    assert authentic["first_unclosed_gate"] == (
        "original_short_wall_stub_disagrees_across_sheets"
    )
    assert authentic["original_door_gap_length_floor_pdf_pts"] == 56.64
    assert authentic["original_door_gap_length_second_pdf_pts"] == 56.88

    forged = deepcopy(authentic)
    forged["status"] = "original_doorway_all_printed_wall_strokes_match_candidate"
    monkeypatch.setattr(
        module, "audit_gpt2_source_material_floor_handoff",
        lambda *args, **kwargs: pytest.fail(
            "conflicting private original doorway must never reach material"
        ),
    )
    result = bridge.source_closed_original_ft_handoff_for_gpt1(
        revision_id=published.revision.revision_id,
        original_floor_page_1_based=7,
        source_cross_sheet_receipt={
            "original_source_sha256": published.revision.source_sha256,
            "original_floor_page": 7,
            "original_finish_page": 11,
            "source_real_door_ink_gap_virtual_closure_only": True,
            "original_floor_source_ids": tuple(sorted(p7)),
            "original_finish_source_ids": tuple(sorted(p11)),
            "source_cross_sheet_translation_pdf_pts": [78.0, 0.0],
        },
        source_material_receipt={}, source_material_authority=None,
        source_definition_selector=None, source_occurrence_selector=None,
        original_finish_code="FT3", canonical_rooms=(), physical_room_id="OFFICE",
        original_doorway_source_ancestry=forged,
    )
    assert result["status"] == "source_original_doorway_ancestry_conflict"
    assert result["floor_finish_quantity_granted"] is False
    assert result["new_firm_quantities"] == 0
    assert hashlib.sha256(original.read_bytes()).hexdigest() == (
        published.revision.source_sha256
    )



@pytest.mark.parametrize("mode", [False, None, "missing", "True", 0, 1])
def test_unverified_doorway_scope_never_bypasses_original_replay(
    monkeypatch, mode,
):
    """Caller flags cannot turn an OPEN doorway into a closed-room authority."""
    cross = _cross_sheet()
    if mode == "missing":
        cross.pop("source_real_door_ink_gap_virtual_closure_only")
    else:
        cross["source_real_door_ink_gap_virtual_closure_only"] = mode
    result, calls = _call(
        monkeypatch, cross=cross, inventory_complete=False,
    )
    assert [x[0] for x in calls] == ["source"]
    assert result["status"] == "source_original_doorway_ancestry_conflict"
    assert result["first_failure"] == "original_doorway_open_gap_scope_unverified"
    assert result["original_doorway_reissue_attempted"] is False
    assert result["floor_finish_quantity_granted"] is False
    assert result["new_firm_quantities"] == 0


def test_original_source_gap_inventory_prevents_selected_stroke_omission(
    monkeypatch,
):
    result,calls=_call(monkeypatch,inventory_complete=False)
    assert result["status"]=="source_original_doorway_ancestry_conflict"
    assert result["first_failure"]=="original_doorway_gap_painted_ink_inventory_incomplete"
    assert result["new_firm_quantities"]==0
    assert [r[0] for r in calls]==[
        "source","source_reissue","source_ink_inventory",
    ]


def test_real_native_pdf_same_axis_ink_inventory_detects_omitted_wall_stub():
    """Recompute source ink over an unfilled doorway, without caller snapshots."""
    import fitz

    doc=fitz.open()
    page=doc.new_page(width=200,height=200)
    for p,q in (
        ((20,20),(20,140)),
        ((120,20),(120,140)),
        ((20,140),(120,140)),
        ((20,20),(24,20)),
        ((80,20),(120,20)),
        # Extra drafting outside the physical gap cannot veto a room source.
        ((142,20),(149,20)),
    ):
        page.draw_line(p,q,color=(0,0,0),width=.48)
    raw=doc.tobytes()
    doc.close()
    def issued(ids, start):
        return {
            "page_1_based":1,
            "original_native_edge_ids":ids,
            "native_components":({
                "native_endpoint_degrees":(
                    {"degree":1,"point_pdf_pt":start},
                    {"degree":1,"point_pdf_pt":(80,20)},
                )
            },),
        }
    audit=module._original_doorway_gap_native_ink_inventory_complete
    assert audit(raw,page_1_based=1,original_room_graph=issued(
        ("d0i0","d1i0","d2i0","d3i0","d4i0"),(24,20),
    ))
    assert not audit(raw,page_1_based=1,original_room_graph=issued(
        ("d0i0","d1i0","d2i0","d4i0"),(20,20),
    ))
    assert not audit(raw,page_1_based=2,original_room_graph=issued(
        ("d0i0","d1i0","d2i0","d3i0","d4i0"),(24,20),
    ))


def test_private_original_omitted_same_axis_d15_stub_is_rejected_at_actual_handoff(
    monkeypatch,
):
    """Source-positive on provided original: even a 4-stroke positive is incomplete."""
    import hashlib
    import os
    from pathlib import Path

    from pb_source_visibility_authority import SourceVisibilityProducer

    location=os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not location:
        pytest.skip("owner-private original not configured; SOURCE NOT VERIFIED")
    original=Path(location)
    assert original.is_file()
    raw=original.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==(
        "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
    )
    source=SourceVisibilityProducer(
        producer_method="gpt2-private-omission-negative",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id="private-omitted-doorway-source",
        source_bytes=raw,
        source_locator="memory://owner-private-omitted-gap.pdf",
        page_ids=("7","11"),
    )
    bridge=module.GPT2OriginalSourceGeometryBridge.from_source_visibility_producer(
        source,
    )
    # The sole real p7/p11 disagreement is the very short left D15 ink
    # stub. Intentionally OMIT it on both pages. A selected-subset source
    # replay can then appear matching, but the full original page has it.
    floor_ids=("d52239i0","d66216i0","d53725i0","d52625i0")
    finish_ids=("d2657i0","d3058i0","d2931i0","d2845i0")
    partial=bridge.original_room_doorway_source_ancestry(
        revision_id=published.revision.revision_id,
        original_floor_page_1_based=7,original_second_page_1_based=11,
        original_floor_source_edge_ids=floor_ids,
        original_second_source_edge_ids=finish_ids,
        original_translation_pdf_pts=(78.0,0.0),
    )
    assert partial["status"]=="original_doorway_all_printed_wall_strokes_match_candidate"
    assert module._original_doorway_gap_native_ink_inventory_complete(
        raw,page_1_based=7,original_room_graph=partial["floor_source_graph"],
    ) is False
    assert module._original_doorway_gap_native_ink_inventory_complete(
        raw,page_1_based=11,original_room_graph=partial["second_plan_source_graph"],
    ) is False

    monkeypatch.setattr(
        module,"audit_gpt2_source_material_floor_handoff",
        lambda *args,**kwargs: pytest.fail(
            "omitted real doorway stroke may not reach material issuer"
        ),
    )
    result=bridge.source_closed_original_ft_handoff_for_gpt1(
        revision_id=published.revision.revision_id,
        original_floor_page_1_based=7,
        source_cross_sheet_receipt={
            "original_source_sha256":published.revision.source_sha256,
            "original_floor_page":7,"original_finish_page":11,
            "source_real_door_ink_gap_virtual_closure_only":True,
            "original_floor_source_ids":tuple(sorted(floor_ids)),
            "original_finish_source_ids":tuple(sorted(finish_ids)),
            "source_cross_sheet_translation_pdf_pts":[78.0,0.0],
        },
        source_material_receipt={},source_material_authority=None,
        source_definition_selector=None,source_occurrence_selector=None,
        original_finish_code="FT3",canonical_rooms=(),physical_room_id="OFFICE",
        original_doorway_source_ancestry=partial,
    )
    assert result["status"]=="source_original_doorway_ancestry_conflict"
    assert result["first_failure"]=="original_doorway_gap_painted_ink_inventory_incomplete"
    assert result["new_firm_quantities"]==0
    assert result["floor_finish_quantity_granted"] is False


@pytest.mark.parametrize("rival_style", [
    {"color": (0, 0, 0), "width": 0.50},
    {"color": (1, 0, 0), "width": 0.48},
    {"color": (1, 1, 1), "width": 0.48},
    {"color": (0.0, 0.5, 0.0), "width": 0.72},
    {"color": (0, 0, 0), "width": 0.48, "dashes": "[2 2] 0"},
    {"color": (0, 0, 0), "width": 0.48, "stroke_opacity": 0.5},
])
def test_native_door_gap_preserves_competing_ink_of_different_paint_styles(
    rival_style,
):
    """No painted different-style doorway rival may evade the native census."""
    import fitz

    doc=fitz.open()
    page=doc.new_page(width=200,height=200)
    for a,b in (
        ((20,20),(20,140)),
        ((120,20),(120,140)),
        ((20,140),(120,140)),
        ((20,20),(24,20)),
        ((80,20),(120,20)),
    ):
        page.draw_line(a,b,color=(0,0,0),width=0.48)
    source_graph={
        "page_1_based":1,
        "original_native_edge_ids":tuple(f"d{i}i0" for i in range(5)),
        "native_components":({
            "native_endpoint_degrees":(
                {"degree":1,"point_pdf_pt":(24,20)},
                {"degree":1,"point_pdf_pt":(80,20)},
            ),
        },),
    }
    audit=module._original_doorway_gap_native_ink_inventory_complete
    assert audit(doc.tobytes(),page_1_based=1,original_room_graph=source_graph)
    page.draw_line((35,20),(45,20),**rival_style)
    source_bytes=doc.tobytes()
    doc.close()
    assert not audit(
        source_bytes,page_1_based=1,original_room_graph=source_graph,
    )


def test_unrelated_coloured_ink_outside_native_doorway_does_not_veto():
    import fitz

    doc=fitz.open()
    page=doc.new_page(width=200,height=200)
    for a,b in (
        ((20,20),(20,140)),((120,20),(120,140)),
        ((20,140),(120,140)),((20,20),(24,20)),((80,20),(120,20)),
    ):
        page.draw_line(a,b,color=(0,0,0),width=0.48)
    page.draw_line((160,20),(175,20),color=(1,0,0),width=0.50)
    graph={
        "page_1_based":1,
        "original_native_edge_ids":tuple(f"d{i}i0" for i in range(5)),
        "native_components":({
            "native_endpoint_degrees":(
                {"degree":1,"point_pdf_pt":(24,20)},
                {"degree":1,"point_pdf_pt":(80,20)},
            ),
        },),
    }
    payload=doc.tobytes()
    doc.close()
    assert module._original_doorway_gap_native_ink_inventory_complete(
        payload,page_1_based=1,original_room_graph=graph,
    )


@pytest.mark.parametrize("vertical", [False, True])
@pytest.mark.parametrize("inside_gap", [False, True])
def test_native_door_gap_retains_unselected_stroked_rectangle_edge(
    vertical, inside_gap,
):
    """Native 're' edge rivals cannot disappear from the full ink census."""
    import fitz

    def turn(point):
        return (point[1], point[0]) if vertical else point

    doc=fitz.open()
    page=doc.new_page(width=200,height=200)
    for a,b in (
        ((20,20),(20,140)), ((120,20),(120,140)),
        ((20,140),(120,140)), ((20,20),(24,20)),
        ((80,20),(120,20)),
    ):
        page.draw_line(turn(a),turn(b),color=(0,0,0),width=0.48)
    graph={
        "page_1_based":1,
        "original_native_edge_ids":tuple(f"d{i}i0" for i in range(5)),
        "native_components":({
            "native_endpoint_degrees":(
                {"degree":1,"point_pdf_pt":turn((24,20))},
                {"degree":1,"point_pdf_pt":turn((80,20))},
            ),
        },),
    }
    audit=module._original_doorway_gap_native_ink_inventory_complete
    assert audit(doc.tobytes(),page_1_based=1,original_room_graph=graph)
    x0,y0,x1,y1=(35,20,45,24) if inside_gap else (145,20,155,24)
    if vertical:
        x0,y0,x1,y1=y0,x0,y1,x1
    page.draw_rect(fitz.Rect(x0,y0,x1,y1),color=(1,0,0),width=0.50)
    assert page.get_drawings()[-1]["items"][0][0]=="re"
    raw=doc.tobytes()
    doc.close()
    assert audit(raw,page_1_based=1,original_room_graph=graph) is (not inside_gap)


@pytest.mark.parametrize("vertical", [False, True])
@pytest.mark.parametrize("inside_gap", [False, True])
@pytest.mark.parametrize("shape_kind", ["qu-upper", "qu-lower", "c"])
def test_native_door_gap_retains_quad_edges_and_collinear_bezier_rivals(
    vertical, inside_gap, shape_kind,
):
    """Native 'qu'/'c' source ink must not evade the original gap census."""
    import fitz

    def turn(point):
        return (point[1],point[0]) if vertical else point

    doc=fitz.open()
    page=doc.new_page(width=200,height=200)
    for a,b in (
        ((20,20),(20,140)), ((120,20),(120,140)),
        ((20,140),(120,140)), ((20,20),(24,20)),
        ((80,20),(120,20)),
    ):
        page.draw_line(turn(a),turn(b),color=(0,0,0),width=0.48)
    graph={
        "page_1_based":1,
        "original_native_edge_ids":tuple(f"d{i}i0" for i in range(5)),
        "native_components":({
            "native_endpoint_degrees":(
                {"degree":1,"point_pdf_pt":turn((24,20))},
                {"degree":1,"point_pdf_pt":turn((80,20))},
            ),
        },),
    }
    audit=module._original_doorway_gap_native_ink_inventory_complete
    assert audit(doc.tobytes(),page_1_based=1,original_room_graph=graph)
    x0,x1=(35,45) if inside_gap else (145,155)
    if shape_kind.startswith("qu"):
        y0,y1=(16,20) if shape_kind=="qu-lower" else (20,24)
        quad=fitz.Quad(*(
            turn(p) for p in ((x0,y0),(x1,y0),(x0,y1),(x1,y1))
        ))
        page.draw_quad(quad,color=(1,0,0),width=0.50)
        assert page.get_drawings()[-1]["items"][0][0]=="qu"
    else:
        page.draw_bezier(*(
            turn(p) for p in (
                (x0,20),(x0+3,20),(x1-3,20),(x1,20)
            )
        ),color=(1,0,0),width=0.50)
        assert page.get_drawings()[-1]["items"][0][0]=="c"
    raw=doc.tobytes()
    doc.close()
    assert audit(raw,page_1_based=1,original_room_graph=graph) is (not inside_gap)


def test_private_original_complete_entrance_retains_differently_weighted_jamb_rivals():
    """Original OFFICE p7 has other visible width ink in its open entrance."""
    import hashlib
    import os
    from pathlib import Path

    from tools.diag_gpt2_source_room_graph_shadow import (
        audit_original_room_edge_graph,
    )

    configured=os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not configured:
        pytest.skip("private original not configured; source not verified")
    path=Path(configured)
    assert path.is_file()
    raw=path.read_bytes()
    sha="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
    assert hashlib.sha256(raw).hexdigest()==sha
    graph=audit_original_room_edge_graph(
        raw,source_sha256=sha,page_1_based=7,
        source_edge_ids=(
            "d52239i0","d66216i0","d53725i0","d52622i0","d52625i0",
        ),
    )
    # The p7 0.96pt original jamb strokes are inside the 0.48pt wall-gap
    # run, and without source-owned physical roles they remain rivals.
    assert module._original_doorway_gap_native_ink_inventory_complete(
        raw,page_1_based=7,original_room_graph=graph,
    ) is False


@pytest.mark.parametrize("vertical", [False, True])
@pytest.mark.parametrize("extra_position", ["inside", "outside"])
def test_selected_original_source_ids_cannot_whitelist_painted_door_gap_ink(
    vertical, extra_position,
):
    """Even a caller-selected native source item must not paint the gap."""
    import fitz

    def turn(point):
        return (point[1], point[0]) if vertical else point

    doc=fitz.open()
    page=doc.new_page(width=200,height=200)
    for a,b in (
        ((20,20),(20,140)), ((120,20),(120,140)),
        ((20,140),(120,140)), ((20,20),(24,20)),
        ((80,20),(120,20)),
    ):
        page.draw_line(turn(a),turn(b),color=(0,0,0),width=0.48)
    x0,x1=(35,45) if extra_position=="inside" else (145,155)
    page.draw_line(
        turn((x0,20)),turn((x1,20)),
        color=(1,0,0),width=0.50,
    )
    # The added painted rival is deliberately in the selected roster.
    # An unselected-rival-only veto would wrongly accept the inside case.
    graph={
        "page_1_based":1,
        "original_native_edge_ids":tuple(f"d{i}i0" for i in range(6)),
        "native_components":({
            "native_endpoint_degrees":(
                {"degree":1,"point_pdf_pt":turn((24,20))},
                {"degree":1,"point_pdf_pt":turn((80,20))},
            ),
        },),
    }
    raw=doc.tobytes()
    doc.close()
    assert module._original_doorway_gap_native_ink_inventory_complete(
        raw,page_1_based=1,original_room_graph=graph,
    ) is (extra_position=="outside")


@pytest.mark.parametrize("vertical", [False, True])
@pytest.mark.parametrize("selected", [False, True])
@pytest.mark.parametrize("shape_kind", [
    "perpendicular", "diagonal", "rectangle", "quad", "curve",
])
@pytest.mark.parametrize("inside_gap", [False, True])
def test_original_gap_vetoes_crossing_ink_regardless_of_selected_ids(
    vertical, selected, shape_kind, inside_gap,
):
    """A crossing native path cannot certify a physically empty door gap."""
    import fitz

    def turn(point):
        return (point[1],point[0]) if vertical else point

    doc=fitz.open()
    page=doc.new_page(width=200,height=200)
    for a,b in (
        ((20,20),(20,140)),((120,20),(120,140)),
        ((20,140),(120,140)),((20,20),(24,20)),
        ((80,20),(120,20)),
    ):
        page.draw_line(turn(a),turn(b),color=(0,0,0),width=0.48)
    x=35 if inside_gap else 145
    if shape_kind=="perpendicular":
        page.draw_line(turn((x,10)),turn((x,30)),color=(1,0,0))
    elif shape_kind=="diagonal":
        page.draw_line(turn((x-10,10)),turn((x+10,30)),color=(1,0,0))
    elif shape_kind=="rectangle":
        a,b=turn((x-2,10)),turn((x+2,30))
        page.draw_rect(fitz.Rect(*a,*b),color=(1,0,0))
    elif shape_kind=="quad":
        page.draw_quad(fitz.Quad(*(
            fitz.Point(*turn(p)) for p in (
                (x-2,10),(x+2,10),(x-2,30),(x+2,30)
            )
        )),color=(1,0,0))
    else:
        page.draw_bezier(*(
            turn(p) for p in (
                (x-10,10),(x-5,15),(x+5,25),(x+10,30)
            )
        ),color=(1,0,0))
    graph={
        "page_1_based":1,
        "original_native_edge_ids":tuple(
            f"d{i}i0" for i in range(6 if selected else 5)
        ),
        "native_components":({
            "native_endpoint_degrees":(
                {"degree":1,"point_pdf_pt":turn((24,20))},
                {"degree":1,"point_pdf_pt":turn((80,20))},
            ),
        },),
    }
    raw=doc.tobytes()
    doc.close()
    assert module._original_doorway_gap_native_ink_inventory_complete(
        raw,page_1_based=1,original_room_graph=graph,
    ) is (not inside_gap)


@pytest.mark.parametrize("vertical", [False, True])
@pytest.mark.parametrize("enters_gap", [False, True])
def test_original_gap_boundary_curve_paint_envelope(vertical, enters_gap):
    """An inward painted curve vetoes; a nearby fully outward curve does not."""
    import fitz

    def turn(point):
        return (point[1],point[0]) if vertical else point

    doc=fitz.open()
    page=doc.new_page(width=200,height=200)
    for a,b in (
        ((20,20),(20,140)),((120,20),(120,140)),
        ((20,140),(120,140)),((20,20),(24,20)),
        ((80,20),(120,20)),
    ):
        page.draw_line(turn(a),turn(b),color=(0,0,0),width=0.48)
    points = (
        ((24,20),(25,10),(30,10),(35,10)) if enters_gap
        else ((22,20),(20,10),(15,10),(10,10))
    )
    page.draw_bezier(*(turn(p) for p in points),color=(1,0,0),width=1.0)
    graph={
        "page_1_based":1,
        "original_native_edge_ids":tuple(f"d{i}i0" for i in range(5)),
        "native_components":({
            "native_endpoint_degrees":(
                {"degree":1,"point_pdf_pt":turn((24,20))},
                {"degree":1,"point_pdf_pt":turn((80,20))},
            ),
        },),
    }
    raw=doc.tobytes()
    doc.close()
    assert module._original_doorway_gap_native_ink_inventory_complete(
        raw,page_1_based=1,original_room_graph=graph,
    ) is (not enters_gap)


@pytest.mark.parametrize("vertical", [False, True])
@pytest.mark.parametrize("selected", [False, True])
@pytest.mark.parametrize("shape_kind", ["rect", "quad", "bezier"])
@pytest.mark.parametrize("placement", ["inside", "outside", "enclosing"])
def test_original_door_gap_rejects_visible_fill_only_path_occupancy(
    vertical, selected, shape_kind, placement,
):
    """Fill-only original ink must veto a door gap even without a stroked edge."""
    import fitz

    def turn(point):
        return (point[1],point[0]) if vertical else point

    doc=fitz.open()
    page=doc.new_page(width=200,height=200)
    for a,b in (
        ((20,20),(20,140)),((120,20),(120,140)),
        ((20,140),(120,140)),((20,20),(24,20)),
        ((80,20),(120,20)),
    ):
        page.draw_line(turn(a),turn(b),color=(0,0,0),width=0.48)
    x0,x1={
        "inside":(35,45),
        "outside":(145,155),
        # Fill completely covers the gap: no rectangle boundary crosses
        # the gap, so checking edges alone is insufficient.
        "enclosing":(10,100),
    }[placement]
    if shape_kind=="rect":
        a,b=turn((x0,18)),turn((x1,22))
        page.draw_rect(fitz.Rect(*a,*b),color=None,fill=(0,0,0))
    elif shape_kind=="quad":
        page.draw_quad(fitz.Quad(*(
            fitz.Point(*turn(p)) for p in (
                (x0,18),(x1,18),(x0,22),(x1,22)
            )
        )),color=None,fill=(0,0,0))
    else:
        page.draw_bezier(*(
            turn(p) for p in (
                (x0,18),(x0+2,17),(x1-2,23),(x1,22)
            )
        ),color=None,fill=(0,0,0))
    assert page.get_drawings()[-1]["type"]=="f"
    assert page.get_drawings()[-1]["color"] is None
    graph={
        "page_1_based":1,
        "original_native_edge_ids":tuple(
            f"d{i}i0" for i in range(6 if selected else 5)
        ),
        "native_components":({
            "native_endpoint_degrees":(
                {"degree":1,"point_pdf_pt":turn((24,20))},
                {"degree":1,"point_pdf_pt":turn((80,20))},
            ),
        },),
    }
    raw=doc.tobytes()
    doc.close()
    assert module._original_doorway_gap_native_ink_inventory_complete(
        raw,page_1_based=1,original_room_graph=graph,
    ) is (placement=="outside")


@pytest.mark.parametrize("vertical", [False, True])
def test_transparent_fill_only_native_path_does_not_veto_door_gap(vertical):
    """A genuinely zero-opacity fill is not painted competing source ink."""
    import fitz

    def turn(point):
        return (point[1],point[0]) if vertical else point

    doc=fitz.open()
    page=doc.new_page(width=200,height=200)
    for a,b in (
        ((20,20),(20,140)),((120,20),(120,140)),
        ((20,140),(120,140)),((20,20),(24,20)),
        ((80,20),(120,20)),
    ):
        page.draw_line(turn(a),turn(b),color=(0,0,0),width=0.48)
    a,b=turn((35,18)),turn((45,22))
    page.draw_rect(
        fitz.Rect(*a,*b),color=None,fill=(0,0,0),fill_opacity=0,
    )
    assert page.get_drawings()[-1]["type"]=="f"
    assert page.get_drawings()[-1]["fill_opacity"]==0
    graph={
        "page_1_based":1,
        "original_native_edge_ids":tuple(f"d{i}i0" for i in range(5)),
        "native_components":({
            "native_endpoint_degrees":(
                {"degree":1,"point_pdf_pt":turn((24,20))},
                {"degree":1,"point_pdf_pt":turn((80,20))},
            ),
        },),
    }
    raw=doc.tobytes()
    doc.close()
    assert module._original_doorway_gap_native_ink_inventory_complete(
        raw,page_1_based=1,original_room_graph=graph,
    )


@pytest.mark.parametrize("vertical", [False, True])
@pytest.mark.parametrize("selected", [False, True])
@pytest.mark.parametrize("inside_gap", [False, True])
@pytest.mark.parametrize("width", [0, 0.5])
def test_raw_pdf_zero_width_hairline_is_painted_original_door_rival(
    vertical, selected, inside_gap, width,
):
    """Actual PDF 0 w hairline must be counted, not normalized by draw_line."""
    import fitz

    def turn(point):
        return (point[1],point[0]) if vertical else point

    doc=fitz.open()
    page=doc.new_page(width=200,height=200)
    for a,b in (
        ((20,20),(20,140)),((120,20),(120,140)),
        ((20,140),(120,140)),((20,20),(24,20)),
        ((80,20),(120,20)),
    ):
        page.draw_line(turn(a),turn(b),color=(0,0,0),width=0.48)
    x=45 if inside_gap else 145
    a,b=turn((x,10)),turn((x,30))
    # PyMuPDF draw_line(width=0) emits 1 w, so write the original PDF
    # operator directly; the source scanner still uses get_drawings().
    first=(a[0],200-a[1])
    second=(b[0],200-b[1])
    prior=page.get_contents()
    ref=doc.get_new_xref()
    doc.update_object(ref,"<< >>")
    doc.update_stream(
        ref,
        (f"q 0 0 0 RG {width} w "
         f"{first[0]} {first[1]} m "
         f"{second[0]} {second[1]} l S Q").encode(),
    )
    doc.xref_set_key(
        page.xref,"Contents",
        "["+" ".join(f"{v} 0 R" for v in prior+[ref])+"]",
    )
    rival=page.get_drawings()[-1]
    assert rival["type"]=="s"
    assert rival["stroke_opacity"]==1
    assert rival["width"]==width
    graph={
        "page_1_based":1,
        "original_native_edge_ids":tuple(
            f"d{i}i0" for i in range(6 if selected else 5)
        ),
        "native_components":({
            "native_endpoint_degrees":(
                {"degree":1,"point_pdf_pt":turn((24,20))},
                {"degree":1,"point_pdf_pt":turn((80,20))},
            ),
        },),
    }
    raw=doc.tobytes()
    doc.close()
    assert module._original_doorway_gap_native_ink_inventory_complete(
        raw,page_1_based=1,original_room_graph=graph,
    ) is (not inside_gap)


@pytest.mark.parametrize("bad_field,bad_value", [
    ("width",None),
    ("width",float("nan")),
    ("stroke_opacity",None),
    ("stroke_opacity",float("nan")),
    ("color",None),
])
def test_unresolved_original_stroke_metadata_cannot_certify_empty_gap(
    monkeypatch,bad_field,bad_value,
):
    """Malformed native paint evidence must abstain, not disappear."""
    import fitz
    from copy import deepcopy

    doc=fitz.open()
    page=doc.new_page(width=200,height=200)
    for a,b in (
        ((20,20),(20,140)),((120,20),(120,140)),
        ((20,140),(120,140)),((20,20),(24,20)),
        ((80,20),(120,20)),((145,10),(145,30)),
    ):
        page.draw_line(a,b,color=(0,0,0),width=0.48)
    drawings=deepcopy(page.get_drawings())
    drawings[-1][bad_field]=bad_value
    doc.close()

    class SourcePage:
        def get_drawings(self):
            return deepcopy(drawings)

    class SourceDoc:
        page_count=1
        def __enter__(self):
            return self
        def __exit__(self,*args):
            return False
        def __getitem__(self,index):
            assert index==0
            return SourcePage()

    monkeypatch.setattr(fitz,"open",lambda **kwargs: SourceDoc())
    graph={
        "page_1_based":1,
        "original_native_edge_ids":tuple(f"d{i}i0" for i in range(5)),
        "native_components":({
            "native_endpoint_degrees":(
                {"degree":1,"point_pdf_pt":(24,20)},
                {"degree":1,"point_pdf_pt":(80,20)},
            ),
        },),
    }
    assert not module._original_doorway_gap_native_ink_inventory_complete(
        b"synthetic-source",page_1_based=1,original_room_graph=graph,
    )



@pytest.mark.parametrize("vertical", [False, True])
@pytest.mark.parametrize("flank", ["both", "left_only", "right_only", "neither"])
def test_native_open_doorway_requires_source_ink_on_both_gap_flanks(
    vertical, flank,
):
    """No single-sided wall observation may certify two-sided gap completeness."""
    import fitz

    def turn(p):
        return (p[1],p[0]) if vertical else p

    doc=fitz.open()
    page=doc.new_page(width=200,height=200)
    base=(
        ((20,20),(20,140)),
        ((120,20),(120,140)),
        ((20,140),(120,140)),
    )
    for a,b in base:
        page.draw_line(turn(a),turn(b),color=(0,0,0),width=.48)
    # In negative cases there is real ink anchored at the gap endpoint
    # but it is PERPENDICULAR to the missing horizontal wall fragment.
    # This must not make one witness sufficient for BOTH sides.
    left=((20,20),(24,20)) if flank in {"both","left_only"} else (
        (24,20),(24,35)
    )
    right=((80,20),(120,20)) if flank in {"both","right_only"} else (
        (80,20),(80,35)
    )
    for a,b in (left,right):
        page.draw_line(turn(a),turn(b),color=(0,0,0),width=.48)
    graph={
        "page_1_based":1,
        "original_native_edge_ids":tuple(f"d{i}i0" for i in range(5)),
        "native_components":({
            "native_endpoint_degrees":(
                {"degree":1,"point_pdf_pt":turn((24,20))},
                {"degree":1,"point_pdf_pt":turn((80,20))},
            ),
        },),
    }
    raw=doc.tobytes()
    doc.close()
    assert module._original_doorway_gap_native_ink_inventory_complete(
        raw,page_1_based=1,original_room_graph=graph,
    ) is (flank=="both")


@pytest.mark.parametrize("vertical", [False, True])
@pytest.mark.parametrize("paint_case", [
    "early_opaque_white_full",
    "late_opaque_white_full",
    "early_opaque_white_partial",
    "early_opaque_black_full",
    "early_translucent_white_full",
    "early_stroked_white_full",
    "early_white_quad_full",
    "early_white_full_then_crossing_stroke",
])
def test_native_gap_rejects_competing_paint_but_not_earlier_canvas_underlay(
    vertical, paint_case,
):
    """Paint order does not let whiteouts or other original ink evade replay."""
    import fitz

    def turn(point):
        return (point[1],point[0]) if vertical else point

    doc=fitz.open()
    page=doc.new_page(width=200,height=200)

    def draw_paint():
        x0,x1=(40,60) if paint_case=="early_opaque_white_partial" else (10,100)
        if paint_case=="early_white_quad_full":
            corners=(
                (x0,15),(x1,15),(x0,25),(x1,25),
            )
            page.draw_quad(
                fitz.Quad(*(fitz.Point(*turn(point)) for point in corners)),
                color=None,fill=(1,1,1),
            )
            return
        a,b=turn((x0,15)),turn((x1,25))
        opts={"color":None,"fill":(1,1,1)}
        if paint_case=="early_opaque_black_full":
            opts["fill"]=(0,0,0)
        if paint_case=="early_translucent_white_full":
            opts["fill_opacity"]=0.5
        if paint_case=="early_stroked_white_full":
            opts["color"]=(1,1,1)
        page.draw_rect(fitz.Rect(*a,*b),**opts)

    early=paint_case!="late_opaque_white_full"
    if early:
        draw_paint()
    start=1 if early else 0
    for a,b in (
        ((20,20),(20,140)),
        ((120,20),(120,140)),
        ((20,140),(120,140)),
        ((20,20),(24,20)),
        ((80,20),(120,20)),
    ):
        page.draw_line(turn(a),turn(b),color=(0,0,0),width=.48)
    if not early:
        draw_paint()
    if paint_case=="early_white_full_then_crossing_stroke":
        page.draw_line(
            turn((50,15)),turn((50,25)),color=(0,0,0),width=.48,
        )
    graph={
        "page_1_based":1,
        "original_native_edge_ids":tuple(
            f"d{i}i0" for i in range(start,start+5)
        ),
        "native_components":({
            "native_endpoint_degrees":(
                {"degree":1,"point_pdf_pt":turn((24,20))},
                {"degree":1,"point_pdf_pt":turn((80,20))},
            ),
        },),
    }
    raw=doc.tobytes()
    doc.close()
    result=module._original_doorway_gap_native_ink_inventory_complete(
        raw,page_1_based=1,original_room_graph=graph,
    )
    assert result is (paint_case=="early_opaque_white_full")


@pytest.mark.parametrize("vertical", [False, True])
@pytest.mark.parametrize("rival_first", [False, True])
@pytest.mark.parametrize("shift", [(0, 0), (50, 70)])
@pytest.mark.parametrize("shape", ["line", "curve", "rectangle", "quad"])
@pytest.mark.parametrize("offset,width,blocked", [
    (0.2, 1.0, True), (1.0, 0.5, False),
    (0.0, 0.5, True), (0.6, 1.0, False),
])
def test_native_door_gap_vetoes_painted_width_not_just_path_centreline(
    vertical, rival_first, shift, shape, offset, width, blocked,
):
    """Near-parallel original paint is a rival; genuine flanks still pass."""
    import fitz

    def turn(point):
        x, y = point[0] + shift[0], point[1] + shift[1]
        return (y, x) if vertical else (x, y)

    doc = fitz.open()
    page = doc.new_page(width=400, height=400)

    def draw_rival():
        y = 20 + offset
        if shape == "line":
            page.draw_line(
                turn((35, y)), turn((45, y)),
                color=(0, 0, 0), width=width,
            )
        elif shape == "curve":
            page.draw_bezier(
                *(fitz.Point(*turn(point)) for point in (
                    (35, y), (38, y), (42, y), (45, y)
                )), color=(0, 0, 0), width=width,
            )
        elif shape == "rectangle":
            page.draw_rect(
                fitz.Rect(*turn((35, y)), *turn((45, y + 0.1))),
                color=(0, 0, 0), width=width,
            )
        else:
            page.draw_quad(
                fitz.Quad(*(fitz.Point(*turn(point)) for point in (
                    (35, y), (45, y), (35, y + 0.1), (45, y + 0.1)
                ))), color=(0, 0, 0), width=width,
            )

    if rival_first:
        draw_rival()
    for a, b in (
        ((20, 20), (20, 140)),
        ((120, 20), (120, 140)),
        ((20, 140), (120, 140)),
        ((20, 20), (24, 20)),
        ((80, 20), (120, 20)),
    ):
        page.draw_line(turn(a), turn(b), color=(0, 0, 0), width=0.48)
    if not rival_first:
        draw_rival()
    raw = doc.tobytes()
    doc.close()

    start = 1 if rival_first else 0
    graph = {
        "page_1_based": 1,
        "original_native_edge_ids": tuple(
            f"d{i}i0" for i in range(start, start + 5)
        ),
        "native_components": ({
            "native_endpoint_degrees": (
                {"degree": 1, "point_pdf_pt": turn((24, 20))},
                {"degree": 1, "point_pdf_pt": turn((80, 20))},
            ),
        },),
    }
    assert module._original_doorway_gap_native_ink_inventory_complete(
        raw, page_1_based=1, original_room_graph=graph,
    ) is (not blocked)


def test_reissued_doorway_never_promotes_negative_sealed_W4_face(monkeypatch):
    result,calls=_call(monkeypatch)
    assert result["status"]=="source_W4_FT_handoff_shadow_only"
    assert result["new_firm_quantities"]==0
    assert result["floor_finish_quantity_granted"] is False


def test_positive_open_doorway_never_issues_firm_without_metric_measurement(monkeypatch):
    result,_=_call(monkeypatch)
    assert result["source_gpt1_floor_finish_input"]["status"]==(
        "gpt2_W4_source_finished_floor_ready_for_GPT1_measurement"
    )
    assert result["source_gpt1_floor_finish_input"]["new_firm_quantities"]==0
    assert result["new_firm_quantities"]==0
