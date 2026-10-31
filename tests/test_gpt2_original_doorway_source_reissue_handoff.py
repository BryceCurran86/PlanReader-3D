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


def _call(monkeypatch, *, cross=None, ancestry=None, actual=None):
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
            return deepcopy(_original_ancestry() if actual is None else actual)

    def material(*args, **kwargs):
        calls.append(("material",))
        return {"status": "source_owned_material_on_original_ink_ring_candidate"}

    def w4(*args, **kwargs):
        calls.append(("w4",))
        return {"original_revision_id": "original-revision"}

    def to_gpt1(*args, **kwargs):
        calls.append(("gpt1_shadow",))
        return {"floor_finish_quantity_granted": False}

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


def test_replayed_original_doorway_reaches_existing_source_only_w4_handoff(monkeypatch):
    result, calls = _call(monkeypatch)
    assert [x[0] for x in calls] == [
        "source", "source_reissue", "material", "w4", "gpt1_shadow"
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
    {"original_finish_source_ids": ("d11i0", "d12i0", "d99i0")},
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
