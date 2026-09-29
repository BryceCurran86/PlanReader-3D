from pb_migration_contracts import EvidenceResolutionStatus
from pb_secondary_area_support_evidence import SecondaryAreaSupportEvidence
from pb_secondary_support_structural_member_adapter import (
    build_secondary_support_structural_member_authority,
)

def evidence(*, mode="physical_symbol", ids=("g1","g2","g3","g4"), kind="physical_support"):
    return SecondaryAreaSupportEvidence(
        zone_type="verandah",
        support_kind=kind,
        support_count=4,
        bay_count=3,
        bay_spans_m=(3.3,3.4,3.3),
        source_pages=(54,),
        chain_ids=("chain-a",),
        zone_bbox=(0.0,0.0,10.0,10.0),
        support_bbox=(0.0,10.0,10.0,12.0),
        zone_text="VERANDAH",
        support_text="",
        support_symbol_ids=ids,
        evidence_mode=mode,
        confidence=0.97,
    )

def build(ev, complete=True):
    return build_secondary_support_structural_member_authority(
        evidence=ev,
        document_id="doc", revision_id="rev", source_sha256="a"*64,
        snapshot_id="snap", decision_scope_id="secondary:verandah",
        view_id="plan-54", view_complete=complete,
    ).resolution

def test_four_proven_symbols_publish_four_physical_members():
    r=build(evidence())
    assert r.status is EvidenceResolutionStatus.CORROBORATED
    assert r.quantity == 4
    assert len({m.physical_member_id for m in r.members}) == 4
    assert {m.source_primitive_ids for m in r.members} == {
        ("g1",),("g2",),("g3",),("g4",)
    }

def test_text_or_bay_count_evidence_without_physical_symbols_never_mints_quantity():
    r=build(evidence(mode="text_specification",ids=()))
    assert r.status is EvidenceResolutionStatus.ABSTAINED
    assert r.quantity is None

def test_incomplete_view_abstains_even_with_four_physical_symbols():
    r=build(evidence(),complete=False)
    assert r.status is EvidenceResolutionStatus.ABSTAINED
    assert r.quantity is None
    assert "secondary_support_view_incomplete" in r.reason_codes

def test_explicit_source_noun_is_preserved_as_member_kind():
    r=build(evidence(kind="pillar"))
    assert r.status is EvidenceResolutionStatus.CORROBORATED
    assert {m.member_kind for m in r.members} == {"pillar"}

def test_generic_physical_support_does_not_invent_material_or_member_subtype():
    r=build(evidence(kind="physical_support"))
    assert r.status is EvidenceResolutionStatus.CORROBORATED
    assert {m.member_kind for m in r.members} == {"structural_support"}

def test_symbol_count_must_match_proven_support_count():
    r=build(evidence(ids=("g1","g2","g3")))
    assert r.status is EvidenceResolutionStatus.ABSTAINED
    assert r.quantity is None

def test_multi_page_instance_row_is_not_treated_as_one_complete_view():
    ev=evidence()
    ev=SecondaryAreaSupportEvidence(
        zone_type=ev.zone_type, support_kind=ev.support_kind,
        support_count=ev.support_count, bay_count=ev.bay_count,
        bay_spans_m=ev.bay_spans_m, source_pages=(54,55),
        chain_ids=ev.chain_ids, zone_bbox=ev.zone_bbox,
        support_bbox=ev.support_bbox, zone_text=ev.zone_text,
        support_text=ev.support_text, support_symbol_ids=ev.support_symbol_ids,
        evidence_mode=ev.evidence_mode, confidence=ev.confidence,
    )
    r=build(ev)
    assert r.status is EvidenceResolutionStatus.ABSTAINED
    assert r.quantity is None
