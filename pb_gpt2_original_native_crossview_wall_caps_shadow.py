"""SHA-pinned original PDF native wall-cap cross-view source diagnostic.

This is only painted source ink. A caller's original path indices are NOT
producer-issued W4 physical identities. No doorway, jamb, threshold, room
floor, source material, metric measurement, FIRM or customer grant.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
from math import isfinite
from typing import Sequence
import fitz
from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class NativeWallCapScope:
    page_number: int
    cap_paths: tuple[int, int]
    face_paths: tuple[int, int, int, int]


@dataclass(frozen=True)
class NativeWallCapSourceReceipt:
    page_number: int
    cap_paths: tuple[int, int]
    face_paths: tuple[int, int, int, int]
    cap_x_pdf_pt: tuple[float, float]
    cap_y_pdf_pt: tuple[float, float]
    face_width_pt: tuple[float, float]


@dataclass(frozen=True)
class NativeCrossViewWallCapShadow:
    status: EvidenceResolutionStatus
    source_sha256: str
    first: NativeWallCapSourceReceipt
    second: NativeWallCapSourceReceipt
    original_translation_receipts: tuple[dict, ...]
    compatible_translations_pdf_pt: tuple[tuple[float, float], ...]
    reason_codes: tuple[str, ...]
    shadow_only: bool = True
    original_w4_wall_issued: bool = False
    physical_jamb_issued: bool = False
    doorway_threshold_issued: bool = False
    physical_floor_issued: bool = False
    material_issued: bool = False
    firm_area_issued: bool = False
    commercial_projection_allowed: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _source_line(drawings, address: int):
    if type(address) is not int or address < 0 or address >= len(drawings):
        raise ValueError("original native drawing address missing")
    drawing = drawings[address]
    # A black vector path is not necessarily visible construction ink.
    # Explicit full stroke opacity and a solid native dash pattern are
    # required before its endpoints may support even SOURCE CANDIDATE.
    opacity = drawing.get("stroke_opacity")
    if (type(opacity) not in (int, float) or not isfinite(opacity)
            or opacity < 1.0 or opacity > 1.0
            or drawing.get("dashes") != "[] 0"):
        raise ValueError("original native source is not visible solid painted ink")
    items = drawing.get("items", ())
    if (len(items) not in (1, 2) or items[0][0] != "l"
            or drawing.get("fill") is not None
            or drawing.get("color") is None
            or any(not isfinite(float(v)) or float(v) < 0 or float(v) > 0.04
                   for v in drawing["color"])):
        raise ValueError("original native source is not a black line")
    _, start, finish = items[0]
    if len(items) == 2 and (
        items[1][0] != "l" or items[1][1] != finish or items[1][2] != start
    ):
        raise ValueError("two unrelated source strokes cannot be one face")
    vals = (float(start.x), float(start.y), float(finish.x), float(finish.y))
    width = float(drawing["width"])
    if not all(isfinite(x) for x in vals) or not isfinite(width) or width <= 0.05:
        raise ValueError("degenerate source line")
    return (*vals, round(width, 4))


def _require_original_path_not_later_covered(page, drawings, index: int) -> None:
    """Fail closed if subsequent source paint hides any chosen cap/face ink.

    Merely being in PDF get_drawings is not proof that an original structural
    ink segment remains visible. Match source sequence to later filled paint,
    using a stroke-width-expanded region so horizontal/vertical zero-area
    segment rectangles cannot silently evade the overlap test. This remains
    SOURCE-ONLY: no W4 or installed-opening identity is minted.
    """
    selected = drawings[index]
    seq = selected.get("seqno")
    box = selected.get("rect")
    width = selected.get("width")
    if (type(seq) is not int or type(width) not in (int, float)
            or not isfinite(width) or width <= 0 or box is None):
        raise ValueError("original native path paint sequence unavailable")
    bounds = tuple(float(v) for v in box)
    if len(bounds) != 4 or not all(isfinite(v) for v in bounds):
        raise ValueError("original native path paint bbox unavailable")
    bboxlog = page.get_bboxlog()
    if seq < 0 or seq >= len(bboxlog):
        raise ValueError("original native source paint sequence out of scope")
    half = max(float(width) / 2, 0.05)
    x0, y0, x1, y1 = bounds
    ink = fitz.Rect(x0 - half, y0 - half, x1 + half, y1 + half)
    for later_seq in range(seq + 1, len(bboxlog)):
        entry = bboxlog[later_seq]
        if len(entry) < 2 or entry[0] not in (
                "fill-path", "fill-image", "fill-shade"):
            continue
        try:
            overlap = ink.intersects(fitz.Rect(entry[1]))
        except (TypeError, ValueError):
            raise ValueError("original native later paint geometry unresolved")
        if not overlap:
            continue
        if entry[0] == "fill-path":
            paint = [candidate for candidate in drawings
                     if candidate.get("seqno") == later_seq]
            if (len(paint) == 1
                    and paint[0].get("fill") is not None
                    and type(paint[0].get("fill_opacity")) in (int, float)
                    and float(paint[0]["fill_opacity"]) == 0.0):
                continue
        raise ValueError("original native wall cap or face is later obscured")


def _inspect_page(page, scope: NativeWallCapScope, tol: float):
    if (type(scope) is not NativeWallCapScope or
            len(scope.cap_paths) != 2 or len(scope.face_paths) != 4 or
            len(set((*scope.cap_paths, *scope.face_paths))) != 6):
        raise ValueError("two independent cap and four independent face paths required")
    drawings = page.get_drawings()
    caps = sorted((_source_line(drawings, p) for p in scope.cap_paths),
                  key=lambda r: r[0])
    faces = tuple(_source_line(drawings, p) for p in scope.face_paths)
    for source_path in (*scope.cap_paths, *scope.face_paths):
        _require_original_path_not_later_covered(page, drawings, source_path)
    left, right = caps
    if right[0] - left[0] <= tol:
        raise ValueError("source wall has no two separated cap ends")
    for x1, y1, x2, y2, width in caps:
        if abs(x1-x2) > tol or abs(y1-y2) <= tol:
            raise ValueError("source cap is not a vertical original segment")
    left_ys, right_ys = (tuple(sorted((x[1],x[3]))) for x in caps)
    if any(abs(a-b) > tol for a,b in zip(left_ys,right_ys)):
        raise ValueError("source cap bands disagree")
    widths = []
    for yy in left_ys:
        matched = [[],[]]
        for x1,y1,x2,y2,w in faces:
            if abs(y1-y2) > tol or abs(y1-yy) > tol:
                continue
            lo, hi = sorted((x1,x2))
            if abs(hi-left[0]) <= tol and lo < left[0]-tol:
                matched[0].append(w)
            if abs(lo-right[0]) <= tol and hi > right[0]+tol:
                matched[1].append(w)
        if any(len(group)!=1 for group in matched):
            raise ValueError("source wall face fails unique original cap continuity")
        widths.append((matched[0][0],matched[1][0]))
    if any(abs(widths[0][k]-widths[1][k]) > 0.05 for k in (0,1)):
        raise ValueError("source wall faces disagree in native painted width")
    return NativeWallCapSourceReceipt(
        scope.page_number, tuple(sorted(scope.cap_paths)),
        tuple(sorted(scope.face_paths)),
        (round(left[0],5),round(right[0],5)),
        tuple(round(y,5) for y in left_ys),
        tuple(round(w,4) for w in widths[0]),
    )


def audit_original_native_wall_cap_translation_shadow(
    original_pdf_bytes: bytes, *, source_sha256: str,
    first: NativeWallCapScope, second: NativeWallCapScope,
    translations_pdf_pt: Sequence[tuple[float,float]],
    native_witness_tolerance_pt: float = 0.25,
) -> NativeCrossViewWallCapShadow:
    """Re-read actual source strokes, preserving *all* registration rivals."""
    if type(original_pdf_bytes) is not bytes or not original_pdf_bytes:
        raise ValueError("original PDF bytes required")
    digest = sha256(original_pdf_bytes).hexdigest()
    if type(source_sha256) is not str or digest != source_sha256:
        raise ValueError("original source SHA mismatch")
    if (type(native_witness_tolerance_pt) not in (int,float) or
            not isfinite(native_witness_tolerance_pt) or
            not 0.001 <= native_witness_tolerance_pt <= 0.25):
        raise ValueError("native source witness tolerance outside approved diagnostic bound")
    if not translations_pdf_pt:
        raise ValueError("complete competing translation hypotheses required")
    with fitz.open(stream=original_pdf_bytes, filetype="pdf") as doc:
        if (type(first) is not NativeWallCapScope or type(second) is not NativeWallCapScope
                or min(first.page_number,second.page_number)<1
                or max(first.page_number,second.page_number)>len(doc)
                or first.page_number==second.page_number):
            raise ValueError("two distinct real original pages required")
        a = _inspect_page(doc[first.page_number-1],first,native_witness_tolerance_pt)
        b = _inspect_page(doc[second.page_number-1],second,native_witness_tolerance_pt)
    if any(abs(a.face_width_pt[i]-b.face_width_pt[i])>native_witness_tolerance_pt
           for i in (0,1)):
        raise ValueError("original source painted wall-face widths disagree")
    receipts=[]; accepted=[]; seen=set()
    for candidate in translations_pdf_pt:
        if (type(candidate) not in (tuple,list) or len(candidate)!=2 or
                any(type(v) not in (int,float) or not isfinite(v) for v in candidate)):
            raise ValueError("finite complete original translation required")
        dx,dy=(round(float(v),5) for v in candidate)
        if (dx,dy) in seen:
            raise ValueError("repeated candidate cannot count twice")
        seen.add((dx,dy))
        residual=(round(a.cap_x_pdf_pt[0]+dx-b.cap_x_pdf_pt[0],5),
                  round(a.cap_x_pdf_pt[1]+dx-b.cap_x_pdf_pt[1],5),
                  round(a.cap_y_pdf_pt[0]+dy-b.cap_y_pdf_pt[0],5),
                  round(a.cap_y_pdf_pt[1]+dy-b.cap_y_pdf_pt[1],5))
        compatible=all(abs(v)<=native_witness_tolerance_pt for v in residual)
        receipts.append(dict(dx_pdf_pt=dx,dy_pdf_pt=dy,
                             cap_residual_pdf_pt=residual,
                             source_ink_compatible=compatible))
        if compatible: accepted.append((dx,dy))
    receipts.sort(key=lambda x:(x["dx_pdf_pt"],x["dy_pdf_pt"]))
    unique=len(accepted)==1
    return NativeCrossViewWallCapShadow(
        EvidenceResolutionStatus.CANDIDATE if unique else EvidenceResolutionStatus.ABSTAINED,
        digest,a,b,tuple(receipts),tuple(sorted(accepted)),
        ("original_native_wall_cap_source_only_candidate",) if unique
        else ("original_native_wall_cap_translation_ambiguous_or_absent",),
    )
