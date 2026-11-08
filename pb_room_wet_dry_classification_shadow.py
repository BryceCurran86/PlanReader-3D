"""Is a room a wet area or a dry area? (SHADOW ONLY, default-off, diagnostic).

An authenticated internal-wall build-up statement can carry a wet-area lining variant. Whether that variant
applies to a recovered room is a fact about the room, not about the wall. This module classifies a room only
from the room label the existing source label authority has already verified for that exact room face
(``LiveCanonicalRoomObject.room_label``), through one explicit, versioned rule table:

* a label whose normalized phrase is listed as a wet-area phrase is ``wet_area``;
* a label whose normalized phrase is listed as a dry-area phrase is ``dry_area``;
* everything else is unclassified and ABSTAINS: no label, a label without its binding lineage, or a phrase
  the table does not list. The absence of a wet phrase never proves that a room is dry.

The rule is a whole-phrase match after one normalization (upper case, punctuation to spaces, trailing room
numbers removed). There is no substring, prefix, fuzzy or nearest match. Each record binds the exact room
scope (document, revision, source SHA, snapshot, page, decision scope, face record), the label binding
record, the label evidence ids and the rule id with the rule-set version, so a consumer can apply it only to
the room face it was derived for.

A classification grants no wall-layer, jamb, finish, metric, area or quantity permission and changes no
gate. It is noncommercial and diagnostic only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

ROOM_WET_DRY_SCHEMA_VERSION = "1.0.0"
ROOM_WET_DRY_RULE_SET_ID = "room_wet_dry_label_rules"
ROOM_WET_DRY_RULE_SET_VERSION = "1.0.0"

# A source classification is a producer-authored diagnostic receipt, not an
# arbitrary caller-constructed decision about wall lining.
_RECORD_SEAL = object()

CLASS_WET_AREA = "wet_area"
CLASS_DRY_AREA = "dry_area"

REASON_CLASSIFIED = "room_wet_dry_classified_by_label_rule"
REASON_LABEL_UNAVAILABLE = "room_label_unavailable"
REASON_LABEL_LINEAGE_INCOMPLETE = "room_label_binding_lineage_incomplete"
REASON_PHRASE_NOT_LISTED = "room_label_phrase_not_in_wet_dry_rule_table"
REASON_ROOM_SCOPE_INCOMPLETE = "room_scope_identity_incomplete"


@dataclass(frozen=True)
class WetDryRoomLabelRule:
    """One explicit rule: the exact normalized label phrases that make a room a wet or a dry area."""

    rule_id: str
    classification: str
    phrases: tuple[str, ...]
    basis: str


# Wet areas are the rooms the wet-area provisions apply to (bathroom, shower, toilet, laundry). Dry phrases
# are rooms those provisions do not cover. Kitchens, garages and outdoor areas are deliberately NOT listed:
# whether a wet-area lining applies there is not decided by a name alone, so they stay unclassified.
WET_DRY_ROOM_LABEL_RULES: tuple[WetDryRoomLabelRule, ...] = (
    WetDryRoomLabelRule("wet:bathroom", CLASS_WET_AREA, ("BATH", "BATHROOM", "ENS", "ENSUITE"),
                        "bathroom or ensuite"),
    WetDryRoomLabelRule("wet:shower", CLASS_WET_AREA, ("SHOWER",), "shower room"),
    WetDryRoomLabelRule("wet:toilet", CLASS_WET_AREA, ("WC", "W C", "TOILET", "POWDER", "POWDER ROOM", "PWDR"),
                        "toilet or powder room"),
    WetDryRoomLabelRule("wet:laundry", CLASS_WET_AREA, ("LDY", "LAUNDRY"), "laundry"),
    WetDryRoomLabelRule("dry:bedroom", CLASS_DRY_AREA, ("BED", "BEDROOM", "MASTER BEDROOM"), "bedroom"),
    WetDryRoomLabelRule("dry:robe", CLASS_DRY_AREA, ("ROBE", "WIR", "BIR", "WALK IN ROBE"), "wardrobe"),
    WetDryRoomLabelRule("dry:linen", CLASS_DRY_AREA, ("LIN", "LINEN"), "linen cupboard"),
    WetDryRoomLabelRule("dry:living", CLASS_DRY_AREA,
                        ("LIVING", "LOUNGE", "FAMILY", "DINING", "MEALS", "MEDIA", "RUMPUS", "THEATRE"),
                        "living room"),
    WetDryRoomLabelRule("dry:study", CLASS_DRY_AREA, ("STUDY", "OFFICE"), "study"),
    WetDryRoomLabelRule("dry:circulation", CLASS_DRY_AREA, ("HALL", "HALLWAY", "ENTRY"), "hall or entry"),
)


def _rule_by_phrase(rules: Sequence[WetDryRoomLabelRule]) -> dict[str, WetDryRoomLabelRule]:
    by_phrase: dict[str, WetDryRoomLabelRule] = {}
    for rule in rules:
        if rule.classification not in (CLASS_WET_AREA, CLASS_DRY_AREA):
            raise ValueError(f"unknown wet/dry class in rule {rule.rule_id}")
        for phrase in rule.phrases:
            if normalize_room_label_phrase(phrase) != phrase:
                raise ValueError(f"rule phrase is not normalized: {phrase!r}")
            if phrase in by_phrase:
                # One phrase may never belong to two rules: there is no precedence to resolve it.
                raise ValueError(f"wet/dry rule phrase listed twice: {phrase!r}")
            by_phrase[phrase] = rule
    return by_phrase


def normalize_room_label_phrase(label: str) -> str:
    """Upper case, every non-alphanumeric character to a space, trailing all-digit tokens removed."""
    tokens = re.sub(r"[^0-9A-Z]+", " ", str(label).upper()).split()
    while tokens and tokens[-1].isdigit():
        tokens.pop()
    return " ".join(tokens)


_RULES_BY_PHRASE = _rule_by_phrase(WET_DRY_ROOM_LABEL_RULES)

_SCOPE_FIELDS = (
    "document_id", "revision_id", "source_sha256", "snapshot_id", "page_id", "decision_scope_id",
    "source_room_face_record_id",
)


@dataclass(frozen=True)
class RoomWetDryClassification:
    record_id: str
    canonical_room_id: str
    physical_room_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    source_room_face_record_id: str
    room_label_binding_record_id: Optional[str]
    room_label_evidence_ids: tuple[str, ...]
    classification: Optional[str]
    rule_id: Optional[str]
    rule_set_id: str
    rule_set_version: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    schema_version: str = ROOM_WET_DRY_SCHEMA_VERSION
    takeoff_eligible: bool = False
    commercial_projection_allowed: bool = False
    grants_finish_or_metric_authority: bool = False
    diagnostic_only: bool = True
    _seal: object = field(default=None, repr=False, compare=False)


def _clean(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value and value == value.strip() else None


def _classify_one(room: Any) -> RoomWetDryClassification:
    scope = {field: _clean(getattr(room, field, None)) for field in _SCOPE_FIELDS}
    label = getattr(room, "room_label", None)
    binding_id = _clean(getattr(room, "room_label_binding_record_id", None))
    raw_evidence = getattr(room, "room_label_evidence_ids", ())
    evidence_ids = tuple(raw_evidence) if type(raw_evidence) is tuple else ()
    lineage_ok = bool(binding_id) and bool(evidence_ids) and all(_clean(item) for item in evidence_ids)

    rule: Optional[WetDryRoomLabelRule] = None
    if any(value is None for value in scope.values()):
        reason = REASON_ROOM_SCOPE_INCOMPLETE
    elif not isinstance(label, str) or not label.strip():
        reason = REASON_LABEL_UNAVAILABLE
    elif not lineage_ok:
        reason = REASON_LABEL_LINEAGE_INCOMPLETE
    else:
        rule = _RULES_BY_PHRASE.get(normalize_room_label_phrase(label))
        reason = REASON_CLASSIFIED if rule is not None else REASON_PHRASE_NOT_LISTED

    classified = rule is not None
    payload = {
        **{field: scope[field] or "" for field in _SCOPE_FIELDS},
        "canonical_room_id": str(getattr(room, "canonical_room_id", "") or ""),
        "physical_room_id": str(getattr(room, "physical_room_id", "") or ""),
        "room_label_binding_record_id": binding_id or "",
        "room_label_evidence_ids": list(evidence_ids),
        "rule_set_id": ROOM_WET_DRY_RULE_SET_ID,
        "rule_set_version": ROOM_WET_DRY_RULE_SET_VERSION,
        "rule_id": rule.rule_id if classified else "",
    }
    return RoomWetDryClassification(
        record_id=stable_contract_id("room_wet_dry", payload),
        canonical_room_id=str(getattr(room, "canonical_room_id", "") or ""),
        physical_room_id=str(getattr(room, "physical_room_id", "") or ""),
        document_id=scope["document_id"] or "",
        revision_id=scope["revision_id"] or "",
        source_sha256=scope["source_sha256"] or "",
        snapshot_id=scope["snapshot_id"] or "",
        page_id=scope["page_id"] or "",
        decision_scope_id=scope["decision_scope_id"] or "",
        source_room_face_record_id=scope["source_room_face_record_id"] or "",
        room_label_binding_record_id=binding_id,
        room_label_evidence_ids=evidence_ids,
        classification=rule.classification if classified else None,
        rule_id=rule.rule_id if classified else None,
        rule_set_id=ROOM_WET_DRY_RULE_SET_ID,
        rule_set_version=ROOM_WET_DRY_RULE_SET_VERSION,
        status=EvidenceResolutionStatus.CORROBORATED if classified else EvidenceResolutionStatus.ABSTAINED,
        reason_codes=(reason,),
        _seal=_RECORD_SEAL,
    )


def classify_room_wet_dry(rooms: Sequence[Any]) -> tuple[RoomWetDryClassification, ...]:
    """One record per room, ordered by record id. Never reads words; only the already-verified room label."""
    return tuple(sorted((_classify_one(room) for room in rooms), key=lambda item: item.record_id))


def _producer_issued_classification_is_valid(item: Any) -> bool:
    """Require an unmodified classification from the existing label-rule issuer.

    Exact matching face/source ids do not authorize caller-provided DRY/WET
    state. Validate record origin and rule/lineage binding before the wall
    finished-face consumer uses this diagnostic. This does not grant a FIRM
    floor, wall or finish.
    """
    if type(item) is not RoomWetDryClassification or item._seal is not _RECORD_SEAL:
        return False
    if (
        item.schema_version != ROOM_WET_DRY_SCHEMA_VERSION
        or item.rule_set_id != ROOM_WET_DRY_RULE_SET_ID
        or item.rule_set_version != ROOM_WET_DRY_RULE_SET_VERSION
        or item.status is not EvidenceResolutionStatus.CORROBORATED
        or item.reason_codes != (REASON_CLASSIFIED,)
        or item.classification not in (CLASS_WET_AREA, CLASS_DRY_AREA)
        or item.takeoff_eligible is not False
        or item.commercial_projection_allowed is not False
        or item.grants_finish_or_metric_authority is not False
        or item.diagnostic_only is not True
    ):
        return False
    if any(_clean(getattr(item, field, None)) is None for field in _SCOPE_FIELDS):
        return False
    if (
        _clean(item.canonical_room_id) is None
        or _clean(item.physical_room_id) is None
        or _clean(item.room_label_binding_record_id) is None
        or type(item.room_label_evidence_ids) is not tuple
        or not item.room_label_evidence_ids
        or any(_clean(x) is None for x in item.room_label_evidence_ids)
    ):
        return False
    if not any(
        rule.rule_id == item.rule_id and rule.classification == item.classification
        for rule in WET_DRY_ROOM_LABEL_RULES
    ):
        return False
    expected_id = stable_contract_id("room_wet_dry", {
        **{field: getattr(item, field) for field in _SCOPE_FIELDS},
        "canonical_room_id": item.canonical_room_id,
        "physical_room_id": item.physical_room_id,
        "room_label_binding_record_id": item.room_label_binding_record_id,
        "room_label_evidence_ids": list(item.room_label_evidence_ids),
        "rule_set_id": ROOM_WET_DRY_RULE_SET_ID,
        "rule_set_version": ROOM_WET_DRY_RULE_SET_VERSION,
        "rule_id": item.rule_id,
    })
    return item.record_id == expected_id


def wet_area_status_by_face_record(
    classifications: Sequence[RoomWetDryClassification],
    records: Sequence[Any],
) -> dict[str, Optional[bool]]:
    """Per sealed room-face record id: False for a dry area, True for a wet area, None when not established.

    A classification applies to a record only when it is CORROBORATED and every scope field (document,
    revision, source SHA, snapshot, page, decision scope, face record id) equals the record's own. Two
    applicable classifications that disagree leave the record unestablished.
    """
    out: dict[str, Optional[bool]] = {}
    for record in records:
        record_id = _clean(getattr(record, "record_id", None))
        if record_id is None:
            continue
        record_scope = {
            "document_id": _clean(getattr(record, "document_id", None)),
            "revision_id": _clean(getattr(record, "revision_id", None)),
            "source_sha256": _clean(getattr(record, "source_sha256", None)),
            "snapshot_id": _clean(getattr(record, "snapshot_id", None)),
            "page_id": _clean(getattr(record, "page_id", None)),
            "decision_scope_id": _clean(getattr(record, "decision_scope_id", None)),
            "source_room_face_record_id": record_id,
        }
        if any(value is None for value in record_scope.values()):
            out[record_id] = None
            continue
        classes = {
            item.classification for item in classifications
            if _producer_issued_classification_is_valid(item)
            and all(getattr(item, field) == value for field, value in record_scope.items())
        }
        out[record_id] = (classes == {CLASS_WET_AREA}) if len(classes) == 1 else None
    return out


def wet_area_status_mapping_is_valid(mapping: Optional[Mapping[str, Optional[bool]]]) -> bool:
    """A consumer-side guard: only str keys and True/False/None values."""
    if mapping is None:
        return True
    return isinstance(mapping, Mapping) and all(
        isinstance(key, str) and (value is None or type(value) is bool) for key, value in mapping.items()
    )


__all__ = [
    "CLASS_DRY_AREA",
    "CLASS_WET_AREA",
    "REASON_CLASSIFIED",
    "REASON_LABEL_LINEAGE_INCOMPLETE",
    "REASON_LABEL_UNAVAILABLE",
    "REASON_PHRASE_NOT_LISTED",
    "REASON_ROOM_SCOPE_INCOMPLETE",
    "ROOM_WET_DRY_RULE_SET_ID",
    "ROOM_WET_DRY_RULE_SET_VERSION",
    "RoomWetDryClassification",
    "WET_DRY_ROOM_LABEL_RULES",
    "WetDryRoomLabelRule",
    "classify_room_wet_dry",
    "normalize_room_label_phrase",
    "wet_area_status_by_face_record",
    "wet_area_status_mapping_is_valid",
]
