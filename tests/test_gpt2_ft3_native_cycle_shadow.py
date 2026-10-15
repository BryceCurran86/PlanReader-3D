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

def test_sub_rounding_gap_is_not_an_exact_source_junction():
    # Before the fix rounding to 4dp incorrectly closed this native gap.
    ds = [
        drawing((0, 0), (2, 0)),
        drawing((2, 0), (2, 2)),
        drawing((2, 2), (0, 2)),
        drawing((0, 2.00004), (0, 0)),
    ]
    before = repr(ds)
    r = inspect_native_component(Page(ds), "d0i0")
    assert r["component_edge_count"] == 4
    assert not r["complete_exact_cycle"]
    degrees = {tuple(entry["point"]): entry["degree"] for entry in r["endpoint_degrees"]}
    assert degrees[(0.0, 2.0)] == 1
    assert degrees[(0.0, 2.00004)] == 1
    assert repr(ds) == before


def test_sub_rounding_source_edge_is_not_erased():
    # Five real native edges, one tiny edge previously quantised to zero.
    ds = [
        drawing((0, 0), (2, 0)),
        drawing((2, 0), (2, 2)),
        drawing((2, 2), (0, 2)),
        drawing((0, 2), (0, 0.00003)),
        drawing((0, 0.00003), (0, 0)),
    ]
    r = inspect_native_component(Page(ds), "d0i0")
    assert r["component_edge_count"] == 5
    assert r["complete_exact_cycle"]
    assert {edge["id"] for edge in r["source_segments"]} == {
        "d0i0", "d1i0", "d2i0", "d3i0", "d4i0"
    }


def test_shared_endpoint_branch_stays_ambiguous_and_preserves_all_edges():
    ds = [
        drawing((0, 0), (2, 0)), drawing((2, 0), (2, 2)),
        drawing((2, 2), (0, 2)), drawing((0, 2), (0, 0)),
        drawing((2, 2), (3, 3)), drawing((3, 3), (4, 2)),
        drawing((4, 2), (2, 2)),
    ]
    r = inspect_native_component(Page(ds), "d0i0")
    assert r["component_edge_count"] == 7
    assert not r["complete_exact_cycle"]
    assert not r["role_granted"]
    assert r["structural_role"] == "UNRESOLVED"
