import pytest
from tools.diag_gpt2_page9_original_rcp_firstgate import audit

def test_wrong_source_sha_must_fail_before_viewport_detection():
    with pytest.raises(ValueError,match="source_sha_mismatch"):
        audit(b"unrelated source bytes")

def test_source_page_universe_must_be_31(monkeypatch):
    from tools import diag_gpt2_page9_original_rcp_firstgate as module
    import hashlib
    monkeypatch.setattr(module, "SOURCE_SHA", hashlib.sha256(b"test").hexdigest())
    import fitz
    doc = fitz.open()
    doc.new_page()
    payload = doc.tobytes()
    doc.close()
    monkeypatch.setattr(module, "SOURCE_SHA", hashlib.sha256(payload).hexdigest())
    with pytest.raises(ValueError, match="source_page_universe_mismatch"):
        audit(payload)


def test_gpt2_source_viewport_type_token_matches_string_and_producer_enum():
    from tools.diag_gpt2_page9_original_rcp_firstgate import _producer_token
    from pb_drawing_evidence_binding import DrawingViewType
    from enum import Enum

    class Status(Enum):
        RESOLVED="resolved"

    assert _producer_token(DrawingViewType.REFLECTED_CEILING_PLAN)==(
        "reflected_ceiling_plan"
    )
    assert _producer_token("reflected_ceiling_plan")=="reflected_ceiling_plan"
    assert _producer_token(Status.RESOLVED)=="resolved"
    assert _producer_token(None)==""
    assert _producer_token(73)==""


def test_gpt2_original_and_proposed_rcp_title_anchors_cannot_cross_bind():
    from tools.diag_gpt2_page9_original_rcp_firstgate import _title_identity

    assert _title_identity("REFLECTED CEILING PLAN", "Reflected  Ceiling Plan")
    assert not _title_identity(
        "ORIGINAL REFLECTED CEILING PLAN", "PROPOSED REFLECTED CEILING PLAN"
    )
    assert not _title_identity("", "REFLECTED CEILING PLAN")
    assert not _title_identity(None, "REFLECTED CEILING PLAN")
    assert not _title_identity("RCP", 3)

def test_gpt2_rcp_nearest_original_vector_frame_never_grants_ownership():
    from tools.diag_gpt2_page9_original_rcp_firstgate import (
        _nearest_native_frames_to_title,
    )
    source_title=(0.,0.,10.,10.)
    frames=(
        (14.,0.,24.,10.),
        (10.,0.,20.,10.),
        (200.,200.,300.,300.),
    )
    rows=_nearest_native_frames_to_title(source_title,frames)
    assert len(rows)==3
    assert [r["title_to_frame_native_distance_pdf_pts"] for r in rows]==[
        0.0,4.0,268.700577
    ]
    assert all(r["original_vector_frame_not_title_owned"] for r in rows)


def test_gpt2_rcp_nearby_native_frame_unavailable_when_geometry_bad():
    from tools.diag_gpt2_page9_original_rcp_firstgate import (
        _nearest_native_frames_to_title,
    )
    assert _nearest_native_frames_to_title(None,())==[]
    assert _nearest_native_frames_to_title((0,0,0,10),((0,0,5,5),))==[]
    assert _nearest_native_frames_to_title((0,0,10,10),(
        (1,1,float("nan"),5),(1,1,0,5),("bad",1,2,3)
    ))==[]



def test_indexed_original_frame_receipts_include_every_candidate_shape():
    from tools.diag_gpt2_page9_original_rcp_firstgate import _frame_source_receipts
    from pb_viewport_segmentation import ViewportLayoutCalibration

    class Point:
        def __init__(self, x, y):
            self.x, self.y = x, y

    class Rect:
        x0, y0, x1, y1 = 0., 0., 50., 80.

    class Page:
        def get_drawings(self):
            return [
                {"items": [("re", Rect())]},
                {"items": [
                    ("l", Point(0, 0), Point(50, 0)),
                    ("l", Point(50, 0), Point(50, 80)),
                    ("l", Point(50, 80), Point(0, 80)),
                    ("l", Point(0, 80), Point(0, 0)),
                ]},
                {"items": [("re", Rect())]},
                {"items": [("l", Point(200, 0), Point(250, 0))]},
            ]

    cal = ViewportLayoutCalibration(
        median_word_height_pt=5.,
        title_frame_gap_pt=10.,
        minimum_frame_span_pt=20.,
        title_separation_pt=10.,
        page_width_pt=500.,
        page_height_pt=500.,
    )
    original = Page()
    first = _frame_source_receipts(original, (0., 0., 50., 80.), cal)
    assert len(first) == 3
    assert sorted(tuple(q["native_source_ids"]) for q in first) == [
        ("d0i0",), ("d1i0", "d1i1", "d1i2", "d1i3"), ("d2i0",)
    ]
    assert all(q["candidate_source_match_not_authority"] for q in first)
    assert _frame_source_receipts(original, (250., 0., 300., 80.), cal) == []


def test_frame_title_competitors_remain_candidates_not_owner():
    from types import SimpleNamespace
    from tools.diag_gpt2_page9_original_rcp_firstgate import _frame_ownership_matrix
    import pb_viewport_segmentation as seg

    class Page:
        rotation = 0
        def get_drawings(self):
            return []
        def get_text(self, mode):
            return {"blocks": []} if mode == "dict" else []

    original = Page()
    cal = seg.ViewportLayoutCalibration(5., 10., 20., 10., 500., 500.)
    frame = (0., 0., 100., 100.)
    anchors = (
        SimpleNamespace(text="ONE PLAN", bbox=(10., 105., 30., 110.),
                        direction=(1., 0.), view_type="reflected_ceiling_plan"),
        SimpleNamespace(text="OTHER PLAN", bbox=(45., 105., 65., 110.),
                        direction=(1., 0.), view_type="reflected_ceiling_plan"),
    )
    result = _frame_ownership_matrix(original, (frame,), anchors, cal)
    assert result["diagnostic_only"]
    assert not result["frame_candidate_matrix_grants_authority"]
    row = result["source_frames"][0]
    # Whether candidates pass actual producer geometric gates or not,
    # the report never chooses one owner or mints a viewport.
    assert row["no_source_role_or_viewport_granted"]
    assert all(a["no_source_role_or_viewport_granted"] for a in result["source_titles"])
    assert len(result["source_titles"]) == 2
    assert row["native_frame_bbox_pdf_pts"] == list(frame)


def test_native_and_display_frame_round_trip_at_right_angles():
    import fitz
    from pb_viewport_segmentation import _to_visual_bbox, _to_native_bbox
    pdf = fitz.open()
    page = pdf.new_page(width=300, height=400)
    box = (25., 30., 180., 230.)
    try:
        for rotation in (0, 90, 180, 270):
            page.set_rotation(rotation)
            displayed = _to_visual_bbox(page, box)
            native = _to_native_bbox(page, displayed)
            assert native == pytest.approx(box, abs=1e-4)
    finally:
        pdf.close()



def test_page9_original_source_native_images_are_not_rcp_geometry():
    from types import SimpleNamespace
    from tools.diag_gpt2_page9_original_rcp_firstgate import (
        _source_native_image_placements,
    )
    class Page:
        def get_image_info(self, *, xrefs):
            assert xrefs
            return [
                {"bbox": (0., 0., 20., 20.), "width": 200, "height": 100, "xref": 0},
                {"bbox": (40., 40., 70., 80.), "width": 20, "height": 30, "xref": 28},
            ]
    anchors = [SimpleNamespace(bbox=(5., 5., 10., 10.), text="REFLECTED CEILING PLAN")]
    result = _source_native_image_placements(Page(), anchors)
    assert result["status"] == "SOURCE_IMAGE_PLACEMENTS_COMPLETE"
    assert result["source_image_placement_count"] == 2
    assert result["image_universe_complete"]
    assert result["source_image_placements"][0]["original_xref"] == 0
    assert len(result["source_image_placements"][0]["overlapping_original_source_titles"]) == 1
    assert not result["source_image_placements"][0]["image_pixels_or_viewport_role_proven"]
    assert not result["source_image_placement_is_rcp_role"]


def test_page9_original_image_placement_invalid_does_not_become_no_images():
    from tools.diag_gpt2_page9_original_rcp_firstgate import (
        _source_native_image_placements,
    )
    class Page:
        def get_image_info(self, *, xrefs):
            return [
                {"bbox": (0., 0., float("nan"), 8.), "width": 12, "height": 8, "xref": 2},
                {"bbox": (0., 0., 20., 30.), "width": 12, "height": 8, "xref": 0},
            ]
    result = _source_native_image_placements(Page(), [])
    assert result["status"] == "SOURCE_IMAGE_PLACEMENT_PARTIAL"
    assert not result["image_universe_complete"]
    assert result["invalid_native_image_placement_indices"] == [0]
    assert result["source_image_placement_count"] == 2
    assert len(result["source_image_placements"]) == 1
    assert not result["source_image_placement_is_rcp_role"]


def test_page9_original_image_api_absence_is_unavailable_not_zero():
    from tools.diag_gpt2_page9_original_rcp_firstgate import (
        _source_native_image_placements,
    )
    result = _source_native_image_placements(object(), ())
    assert result["status"] == "SOURCE_IMAGE_API_UNAVAILABLE"
    assert not result["image_universe_complete"]
    assert not result["source_image_placement_is_rcp_role"]


from tools.diag_gpt2_page9_original_rcp_firstgate import (
    _original_title_frame_relation,
)

@pytest.mark.parametrize("frame,relation",[
    ((0.,0.,30.,30.),"frame_strictly_contains_title"),
    ((10.,10.,30.,30.),"frame_contains_title_on_boundary"),
    ((14.,14.,28.,28.),"title_contains_original_frame"),
    ((15.,0.,25.,20.),"partial_native_overlap"),
    ((20.,10.,40.,30.),"boundary_contact_only"),
    ((40.,40.,70.,70.),"source_geometries_disjoint"),
])
def test_gpt2_all_original_title_frame_relations_survive(frame,relation):
    title=(10.,10.,20.,20.)
    result=_original_title_frame_relation(title,frame)
    assert result["original_native_geometric_relation"]==relation
    assert not result["title_owns_physical_viewport"]
    assert not result["title_frame_structural_ownership_proven"]


def test_gpt2_no_nearest_four_source_truncation_while_all_rivals_retained():
    from tools.diag_gpt2_page9_original_rcp_firstgate import (
        _nearest_native_frames_to_title,
    )
    frames=[(10.*i,50.,10.*i+9.,60.) for i in range(8)]
    rows=_nearest_native_frames_to_title((0.,0.,9.,9.),frames)
    assert len(rows)==8
    assert all(r["original_vector_frame_not_title_owned"] for r in rows)
    assert len(_nearest_native_frames_to_title(
        (0.,0.,9.,9.),list(reversed(frames))
    ))==8
    assert rows==_nearest_native_frames_to_title(
        (0.,0.,9.,9.),list(reversed(frames))
    )
    with pytest.raises(ValueError,match="nonpositive"):
        _nearest_native_frames_to_title((0.,0.,9.,9.),frames,limit=0)


@pytest.mark.parametrize("bad",[
    (0,0,0,12),(0,0,13,0),
    (0,0,float("nan"),10),
    (0,0,float("inf"),10),
    ("0",0,10,10),
    (True,0,10,10),
])
def test_gpt2_title_frame_relation_invalid_source_geometry_fails_closed(bad):
    with pytest.raises(ValueError,match="invalid original title/frame geometry"):
        _original_title_frame_relation(bad,(0.,0.,20.,20.))


def test_gpt2_source_native_title_relation_matrix_never_grants_rcp():
    from types import SimpleNamespace
    from tools.diag_gpt2_page9_original_rcp_firstgate import _frame_ownership_matrix
    import pb_viewport_segmentation as seg
    class Page:
        rotation=0
        def get_drawings(self):
            return []
        def get_text(self,mode):
            return {"blocks": []} if mode=="dict" else []
    cal=seg.ViewportLayoutCalibration(5.,10.,20.,10.,500.,500.)
    frames=((0.,0.,100.,100.),(120.,120.,160.,160.))
    anchors=(
        SimpleNamespace(text="REFLECTED CEILING PLAN",
                        bbox=(10.,10.,20.,20.),direction=(1.,0.),
                        view_type="reflected_ceiling_plan"),
        SimpleNamespace(text="PROP. REFLECTED CEILING PLAN",
                        bbox=(125.,125.,135.,135.),direction=(1.,0.),
                        view_type="reflected_ceiling_plan"),
    )
    report=_frame_ownership_matrix(Page(),frames,anchors,cal)
    assert not report["frame_candidate_matrix_grants_authority"]
    assert all(len(t["all_original_native_frame_relations"])==2
               for t in report["source_titles"])
    assert all(t["all_original_native_frames_evaluated"]
               and not t["original_frame_relationships_grant_role"]
               for t in report["source_titles"])
    assert all(not row["title_owns_physical_viewport"]
               for t in report["source_titles"]
               for row in t["all_original_native_frame_relations"])
