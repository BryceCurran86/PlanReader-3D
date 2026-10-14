"""Authentic isolated G17 lineage is available without publishing a host."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

import pb_opening_host_binding_authority as host
from pb_migration_contracts import EvidenceResolutionStatus


def fixture(monkeypatch):
    rows=[
        ("f1","raster_wall_band_face",(-5.,-1.,0.,-1.)),
        ("f2","raster_wall_band_face",(-5.,1.,0.,1.)),
        ("e1","raster_wall_band_end",(0.,-1.,0.,1.)),
        ("f3","raster_wall_band_face",(10.,-1.,15.,-1.)),
        ("f4","raster_wall_band_face",(10.,1.,15.,1.)),
        ("e2","raster_wall_band_end",(10.,-1.,10.,1.)),
        ("ink1","raster_line_run",(0.,0.,10.,0.)),
    ]
    receipts={}
    for id,kind,geo in rows:
        receipts[id]=SimpleNamespace(
            observation_id=id,document_id="doc",revision_id="rev",
            source_sha256="a"*64,snapshot_id="source-snapshot",
            page_id="3",derivation_parent_ids=("parent-"+id,),
            source_primitive_ref="visible:raster_opening_primitive:original-rect:"+id,
            observation_kind=kind,geometry=geo,
        )
    class FakeVisibility:
        def __init__(self):
            self.receipts=receipts
        def resolve_raster_opening_primitive(self, selector):
            obj=self.receipts.get(selector.observation_id)
            if obj is None or (selector.document_id!=obj.document_id
                or selector.revision_id!=obj.revision_id
                or selector.source_sha256!=obj.source_sha256
                or selector.snapshot_id!=obj.snapshot_id):
                return SimpleNamespace(status=EvidenceResolutionStatus.ABSTAINED,observation=None)
            return SimpleNamespace(status=EvidenceResolutionStatus.CORROBORATED,observation=obj)
    monkeypatch.setattr(host,"SourceVisibilityAuthority",FakeVisibility)
    vis=FakeVisibility()
    authority=SimpleNamespace(source_visibility_authority=lambda:vis)
    opening=SimpleNamespace(
        document_id="doc",revision_id="rev",source_sha256="a"*64,
        snapshot_id="source-snapshot",page_id="3",
        source_observation_ids=tuple(receipts),
    )
    return authority,opening,vis


def test_separately_authenticated_original_g17_lines_include_exact_six_source_refs(monkeypatch):
    auth,opening,vis=fixture(monkeypatch)
    before=deepcopy(vis.receipts)
    actual=host._authenticated_isolated_g17_source_lines(auth,opening)
    assert len(actual)==6
    assert all(x.startswith("raster_opening_primitive:") for x in actual)
    assert set(actual)=={"raster_opening_primitive:original-rect:"+x for x
                        in ("f1","f2","e1","f3","f4","e2")}
    assert actual["raster_opening_primitive:original-rect:e1"]==(0.,-1.,0.,1.)
    assert vis.receipts==before
    assert "raster_opening_primitive:original-rect:ink1" not in actual


def test_source_observation_order_invariance(monkeypatch):
    auth,opening,_=fixture(monkeypatch)
    expected=host._authenticated_isolated_g17_source_lines(auth,opening)
    opening.source_observation_ids=tuple(reversed(opening.source_observation_ids))
    assert host._authenticated_isolated_g17_source_lines(auth,opening)==expected


@pytest.mark.parametrize("change",[
    "foreign_page","foreign_sha","foreign_snapshot","duplicate_id","duplicate_parent",
    "missing_face","missing_inner_cap","raster_ref_spoof","conflicting_geometry",
    "unsupported_primitive_kind","conflicting_producer","ordinary_instead",
])
def test_malformed_or_untrusted_source_never_becomes_lineage_member(monkeypatch,change):
    auth,opening,vis=fixture(monkeypatch)
    if change=="foreign_page":
        vis.receipts["f1"].page_id="99"
    elif change=="foreign_sha":
        vis.receipts["f1"].source_sha256="b"*64
    elif change=="foreign_snapshot":
        opening.snapshot_id="foreign"
    elif change=="duplicate_id":
        opening.source_observation_ids=("f1","f1",*opening.source_observation_ids[1:])
    elif change=="duplicate_parent":
        vis.receipts["f2"].derivation_parent_ids=("parent-f1",)
    elif change=="missing_face":
        opening.source_observation_ids=tuple(x for x in opening.source_observation_ids if x!="f1")
    elif change=="missing_inner_cap":
        opening.source_observation_ids=tuple(x for x in opening.source_observation_ids if x!="e1")
    elif change=="raster_ref_spoof":
        vis.receipts["f1"].source_primitive_ref="visible:raster_segment:forged"
    elif change=="conflicting_geometry":
        vis.receipts["f1"].geometry=(0.,0.,0.,0.)
    elif change=="unsupported_primitive_kind":
        vis.receipts["f1"].observation_kind="raster_door_tag"
    elif change=="conflicting_producer":
        vis.receipts["f1"].derivation_parent_ids=()
    else:
        vis.receipts["f1"].observation_kind="native_pdf_visible_segment"
    assert host._authenticated_isolated_g17_source_lines(auth,opening)=={}


def test_only_g17_original_source_reader_is_used(monkeypatch):
    auth,opening,vis=fixture(monkeypatch)
    class NotActualVisibility:
        def resolve_raster_opening_primitive(self,selector):
            raise RuntimeError("fake producer must not be queried")
    auth.source_visibility_authority=lambda:NotActualVisibility()
    assert host._authenticated_isolated_g17_source_lines(auth,opening)=={}
