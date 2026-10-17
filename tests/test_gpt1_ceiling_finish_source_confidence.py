"""Shadow ceiling finish evidence must have truthful finite source confidence."""
from dataclasses import replace
import pytest

from pb_ceiling_lining_quantity import resolve_ceiling_finish_entity
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_c15_ceiling_lining_quantity import (
    _context, _document, _viewport, _finish_atom, SCOPE_ID,
)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), -0.1, 1.1, True, "0.9"])
def test_malformed_ceiling_source_confidence_does_not_pass_as_corrob_finish(bad):
    atom=_finish_atom()
    # A normal EvidenceAtom constructor rejects malformed confidence. Forge
    # an impossible downstream receipt to exercise this independent consumer.
    object.__setattr__(atom,"confidence",bad)
    result=resolve_ceiling_finish_entity(
        evidence_atoms=(atom,),scope_entity_id=SCOPE_ID,
        context=_context(),document=_document(),
        viewport=_viewport(),page_no=1,
    )
    assert result is not None
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "finish_source_confidence_invalid" in result.reason_codes


def test_real_finite_source_confidence_preserves_shadow_scope():
    for value in [0.0,0.5,1.0]:
        atom=replace(_finish_atom(),confidence=value)
        result=resolve_ceiling_finish_entity(
            evidence_atoms=(atom,),scope_entity_id=SCOPE_ID,
            context=_context(),document=_document(),
            viewport=_viewport(),page_no=1,
        )
        assert result is not None
        assert result.status is EvidenceResolutionStatus.CORROBORATED
        assert result.confidence == value
