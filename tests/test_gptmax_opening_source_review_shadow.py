"""Exercise source-owned review projections without bypassing authorities."""
from dataclasses import asdict, replace
import json
import zipfile

import fitz
import pytest

from pb_opening_source_review_shadow import (
    aperture_geometry_shadow, transform_aperture_point_shadow,
    opening_source_lineage_packet, build_opening_review_packets,
    compare_opening_source_correspondence, nominal_opening_obj_shadow,
)
from pb_nominal_opening_canonical_shadow import build_nominal_opening_canonical_shadow
from tools.recover_source_preserving_openings_shadow import recover_source_preserving_openings_pages_shadow
from tools.build_opening_source_review_package import build_opening_source_review_package
from test_raster_connected_host_frame import _fixture
from test_opening_label_dimension_authority import _pdf, _ingest, _opening_selector
from test_gptmax_source_geometry_recovery_batch import source


@pytest.mark.parametrize("transform",[{},dict(dx=35,dy=20),dict(rotation=1),dict(rotation=2),
    dict(scale=2),dict(unrelated=True)])
def test_owned_local_geometry_and_coordinate_transform_are_reversible(transform):
    p,c,_producer,bound=_fixture(**transform)
    before=tuple(asdict(x) for x in c.opening_bindings)
    for selector,opening,*_ in bound:
        geometry=aperture_geometry_shadow(p,selector)
        assert geometry["opening_identity_id"]==opening.record_id
        assert len(geometry["polygon_pt"])==4
        assert geometry["metric_geometry_resolved"] is False
        for point in ((0.,0.),(geometry["span_pt"],geometry["band_thickness_pt"]/2),(-1.,2.)):
            page=transform_aperture_point_shadow(p,selector,point,to_page=True)
            assert transform_aperture_point_shadow(p,selector,page)==pytest.approx(point)
        assert aperture_geometry_shadow(p,selector)==geometry
    assert tuple(asdict(x) for x in c.opening_bindings)==before


@pytest.mark.parametrize("point",[(float("nan"),0),(1,float("inf")),(True,0),(),(1,2,3)])
def test_bad_coordinate_values_cannot_enter_source_projection(point):
    p,_c,_producer,bound=_fixture()
    with pytest.raises(ValueError):transform_aperture_point_shadow(p,bound[0][0],point)


def test_lineage_packet_preserves_every_parent_and_refuses_foreign_label():
    p,c,_producer,bound=_fixture()
    selector=bound[0][0]
    packet=opening_source_lineage_packet(p,selector)
    assert packet["source_proof_closed"] is True
    assert packet["authority_import_allowed"] is False
    ids={r["observation_id"] for r in packet["observations"]}
    assert set(packet["roots"])<=ids
    assert all(set(r["derivation_parent_ids"])<=ids for r in packet["observations"])
    with pytest.raises(ValueError):opening_source_lineage_packet(p,selector,additional_text_ids=("foreign",))
    assert aperture_geometry_shadow(p,replace(selector,source_sha256="0"*64)) is None
    reviews=build_opening_review_packets(p,c)
    assert len(reviews)==2
    assert all(r["takeoff_eligible"] is False and r["deduction_authority"] is False for r in reviews)
    assert all(r["local_aperture_frame"]["status"]=="candidate" for r in reviews)
    assert all(r["local_aperture_frame"]["evidence"]["whole_wall_frame_id"] is None for r in reviews)
    assert all(r["source_related_wall_candidates"] for r in reviews)
    assert build_opening_review_packets(p,c)==reviews
    correspond=compare_opening_source_correspondence(reviews,reviews)
    assert all(len(r["exact_source_support_original_ids"])==1 for r in correspond)
    assert all(r["physical_identity_alias_granted"] is False for r in correspond)


def test_source_correspondence_retains_all_exact_alternatives_without_alias():
    from copy import deepcopy
    p,c,*_=_fixture()
    packet=build_opening_review_packets(p,c)[0]
    other=deepcopy(packet);other["packet_id"]+="_other";other["opening_identity_id"]="second"
    result=compare_opening_source_correspondence((other,packet),(packet,))[0]
    assert set(result["exact_source_support_original_ids"])=={packet["opening_identity_id"],"second"}
    assert result["physical_identity_alias_granted"] is False
    foreign=deepcopy(packet);foreign["physical_opening"]["source_sha256"]="0"*64
    assert not compare_opening_source_correspondence((packet,),(foreign,))[0]["exact_source_support_original_ids"]


def test_nominal_3d_asset_is_a_flat_unplaced_face_and_never_invents_depth():
    p,pub=_ingest(_pdf(labels=((88.,124.,"2127 STACKER"),)),"nominal-obj")
    opening=build_nominal_opening_canonical_shadow(p,_opening_selector(p,pub))
    asset=nominal_opening_obj_shadow(opening)
    vertices=[tuple(map(float,line.split()[1:])) for line in asset.splitlines() if line.startswith("v ")]
    assert vertices==[(0,0,0),(2.7,0,0),(2.7,0,2.1),(0,0,2.1)]
    assert asset.count("\nf ")==2
    opening.wall_id="unapproved"
    with pytest.raises(ValueError):nominal_opening_obj_shadow(opening)


def test_fork_replays_each_original_revision_without_copying_observations():
    p,first=source()
    second=p.ingest_native_pdf_bytes(document_id="original",source_bytes=_pdf(labels=()),
        source_locator="memory://revision-2.pdf",page_ids=(1,))
    fork,replay=p.fork_native_source_shadow(second.revision.revision_id,
        include_revision_ancestry_shadow=True,raster_paired_outer_faces_shadow=True)
    assert replay.revision.supersedes_revision_id==first.revision.revision_id
    assert fork._producer._store is not p._producer._store
    assert set(fork._producer._store.revisions)==set(p._producer._store.revisions)
    assert fork._producer.current_revision_id("original")==second.revision.revision_id
    assert p.published_snapshot_for_revision(second.revision.revision_id) is second
    p._producer._store.source_bytes_by_revision[first.revision.revision_id]=b"damaged ancestor"
    with pytest.raises(ValueError):p.fork_native_source_shadow(second.revision.revision_id,
        include_revision_ancestry_shadow=True)


def test_multi_page_recovery_keeps_original_issuer_and_builds_portable_package(tmp_path):
    p,pub=source()
    document=fitz.open(stream=_pdf(labels=((88.,124.,"2127 STACKER"),)),filetype="pdf")
    document.fullcopy_page(0)
    payload=document.tobytes();document.close()
    pub=p.ingest_native_pdf_bytes(document_id="two-pages",source_bytes=payload,
        source_locator="memory://two.pdf",page_ids=(1,2))
    batch=recover_source_preserving_openings_pages_shadow(p,revision_id=pub.revision.revision_id,
        page_ids=("2","1"),exact_nomination_shadow=True,source_fragment_roles_shadow=True)
    assert batch["page_ids"]==("1","2")
    assert batch["original_issuer_body_unchanged_during_fork"] is True
    assert len(batch["page_reports"])==2
    assert {r["page_id"] for report in batch["page_reports"] for r in report["alternate_opening_review_packets"]}=={"1","2"}
    report=batch["page_reports"][0]
    assert report["new_authority_promotion_granted"] is False
    a,b=tmp_path/"a.zip",tmp_path/"b.zip"
    build_opening_source_review_package(report,a);build_opening_source_review_package(report,b)
    assert a.read_bytes()==b.read_bytes()
    with zipfile.ZipFile(a) as archive:
        names=archive.namelist()
        assert "review.html" in names and "source-evidence-work-queue.csv" in names
        assert any(n.endswith(".obj") for n in names)
        assert all(not n.endswith((".pdf",".png",".jpg")) for n in names)
        html=archive.read("review.html").decode()
        assert "__OPENING_REVIEW_DATA__" not in html and "https://" not in html
        manifest=json.loads(archive.read("manifest.json"))
        from hashlib import sha256
        assert all(sha256(archive.read(r["path"])).hexdigest()==r["sha256"] for r in manifest["entries"])
    with pytest.raises(ValueError):build_opening_source_review_package(report,tmp_path/"source.pdf")


def test_missing_original_source_parent_is_first_review_evidence_gate(monkeypatch):
    import pb_opening_source_review_shadow as review
    source, composition, *_ = _fixture()
    authentic = review.opening_source_lineage_packet

    def unresolved(*args, **kwargs):
        lineage = authentic(*args, **kwargs)
        if lineage is None:
            return None
        return {**lineage, "source_proof_closed": False,
                "unresolved_parent_ids": ("missing-parent",)}

    monkeypatch.setattr(review, "opening_source_lineage_packet", unresolved)
    packets = review.build_opening_review_packets(source, composition)
    positive = [p for p in packets if p["physical_opening"] is not None]
    assert positive
    assert all(p["next_required_evidence"][0] == "original_source_parent_lineage"
               for p in positive)
    assert all(p["source_lineage"]["unresolved_parent_ids"] == ("missing-parent",)
               and not p["takeoff_eligible"] and not p["deduction_authority"]
               for p in positive)
