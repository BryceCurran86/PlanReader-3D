"""Adversarial semantic-receipt origin tests for default-off 3Laurel lining shadow.

A plausible same-source face label is not sufficient to inject a caller-authored
DRY/WET flag into the physical finished-face gate. This file creates no
customer quantity, floor finish, physical wall identity or frozen score.
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_room_wet_dry_classification_shadow import (
    CLASS_DRY_AREA,
    CLASS_WET_AREA,
    REASON_CLASSIFIED,
    ROOM_WET_DRY_RULE_SET_VERSION,
    RoomWetDryClassification,
    classify_room_wet_dry,
    wet_area_status_by_face_record,
)


_SCOPE = {
    "document_id": "doc-1",
    "revision_id": "rev-1",
    "source_sha256": "a" * 64,
    "snapshot_id": "snap-1",
    "page_id": "3",
    "decision_scope_id": "wall-source:3",
    "source_room_face_record_id": "face-17",
}


def _room(label="BED 2"):
    return SimpleNamespace(
        **_SCOPE,
        canonical_room_id="room-17",
        physical_room_id="physical-room-17",
        room_label=label,
        room_label_binding_record_id="label-source-owned-17",
        room_label_evidence_ids=("label-word-17",),
    )


def _face():
    return SimpleNamespace(
        record_id="face-17",
        **{field: value for field, value in _SCOPE.items() if field != "source_room_face_record_id"},
    )


def _class(label="BED 2"):
    one, = classify_room_wet_dry((_room(label),))
    return one


def _apply(item):
    return wet_area_status_by_face_record((item,), (_face(),))


def test_issuer_binds_its_own_source_complete_dry_and_wet_receipts():
    dry, wet = _class(), _class("ENS")
    assert dry.classification == CLASS_DRY_AREA
    assert wet.classification == CLASS_WET_AREA
    assert dry.reason_codes == (REASON_CLASSIFIED,)
    assert dry.rule_set_version == ROOM_WET_DRY_RULE_SET_VERSION
    assert _apply(dry) == {"face-17": False}
    assert _apply(wet) == {"face-17": True}
    assert dry.commercial_projection_allowed is False
    assert wet.takeoff_eligible is False


def test_caller_constructed_dataclass_cannot_claim_producer_authorship():
    original = _class()
    # Reconstruct all public lineage/class/record-id fields identically.
    copied = RoomWetDryClassification(**{
        name: value for name, value in vars(original).items() if name != "_seal"
    })
    assert copied == original  # public dataclass values are indistinguishable
    assert _apply(copied) == {"face-17": None}
    assert _apply(replace(original, _seal=None)) == {"face-17": None}
    assert _apply(replace(original, _seal=object())) == {"face-17": None}


@pytest.mark.parametrize("forgery", (
    {"classification": CLASS_WET_AREA},
    {"rule_id": "wet:bathroom"},
    {"record_id": "unowned-sha-and-rule"},
    {"rule_set_id": "another-ruleset"},
    {"rule_set_version": "untrusted"},
    {"schema_version": "2.0.0"},
    {"reason_codes": ("not-source-owned",)},
    {"canonical_room_id": "borrowed-room"},
    {"physical_room_id": "borrowed-physical-room"},
    {"room_label_binding_record_id": "borrowed-label-binding"},
    {"room_label_evidence_ids": ("borrowed-label-observation",)},
    {"commercial_projection_allowed": True},
    {"takeoff_eligible": True},
    {"grants_finish_or_metric_authority": True},
    {"diagnostic_only": False},
))
def test_replacement_of_authentic_source_receipt_never_changes_wall_lining(
    forgery,
):
    authentic = _class()
    forged = replace(authentic, **forgery)
    assert _apply(forged) == {"face-17": None}
    # A bad candidate never interferes with a separate intact exact-source receipt.
    assert wet_area_status_by_face_record(
        (forged, authentic), (_face(),)
    ) == {"face-17": False}


@pytest.mark.parametrize("forgery", (
    {"status": EvidenceResolutionStatus.CANDIDATE},
    {"status": EvidenceResolutionStatus.ABSTAINED},
    {"source_sha256": "b" * 64},
    {"revision_id": "rev-foreign"},
    {"snapshot_id": "snapshot-foreign"},
    {"document_id": "document-foreign"},
    {"page_id": "4"},
    {"decision_scope_id": "wall-source:4"},
    {"source_room_face_record_id": "face-foreign"},
    {"room_label_evidence_ids": ()},
    {"room_label_binding_record_id": ""},
))
def test_status_scope_and_missing_label_receipts_do_not_authenticate(
    forgery,
):
    assert _apply(replace(_class(), **forgery)) == {"face-17": None}


def test_forged_abstention_cannot_be_upgraded_into_dry_or_wet():
    unlisted = _class("KITCHEN")
    assert unlisted.status is EvidenceResolutionStatus.ABSTAINED
    assert _apply(unlisted) == {"face-17": None}
    for classification, rule in (
        (CLASS_DRY_AREA, "dry:bedroom"),
        (CLASS_WET_AREA, "wet:bathroom"),
    ):
        forged = replace(
            unlisted, classification=classification, rule_id=rule,
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(REASON_CLASSIFIED,),
        )
        assert _apply(forged) == {"face-17": None}


def test_unrelated_faces_and_duplicate_rivals_remain_fail_closed():
    dry, wet = _class(), _class("ENS")
    assert wet_area_status_by_face_record((dry, wet), (_face(),)) == {
        "face-17": None,
    }
    wrong = SimpleNamespace(**{
        **vars(_face()), "record_id": "face-18",
    })
    assert wet_area_status_by_face_record((dry,), (wrong,)) == {
        "face-18": None,
    }
