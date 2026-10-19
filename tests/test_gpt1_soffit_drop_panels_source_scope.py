"""Global soffit area and per-drop-panel dimensions are different source scopes."""
from pb_formwork_trade_authority import FormworkElementSpec,calculate_soffit_formwork_items

def _slab(**args):
    fields=dict(element_type="soffit",element_id="synthetic-slab",section="Structure",
      description="synthetic soffit",area_m2=100.0,count=4,
      length_m=2.0,width_m=2.0,depth_m=0.15)
    fields.update(args)
    return FormworkElementSpec(**fields)

def test_source_soffit_area_and_repeated_drop_panel_dimensions_both_survive():
    out=calculate_soffit_formwork_items(_slab())
    assert len(out)==2
    assert out[0].quantity==100.0
    assert out[0].unit=="m²"
    assert out[1].quantity==20.8
    assert out[1].inclusion_status=="PROVISIONAL"

def test_without_source_panel_depth_global_area_and_explicit_axes_must_agree():
    assert calculate_soffit_formwork_items(_slab(depth_m=0.0))==[]

def test_plain_independently_figured_global_soffit_area_is_still_preserved():
    out=calculate_soffit_formwork_items(_slab(
        count=1,depth_m=0.0,length_m=10.0,width_m=10.0
    ))
    assert len(out)==1 and out[0].quantity==100.0
