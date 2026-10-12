"""Q02 native ceiling source page/viewport must be exact, not coerced."""
from dataclasses import replace

import pytest

from pb_live_ceiling_area_quantity_publication import publish_live_ceiling_area_quantities
from pb_live_ceiling_area_source_closed_export import build_live_ceiling_area_source_traces
from tests.test_live_ceiling_area_quantity_publication import _ceiling,_shadow_quantity,_result


def test_original_documented_ceiling_still_publishes_exact_source_area():
    source=_result()
    quantities=publish_live_ceiling_area_quantities(source)
    assert len(quantities)==1
    assert quantities[0].value==13.270425
    traces=build_live_ceiling_area_source_traces(
        source,workspace_id=7,project_id="source-project",
    )
    assert len(traces)==1


@pytest.mark.parametrize("page", [True,1.0,"1",0,-1,None])
def test_forged_ceiling_page_cannot_publish_even_if_shadow_aliases_it(page):
    ceiling=replace(_ceiling(),source_page=page)
    shadow=_shadow_quantity()
    source=replace(shadow,metadata={
        **dict(shadow.metadata),"page_no":page,
    })
    result=_result(ceiling=ceiling,shadow=source)
    assert publish_live_ceiling_area_quantities(result)==()
    assert build_live_ceiling_area_source_traces(
        result,workspace_id=7,project_id="source-project",
    )=={}


@pytest.mark.parametrize("viewport",[True," vp-1","vp-1 ",None,1,""])
def test_forged_ceiling_viewport_cannot_mint_documented_area(viewport):
    ceiling=replace(_ceiling(),viewport_id=viewport)
    shadow=_shadow_quantity()
    source=replace(shadow,metadata={
        **dict(shadow.metadata),"viewport_id":viewport,
    })
    result=_result(ceiling=ceiling,shadow=source)
    assert publish_live_ceiling_area_quantities(result)==()
