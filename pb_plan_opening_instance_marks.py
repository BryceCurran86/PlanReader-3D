"""Recover hyphenated W-# / D-# instance marks on scanned floor plans.

Some drawing packages never print a schedule total. They stamp each opening
on the plan as ``W-1``, ``W-2``, ``D-1``. Native PDF text is empty on those
sheets because the labels live in the raster overlay.

This module:

- Isolates dark, non-chromatic ink so hatch and service colour do not OCR,
  then re-reads dark luminance so black/brown stamps on orange door-swings
  are not deleted with the fill.
- Accepts hyphenated marks glued to a neighbouring ``PV`` token (``PVD-2``).
- Accepts only hyphenated marks (``W-1``), so grid letters plus grid numbers
  cannot become ``D1``.
- Assembles a nearby ``W-`` + digit fragment. A lone ``-N`` is promoted to
  ``W-N`` only when it sits on the same band as other window marks.
- Counts an unmatched ``W-`` / ``D-`` prefix on that band as one extra
  instance (OCR dropped the digit) toward an *aggregate* total only.
- Across duplicate service overlays of the same plan, keeps the single
  richest page rather than summing.

Typed schedule rows (W1=n from a table/card/chain) remain authoritative.
When those already exist, this layer stays silent. When several window
identities are present as plan stamps and the package documents a casement
window system, the caller may emit ``steel_casement_windows`` as the stamp
count — not the individual W1/W2 tags, which would hallucinate against a
lumped BOQ item.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

import cv2
import fitz
import numpy as np
from PIL import Image

try:
    import pytesseract
except ImportError:  # pragma: no cover - exercised only where the optional
    # tesseract binary/binding is absent (e.g. CI). OCR recovery is one
    # evidence source among several in this pipeline; its absence must not
    # crash import of the whole module, only silently withhold OCR-derived
    # marks (see _ocr_parts_from_ink below).
    pytesseract = None

from pb_opening_tag_normalization import normalize_opening_tag

_FULL_RE = re.compile(r"^([WD])-([0-9]{1,2})$")
_FRAG_RE = re.compile(r"^(?:[WD]|[WD]-|-[0-9]{1,2}|[0-9]{1,2}|-)$")
_EMBEDDED_RE = re.compile(r"([WD])-([0-9]{1,2})")
_OCR_WHITELIST = "PVWD-0123456789"
_CASEMENT_RE = re.compile(
    r"\bcasement\b|\bwindows?\s+complete\b|\bsteel\s+casement\b",
    re.I,
)
_DOOR_SYSTEM_RE = re.compile(
    r"\bdoors?\s+complete\b|\bflush\s+doors?\b|\bcasement\s+doors?\b|\bpanel\s+doors?\b|\bsteel\s+doors?\b|\btimber\s+doors?\b|\bdoor\s+schedule\b|\bstorage\s+doors?\b",
    re.I,
)
_MIN_WINDOW_TYPES = 2
_MIN_WINDOW_INSTANCES = 3
_MIN_DOOR_TYPES = 1
_MIN_DOOR_INSTANCES = 1
_MAX_MARK_INDEX = 12

_DOOR_SWING_DPI = 150
_DOOR_SWING_MIN_SEEDS = 3
_DOOR_SWING_HUE_STEP = 5
_DOOR_SWING_HUE_TOL = 7
_DOOR_SWING_MIN_SAT = 55
_DOOR_SWING_MIN_VAL = 70
_DOOR_SWING_MIN_SIDE_PT = 8.0
_DOOR_SWING_MAX_SIDE_PT = 65.0
_DOOR_SWING_MIN_AREA_PT2 = 50.0
_DOOR_SWING_MAX_AREA_PT2 = 450.0
_DOOR_SWING_MIN_ASPECT = 0.35
_DOOR_SWING_MIN_FILL_RATIO = 0.07
_DOOR_SWING_MAX_FILL_RATIO = 0.28
_DOOR_SWING_MATCH_RADIUS_PT = 38.0
_DOOR_SWING_LOCAL_REPEAT_RADIUS_PT = 95.0


@dataclass(frozen=True)
class PlanInstanceMark:
    tag: str
    trade: str
    conf: float
    x: float
    y: float
    raw: str
    page: int
    complete: bool


@dataclass(frozen=True)
class PlanInstanceOpeningTotals:
    window_count: int
    door_count: int
    window_types: Tuple[str, ...]
    door_types: Tuple[str, ...]
    source_page: int
    evidence_text: str
    door_geometry_count: Optional[int] = None
    door_geometry_evidence: str = ""


def package_documents_casement_windows(texts: Iterable[str]) -> bool:
    blob = "\n".join(texts)
    return bool(_CASEMENT_RE.search(blob))


def package_documents_door_system(texts: Iterable[str]) -> bool:
    blob = "\n".join(texts)
    return bool(_DOOR_SYSTEM_RE.search(blob))


def _isolate_ink(rgb: np.ndarray, dark: int = 130, sat: int = 32) -> np.ndarray:
    red = rgb[:, :, 0].astype(int)
    green = rgb[:, :, 1].astype(int)
    blue = rgb[:, :, 2].astype(int)
    chromatic = (
        np.maximum(np.maximum(red, green), blue)
        - np.minimum(np.minimum(red, green), blue)
    ) > sat
    ink = (red < dark) & (green < dark) & (blue < dark) & ~chromatic
    canvas = np.full(red.shape, 255, np.uint8)
    canvas[ink] = 0
    return 255 - cv2.morphologyEx(
        255 - canvas, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8)
    )


def _isolate_dark_luma(rgb: np.ndarray, dark: int = 150) -> np.ndarray:
    """Keep dark pixels even when they sit on chromatic annotation fills.

    Black/brown ``D-2`` stamps are often drawn on orange door-swing arcs.
    Dropping every chromatic pixel removes the glyph; luminance keeps the
    letter while still discarding bright orange fill.
    """
    red = rgb[:, :, 0].astype(np.float32)
    green = rgb[:, :, 1].astype(np.float32)
    blue = rgb[:, :, 2].astype(np.float32)
    luma = 0.30 * red + 0.59 * green + 0.11 * blue
    canvas = np.full(red.shape, 255, np.uint8)
    canvas[luma < dark] = 0
    return 255 - cv2.morphologyEx(
        255 - canvas, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8)
    )


def _normalize_mark_token(token: str) -> Optional[str]:
    """Return a hyphenated W/D token, including OCR glue such as ``PVD-2``."""
    if _FULL_RE.fullmatch(token) or _FRAG_RE.fullmatch(token):
        return token
    embedded = _EMBEDDED_RE.search(token)
    if not embedded:
        return None
    return f"{embedded.group(1).upper()}-{int(embedded.group(2))}"


def _rgb_from_pixmap(pix: fitz.Pixmap) -> Optional[np.ndarray]:
    try:
        if pix.n - pix.alpha > 3:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        if pix.n < 3:
            return None
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n
        )
        return arr[:, :, :3].copy()
    except Exception:
        return None


def _ocr_parts_from_ink(ink: np.ndarray, min_conf: float = 20.0) -> List[dict]:
    parts: List[dict] = []
    if pytesseract is not None:
        try:
            data = pytesseract.image_to_data(
                Image.fromarray(ink),
                output_type=pytesseract.Output.DICT,
                config=f"--psm 11 -c tessedit_char_whitelist={_OCR_WHITELIST}",
            )
            for i, raw in enumerate(data.get("text", [])):
                token = _normalize_mark_token((raw or "").strip())
                if not token:
                    continue
                try:
                    conf = float(data["conf"][i])
                except (TypeError, ValueError):
                    continue
                if conf < min_conf:
                    continue
                parts.append(
                    {
                        "t": token,
                        "conf": conf,
                        "x": float(data["left"][i]),
                        "y": float(data["top"][i]),
                        "w": float(data["width"][i]),
                        "h": float(data["height"][i]),
                    }
                )
            if parts:
                return parts
        except Exception:
            pass

    # Portable RapidOCR fallback when Tesseract is absent or returns no marks
    try:
        from pb_portable_raster_ocr_authority import RapidOCRBackend

        rapid = RapidOCRBackend()
        if rapid.is_available():
            img = Image.fromarray(ink)
            lines = rapid.extract_lines(img, dpi=150)
            for line in lines:
                c = 100.0 if line.confidence is None else float(line.confidence) * 100.0
                if c < min_conf:
                    continue
                text = (line.text or "").strip()
                if not text:
                    continue
                words = text.split()
                if not words:
                    continue
                x0, y0, x1, y1 = line.bbox_px
                total_w = max(1.0, float(x1 - x0))
                h = max(1.0, float(y1 - y0))
                word_w = total_w / len(words)
                for idx, w_raw in enumerate(words):
                    tok = _normalize_mark_token(w_raw)
                    if not tok:
                        continue
                    wx0 = x0 + idx * word_w
                    parts.append(
                        {
                            "t": tok,
                            "conf": c,
                            "x": float(wx0),
                            "y": float(y0),
                            "w": float(word_w),
                            "h": h,
                        }
                    )
            return parts
    except Exception:
        pass

    return parts


def _ocr_parts(rgb: np.ndarray, min_conf: float = 20.0) -> List[dict]:
    """OCR dark non-chromatic ink and dark luminance (labels on coloured fills)."""
    parts = _ocr_parts_from_ink(_isolate_ink(rgb), min_conf=min_conf)
    parts.extend(_ocr_parts_from_ink(_isolate_dark_luma(rgb), min_conf=min_conf))
    return parts


def _emit_mark(
    marks: List[PlanInstanceMark],
    tag: str,
    conf: float,
    x: float,
    y: float,
    raw: str,
    page: int,
    complete: bool,
) -> None:
    match = re.search(r"(\d+)", tag)
    if match is None:
        return
    number = int(match.group(1))
    if number < 1 or number > _MAX_MARK_INDEX:
        return
    trade = "windows" if tag.startswith("W") else "doors"
    marks.append(
        PlanInstanceMark(
            tag=tag,
            trade=trade,
            conf=conf,
            x=x,
            y=y,
            raw=raw,
            page=page,
            complete=complete,
        )
    )


def _assemble(
    parts: Sequence[dict],
    *,
    origin_x: float,
    origin_y: float,
    scale_x: float,
    scale_y: float,
    page: int,
    max_dx_px: float = 50.0,
    max_dy_px: float = 16.0,
) -> List[PlanInstanceMark]:
    """Turn OCR pieces into hyphenated marks. Grid D + 1 never joins."""
    ordered = sorted(parts, key=lambda part: (part["y"], part["x"]))
    used = set()
    marks: List[PlanInstanceMark] = []
    leftovers: List[dict] = []

    def to_page(px: float, py: float) -> Tuple[float, float]:
        return origin_x + px * scale_x, origin_y + py * scale_y

    for i, part in enumerate(ordered):
        if i in used:
            continue
        full = _FULL_RE.fullmatch(part["t"])
        if full:
            used.add(i)
            cx, cy = to_page(part["x"] + part["w"] / 2.0, part["y"] + part["h"] / 2.0)
            _emit_mark(
                marks,
                f"{full.group(1).upper()}{int(full.group(2))}",
                part["conf"],
                cx,
                cy,
                part["t"],
                page,
                True,
            )
            continue

        cluster = [part]
        used.add(i)
        end = part["x"] + part["w"]
        mid_y = part["y"] + part["h"] / 2.0
        for j, other in enumerate(ordered):
            if j in used:
                continue
            other_y = other["y"] + other["h"] / 2.0
            if abs(other_y - mid_y) > max_dy_px:
                continue
            if 0.0 <= other["x"] - end <= max_dx_px:
                cluster.append(other)
                used.add(j)
                end = max(end, other["x"] + other["w"])
        text = "".join(item["t"] for item in sorted(cluster, key=lambda item: item["x"]))
        text = text.replace("--", "-")
        joined = re.search(r"([WD])-([0-9]{1,2})", text)
        if joined:
            cx, cy = to_page(
                sum(item["x"] + item["w"] / 2.0 for item in cluster) / len(cluster),
                sum(item["y"] + item["h"] / 2.0 for item in cluster) / len(cluster),
            )
            _emit_mark(
                marks,
                f"{joined.group(1).upper()}{int(joined.group(2))}",
                min(item["conf"] for item in cluster),
                cx,
                cy,
                text,
                page,
                True,
            )
        else:
            leftovers.extend(cluster)

    window_marks = [mark for mark in marks if mark.trade == "windows" and mark.complete]
    if window_marks:
        for part in leftovers:
            dropped = re.fullmatch(r"-([0-9]{1,2})", part["t"])
            if not dropped:
                continue
            _, py = to_page(part["x"] + part["w"] / 2.0, part["y"] + part["h"] / 2.0)
            if not any(abs(py - m.y) <= 15.0 for m in window_marks):
                continue
            cx, cy = to_page(part["x"] + part["w"] / 2.0, part["y"] + part["h"] / 2.0)
            _emit_mark(
                marks,
                f"W{int(dropped.group(1))}",
                part["conf"],
                cx,
                cy,
                part["t"],
                page,
                False,
            )

    for part in leftovers:
        if part["t"] not in {"W-", "D-"}:
            continue
        cx, cy = to_page(part["x"] + part["w"] / 2.0, part["y"] + part["h"] / 2.0)
        if any(abs(cx - mark.x) < 25.0 and abs(cy - mark.y) < 18.0 for mark in marks):
            continue
        prefix = part["t"][0]
        trade = "windows" if prefix == "W" else "doors"
        marks.append(
            PlanInstanceMark(
                tag=f"{prefix}?",
                trade=trade,
                conf=part["conf"],
                x=cx,
                y=cy,
                raw=part["t"],
                page=page,
                complete=False,
            )
        )
    return marks


def _nms(marks: Sequence[PlanInstanceMark], dist: float = 12.0) -> List[PlanInstanceMark]:
    ordered = sorted(marks, key=lambda mark: (-mark.conf, -int(mark.complete)))
    kept: List[PlanInstanceMark] = []
    for mark in ordered:
        if any(abs(mark.x - other.x) < dist and abs(mark.y - other.y) < dist for other in kept):
            continue
        kept.append(mark)
    return kept


def extract_marks_from_page(page: fitz.Page, page_num: int) -> List[PlanInstanceMark]:
    hits: List[PlanInstanceMark] = []
    try:
        infos = page.get_image_info(xrefs=True)
    except Exception:
        infos = []
    # Preserve OCR from qualifying embedded image regions even when a PDF printer
    # slices a page into multiple strips. Cross-source NMS below removes duplicates,
    # while the full-page passes recover labels that happen to straddle strip seams.
    for info in infos:
        width = int(info.get("width") or 0)
        height = int(info.get("height") or 0)
        if width * height < 400 * 180:
            continue
        try:
            pix = fitz.Pixmap(page.parent, info["xref"])
        except Exception:
            continue
        rgb = _rgb_from_pixmap(pix)
        if rgb is None:
            continue
        bbox = info["bbox"]
        scale_x = (bbox[2] - bbox[0]) / max(rgb.shape[1], 1)
        scale_y = (bbox[3] - bbox[1]) / max(rgb.shape[0], 1)
        hits.extend(
            _assemble(
                _ocr_parts(rgb),
                origin_x=float(bbox[0]),
                origin_y=float(bbox[1]),
                scale_x=scale_x,
                scale_y=scale_y,
                page=page_num,
            )
        )

    # Two calibrated render scales are intentionally retained. The second pass
    # recovers small neighbouring marks lost by a single downsample; NMS makes
    # duplicate detections harmless.
    for dpi in (200, 240):
        try:
            pix = page.get_pixmap(dpi=dpi)
            rgb = _rgb_from_pixmap(pix)
        except Exception:
            rgb = None
        if rgb is None:
            continue
        scale_x = page.rect.width / max(rgb.shape[1], 1)
        scale_y = page.rect.height / max(rgb.shape[0], 1)
        hits.extend(
            _assemble(
                _ocr_parts(rgb),
                origin_x=0.0,
                origin_y=0.0,
                scale_x=scale_x,
                scale_y=scale_y,
                page=page_num,
            )
        )
    return _nms(hits, dist=12.0)


def extract_plan_instance_opening_totals(
    doc: fitz.Document,
    pages: Sequence[int],
) -> Optional[PlanInstanceOpeningTotals]:
    """Return aggregate window/door stamp counts from the richest plan page."""
    by_page: dict[int, List[PlanInstanceMark]] = {}
    for pno in pages:
        if pno < 0 or pno >= len(doc):
            continue
        page = doc[pno]
        try:
            has_large_raster = any(
                int(image[2] or 0) * int(image[3] or 0) >= 400 * 200
                for image in page.get_images()
            )
        except Exception:
            has_large_raster = False
        if not has_large_raster:
            continue
        native = page.get_text("text") or ""
        # Stamp labels live on scanned overlays whose native text is the
        # title block only. Dense vector note sheets are skipped.
        if len(native.strip()) > 400:
            continue
        marks = extract_marks_from_page(page, pno + 1)
        if marks:
            by_page[pno + 1] = marks
    if not by_page:
        return None

    def richness(item: Tuple[int, List[PlanInstanceMark]]) -> Tuple[int, int]:
        marks = item[1]
        windows = sum(1 for mark in marks if mark.trade == "windows")
        return windows, len(marks)

    source_page, marks = max(by_page.items(), key=richness)
    windows = [mark for mark in marks if mark.trade == "windows"]
    doors = [mark for mark in marks if mark.trade == "doors"]
    window_types = tuple(sorted({mark.tag for mark in windows if mark.complete}))
    door_types = tuple(sorted({mark.tag for mark in doors if mark.complete}))
    evidence = "; ".join(
        f"{mark.tag}:{mark.raw}@{mark.page}" for mark in marks[:24]
    )
    door_count = len(doors)
    door_geometry_count: Optional[int] = None
    door_geometry_evidence = ""
    if doors:
        geometry = _recover_one_local_door_swing_repeat(
            doc[source_page - 1],
            doors,
        )
        if geometry is not None and geometry[0] > door_count:
            door_geometry_count, door_geometry_evidence = geometry
            door_count = door_geometry_count
            evidence = (
                f"{evidence}; {door_geometry_evidence}"
                if evidence
                else door_geometry_evidence
            )
    return PlanInstanceOpeningTotals(
        window_count=len(windows),
        door_count=door_count,
        window_types=window_types,
        door_types=door_types,
        source_page=source_page,
        evidence_text=evidence,
        door_geometry_count=door_geometry_count,
        door_geometry_evidence=door_geometry_evidence,
    )



def _circular_hue_diff(hue: np.ndarray, center: int) -> np.ndarray:
    diff = np.abs(hue.astype(np.int16) - int(center))
    return np.minimum(diff, 180 - diff)


def _chromatic_swing_candidates(
    rgb: np.ndarray,
    *,
    page_width_pt: float,
) -> List[dict]:
    """Return hue-grouped, open-arc-sized chromatic contour candidates.

    The caller does not trust these contours by themselves.  They become
    meaningful only when a hue group spatially corroborates already detected
    D-# instance marks on the same floor-plan page.
    """
    if rgb is None or rgb.size == 0 or page_width_pt <= 0:
        return []
    scale = float(rgb.shape[1]) / float(page_width_pt)
    if scale <= 0:
        return []
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    hue = hsv[:, :, 0]
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    grouped: List[dict] = []

    for center in range(0, 180, _DOOR_SWING_HUE_STEP):
        mask = (
            (_circular_hue_diff(hue, center) <= _DOOR_SWING_HUE_TOL)
            & (sat >= _DOOR_SWING_MIN_SAT)
            & (val >= _DOOR_SWING_MIN_VAL)
        ).astype(np.uint8) * 255
        mask = cv2.morphologyEx(
            mask, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8)
        )
        contours, _ = cv2.findContours(
            mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE
        )
        candidates: List[dict] = []
        for contour in contours:
            x, y, width, height = cv2.boundingRect(contour)
            area_px = float(cv2.contourArea(contour))
            width_pt = float(width) / scale
            height_pt = float(height) / scale
            area_pt2 = area_px / (scale * scale)
            if not (
                _DOOR_SWING_MIN_SIDE_PT <= width_pt <= _DOOR_SWING_MAX_SIDE_PT
                and _DOOR_SWING_MIN_SIDE_PT <= height_pt <= _DOOR_SWING_MAX_SIDE_PT
            ):
                continue
            aspect = min(width_pt, height_pt) / max(width_pt, height_pt)
            if aspect < _DOOR_SWING_MIN_ASPECT:
                continue
            if not (
                _DOOR_SWING_MIN_AREA_PT2
                <= area_pt2
                <= _DOOR_SWING_MAX_AREA_PT2
            ):
                continue
            bbox_area = max(width_pt * height_pt, 1e-6)
            fill_ratio = area_pt2 / bbox_area
            if not (
                _DOOR_SWING_MIN_FILL_RATIO
                <= fill_ratio
                <= _DOOR_SWING_MAX_FILL_RATIO
            ):
                continue
            if len(contour) < 20:
                continue
            candidates.append(
                {
                    "center": (
                        (float(x) + float(width) / 2.0) / scale,
                        (float(y) + float(height) / 2.0) / scale,
                    ),
                    "width": width_pt,
                    "height": height_pt,
                    "area": area_pt2,
                    "fill_ratio": fill_ratio,
                }
            )
        if candidates:
            grouped.append({"hue": center, "candidates": candidates})
    return grouped


def _similar_swing_geometry(candidate: dict, reference: dict) -> bool:
    def ratio(a: float, b: float) -> float:
        lo = max(min(float(a), float(b)), 1e-6)
        return max(float(a), float(b)) / lo

    # A missing single-leaf swing should resemble one of the source-authenticated
    # swing contours.  Double-leaf doors may split into two smaller contours, so
    # only one good reference match is required.
    return (
        ratio(candidate["width"], reference["width"]) <= 1.75
        and ratio(candidate["height"], reference["height"]) <= 1.75
        and ratio(candidate["area"], reference["area"]) <= 2.0
        and ratio(candidate["fill_ratio"], reference["fill_ratio"]) <= 1.8
    )


def _recover_one_local_door_swing_repeat_from_rgb(
    rgb: np.ndarray,
    *,
    page_width_pt: float,
    door_marks: Sequence[PlanInstanceMark],
) -> Optional[Tuple[int, str]]:
    """Recover exactly one OCR-missed door from repeated coloured swing geometry.

    D-# OCR marks are the authority seeds.  Their nearby swing contours teach the
    page-local hue and physical contour scale.  Publication is allowed only when
    every seed is corroborated and exactly one additional local, same-geometry
    repeat remains.  Multiple unmatched repeats fail closed.
    """
    seeds = [mark for mark in door_marks if mark.trade == "doors"]
    if len(seeds) < _DOOR_SWING_MIN_SEEDS:
        return None
    if sum(1 for mark in seeds if mark.complete) < 2:
        return None

    scored: List[Tuple[int, int, float, dict]] = []
    for group in _chromatic_swing_candidates(
        rgb, page_width_pt=page_width_pt
    ):
        candidates = group["candidates"]
        matched = 0
        distance_sum = 0.0
        for mark in seeds:
            distances = [
                math.hypot(
                    cand["center"][0] - mark.x,
                    cand["center"][1] - mark.y,
                )
                for cand in candidates
            ]
            if not distances:
                continue
            distance = min(distances)
            distance_sum += distance
            if distance <= _DOOR_SWING_MATCH_RADIUS_PT:
                matched += 1
        # Full seed corroboration is intentionally strict. A hue that cannot
        # explain every detected D mark is not allowed to mint another door.
        if matched != len(seeds):
            continue
        if len(candidates) > len(seeds) + 3:
            continue
        scored.append((matched, len(candidates), distance_sum, group))

    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], item[1], item[2], item[3]["hue"]))
    group = scored[0][3]
    candidates = group["candidates"]

    assigned: dict[int, List[dict]] = {idx: [] for idx in range(len(seeds))}
    unassigned: List[dict] = []
    for candidate in candidates:
        distances = [
            math.hypot(
                candidate["center"][0] - mark.x,
                candidate["center"][1] - mark.y,
            )
            for mark in seeds
        ]
        nearest = min(distances)
        if nearest <= _DOOR_SWING_MATCH_RADIUS_PT:
            assigned[distances.index(nearest)].append(candidate)
        else:
            unassigned.append(candidate)

    if any(not rows for rows in assigned.values()):
        return None
    # Any second unassigned full-size contour in the learned hue group makes the
    # recovery ambiguous, even if it lies farther from the seed cluster.
    if len(unassigned) != 1:
        return None
    missing = unassigned[0]
    nearest_seed = min(
        math.hypot(
            missing["center"][0] - mark.x,
            missing["center"][1] - mark.y,
        )
        for mark in seeds
    )
    if nearest_seed > _DOOR_SWING_LOCAL_REPEAT_RADIUS_PT:
        return None

    reference_candidates = [
        candidate for rows in assigned.values() for candidate in rows
    ]
    if not any(
        _similar_swing_geometry(missing, reference)
        for reference in reference_candidates
    ):
        return None

    recovered = len(seeds) + 1
    cx, cy = missing["center"]
    evidence = (
        "seeded_chromatic_door_swing_repeat:"
        f"hue={group['hue']};seeds={len(seeds)};"
        f"repeat=({cx:.1f},{cy:.1f})"
    )
    return recovered, evidence


def _recover_one_local_door_swing_repeat(
    page: fitz.Page,
    door_marks: Sequence[PlanInstanceMark],
) -> Optional[Tuple[int, str]]:
    try:
        pix = page.get_pixmap(dpi=_DOOR_SWING_DPI, alpha=False)
        rgb = _rgb_from_pixmap(pix)
    except Exception:
        return None
    if rgb is None:
        return None
    return _recover_one_local_door_swing_repeat_from_rgb(
        rgb,
        page_width_pt=float(page.rect.width),
        door_marks=door_marks,
    )


def should_emit_casement_window_total(
    totals: PlanInstanceOpeningTotals,
    existing_tags: Iterable[str],
) -> bool:
    """True when plan stamps should become a lumped casement-window total."""
    if any(
        (norm := normalize_opening_tag(tag)) is not None and norm.trade_type == "windows"
        for tag in existing_tags
    ):
        return False
    if "steel_casement_windows" in existing_tags or "windows_complete" in existing_tags:
        return False
    if len(totals.window_types) < _MIN_WINDOW_TYPES:
        return False
    if totals.window_count < _MIN_WINDOW_INSTANCES:
        return False
    return True


def should_emit_door_total(
    totals: PlanInstanceOpeningTotals,
    existing_tags: Iterable[str],
) -> bool:
    """True when plan stamps should become a lumped doors_complete total."""
    if any(
        (norm := normalize_opening_tag(tag)) is not None and norm.trade_type == "doors"
        for tag in existing_tags
    ):
        return False
    if "doors_complete" in existing_tags or "doors" in existing_tags:
        return False
    if len(totals.door_types) < _MIN_DOOR_TYPES:
        return False
    if totals.door_count < _MIN_DOOR_INSTANCES:
        return False
    return True

