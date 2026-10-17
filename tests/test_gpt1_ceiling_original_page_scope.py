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
    context=_context()
    object.__setattr__(context,"viewport_page_ownership",(("vp-floor-1",2),))
    assert "viewport_page_mismatch" in _blockers(context=context)
