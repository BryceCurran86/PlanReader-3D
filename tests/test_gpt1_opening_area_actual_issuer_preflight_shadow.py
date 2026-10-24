"""The actual source-issued area preflight, never a shadow guess, is final."""
from dataclasses import MISSING, fields, replace

import pytest

from pb_live_opening_area_quantity_publication import _opening_quantity
from pb_live_physical_opening_void_composition import (
    LiveCanonicalOpeningObject, LivePhysicalOpeningVoidComposition,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_gpt1_opening_area_actual_issuer_preflight_shadow import (
    reconcile_gpt1_area_review_with_issuer,
)
from tests.test_gptmax_lot16_host_frame_gpt1_handoff import fixture, run


def _typed(canonical):
    """Model the actual immutable canonical dataclass, not producer authority."""
    rows=[]
    for item in canonical:
        vals={
            "semantic_class":"physical_opening",
            "structural_pattern":item.get("structural_pattern") or "",
            "source_lineage_root_ids":("source-own-1",),
            "source_geometries":(),
            "schedule_count_explicit":False,
            "schedule_row_observation_ids":(),
        }
        vals.update(item)
        for field in fields(LiveCanonicalOpeningObject):
            if field.name not in vals:
                if field.default is not MISSING:
                    vals[field.name]=field.default
                elif field.name.endswith("_ids"):
                    vals[field.name]=()
                elif field.name in ("geometry_complete","schedule_count_explicit"):
                    vals[field.name]=False
                else:
                    vals[field.name]=None
        vals["evidence_ids"]=tuple(vals["evidence_ids"])
        vals["source_observation_ids"]=tuple(vals["source_observation_ids"])
        rows.append(LiveCanonicalOpeningObject(**{
            f.name:vals[f.name] for f in fields(LiveCanonicalOpeningObject)
        }))
    return LivePhysicalOpeningVoidComposition(
        revision_id=canonical[0]["revision_id"],
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=(),
        traces=(),
        physical_opening_void_authorities={},
        void_selectors={},
        canonical_openings=tuple(rows),
    )


def _original_case():
    rows,c=fixture()
    rows[2]["frame_record"]=None
    c[2]["host_frame_record_id"]=None
    return rows,c


def test_real_typed_opening_area_issuer_matches_only_source_review_ready():
    rows,c=_original_case()
    source=run(rows,c)
    real=_typed(c)
    q=_opening_quantity(real.canonical_openings[2])
    assert q is not None
    assert q.semantic_key=="window_area:physical-3"
    assert q.value==2.16 and q.unit=="m2"
    assert q.input_entity_ids==("physical-3",)
    assert q.metadata["area_basis"]=="figured_opening_label"
    pre=reconcile_gpt1_area_review_with_issuer(real,source)
    assert pre["source_review_issuer_compatible_ids"] == ["physical-3"]
    assert pre["measurement_published"] is False
    assert pre["customer_seal_granted"] is False
    assert pre["opening_count_granted"] is False
    assert pre["shadow_only"]


@pytest.mark.parametrize("tamper", [
    lambda o:replace(o,area_m2=None),
    lambda o:replace(o,area_m2=8.82),
    lambda o:replace(o,area_basis="resolved_opening_geometry"),
    lambda o:replace(o,representative_observation_id="foreign"),
    lambda o:replace(o,source_observation_ids=()),
    lambda o:replace(o,viewport_id=""),
    lambda o:replace(o,host_binding_record_id="unowned-host"),
    lambda o:replace(o,source_sha256="0"*64),
])
def test_forged_publisher_relevant_field_cannot_pass_shadow_parity(tamper):
    rows,c=_original_case()
    source=run(rows,c)
    real=_typed(c)
    changed=list(real.canonical_openings)
    changed[2]=tamper(changed[2])
    fake=replace(real,canonical_openings=tuple(changed))
    with pytest.raises((ValueError, RuntimeError)):
        reconcile_gpt1_area_review_with_issuer(fake,source)


def test_preexisting_original_signed_quantity_not_rediscovered():
    rows,c=_original_case()
    rows[2]["quantity_id"]="existing-source-sealed"
    source=run(rows,c)
    output=reconcile_gpt1_area_review_with_issuer(_typed(c),source)
    assert output["source_review_issuer_compatible_ids"] == []
    assert output["issuer_compatible_but_source_abstained_ids"] == []


def test_one_unknown_original_opening_cannot_be_silently_dropped():
    rows,c=_original_case()
    source=run(rows,c)
    physical=_typed(c)
    narrower=replace(physical,canonical_openings=physical.canonical_openings[:-1])
    with pytest.raises(ValueError,match="inventory mismatch"):
        reconcile_gpt1_area_review_with_issuer(narrower,source)


def test_review_only_no_extra_3d_count_or_customer_authority():
    rows,c=_original_case()
    source=run(rows,c)
    pre=reconcile_gpt1_area_review_with_issuer(_typed(c),source)
    assert pre["benchmark_score_granted"] is False
    assert pre["measurement_published"] is False
    assert pre["opening_count_granted"] is False
    assert pre["customer_seal_granted"] is False


@pytest.mark.parametrize("field", [
    "original_opening_kind_source_authority_reproved",
    "filling_kind_source_supported",
    "figured_area_receipt_bound",
    "original_figured_label_source_scope_bound",
    "original_host_binding_receipt_bound",
    "original_physical_source_observation_receipts_bound",
])
def test_positive_publisher_cannot_override_failed_original_source_gate(field):
    rows, canonical = _original_case()
    source = run(rows, canonical)
    ready = source["gpt1_new_area_review_candidates"]
    assert len(ready) == 1
    assert ready[0]["new_gpt1_area_candidate_handoff"] is True
    ready[0][field] = False
    # _opening_quantity would still accept this typed object, but the
    # source-reviewed handoff must fail-closed on its missing independent gate.
    with pytest.raises(ValueError, match="source review claim lacks"):
        reconcile_gpt1_area_review_with_issuer(_typed(canonical), source)


@pytest.mark.parametrize("field,value", [
    ("opening_kind", "door"),
    ("page_id", "foreign-page"),
    ("viewport_id", "foreign-viewport"),
])
def test_publisher_object_cannot_replay_original_semantic_or_view_owner(field, value):
    rows, canonical = _original_case()
    source = run(rows, canonical)
    real = _typed(canonical)
    changed = list(real.canonical_openings)
    changed[2] = replace(changed[2], **{field: value})
    with pytest.raises(ValueError, match="foreign source/signed review decision"):
        reconcile_gpt1_area_review_with_issuer(
            replace(real, canonical_openings=tuple(changed)), source,
        )


def test_rekeyed_original_kind_claim_cannot_pass_source_to_issuer_parity():
    rows, canonical = _original_case()
    source = run(rows, canonical)
    source["gpt1_new_area_review_candidates"][0][
        "original_canonical_opening_kind"
    ] = "door"
    with pytest.raises(ValueError, match="foreign source/signed review decision"):
        reconcile_gpt1_area_review_with_issuer(_typed(canonical), source)


def test_original_authenticated_frame_receipt_matches_real_typed_issuer():
    # A fully framed opening remains eligible for gross FIGURED area.
    rows, canonical = fixture()
    source = run(rows, canonical)
    assert len(source["gpt1_new_area_review_candidates"]) == 1
    original = source["gpt1_new_area_review_candidates"][0]
    assert original["authenticated_frame_record_id"] == "frame-3"
    assert original["original_host_frame_receipt_bound"] is True
    typed = _typed(canonical)
    assert _opening_quantity(typed.canonical_openings[2]) is not None
    result = reconcile_gpt1_area_review_with_issuer(typed, source)
    assert result["source_review_issuer_compatible_ids"] == ["physical-3"]
    assert result["measurement_published"] is False


@pytest.mark.parametrize("field,value", [
    ("original_host_frame_receipt_bound", False),
    ("authenticated_frame_record_id", "foreign-original-frame"),
    ("authenticated_host_record_id", "foreign-original-host"),
    ("authenticated_frame_record_id", ""),
])
def test_forged_original_host_or_frame_cannot_pass_real_issuer_preflight(
    field, value,
):
    rows, canonical = fixture()
    source = run(rows, canonical)
    assert len(source["gpt1_new_area_review_candidates"]) == 1
    typed = _typed(canonical)
    # The ordinary issuer is still compatible: its typed canonical input
    # cannot validate a DIFFERENT source review queue on the caller's behalf.
    assert _opening_quantity(typed.canonical_openings[2]) is not None
    source["gpt1_new_area_review_candidates"][0][field] = value
    with pytest.raises(ValueError, match="host/frame source receipt"):
        reconcile_gpt1_area_review_with_issuer(typed, source)


def test_foreign_typed_frame_with_positive_real_issuer_fails_source_parity():
    rows, canonical = fixture()
    source = run(rows, canonical)
    typed = _typed(canonical)
    changed = list(typed.canonical_openings)
    original = changed[2]
    changed[2] = replace(
        original,
        host_frame_record_id="foreign-typed-frame",
        evidence_ids=original.evidence_ids + ("foreign-typed-frame",),
    )
    forged = replace(typed, canonical_openings=tuple(changed))
    assert _opening_quantity(forged.canonical_openings[2]) is not None
    with pytest.raises(ValueError, match="host/frame source receipt"):
        reconcile_gpt1_area_review_with_issuer(forged, source)


def test_canonical_frame_cannot_be_added_to_source_frame_absent_area():
    rows, canonical = _original_case()
    source = run(rows, canonical)
    typed = _typed(canonical)
    changed = list(typed.canonical_openings)
    original = changed[2]
    changed[2] = replace(
        original,
        host_frame_record_id="unreviewed-canonical-frame",
        evidence_ids=original.evidence_ids + ("unreviewed-canonical-frame",),
    )
    forged = replace(typed, canonical_openings=tuple(changed))
    assert _opening_quantity(forged.canonical_openings[2]) is not None
    with pytest.raises(ValueError, match="host/frame source receipt"):
        reconcile_gpt1_area_review_with_issuer(forged, source)

def test_source_figured_review_cannot_borrow_elevation_frame_issuer_basis():
    # The real quantity issuer supports both bases using the same physical
    # object, value and figured-area evidence ID. Only one was source reviewed.
    rows, canonical = _original_case()
    source = run(rows, canonical)
    typed = _typed(canonical)
    original = typed.canonical_openings[2]
    assert original.area_basis == "figured_opening_label"
    figured_quantity = _opening_quantity(original)
    assert figured_quantity is not None
    substitute = replace(original, area_basis="authenticated_elevation_frame")
    elevation_quantity = _opening_quantity(substitute)
    assert elevation_quantity is not None
    assert elevation_quantity.value == figured_quantity.value
    assert elevation_quantity.evidence_ids == figured_quantity.evidence_ids
    # Reject only the false original source preflight approval, never the
    # independently authorized elevation branch of the production issuer.
    with pytest.raises(ValueError, match="figured-label area basis"):
        reconcile_gpt1_area_review_with_issuer(
            replace(
                typed, canonical_openings=(
                    *typed.canonical_openings[:2],
                    substitute,
                    *typed.canonical_openings[3:],
                ),
            ),
            source,
        )

@pytest.mark.parametrize("rekey_field", ["document_id", "revision_id"])
def test_entire_canonical_document_revision_rekey_rejected(rekey_field):
    # Re-key every canonical member together: internal composition revision
    # and source-snapshot consistency still hold, and the REAL issuer remains
    # technically compatible. The unmodified original source review must
    # independently veto this foreign source envelope.
    rows, canonical = _original_case()
    source = run(rows, canonical)
    typed = _typed(canonical)
    foreign = "foreign-original-" + rekey_field
    tampered = tuple(
        replace(item, **{rekey_field: foreign})
        for item in typed.canonical_openings
    )
    assert _opening_quantity(tampered[2]) is not None
    forged = replace(
        typed,
        canonical_openings=tampered,
        revision_id=foreign if rekey_field == "revision_id" else typed.revision_id,
    )
    with pytest.raises(ValueError, match="foreign source/signed review decision"):
        reconcile_gpt1_area_review_with_issuer(forged, source)


@pytest.mark.parametrize("source_field", [
    "original_canonical_document_id",
    "original_canonical_revision_id",
])
def test_forged_review_document_revision_receipt_rejected(source_field):
    rows, canonical = _original_case()
    source = run(rows, canonical)
    source["gpt1_new_area_review_candidates"][0][source_field] = "foreign-source-scope"
    assert _opening_quantity(_typed(canonical).canonical_openings[2]) is not None
    with pytest.raises(ValueError, match="foreign source/signed review decision"):
        reconcile_gpt1_area_review_with_issuer(_typed(canonical), source)

@pytest.mark.parametrize("field,replacement", [
    ("host_wall_id", "foreign-wall-with-same-host-binding"),
    ("representative_observation_id", "foreign-representative"),
])
def test_source_review_rejects_foreign_typed_wall_or_evidence_roster(field, replacement):
    rows, canonical = _original_case()
    source = run(rows, canonical)
    typed = _typed(canonical)
    opening = typed.canonical_openings[2]
    amended = replace(opening, **{field: replacement})
    # Keep the real issuer technically eligible, to prove the independent
    # source-review gate (not an earlier generic issuer refusal) is exercised.
    if field == "representative_observation_id":
        amended = replace(
            amended,
            source_observation_ids=opening.source_observation_ids + (replacement,),
            evidence_ids=opening.evidence_ids + (replacement,),
        )
    assert _opening_quantity(amended) is not None
    changed = tuple(amended if i == 2 else v
                    for i, v in enumerate(typed.canonical_openings))
    with pytest.raises(ValueError, match="foreign source/signed review decision"):
        reconcile_gpt1_area_review_with_issuer(
            replace(typed, canonical_openings=changed), source,
        )


def test_added_authenticated_looking_witness_cannot_pass_source_review():
    rows, canonical = _original_case()
    source = run(rows, canonical)
    typed = _typed(canonical)
    opening = typed.canonical_openings[2]
    amended = replace(
        opening,
        source_observation_ids=opening.source_observation_ids + ("extra-source-observation",),
        evidence_ids=opening.evidence_ids + ("extra-source-observation",),
    )
    assert _opening_quantity(amended) is not None
    with pytest.raises(ValueError, match="foreign source/signed review decision"):
        reconcile_gpt1_area_review_with_issuer(
            replace(typed, canonical_openings=tuple(
                amended if i == 2 else v for i, v in enumerate(typed.canonical_openings)
            )), source,
        )


def test_added_nonobservational_evidence_cannot_pass_original_roster():
    rows, canonical = _original_case()
    source = run(rows, canonical)
    typed = _typed(canonical)
    opening = typed.canonical_openings[2]
    amended = replace(opening, evidence_ids=opening.evidence_ids + ("unreviewed-witness",))
    assert _opening_quantity(amended) is not None
    with pytest.raises(ValueError, match="foreign source/signed review decision"):
        reconcile_gpt1_area_review_with_issuer(
            replace(typed, canonical_openings=tuple(
                amended if i == 2 else v for i, v in enumerate(typed.canonical_openings)
            )), source,
        )


@pytest.mark.parametrize("field", [
    "original_canonical_host_wall_id",
    "original_canonical_representative_observation_id",
    "original_canonical_source_observation_ids",
    "original_canonical_evidence_ids",
])
def test_forged_original_review_wall_or_witness_receipt_refused(field):
    rows, canonical = _original_case()
    source = run(rows, canonical)
    review = source["gpt1_new_area_review_candidates"][0]
    review[field] = ("foreign-source-identity",) if field.endswith("_ids") else "foreign-source-identity"
    assert _opening_quantity(_typed(canonical).canonical_openings[2]) is not None
    with pytest.raises(ValueError, match="foreign source/signed review decision"):
        reconcile_gpt1_area_review_with_issuer(_typed(canonical), source)

@pytest.mark.parametrize("operation", ["add", "remove"])
def test_abstained_original_physical_member_must_retain_complete_evidence_roster(operation):
    # One unsupported opening must not hide a forged or deleted witness while
    # a *different* physically independent opening remains source review-ready.
    rows, canonical = _original_case()
    source = run(rows, canonical)
    assert source["gpt1_new_area_review_candidates"][0]["physical_opening_id"] == "physical-3"
    typed = _typed(canonical)
    abstained = typed.canonical_openings[0]
    assert _opening_quantity(abstained) is None
    original_receipts = abstained.evidence_ids
    amended_receipts = (
        original_receipts + ("foreign-abstained-witness",)
        if operation == "add"
        else original_receipts[:-1]
    )
    assert amended_receipts != original_receipts
    amended = replace(abstained, evidence_ids=amended_receipts)
    assert _opening_quantity(amended) is None
    with pytest.raises(ValueError, match="foreign source/signed review decision"):
        reconcile_gpt1_area_review_with_issuer(
            replace(
                typed,
                canonical_openings=(amended, *typed.canonical_openings[1:]),
            ),
            source,
        )
