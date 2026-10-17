"""A source finish observation identity has exactly one original meaning."""
from dataclasses import replace
from pb_ceiling_lining_quantity import resolve_ceiling_finish_entity
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_c15_ceiling_lining_quantity import _context,_document,_viewport,_finish_atom,SCOPE_ID


def _result(*atoms):
    return resolve_ceiling_finish_entity(
        evidence_atoms=atoms,scope_entity_id=SCOPE_ID,
        context=_context(),document=_document(),
        viewport=_viewport(),page_no=1,
    )


def test_one_original_finish_observation_stays_usable():
    assert _result(_finish_atom()).status is EvidenceResolutionStatus.CORROBORATED


def test_same_exact_material_observation_repeated_in_two_scopes_is_not_two_materials():
    first=_finish_atom()
    result=_result(first, replace(first))
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence_ids == (first.evidence_id,)


def test_rekeyed_semantic_of_same_source_evidence_id_quarantines_both():
    first=_finish_atom()
    altered=replace(first,raw_text="CEILING FINISH: suspended acoustic grid")
    for values in ((first,altered),(altered,first)):
        result=_result(*values)
        assert result.status is EvidenceResolutionStatus.ABSTAINED
        assert "ceiling_source_evidence_identity_conflict" in result.reason_codes


def test_same_original_id_with_altered_confidence_still_conflicts():
    atom=_finish_atom()
    rival=replace(atom,confidence=0.5)
    assert "ceiling_source_evidence_identity_conflict" in _result(atom,rival).reason_codes


def test_one_original_material_mark_cannot_bind_to_two_ceiling_scopes():
    original=_finish_atom()
    reused=replace(original,metadata={"scope_entity_id":"other-physical-room"})
    for order in ((original,reused),(reused,original)):
        result=_result(*order)
        assert result.status is EvidenceResolutionStatus.ABSTAINED
        assert "ceiling_source_evidence_identity_conflict" in result.reason_codes


def test_unrelated_other_scope_with_independent_original_id_is_ignored():
    original=_finish_atom()
    unrelated=replace(
        original,evidence_id="independent-source-mark",
        metadata={"scope_entity_id":"other-physical-room"},
        raw_text="CEILING FINISH: acoustic mineral fibre grid",
    )
    for order in ((original,unrelated),(unrelated,original)):
        result=_result(*order)
        assert result.status is EvidenceResolutionStatus.CORROBORATED
        assert result.evidence_ids == (original.evidence_id,)
