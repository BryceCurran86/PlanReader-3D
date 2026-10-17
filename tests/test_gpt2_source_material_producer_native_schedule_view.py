"""Producer only consumes genuine source CAD schedule when explicitly scoped."""
import hashlib
from pathlib import Path

import fitz
import pytest
import pb_source_material_semantic_authority as materials
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import segment_page_viewports

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _source_two_pages():
    d=fitz.open()
    a=d.new_page(width=350,height=250)
    a.insert_text((40,60),"MATERIAL SCHEDULE")
    d.new_page(width=350,height=250)
    d[1].insert_text((40,60),"FLOOR PLAN")
    raw=d.tobytes()
    d.close()
    src=SourceVisibilityProducer(producer_method="gpt2-shadow-test",
        producer_version="1")
    pub=src.ingest_native_pdf_bytes(
        document_id="synthetic-two-page-source",source_bytes=raw,
        source_locator="memory://source-shadow",
        page_ids=("1","2"))
    return src,pub


def test_producer_page_scope_and_default_unchanged_native_multipath_flag(monkeypatch):
    src,pub=_source_two_pages()
    normal=materials.SourceMaterialSemanticProducer.from_source_visibility_producer(src)
    opted=materials.SourceMaterialSemanticProducer.for_source_native_multipath_schedule_shadow(
        src,page_ids=("2",))
    assert normal._source_native_schedule_page_ids==frozenset()
    assert opted._source_native_schedule_page_ids==frozenset({"2"})
    captured=[]
    def trace(_page,*,page_number,**kwargs):
        captured.append((page_number,dict(kwargs)))
        return []
    monkeypatch.setattr(materials,"segment_page_viewports",trace)
    normal.publish(pub.revision.revision_id)
    assert captured==[(1,{}),(2,{})]
    captured.clear()
    opted.publish(pub.revision.revision_id)
    assert captured==[
        (1,{}),
        (2,{"source_connected_table_cell_shadow":True,
            "source_native_multipath_semantic_frame_shadow":True}),
    ]
    assert opted.published_plan_viewports()==()
    assert normal.published_plan_viewports()==()


def test_original_a120_real_schedule_recovers_without_physical_rcp_m2():
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    with fitz.open(stream=raw,filetype="pdf") as doc:
        page=doc[8]
        default=segment_page_viewports(page,page_number=9)
        source=segment_page_viewports(page,page_number=9,
            source_connected_table_cell_shadow=True,
            source_native_multipath_semantic_frame_shadow=True)
        assert {x.view_id:x for x in default}["view_p9_4"].status=="resolved"
        by_id={x.view_id:x for x in source}
        table=by_id["view_p9_4"]
        assert table.status=="resolved"
        assert all(abs(a-b)<.02 for a,b in zip(
            table.bounding_box,(1393.68,416.,1496.4,991.04)))
        assert by_id["view_p9_5"].status=="ambiguous"
        assert by_id["view_p9_5"].bounding_box is None
        assert by_id["view_p9_5"].provenance.get(
            "independent_plan_extent_unproven") is True
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()==SHA


def test_invalid_schedule_page_scope_never_enables_original_source_mode():
    src,_pub=_source_two_pages()
    for ids in ((),("0",),("01",),("two",),("2","1.5"),"2",["2",2]):
        with pytest.raises(ValueError):
            materials.SourceMaterialSemanticProducer.for_source_native_multipath_schedule_shadow(
                src,page_ids=ids)

def test_scoped_original_schedule_page_not_in_source_revision_is_not_silent_empty():
    src, pub = _source_two_pages()
    material = materials.SourceMaterialSemanticProducer.for_source_native_multipath_schedule_shadow(
        src, page_ids=("3",))
    with pytest.raises(ValueError, match="outside_published_source_coverage"):
        material.publish(pub.revision.revision_id)
    # No phantom original schedule or physical ceiling result can be issued.
    assert material.published_plan_viewports() == ()

def test_explicit_source_schedule_requires_an_existing_producer_revision():
    src, _pub = _source_two_pages()
    material = materials.SourceMaterialSemanticProducer.for_source_native_multipath_schedule_shadow(
        src, page_ids=("2",))
    with pytest.raises(ValueError, match="original_schedule_source_revision_unavailable"):
        material.publish("nonexistent-private-source-revision")
    assert material.published_plan_viewports() == ()

@pytest.mark.parametrize("drawing_title", [
    "GRID REFLECTED CEILING PLAN",
    "GRID CEILING PLAN",
    "GRID CEILING LAYOUT PLAN",
    "REFLECTED CEILING GRID PLAN",
    "CEILING GRID LAYOUT PLAN",
])
def test_source_grid_drawing_titles_are_not_ceiling_material_mark_occurrences(drawing_title):
    # A material-code word in a complete sheet title is not the printed
    # occurrence of that material on an individual physical ceiling.
    assert materials._source_owned_material_codes_in_line(
        drawing_title, {"GRID": {}}
    ) == ()
    assert materials._source_owned_material_codes_in_line(
        "GRID", {"GRID": {}}
    ) == ("GRID",)
