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
    return {
        "status": status,
        "original_source_sha256": SOURCE_SHA,
        "original_page_1_based": page,
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
        ("source-geometric-issuer",),
        ("source-material-issuer",),
    ]
    assert outcome["status"]=="original_source_doorway_bound_floor_finish_shadow_only"
    assert outcome["new_firm_quantities"]==0
    assert outcome["customer_floor_finish_area_issued"] is False
    assert outcome["source_virtual_door_connectors_are_structural"] is False
    assert outcome["original_source_sha256"]==SOURCE_SHA
