"""Synthetic proof for the input path of the shadow-only door-swing figure binding (native arcs, figure words)."""
from __future__ import annotations

import hashlib
import math

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
import pb_door_swing_figure_binding_adapter as ad
import pb_door_swing_figure_binding_shadow as sw
from pb_source_visibility_authority import SourceVisibilityProducer

K = ad.KAPPA


def cubic(cx, cy, r, sx=1, sy=1):
    """Quarter circle about (cx, cy): from (cx+sx*r, cy) to (cx, cy+sy*r)."""
    return ((cx + sx * r, cy), (cx + sx * r, cy + sy * K * r), (cx + sx * K * r, cy + sy * r), (cx, cy + sy * r))


# ------------------------------------------------------------------------------------------------ pure arc recognition
@pytest.mark.parametrize("sx,sy", [(1, 1), (1, -1), (-1, 1), (-1, -1)])
def test_a_true_quarter_circle_is_an_arc_centred_on_its_hinge_in_every_orientation(sx, sy):
    arc = ad.quarter_circle_arc(*cubic(100.0, 100.0, 30.0, sx, sy), "a1", ("a1",))
    assert arc is not None
    assert sw.hinge_corners(arc) == ((100.0, 100.0),)
    assert math.hypot(arc.mx - 100.0, arc.my - 100.0) == pytest.approx(30.0, rel=2e-3)      # the midpoint is one radius out


def test_arcs_with_swapped_endpoints_are_still_centred_on_the_same_hinge():
    p0, p1, p2, p3 = cubic(100.0, 100.0, 30.0)
    arc = ad.quarter_circle_arc(p3, p2, p1, p0, "rev")
    assert arc is not None and sw.hinge_corners(arc) == ((100.0, 100.0),)


def test_look_alike_curves_are_not_quarter_circles():
    p0, p1, p2, p3 = cubic(100.0, 100.0, 30.0)
    assert ad.quarter_circle_arc((130.0, 100.0), (130.0, 106.0), (124.0, 120.0), (100.0, 120.0), "ellipse") is None     # 30 x 20
    flat = ((130.0, 100.0), (130.0, 103.0), (103.0, 130.0), (100.0, 130.0))                   # control points far too short
    assert ad.quarter_circle_arc(*flat, "flat") is None
    s_curve = ((130.0, 100.0), (130.0 + 16.6, 100.0), (100.0 - 16.6, 130.0), (100.0, 130.0))   # tangents parallel, not perpendicular
    assert ad.quarter_circle_arc(*s_curve, "s") is None
    diag = ((130.0, 100.0), (130.0 - 9.0, 100.0 + 9.0), (100.0 + 9.0, 130.0 - 9.0), (100.0, 130.0))
    assert ad.quarter_circle_arc(*diag, "diag") is None                                       # tangents not axis-aligned
    assert ad.quarter_circle_arc((0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0), "zero") is None
    assert ad.quarter_circle_arc((float("nan"), 0.0), p1, p2, p3, "nan") is None


def test_a_non_circular_cubic_with_quarter_circle_control_lengths_is_not_an_arc():
    k = ad.KAPPA * 30.0
    p = ((130.0, 100.0), (130.0, 100.0 + k), (100.0 + k, 120.0), (100.0, 120.0))       # 30 x 20 but control arms of a radius-30 arc
    assert ad.quarter_circle_arc(*p, "squashed") is None


def test_a_diagonal_end_tangent_is_not_an_arc_even_when_the_start_tangent_is_axis_aligned():
    k = ad.KAPPA * 30.0
    d = k / math.sqrt(2.0)
    p = ((130.0, 100.0), (130.0, 100.0 + k), (100.0 + d, 130.0 - d), (100.0, 130.0))
    assert ad.quarter_circle_arc(*p, "diag-end") is None


def test_swing_ink_needs_a_stroke_only_drawing_by_both_markers():
    ink = {"fill": None, "type": "s", "color": (0, 0, 0), "stroke_opacity": 1.0}
    assert ad._is_swing_ink(ink)
    assert not ad._is_swing_ink({**ink, "fill": (0.9, 0.9, 0.9)})                  # a fill, whatever the type says
    assert not ad._is_swing_ink({**ink, "type": "fs"})                              # stroke and fill, whatever the fill says
    assert not ad._is_swing_ink({**ink, "color": (0.5, 0.5, 0.5)})
    assert not ad._is_swing_ink({**ink, "stroke_opacity": 0.5})
    assert not ad._is_swing_ink({**ink, "stroke_opacity": None})


# ------------------------------------------------------------------------------------------------ native drawings
def _pdf_with(draw) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    draw(page)
    return doc.tobytes()


def _bezier(page, pts, **kw):
    page.draw_bezier(*[fitz.Point(*p) for p in pts], **kw)


def _swing_pdf() -> bytes:
    def draw(page):
        _bezier(page, cubic(100.0, 100.0, 30.0), color=(0, 0, 0), width=0.34)                          # a door swing
        _bezier(page, cubic(200.0, 100.0, 30.0), color=(0.7, 0.7, 0.7), width=0.34)                    # grey: not swing ink
        _bezier(page, cubic(100.0, 200.0, 30.0), color=(0, 0, 0), fill=(0.9, 0.9, 0.9), width=0.34, closePath=True)  # filled shape
        _bezier(page, cubic(200.0, 200.0, 30.0), color=(0, 0, 0), width=0.34, stroke_opacity=0.5)      # translucent
        page.draw_oval(fitz.Rect(300, 100, 360, 130), color=(0, 0, 0), width=0.34)                      # an ellipse: four non-square cubics
        page.draw_line((100.0, 100.0), (130.0, 100.0), color=(0, 0, 0), width=0.34)                    # a leaf line is not an arc
    return _pdf_with(draw)


def test_only_opaque_dark_stroke_only_true_quarter_circles_are_swing_arcs():
    payload = _swing_pdf()
    sha = hashlib.sha256(payload).hexdigest()
    arcs = ad.read_native_swing_arcs(payload, expected_sha256=sha, page_number=1)
    assert len(arcs) == 1
    arc = arcs[0]
    assert arc.arc_id.startswith("native-cubic:p1:") and arc.receipt_ids == (arc.arc_id,)
    corners = sw.hinge_corners(arc)
    assert len(corners) == 1 and corners[0] == pytest.approx((100.0, 100.0), abs=0.01)
    assert arcs == ad.read_native_swing_arcs(payload, expected_sha256=sha, page_number=1)           # deterministic


def test_a_hash_mismatch_refuses_the_whole_page():
    payload = _swing_pdf()
    with pytest.raises(ValueError):
        ad.read_native_swing_arcs(payload, expected_sha256="0" * 64, page_number=1)


def test_arcs_are_read_for_the_requested_page_only():
    doc = fitz.open(stream=_swing_pdf(), filetype="pdf")
    page2 = doc.new_page(width=400, height=300)
    page2.draw_bezier(*[fitz.Point(*p) for p in cubic(50.0, 50.0, 20.0)], color=(0, 0, 0), width=0.34)
    payload = doc.tobytes()
    sha = hashlib.sha256(payload).hexdigest()
    one = ad.read_native_swing_arcs(payload, expected_sha256=sha, page_number=1)
    two = ad.read_native_swing_arcs(payload, expected_sha256=sha, page_number=2)
    assert len(one) == 1 and len(two) == 1 and one[0].arc_id != two[0].arc_id and two[0].arc_id.startswith("native-cubic:p2:")


# ------------------------------------------------------------------------------------------------ figure words through the real producers
def _ingest(payload: bytes, pages=(1,)):
    source = SourceVisibilityProducer(producer_method="live-physical-net-wall", producer_version="1")
    sha = hashlib.sha256(payload).hexdigest()
    initial = source.ingest_native_pdf_bytes(document_id=f"live-source:{sha[:32]}", source_bytes=payload,
                                             source_locator="memory://door.pdf", page_ids=pages)
    return source, initial.revision.revision_id


def _door_pdf() -> bytes:
    def draw(page):
        _bezier(page, cubic(100.0, 100.0, 30.0), color=(0, 0, 0), width=0.34)
        page.insert_text((106, 118), "870", fontsize=8)          # inside the swing
        page.insert_text((106, 128), "D1", fontsize=8)           # a tag, not a figure
        page.insert_text((250, 118), "1,200", fontsize=8)        # a figure elsewhere
    return _pdf_with(draw)


def test_figure_words_come_from_text_integrity_receipts_with_a_trust_tag():
    source, revision = _ingest(_door_pdf())
    words = ad.read_figure_words(source, revision_id=revision, page_id="1")
    assert sorted(w.text for w in words) == ["1,200", "870"]                    # the tag is not a figure
    assert all(w.text_trust in ("corroborated", "raw_unverified", "") for w in words)
    assert all(w.receipt_ids == (w.word_id,) and w.x1 > w.x0 and w.y1 > w.y0 for w in words)
    assert len({w.word_id for w in words}) == len(words)
    assert ad.read_figure_words(source, revision_id="source_revision_foreign", page_id="1") == ()
    assert ad.read_figure_words(source, revision_id=revision, page_id="2") == ()             # no words of another page


def test_end_to_end_a_figure_in_the_native_swing_binds_to_the_opening_by_geometry_only():
    payload = _door_pdf()
    sha = hashlib.sha256(payload).hexdigest()
    arcs = ad.read_native_swing_arcs(payload, expected_sha256=sha, page_number=1)
    source, revision = _ingest(payload)
    words = ad.read_figure_words(source, revision_id=revision, page_id="1")
    opening = sw.OpeningEnds("door1", 100.0, 101.0, 130.0, 101.0, 2.5, ("opening-receipt",))
    (binding,) = sw.bind_figures_to_swings([opening], arcs, words, enabled=True)
    assert binding.status is EvidenceResolutionStatus.CANDIDATE and binding.figure_text == "870"
    assert binding.figure_word_id == next(w.word_id for w in words if w.text == "870")
    assert "opening-receipt" in binding.source_observation_ids and arcs[0].arc_id in binding.source_observation_ids
    # the far figure never competes
    assert binding.reason_codes == (sw.SWING_BINDING_CANDIDATE,)


def test_two_figures_in_one_native_swing_abstain_end_to_end():
    def draw(page):
        _bezier(page, cubic(100.0, 100.0, 30.0), color=(0, 0, 0), width=0.34)
        page.insert_text((103, 110), "870", fontsize=8)
        page.insert_text((101, 122), "900", fontsize=8)
    payload = _pdf_with(draw)
    arcs = ad.read_native_swing_arcs(payload, expected_sha256=hashlib.sha256(payload).hexdigest(), page_number=1)
    source, revision = _ingest(payload)
    words = ad.read_figure_words(source, revision_id=revision, page_id="1")
    opening = sw.OpeningEnds("door1", 100.0, 101.0, 130.0, 101.0, 2.5)
    (binding,) = sw.bind_figures_to_swings([opening], arcs, words, enabled=True)
    assert binding.status is EvidenceResolutionStatus.ABSTAINED and binding.reason_codes == (sw.MULTIPLE_FIGURES_IN_SWING,)


# ------------------------------------------------------------------------------------------------ trust tagging (stubbed receipts)
from types import SimpleNamespace   # noqa: E402


def _stub_source(rows):
    """rows: (observation_id, status, trusted_text, receipt kwargs) -> a source exposing the two producer calls used."""
    receipts = {}
    for oid, status, trusted_text, kw in rows:
        base = dict(page_id="1", geometry=(10.0, 10.0, 20.0, 18.0), raw_text="870", trusted=False, reason_codes=())
        base.update(kw)
        receipts[oid] = SimpleNamespace(status=status, trusted_text=trusted_text, receipt=SimpleNamespace(**base))
    published = SimpleNamespace(
        revision=SimpleNamespace(document_id="d", revision_id="r", source_sha256="s"), snapshot=SimpleNamespace(snapshot_id="n"),
        text_observation_ids=tuple(receipts))
    integrity = SimpleNamespace(resolve_text=lambda selector: receipts[selector.observation_id])
    return SimpleNamespace(published_snapshot_for_revision=lambda rid: published if rid == "r" else None,
                           text_integrity_authority=lambda: integrity)


def test_text_trust_tags_follow_the_receipt_and_untrusted_figures_are_never_dropped():
    from pb_pdf_text_integrity_authority import TEXT_CLIP_STATE_UNRESOLVED, TEXT_GLYPH_MAPPING_UNVERIFIED
    C, A = EvidenceResolutionStatus.CORROBORATED, EvidenceResolutionStatus.ABSTAINED
    rows = [
        ("ok", C, "870", dict(trusted=True)),
        ("raw", A, None, dict(reason_codes=(TEXT_GLYPH_MAPPING_UNVERIFIED,), raw_text="900")),
        ("raw2", A, None, dict(reason_codes=(TEXT_GLYPH_MAPPING_UNVERIFIED, TEXT_CLIP_STATE_UNRESOLVED), raw_text="1,200")),
        ("noreason", A, None, dict(reason_codes=(), raw_text="720")),               # an empty reason set is a subset of everything: never raw
        ("other", A, None, dict(reason_codes=("text_font_binding_unverified",), raw_text="600")),
        ("note", A, None, dict(reason_codes=(TEXT_GLYPH_MAPPING_UNVERIFIED,), raw_text="ENTRY")),
        ("elsewhere", C, "870", dict(trusted=True, page_id="2")),
        ("badbox", A, None, dict(raw_text="450", geometry=(1.0, 2.0, 3.0))),
    ]
    words = {w.word_id: w for w in ad.read_figure_words(_stub_source(rows), revision_id="r", page_id="1")}
    assert set(words) == {"ok", "raw", "raw2", "noreason", "other"}                  # the tag, the other page and the bad box are out
    assert words["ok"].text_trust == "corroborated"
    assert words["raw"].text_trust == "raw_unverified" and words["raw2"].text_trust == "raw_unverified"
    assert words["noreason"].text_trust == "" and words["other"].text_trust == ""      # still returned: they must be able to veto
    assert words["raw"].text == "900" and words["raw2"].text == "1,200"


# ------------------------------------------------------------------------------------------------ isolation
def test_nothing_in_production_imports_the_adapter_or_the_core():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    names = ("pb_door_swing_figure_binding_adapter", "pb_door_swing_figure_binding_shadow")
    importers = sorted(p.name for p in root.glob("*.py") if p.name not in {n + ".py" for n in names}
                       and any(n in p.read_text(encoding="utf-8", errors="ignore") for n in names))
    assert importers == [], importers
