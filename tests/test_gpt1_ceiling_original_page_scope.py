"""A source RCP page cannot be borrowed by numeric aliases."""
import pytest
from pb_ceiling_lining_quantity import _base_context_blockers
from tests.test_c15_ceiling_lining_quantity import _context, _document, _viewport


def _blockers(page=1,context=None):
    return _base_context_blockers(
        context=_context() if context is None else context,
        document=_document(),viewport=_viewport(),page_no=page,
    )


def test_owned_exact_integer_page_is_still_eligible():
    assert _blockers() == ()


@pytest.mark.parametrize("bad_page", [True,1.0,1.9,"1",None,-1,0])
def test_alias_page_types_cannot_claim_original_rcp_area(bad_page):
    assert "page_not_owned" in _blockers(page=bad_page)


def test_missing_page_is_not_coerced_into_other_viewport():
    context=_context(viewport_page_ownership=(("vp-floor-1",2),))
    assert "viewport_page_mismatch" in _blockers(context=context)


def test_corrupted_nonpage_does_not_crash_or_positive_approve_source_finish():
    from pb_ceiling_lining_quantity import resolve_ceiling_finish_entity
    from pb_migration_contracts import EvidenceResolutionStatus
    from tests.test_c15_ceiling_lining_quantity import _finish_atom, SCOPE_ID
    for invalid in (True,1.5,"1",None):
        result=resolve_ceiling_finish_entity(
            evidence_atoms=(_finish_atom(),),scope_entity_id=SCOPE_ID,
            context=_context(),document=_document(),viewport=_viewport(),
            page_no=invalid,
        )
        assert result is not None
        assert result.status is EvidenceResolutionStatus.ABSTAINED
        assert result.metadata["page_no"] is None


def test_corrupted_page_yields_blocked_provisional_ceiling_quantity_not_exception():
    from pb_ceiling_lining_quantity import build_ceiling_lining_quantity
    from tests.test_c15_ceiling_lining_quantity import (
        _area_quantity, _finish_atom, SCOPE_ID,
    )
    for invalid in (True,1.5,"1",None):
        result=build_ceiling_lining_quantity(
            scope_entity_id=SCOPE_ID,
            area_quantity=_area_quantity(),
            finish_evidence_atoms=(_finish_atom(),),
            context=_context(),
            document=_document(),
            viewport=_viewport(),
            page_no=invalid,
        )
        assert result.abstained
        assert result.value is None
        assert result.metadata["page_no"] is None


def test_upstream_documented_area_cannot_relabel_original_page_by_coercion():
    from dataclasses import replace
    from pb_ceiling_lining_quantity import build_ceiling_lining_quantity
    from tests.test_c15_ceiling_lining_quantity import (
        _area_quantity, _finish_atom, SCOPE_ID,
    )
    original=_area_quantity()
    for incorrect in (True,1.0,1.5,"1",None):
        metadata=dict(original.metadata)
        metadata["page_no"]=incorrect
        forged=replace(original,metadata=metadata)
        result=build_ceiling_lining_quantity(
            scope_entity_id=SCOPE_ID,area_quantity=forged,
            finish_evidence_atoms=(_finish_atom(),),
            context=_context(),document=_document(),viewport=_viewport(),
            page_no=1,
        )
        assert result.abstained and result.value is None
        assert "upstream_area_page_unbound" in result.blocking_reasons


def test_original_upstream_integer_page_still_reuses_documented_area_provisionally():
    from pb_ceiling_lining_quantity import build_ceiling_lining_quantity
    from tests.test_c15_ceiling_lining_quantity import (
        _area_quantity, _finish_atom, SCOPE_ID,
    )
    actual=build_ceiling_lining_quantity(
        scope_entity_id=SCOPE_ID,area_quantity=_area_quantity(),
        finish_evidence_atoms=(_finish_atom(),),
        context=_context(),document=_document(),viewport=_viewport(),page_no=1,
    )
    assert not actual.abstained
    assert actual.value == _area_quantity().value
