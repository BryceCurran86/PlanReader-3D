"""Synthetic drawings for the plan callout -> glazing strip shadow tests.

Every drawing is generated from scratch with PyMuPDF; nothing is read from any project file.
The helper draws what a CAD export draws (thin black strokes, double ink, white masks) and then
reads ink and words back from the PDF into the same record types the producer adapter builds.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import fitz

import pb_source_plan_glazing_strip_callout_shadow as shadow

MM_PER_PT = 17.64          # a drawing scale used only to make consistent synthetic fixtures
BLACK = (0, 0, 0)
W = 0.48
HEX_R = 12.0
HEX_H = HEX_R * math.sin(math.radians(60))     # the callout's half-height across the flats
GAP = 4.0                                       # callout flat to strip band
PATTERN = r"[WD]\d+"
Q_PT = 0.24
Q_MM = 5.0
OWNERSHIP = shadow.SourceOwnership("doc-1", "rev-1", "snap-1", "a" * 64, shadow.PRODUCER_INPUT_PROVENANCE)

CAND = shadow.EvidenceResolutionStatus.CANDIDATE
ABST = shadow.EvidenceResolutionStatus.ABSTAINED
CONF = shadow.EvidenceResolutionStatus.CONFLICT


@dataclass
class Frame:
    mark: str
    bbox: tuple
    panels: int
    width_mm: float
    record_suffix: str = ""


class Sheet:
    """Two-page synthetic sheet: page 1 the plan, page 2 the elevation."""

    def __init__(self, size=(900.0, 700.0)):
        self.size = size
        self.doc = fitz.open()
        self.doc.new_page(width=size[0], height=size[1])
        self.doc.new_page(width=size[0], height=size[1])
        self.frames: list[Frame] = []

    # PyMuPDF orphans a page object once another page is added, so pages are fetched on use.
    @property
    def plan(self):
        return self.doc[0]

    @property
    def elev(self):
        return self.doc[1]

    # --- primitives -----------------------------------------------------------------
    def line(self, a, b, page=None, double=False, width=W, color=BLACK):
        page = page or self.plan
        for _ in range(2 if double else 1):
            page.draw_line(fitz.Point(*a), fitz.Point(*b), color=color, width=width)

    def text(self, xy, text, page=None, size=8):
        (page or self.plan).insert_text(fitz.Point(*xy), text, fontsize=size, fontname="helv")

    # --- window strip (axis 'H' runs along x, 'V' along y) ----------------------------
    def strip(self, axis, lo, n0, panels=3, frame_len=204.0, post=2.64, depth=5.52, pane=(2.4, 3.12), width=W,
              pane_width=None, end_posts=True):
        panel_len = (frame_len - (panels + 1) * post) / panels
        edges = []
        pos = lo
        for k in range(panels + 1):
            edges.append(("post", pos, pos + post))
            pos += post
            if k < panels:
                edges.append(("panel", pos, pos + panel_len))
                pos += panel_len

        def pt(along, off):
            return (along, off) if axis == "H" else (off, along)

        for kind, a, b in edges:
            if kind == "post":
                if not end_posts and (a == lo or abs(b - (lo + frame_len)) < 1e-6):
                    continue
                for off in (n0, n0 + depth):
                    self.line(pt(a, off), pt(b, off), width=width)
            else:
                for off in (n0, n0 + depth):
                    self.line(pt(a, off), pt(b, off), double=True, width=width)
                for edge in (a, b):             # the cell is closed across its full depth
                    self.line(pt(edge, n0), pt(edge, n0 + depth), width=width)
                pw = width if pane_width is None else pane_width
                for off in (n0 + pane[0], n0 + pane[1]):
                    self.line(pt(a, off), pt(b, off), width=pw)
                self.line(pt(a, n0 + pane[0]), pt(a, n0 + pane[1]), width=pw)
                self.line(pt(b, n0 + pane[0]), pt(b, n0 + pane[1]), width=pw)
        return {"axis": axis, "frame": (lo, lo + frame_len), "band": (n0, n0 + depth), "panels": panels}

    # --- callout --------------------------------------------------------------------
    def callout(self, centre, text, r=HEX_R, drop_edge=None, ink_twice=True, extra_ring=False):
        cx, cy = centre
        pts = [(cx + r * math.cos(math.radians(60 * i)), cy + r * math.sin(math.radians(60 * i))) for i in range(6)]
        for i in range(6):
            if drop_edge == i:
                continue
            self.line(pts[i], pts[(i + 1) % 6], double=ink_twice)
        if extra_ring:
            big = [(cx + 1.15 * r * math.cos(math.radians(60 * i)), cy + 1.15 * r * math.sin(math.radians(60 * i)))
                   for i in range(6)]
            for i in range(6):
                self.line(big[i], big[(i + 1) % 6])
        self.text((cx - 5.0, cy + 2.5), text)

    # --- elevation ------------------------------------------------------------------
    def elevation_frame(self, mark, bbox, panels, width_mm, panel_word="FG"):
        x0, y0, x1, y1 = bbox
        for k in range(panels):
            fx = x0 + (k + 0.5) * (x1 - x0) / panels
            self.text((fx - 3, (y0 + y1) / 2), panel_word, page=self.elev)
        self.frames.append(Frame(mark, bbox, panels, width_mm))

    # --- finish ---------------------------------------------------------------------
    def pdf(self) -> bytes:
        return self.doc.tobytes()


def ink_of(pdf: bytes, page_index=0):
    """The visible stroked segments of a page, as the producer adapter would hand them over."""
    out = []
    with fitz.open(stream=pdf, filetype="pdf") as doc:
        for n, d in enumerate(doc[page_index].get_drawings()):
            col, width = d.get("color"), d.get("width")
            if d.get("type") not in ("s", "fs") or not col or width is None:
                continue
            for m, it in enumerate(d["items"]):
                if it[0] == "l":
                    pieces = [(it[1].x, it[1].y, it[2].x, it[2].y)]
                elif it[0] == "re":
                    r = it[1]
                    pieces = [(r.x0, r.y0, r.x1, r.y0), (r.x1, r.y0, r.x1, r.y1),
                              (r.x1, r.y1, r.x0, r.y1), (r.x0, r.y1, r.x0, r.y0)]
                else:
                    continue
                for e, (x0, y0, x1, y1) in enumerate(pieces):
                    out.append(shadow.PlanInkSegment(f"d{n}i{m}e{e}", x0, y0, x1, y1, float(width), max(col) <= 0.1))
    return out


def words_of(pdf: bytes, page_index=0):
    with fitz.open(stream=pdf, filetype="pdf") as doc:
        return [shadow.PlanTextObservation(f"p{page_index + 1}:{w[4]}:{i}", w[4], tuple(w[:4]))
                for i, w in enumerate(doc[page_index].get_text("words"))]


def types_of(sheet: Sheet, *, with_marks=None, width_scale=1.0):
    out = []
    for f in sheet.frames:
        if with_marks is not None and f.mark not in with_marks:
            continue
        out.append(shadow.ElevationTypeObservation(
            type_mark=f.mark, record_id=f"record:{f.mark}{f.record_suffix}",
            display_width_mm=f.width_mm * width_scale, panel_count=f.panels))
    return out


def scope_for(sheet: Sheet, *, ownership=OWNERSHIP, viewports="page", **kw):
    if viewports == "page":
        viewports = (shadow.PlanViewportRef("view_plan", (0.0, 0.0, sheet.size[0], sheet.size[1])),)
    return shadow.PlanCalloutStripScope(
        ownership=ownership, plan_page_id="1", elevation_page_id="2", callout_mark_pattern=PATTERN,
        coordinate_quantum_pt=Q_PT, dimension_quantum_mm=Q_MM, plan_viewports=viewports, **kw)


def run(sheet: Sheet, *, scope=None, ink=None, words=None, types=None, **scope_kw):
    pdf = sheet.pdf()
    scope = scope or scope_for(sheet, **scope_kw)
    ink = ink_of(pdf) if ink is None else ink
    words = words_of(pdf) if words is None else words
    types = types_of(sheet) if types is None else types
    result = shadow.audit_plan_callout_to_glazing_strip_shadow(scope, ink=ink, words=words, elevation_types=types)
    return result


def by_mark(result):
    return {c.tag_mark: c for c in result.correspondences}


def add_window(sheet, k, mark, *, panels=3, length=204.0, axis="H", elevation_panels=None, width_mm=None,
               side=+1, dx=0.0, dy=0.0, elevation=True, callout=True):
    """One strip + callout + (optionally) elevation type; windows are spaced 380 pt apart."""
    lo = 60.0 + 380.0 * k + dx
    n0 = 300.0 + dy
    s = sheet.strip(axis, lo, n0, panels=panels, frame_len=length)
    mid = (s["frame"][0] + s["frame"][1]) / 2.0 + 2.0
    if axis == "H":
        centre = (mid, (s["band"][1] + GAP + HEX_H) if side > 0 else (s["band"][0] - GAP - HEX_H))
    else:
        centre = ((s["band"][1] + GAP + HEX_H) if side > 0 else (s["band"][0] - GAP - HEX_H), mid)
    if callout:
        sheet.callout(centre, mark)
    if elevation:
        n = panels if elevation_panels is None else elevation_panels
        sheet.elevation_frame(mark, (20.0 + 440.0 * k, 100.0, 20.0 + 440.0 * k + 40.0 * max(n, 1), 220.0), n,
                              (length * MM_PER_PT) if width_mm is None else width_mm)
    return s, centre


def three_windows(size=(1400.0, 900.0), **kw):
    sheet = Sheet(size=size)
    add_window(sheet, 0, "W1", panels=3, length=204.0, **kw)
    add_window(sheet, 1, "W2", panels=3, length=232.0, **kw)
    add_window(sheet, 2, "W3", panels=5, length=120.0, **kw)
    return sheet


def decision(result):
    return {c.tag_mark: (c.status, c.reason_codes, tuple((n, s) for n, s in c.conditions)) for c in result.correspondences}
