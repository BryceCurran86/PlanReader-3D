"""Hostile read-only source component tests: no structural role granted."""
from tools.diag_gpt2_ft3_native_cycle_shadow import inspect_native_component

class P:
    def __init__(self,x,y):
        self.x=x;self.y=y

class Page:
    def __init__(self, drawings):
        self.drawings=drawings
    def get_drawings(self):
        return self.drawings

def item(a,b):
    return ("l",P(*a),P(*b))

def drawing(a,b,width=.48,color=(0,0,0)):
    return {"items":[item(a,b)],"width":width,"color":color,"fill":None,"layer":"","dashes":"[] 0","type":"s"}

def test_closed_mark_candidate_never_promotes_role():
    ds=[drawing((0,0),(2,0)),drawing((2,0),(2,2)),drawing((2,2),(0,2)),drawing((0,2),(0,0))]
    baseline=repr(ds)
    result=inspect_native_component(Page(ds),"d0i0")
    assert result["complete_exact_cycle"] is True
    assert result["component_edge_count"]==4
    assert result["role_granted"] is False
    assert result["structural_role"]=="UNRESOLVED"
    assert repr(ds)==baseline

def test_real_closed_structural_room_is_not_suppressed():
    ds=[drawing((0,0),(2,0)),drawing((2,0),(2,2)),drawing((2,2),(0,2)),drawing((0,2),(0,0))]
    r=inspect_native_component(Page(ds),"d0i0")
    assert r["complete_exact_cycle"]
    assert not r["role_granted"]

def test_broken_cycle_and_mixed_style_are_not_elected():
    ds=[drawing((0,0),(2,0)),drawing((2,0),(2,2)),drawing((2,2),(0,2),width=.24)]
    r=inspect_native_component(Page(ds),"d0i0")
    assert not r["complete_exact_cycle"]
    assert r["component_edge_count"]==2

def test_crossing_and_conflict_retained_not_joined_by_proximity():
    ds=[drawing((0,0),(2,0)),drawing((2,0),(2,2)),
        drawing((2,2),(0,2)),drawing((0,2),(0,0)),
        drawing((2.001,0),(2.001,2),color=(.5,.5,.5))]
    r=inspect_native_component(Page(ds),"d0i0")
    assert r["complete_exact_cycle"]
    assert r["component_edge_count"]==4
    assert not r["role_granted"]

def test_seed_missing_abstains():
    r=inspect_native_component(Page([]),"d999i0")
    assert r["status"]=="SEED_NOT_FOUND"
    assert r["role_granted"] is False
