"""Synthetic /Rotate fixtures and helpers for the page-frame shadow tests.

Self-contained (PyMuPDF 1.28.0 behaviour), deterministic bytes (every save uses
``no_new_id=True``; a default ``tobytes()`` embeds a time-dependent /ID). One visual
sheet is authored at /Rotate 0/90/180/270 so the DISPLAYED sheet is identical while
the native content and MediaBox differ. Draw on a plain page, wrap the content in a
single new stream with a translation, then declare boxes/UserUnit/Rotate by key:
``page.draw_*`` on an already rotated or offset-CropBox page lands in the wrong place,
and ``update_stream`` on ``get_contents()[0]`` alone duplicates lines.
"""
from __future__ import annotations

import copy
import hashlib

import fitz

# pb_page_frame_shadow is imported lazily (inside the helpers that need it) so that
# building fixtures never imports the module under test: the shadow-proof test
# relies on a subprocess that builds PDFs with this file yet never loads it.

VW, VH = 841.89, 595.28           # VISUAL (displayed) sheet size in unscaled points (A4 landscape, non-integer)
T = 12.0                          # distance between the two wall faces; > 2.5pt snap x review band, else faces' ends read NEAR_JUNCTION_REVIEW


def wall_specs(vw=VW, vh=VH):
    """(label, visual centreline (x0,y0,x1,y1), end classes E=true visual page edge / I=interior)."""
    return [
        ("touches_visual_top", (150, 0, 150, 140), "EI"), ("touches_visual_bottom", (60, vh - 140, 60, vh), "IE"),
        ("touches_visual_left", (0, 230, 140, 230), "EI"), ("touches_visual_right", (vw - 140, 340, vw, 340), "IE"),
        ("interior_h", (330, 420, 470, 420), "II"), ("interior_v", (520, 180, 520, 320), "II"),
        ("near_edge_top_4pt", (640, 4, 640, 130), "II"), ("near_edge_right_4pt", (vw - 130, 500, vw - 4, 500), "II"),
        # interior on the visual sheet, but the NATIVE coordinate equals the legacy (rotated) page-rect boundary
        ("lookalike_x_eq_vw_minus_vh", (vw - vh, 470, vw - vh + 140, 470), "II"),
        ("lookalike_x_eq_vh", (vh, 545, vh + 140, 545), "II")]


def to_native(rot, vw, vh, dx, dy):
    """Exact visual(display) -> native (y-down, unscaled, crop-origin) map; native box is (vw,vh) or (vh,vw)."""
    return {0: (dx, dy), 90: (dy, vw - dx), 180: (vw - dx, vh - dy), 270: (vh - dy, dx)}[rot]


def _rt(doc):
    b = doc.tobytes(no_new_id=True)
    doc.close()
    return fitz.open(stream=b, filetype="pdf")


def build_sheet(rotation=0, *, user_unit=1, vw=VW, vh=VH, rotate_key="canonical", crop_margins=None,
                origin=(0.0, 0.0), sideways_from=None, walls=True, cm_scale=None) -> bytes:
    """rotation: canonical 0/90/180/270 the CONTENT is authored for (displayed sheet identical for all).
    rotate_key: 'canonical' | 'absent' | 'inherit' (set on Pages node) | raw int/str spelling for /Rotate
      (e.g. 450, -90, 45, 91, -1).  cm_scale: write the wall strokes through `q s 0 0 s 0 0 cm` with
      coordinates divided by s, so edge ends land up to a few float32 ulp off the extent edge.  crop_margins (l,b,r,t): MediaBox area outside the CropBox (PDF space);
    origin: MediaBox lower-left.  sideways_from: author for this rotation but write /Rotate 0."""
    rot = sideways_from if sideways_from is not None else rotation
    nw, nh = (vw, vh) if rot in (0, 180) else (vh, vw)              # native (unrotated) effective box
    doc = fitz.open()
    page = doc.new_page(width=nw, height=nh)                        # draw on a plain, uncropped, unrotated page
    manual = []
    if walls:
        for _label, (x0, y0, x1, y1), _e in wall_specs(vw, vh):
            (ax, ay), (bx, by) = to_native(rot, vw, vh, x0, y0), to_native(rot, vw, vh, x1, y1)
            horiz = abs(ay - by) < abs(ax - bx)
            for s in (-T / 2, T / 2):                               # the two parallel wall faces
                p, q = ((ax, ay + s), (bx, by + s)) if horiz else ((ax + s, ay), (bx + s, by))
                if cm_scale is None:
                    page.draw_line(p, q, color=(0, 0, 0), width=1.0)
                else:                                               # native y-down -> PDF y-up, divided by cm_scale
                    manual.append("%.9g %.9g m %.9g %.9g l S\n" % (
                        p[0] / cm_scale, (nh - p[1]) / cm_scale, q[0] / cm_scale, (nh - q[1]) / cm_scale))
    page.insert_text(fitz.Point(*to_native(rot, vw, vh, 60, 60)), "FLOOR PLAN", fontsize=14, rotate=rot)
    m = crop_margins or (0, 0, 0, 0)
    ox, oy = origin
    # translate content into the (possibly offset) CropBox with ONE new content stream, then declare the boxes
    extra = b""
    if manual:
        extra = ("q %.9g 0 0 %.9g 0 0 cm\n1 w 0 0 0 RG\n" % (cm_scale, cm_scale) + "".join(manual) + "Q\n").encode()
    body = b"q 1 0 0 1 %g %g cm\n" % (ox + m[0], oy + m[1]) + page.read_contents() + b"\n" + extra + b"Q\n"
    cx = doc.get_new_xref()
    doc.update_object(cx, "<<>>")
    doc.update_stream(cx, body)
    doc.xref_set_key(page.xref, "Contents", "%d 0 R" % cx)          # update_stream on get_contents()[0] alone duplicates
    doc.xref_set_key(page.xref, "MediaBox", "[%.6f %.6f %.6f %.6f]" % (ox, oy, ox + nw + m[0] + m[2], oy + nh + m[1] + m[3]))
    doc.xref_set_key(page.xref, "CropBox", "[%.6f %.6f %.6f %.6f]" % (ox + m[0], oy + m[1], ox + m[0] + nw, oy + m[1] + nh))
    if user_unit != 1:
        doc.xref_set_key(page.xref, "UserUnit", str(user_unit))
    key = 0 if sideways_from is not None else (rotation if rotate_key == "canonical" else rotate_key)
    if key == "absent":
        doc.xref_set_key(page.xref, "Rotate", "null")
    elif key == "inherit":
        doc.xref_set_key(page.xref, "Rotate", "null")
        px = int(doc.xref_get_key(doc.pdf_catalog(), "Pages")[1].split()[0])
        doc.xref_set_key(px, "Rotate", str(rotation))
    else:
        doc.xref_set_key(page.xref, "Rotate", str(key))
    return _rt(doc).tobytes(no_new_id=True)


def expected_faces(rot, vw=VW, vh=VH, uu=1):
    """{'label#fK': (native_end_a, native_end_b, 'EI'-classes)} in PyMuPDF native points (x UserUnit)."""
    out = {}
    for lab, (x0, y0, x1, y1), e in wall_specs(vw, vh):
        a, b = to_native(rot, vw, vh, x0, y0), to_native(rot, vw, vh, x1, y1)
        horiz = abs(a[1] - b[1]) < abs(a[0] - b[0])
        for i, s in enumerate((-T / 2, T / 2)):
            p, q = ((a[0], a[1] + s), (b[0], b[1] + s)) if horiz else ((a[0] + s, a[1]), (b[0] + s, b[1]))
            out[f"{lab}#f{i}"] = ((p[0] * uu, p[1] * uu), (q[0] * uu, q[1] * uu), e)
    return out


def match_unique(cands, expected, tol=1e-3):
    """cands: [(pt_a, pt_b), ...]. Exact-endpoint match (tol ~ 30x float32 ulp), EXACTLY one hit required
    (no nearest/first); raises AssertionError on 0 or >1 hits.  Returns {label: candidate index}."""
    d = lambda u, v: max(abs(u[0] - v[0]), abs(u[1] - v[1]))
    m = {}
    for lab, (p, q, _e) in expected.items():
        hits = [i for i, (a, b) in enumerate(cands)
                if (d(a, p) < tol and d(b, q) < tol) or (d(a, q) < tol and d(b, p) < tol)]
        assert len(hits) == 1, (lab, hits)
        m[lab] = hits[0]
    assert len(set(m.values())) == len(m)
    return m


DOC_ID = "frame-doc"


def ownership_for(data: bytes, document_id: str = DOC_ID) -> dict:
    from pb_page_frame_shadow import revision_id_for

    sha = hashlib.sha256(data).hexdigest()
    return {"document_id": document_id, "source_sha256": sha, "revision": revision_id_for(document_id, sha)}


def describe_bytes(data: bytes, page_no: int = 1, *, document_id: str = DOC_ID):
    from pb_page_frame_shadow import describe_page_frame

    doc = fitz.open(stream=data, filetype="pdf")
    try:
        return describe_page_frame(doc[page_no - 1], page_no=page_no, **ownership_for(data, document_id))
    finally:
        doc.close()


class FakeRect:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1

    @property
    def width(self):
        return self.x1 - self.x0

    @property
    def height(self):
        return self.y1 - self.y0


class FakeParent:
    def __init__(self, keys):
        self.keys = dict(keys)

    def xref_get_key(self, xref, key):
        return self.keys.get(key, ("null", "null"))


class FakePage:
    """Duck-typed page for degenerate / contradictory metadata. Deep-copied attrs."""

    def __init__(self, *, rect=(0.0, 0.0, 842.0, 595.0), rotation=0, mediabox=(0.0, 0.0, 842.0, 595.0),
                 cropbox=(0.0, 0.0, 842.0, 595.0), keys=None):
        self.rect = FakeRect(*copy.deepcopy(rect))
        self.rotation = rotation
        self.mediabox = FakeRect(*copy.deepcopy(mediabox))
        self.cropbox = FakeRect(*copy.deepcopy(cropbox))
        self.xref = 7
        self.parent = FakeParent(keys or {})


def set_page_key(data: bytes, key: str, value: str) -> bytes:
    """Return deterministic PDF bytes with one page-dictionary key overwritten."""
    doc = fitz.open(stream=data, filetype="pdf")
    doc.xref_set_key(doc[0].xref, key, value)
    out = doc.tobytes(no_new_id=True)
    doc.close()
    return out


def set_pages_node_key(data: bytes, key: str, value: str) -> bytes:
    """Return deterministic PDF bytes with one key set on the /Pages node (inherited by the pages)."""
    doc = fitz.open(stream=data, filetype="pdf")
    pages_xref = int(doc.xref_get_key(doc.pdf_catalog(), "Pages")[1].split()[0])
    doc.xref_set_key(pages_xref, key, value)
    out = doc.tobytes(no_new_id=True)
    doc.close()
    return out
