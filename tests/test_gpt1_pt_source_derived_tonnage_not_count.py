"""No tendon/stressing quantity may be commercially verified from defaults."""
from __future__ import annotations
import pytest
from pb_post_tension_trade_authority import (
    PTExtractionSpec,calculate_pt_slab_items,calculate_pt_band_beam_items,
)


def _slab(**kwargs):
    fields=dict(element_type="pt_slab",element_id="source-neutral",
        section="Structure",description="synthetic source slab",
        area_m2=400.0,thickness_m=.20)
    fields.update(kwargs)
    return PTExtractionSpec(**fields)


def _beam(**kwargs):
    fields=dict(element_type="pt_band_beam",element_id="source-neutral-beam",
        section="Structure",description="synthetic source band beam",
        length_m=30.0,width_m=1.2,thickness_m=.45)
    fields.update(kwargs)
    return PTExtractionSpec(**fields)


def test_default_tendon_density_not_certified_as_measured_count():
    rows=calculate_pt_slab_items(_slab())
    assert len(rows)==7
    tonnes=next(x for x in rows if x.unit=="t")
    assert tonnes.quantity==1.400
    assert tonnes.to_core_row(1,"now")["quantity"]==1.400
    assert all(x.inclusion_status=="PROVISIONAL" for x in rows)
    assert all(x.quantity_status=="Provisional" for x in rows)


def test_original_tendon_area_and_axes_disagreement_must_not_mint_weight_or_ducts():
    assert calculate_pt_slab_items(_slab(
        area_m2=400.0,length_m=20.0,width_m=30.0
    ))==[]


@pytest.mark.parametrize("bad",[True,False,"400",float("nan"),float("inf"),10**400,-1])
def test_untyped_or_invalid_slab_area_cannot_mint_pt_steel(bad):
    assert calculate_pt_slab_items(_slab(area_m2=bad))==[]


@pytest.mark.parametrize("bad",[True,False,2.5,"4",None,0,-1,10**400])
def test_untyped_or_oversized_tendon_strand_count_abstains(bad):
    assert calculate_pt_slab_items(_slab(strands_per_tendon=bad))==[]


@pytest.mark.parametrize("bad",[True,False,"12.7",float("nan"),float("inf"),0,-1])
def test_source_unproved_strand_diameter_abstains(bad):
    assert calculate_pt_slab_items(_slab(strand_diameter_mm=bad))==[]


def test_bonded_default_grouting_still_visible_but_not_verified():
    rows=calculate_pt_slab_items(_slab(is_bonded=True))
    grouting=next(x for x in rows if "grouting" in x.element.lower())
    assert grouting.inclusion_status=="PROVISIONAL"


def test_pt_band_beam_default_two_ducts_is_provisional_not_signed_count():
    rows=calculate_pt_band_beam_items(_beam())
    assert len(rows)==2
    assert rows[0].quantity==30.0
    assert rows[1].quantity==4.0
    assert all(x.inclusion_status=="PROVISIONAL" for x in rows)
