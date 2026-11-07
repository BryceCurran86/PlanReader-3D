"""Opt-in source-owned room wet/dry classification for the finished-face gate (shadow, noncommercial)."""
from __future__ import annotations

import copy
import random
from dataclasses import replace
from types import SimpleNamespace

import pytest

from pb_layered_wall_face_identity_shadow import REASON_WET_AREA_STATUS, VERDICT_RESOLVED, VERDICT_UNRESOLVED
from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
from pb_live_physical_net_wall_integration import (
    _collect_live_physical_net_wall_claim,
    _finished_face_receipts,
    collect_live_physical_net_wall_claim,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_room_wet_dry_classification_shadow import (
    CLASS_DRY_AREA,
    CLASS_WET_AREA,
    REASON_CLASSIFIED,
    REASON_LABEL_LINEAGE_INCOMPLETE,
    REASON_LABEL_UNAVAILABLE,
    REASON_PHRASE_NOT_LISTED,
    REASON_ROOM_SCOPE_INCOMPLETE,
    ROOM_WET_DRY_RULE_SET_VERSION,
    WET_DRY_ROOM_LABEL_RULES,
    WetDryRoomLabelRule,
    _rule_by_phrase,
    classify_room_wet_dry,
    normalize_room_label_phrase,
    wet_area_status_by_face_record,
)
from tests.test_layered_finished_face_gate_v1 import layered_room_pdf

SCOPE = dict(
    document_id="doc", revision_id="rev", source_sha256="a" * 64, snapshot_id="snap", page_id="1",
    decision_scope_id="wall-source:page-1",
)


def _room(label="BED 2", *, face="face-1", binding="label-1", evidence=("w1", "w2"), **overrides):
    fields = dict(
        canonical_room_id=f"room-{face}", physical_room_id=f"phys-{face}", source_room_face_record_id=face,
        room_label=label, room_label_binding_record_id=binding, room_label_evidence_ids=tuple(evidence), **SCOPE,
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _record(face="face-1", **overrides):
    fields = dict(record_id=face, **SCOPE)
    fields.update(overrides)
    return SimpleNamespace(**fields)


# ------------------------------------------------------------------------------------------------ the rule


@pytest.mark.parametrize("label, phrase", [
    ("BED 2", "BED"), ("bed 12 ", "BED"), ("W.C.", "W C"), ("Walk-in Robe", "WALK IN ROBE"), ("BED2", "BED2"),
    ("ENS 1 2", "ENS"), ("  ", ""),
])
def test_normalization_is_case_punctuation_and_trailing_number_only(label, phrase):
    assert normalize_room_label_phrase(label) == phrase


def test_the_rule_table_is_explicit_normalized_and_has_one_class_per_phrase():
    by_phrase = _rule_by_phrase(WET_DRY_ROOM_LABEL_RULES)
    assert set(by_phrase) == {phrase for rule in WET_DRY_ROOM_LABEL_RULES for phrase in rule.phrases}
    assert {rule.classification for rule in WET_DRY_ROOM_LABEL_RULES} == {CLASS_WET_AREA, CLASS_DRY_AREA}
    # a phrase listed under two rules has no precedence to resolve it: the table refuses to load
    with pytest.raises(ValueError):
        _rule_by_phrase((*WET_DRY_ROOM_LABEL_RULES, WetDryRoomLabelRule("wet:x", CLASS_WET_AREA, ("BED",), "x")))
    with pytest.raises(ValueError):
        _rule_by_phrase((WetDryRoomLabelRule("dry:x", CLASS_DRY_AREA, ("bed",), "x"),))
    with pytest.raises(ValueError):
        _rule_by_phrase((WetDryRoomLabelRule("x", "damp", ("X",), "x"),))


@pytest.mark.parametrize("label, expected, rule_id", [
    ("BED 2", CLASS_DRY_AREA, "dry:bedroom"), ("ROBE", CLASS_DRY_AREA, "dry:robe"),
    ("LIN", CLASS_DRY_AREA, "dry:linen"), ("ENS", CLASS_WET_AREA, "wet:bathroom"),
    ("W.C.", CLASS_WET_AREA, "wet:toilet"), ("LAUNDRY", CLASS_WET_AREA, "wet:laundry"),
])
def test_a_listed_phrase_owns_its_class_through_its_rule(label, expected, rule_id):
    record, = classify_room_wet_dry([_room(label)])
    assert (record.classification, record.rule_id, record.status) == (expected, rule_id, EvidenceResolutionStatus.CORROBORATED)
    assert record.reason_codes == (REASON_CLASSIFIED,) and record.rule_set_version == ROOM_WET_DRY_RULE_SET_VERSION
    assert (record.takeoff_eligible, record.commercial_projection_allowed, record.grants_finish_or_metric_authority) == (
        False, False, False)


@pytest.mark.parametrize("label", ["KITCHEN", "GARAGE", "ALFRESCO", "BEDROOM STORE", "BED ENS", "BED2", "PANTRY", "STORE"])
def test_an_unlisted_phrase_abstains_and_absence_of_a_wet_phrase_never_proves_dry(label):
    record, = classify_room_wet_dry([_room(label)])
    assert record.classification is None and record.rule_id is None
    assert record.status is EvidenceResolutionStatus.ABSTAINED and record.reason_codes == (REASON_PHRASE_NOT_LISTED,)


@pytest.mark.parametrize("room, reason", [
    (_room(None), REASON_LABEL_UNAVAILABLE),
    (_room("   "), REASON_LABEL_UNAVAILABLE),
    (_room("BED 2", binding=None), REASON_LABEL_LINEAGE_INCOMPLETE),
    (_room("BED 2", evidence=()), REASON_LABEL_LINEAGE_INCOMPLETE),
    (_room("BED 2", evidence=("w1", " w2")), REASON_LABEL_LINEAGE_INCOMPLETE),
    (_room("BED 2", revision_id=""), REASON_ROOM_SCOPE_INCOMPLETE),
    (_room("BED 2", source_sha256=None), REASON_ROOM_SCOPE_INCOMPLETE),
    (_room("BED 2", face=" face-1"), REASON_ROOM_SCOPE_INCOMPLETE),
])
def test_an_unauthenticated_or_unbound_label_abstains(room, reason):
    record, = classify_room_wet_dry([room])
    assert record.classification is None and record.status is EvidenceResolutionStatus.ABSTAINED
    assert record.reason_codes == (reason,)


def test_records_carry_the_label_lineage_and_are_replay_and_order_invariant():
    rooms = [_room("BED 2", face=f"face-{i}", binding=f"label-{i}", evidence=(f"w{i}",)) for i in range(6)]
    first = classify_room_wet_dry(rooms)
    shuffled = list(rooms)
    random.Random(7).shuffle(shuffled)
    assert classify_room_wet_dry(shuffled) == first
    assert len({record.record_id for record in first}) == len(rooms)
    by_face = {record.source_room_face_record_id: record for record in first}
    assert by_face["face-3"].room_label_binding_record_id == "label-3"
    assert by_face["face-3"].room_label_evidence_ids == ("w3",)
    # a different rule version would give a different id (the id binds the rule set)
    assert first == classify_room_wet_dry(copy.deepcopy(rooms))


def test_classification_never_mutates_its_input():
    rooms = [_room("BED 2"), _room("ENS", face="face-2")]
    before = copy.deepcopy(rooms)
    classify_room_wet_dry(rooms)
    assert rooms == before


# ------------------------------------------------------------------------------------- consumer lineage


def test_a_record_gets_a_status_only_from_a_classification_of_its_own_scope():
    dry, = classify_room_wet_dry([_room("BED 2")])
    wet, = classify_room_wet_dry([_room("ENS")])
    assert wet_area_status_by_face_record([dry], [_record()]) == {"face-1": False}
    assert wet_area_status_by_face_record([wet], [_record()]) == {"face-1": True}
    for field, value in [("revision_id", "rev-2"), ("source_sha256", "b" * 64), ("document_id", "doc-2"),
                         ("snapshot_id", "snap-2"), ("page_id", "2"), ("decision_scope_id", "wall-source:page-2")]:
        assert wet_area_status_by_face_record([dry], [_record(**{field: value})]) == {"face-1": None}, field
    assert wet_area_status_by_face_record([dry], [_record("face-2")]) == {"face-2": None}  # wrong room
    assert wet_area_status_by_face_record([dry], [_record(revision_id=None)]) == {"face-1": None}


def test_conflicting_or_abstained_classifications_leave_the_status_unestablished():
    dry, = classify_room_wet_dry([_room("BED 2")])
    wet, = classify_room_wet_dry([_room("ENS")])
    unknown, = classify_room_wet_dry([_room("KITCHEN")])
    assert wet_area_status_by_face_record([dry, wet], [_record()]) == {"face-1": None}
    assert wet_area_status_by_face_record([dry, dry], [_record()]) == {"face-1": False}
    assert wet_area_status_by_face_record([unknown], [_record()]) == {"face-1": None}
    forged = replace(unknown, classification=CLASS_DRY_AREA)  # ABSTAINED with a class: still ignored
    assert wet_area_status_by_face_record([forged], [_record()]) == {"face-1": None}
    assert wet_area_status_by_face_record([SimpleNamespace(**vars(dry))], [_record()]) == {"face-1": None}


def test_the_receipt_helper_rejects_a_malformed_status_mapping():
    with pytest.raises(TypeError):
        _finished_face_receipts(records=(), payload=b"", page_no=1, statements=(), scale_calibration=None,
                                room_is_wet_area_by_record={"face-1": "dry"})


# ------------------------------------------------------------------------------------ whole claim, ungated

WET_VARIANT_141 = (
    "THE INTERNAL WALLS TO BE 141mm PINE STUD FRAMES AND SHALL BE LINED WITH 10mm GYPROCK "
    "AND 6mm VILLA BOARD TO THE WET AREA'S AS REQUIRED"
)


_PDF_CACHE: dict[tuple[str, str], bytes] = {}


def _claim(tmp_path, *, label="BED 2", classify=None, note=WET_VARIANT_141):
    # Build each document once: a rebuilt PDF has new metadata, hence a new SHA and new record ids.
    data = _PDF_CACHE.setdefault((label, note), layered_room_pdf(note=note, scale_bar=True, label=label))
    path = tmp_path / "wet-dry.pdf"
    path.write_bytes(data)
    return collect_live_physical_net_wall_claim(
        path, pages=(0,), topology_pages=(0,), surface_semantic_pages=(0,), layered_doorway_room_rings=True,
        layered_finished_face_gate=True, layered_finished_face_statement_pages=(0,),
        **({"room_wet_dry_classification": classify} if classify is not None else {}),
    )


def test_keywords_are_explicit_booleans_and_need_the_finished_face_gate(tmp_path):
    path = tmp_path / "k.pdf"
    path.write_bytes(layered_room_pdf())
    for call in (collect_live_physical_net_wall_claim, _collect_live_physical_net_wall_claim):
        with pytest.raises(ValueError):
            call(path, pages=(0,), layered_doorway_room_rings=True, layered_finished_face_gate=True,
                 room_wet_dry_classification=1)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            call(path, pages=(0,), layered_doorway_room_rings=True, room_wet_dry_classification=True)


def test_ungated_the_claim_is_unchanged_and_carries_no_classification(tmp_path):
    omitted = _claim(tmp_path)
    explicit_false = _claim(tmp_path, classify=False)
    assert omitted.room_wet_dry_classifications == () == explicit_false.room_wet_dry_classifications
    assert omitted.layered_finished_face_receipts == explicit_false.layered_finished_face_receipts
    receipt, = omitted.layered_finished_face_receipts
    assert receipt.verdict == VERDICT_UNRESOLVED and REASON_WET_AREA_STATUS in receipt.reason_codes


def test_a_dry_label_settles_only_the_wet_area_reason_and_still_issues_nothing(tmp_path):
    claim = _claim(tmp_path, classify=True)
    room, = claim.canonical_rooms
    record, = claim.room_wet_dry_classifications
    assert (record.classification, record.rule_id) == (CLASS_DRY_AREA, "dry:bedroom")
    assert record.source_room_face_record_id == room.source_room_face_record_id
    assert record.room_label_binding_record_id == room.room_label_binding_record_id
    assert record.room_label_evidence_ids == room.room_label_evidence_ids
    receipt, = claim.layered_finished_face_receipts
    assert receipt.ring_record_id == record.source_room_face_record_id  # the receipt joins to its classification
    assert receipt.verdict == VERDICT_RESOLVED and REASON_WET_AREA_STATUS not in receipt.reason_codes
    # the gate is not relaxed: no documented, scaled, floor, finish or ceiling quantity
    assert claim.room_area_quantity_evidence == () and publish_live_floor_area_quantities(claim) == ()
    assert claim.floor_finish_quantity_evidence == () and claim.ceiling_lining_quantity_evidence == ()
    assert {c for _r, c in claim.same_view_room_area_first_failure_codes} == {
        "same_view_layered_ring_finished_face_not_established"}


@pytest.mark.parametrize("label, expected_class", [("ENS", CLASS_WET_AREA), ("KITCHEN", None)])
def test_a_wet_or_unlisted_label_keeps_the_wet_area_reason(tmp_path, label, expected_class):
    claim = _claim(tmp_path, label=label, classify=True)
    record, = claim.room_wet_dry_classifications
    assert record.classification == expected_class
    receipt, = claim.layered_finished_face_receipts
    assert receipt.verdict == VERDICT_UNRESOLVED and REASON_WET_AREA_STATUS in receipt.reason_codes
    assert claim.room_area_quantity_evidence == () and publish_live_floor_area_quantities(claim) == ()


def test_without_a_wet_area_variant_the_classification_changes_no_receipt(tmp_path):
    frame_only = "THE INTERNAL WALLS TO BE 141mm PINE STUD FRAMES AND SHALL BE LINED WITH 10mm GYPROCK"
    off = _claim(tmp_path, note=frame_only)
    on = _claim(tmp_path, note=frame_only, classify=True)
    assert off.layered_finished_face_receipts == on.layered_finished_face_receipts
    assert on.room_wet_dry_classifications and not off.room_wet_dry_classifications
