"""PlanReader v1.2.19 automatic drawing triage, self-calibration and geometry.

This module makes the non-AI workflow materially more automatic while keeping a
strict evidence hierarchy:

* pages that are irrelevant to painting take-off are auto-deselected before
  raster processing (they remain in the drawing register and can be restored);
* manual page calibration is never overwritten;
* vector-PDF dimension lines are preferred for automatic calibration;
* printed scale is a provisional fallback and calibrated floor-plan geometry can
  cross-reference elevation width where the facade orientation is identifiable;
* clearly documented unit areas become floor-area reference rows automatically;
* unit polygons detected from closed drawing boundaries remain provisional until
  reviewed;
* elevation gross areas / explicitly documented substrate areas become external
  take-off rows and are linked to an automatically derived 3D envelope.

No commercial rates, coating systems, coats or productivity are invented here.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import math
import numbers
import re
from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover - production dependency exists
    cv2 = None

import pb_takeoff_row_contract as takeoff_contract

try:
    import pb_3d_surface_editor_v1212 as surface_v1212
except Exception:  # pragma: no cover
    surface_v1212 = None

VERSION = "1.2.19"
SOURCE_PREFIX = f"PB Auto Geometry v{VERSION}"
MODEL_SOURCE_PREFIX = f"{SOURCE_PREFIX} · envelope"
SETTING_KEY = "auto_geometry_v1219"

_KEEP_TYPES = {
    "Floor Plan",
    "Reflected Ceiling Plan",
    "Elevation",
    "Section",
    "Door / Window Schedule",
    "Finishes Schedule",
    "Specification",
    "Render / Artist's Impression",
}
_DROP_TYPES = {"Structural", "Services", "Landscape / Civil"}
_RELEVANT_WORDS = (
    "paint", "painting", "finish", "colour", "color", "cladding", "render",
    "soffit", "eave", "fascia", "balustrade", "external", "elevation",
    "floor plan", "ceiling", "door schedule", "window schedule", "substrate",
    "linea", "easylap", "textureboard", "weatherboard", "blockwork",
)
_ROOF_RELEVANT_WORDS = ("soffit", "eave", "fascia", "canopy", "awning", "paint")
_UNIT_LABEL_RE = re.compile(
    r"\b(?:UNIT|APT|APARTMENT|VILLA|TOWNHOUSE|TENANCY)\s*[-#:]*\s*([A-Z0-9][A-Z0-9.-]*)\b",
    re.IGNORECASE,
)
_AREA_RE = re.compile(r"\b(\d{1,4}(?:\.\d{1,2})?)\s*(?:m\s*[²2]|sqm|sq\.?\s*m)\b", re.IGNORECASE)
_DIM_RE = re.compile(r"(?<![:\d])(?P<num>\d{2,5}(?:\.\d{1,3})?)\s*(?P<unit>mm|m)?(?!\s*[:\d])", re.IGNORECASE)

_SUBSTRATE_RULES: Sequence[Tuple[Tuple[str, ...], str, str]] = (
    (("lineaboard", "linea"), "EC1", "Lineaboard Cladding"),
    (("textureboard",), "EC2", "Textureboard Cladding"),
    (("easylap",), "EC3", "Easylap Cladding"),
    (("render", "rendered block", "blockwork"), "RBL", "Rendered / Blockwork"),
    (("timber look", "timber cladding", "weatherboard"), "EC5", "Timber / Weatherboard Cladding"),
    (("soffit", "eave"), "SOF", "Soffits / Eaves"),
    (("screen",), "SCR", "Screens"),
    (("balustrade",), "BA1", "Balustrade"),
    (("sunhood", "sun hood"), "SHD", "Sunhoods"),
    (("downpipe",), "DP", "Downpipes"),
    (("garage door",), "GD", "Garage Doors"),
)


def _num(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def _safe_json(value: Any, fallback: Any) -> Any:
    try:
        return json.loads(str(value or ""))
    except Exception:
        return fallback


def _is_auto_scale(page: Dict[str, Any]) -> bool:
    return str(page.get("scale_text") or "").startswith("Auto ")


def page_relevance(page_type: Any, text: Any = "", label: Any = "") -> Tuple[bool, str, int]:
    """Conservatively decide whether a sheet is useful for painting take-off.

    Auto-discard means ``selected=0`` only. The sheet row and source document are
    retained so an estimator can reselect it at any time.
    """
    kind = str(page_type or "Other").strip() or "Other"
    low = f"{text or ''} {label or ''}".lower()
    if kind in _DROP_TYPES:
        return False, f"{kind} is normally outside painting take-off", 0
    if kind in _KEEP_TYPES:
        return True, f"{kind} is a painting take-off source", 100
    if kind == "Roof Plan":
        keep = any(word in low for word in _ROOF_RELEVANT_WORDS)
        return keep, ("Roof sheet contains eave/soffit/fascia scope" if keep else "Roof plan has no painting-scope keywords"), 70 if keep else 10
    if kind == "Title / Drawing Register":
        return False, "Reference sheet retained in register but not rasterised for take-off", 20
    if any(word in low for word in _RELEVANT_WORDS):
        return True, "Painting-scope keywords found on otherwise unclassified sheet", 60
    return False, "No painting take-off evidence found", 5


def auto_select_document_pages(app: Any, document_id: int) -> Dict[str, Any]:
    rows = app.lquery(
        "SELECT id,page_no,page_label,page_type,extracted_text,selected FROM pages WHERE document_id=? ORDER BY page_no,id",
        (int(document_id),),
    )
    decisions: List[Dict[str, Any]] = []
    conn = app.local_connect()
    try:
        for row in rows:
            keep, reason, score = page_relevance(row.get("page_type"), row.get("extracted_text"), row.get("page_label"))
            conn.execute("UPDATE pages SET selected=? WHERE id=?", (1 if keep else 0, int(row["id"])))
            decisions.append({
                "page_id": int(row["id"]), "page_no": int(row.get("page_no") or 0),
                "label": str(row.get("page_label") or ""), "type": str(row.get("page_type") or ""),
                "selected": bool(keep), "reason": reason, "score": score,
            })
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {
        "document_id": int(document_id),
        "kept": sum(1 for item in decisions if item["selected"]),
        "discarded": sum(1 for item in decisions if not item["selected"]),
        "pages": decisions,
    }


def _dimension_value_m(token: Any) -> Optional[float]:
    text = str(token or "").strip().lower().replace(",", "")
    match = _DIM_RE.fullmatch(text)
    if not match:
        return None
    value = _num(match.group("num"))
    unit = str(match.group("unit") or "").lower()
    if unit == "mm" or (not unit and value >= 100):
        value /= 1000.0
    elif unit != "m":
        return None
    if not (0.30 <= value <= 100.0):
        return None
    return value


def _line_distance_to_box(x1: float, y1: float, x2: float, y2: float, box: Sequence[float]) -> float:
    x0, y0, bx1, by1 = [float(v) for v in box[:4]]
    cx, cy = (x0 + bx1) / 2.0, (y0 + by1) / 2.0
    if abs(y2 - y1) <= abs(x2 - x1):
        outside = max(0.0, min(x1, x2) - cx, cx - max(x1, x2))
        return abs((y1 + y2) / 2.0 - cy) + outside
    outside = max(0.0, min(y1, y2) - cy, cy - max(y1, y2))
    return abs((x1 + x2) / 2.0 - cx) + outside


def _iter_pdf_lines(drawing_items: Iterable[Any]) -> Iterable[Tuple[float, float, float, float]]:
    for drawing in drawing_items or []:
        for item in drawing.get("items", []) if isinstance(drawing, dict) else []:
            if not item or item[0] != "l" or len(item) < 3:
                continue
            p1, p2 = item[1], item[2]
            try:
                yield float(p1.x), float(p1.y), float(p2.x), float(p2.y)
            except Exception:
                try:
                    yield float(p1[0]), float(p1[1]), float(p2[0]), float(p2[1])
                except Exception:
                    continue


def choose_dimension_calibration(candidates: Sequence[Dict[str, Any]], expected_px_per_m: float = 0.0) -> Optional[Dict[str, Any]]:
    """Choose a dimension-line calibration using score plus consensus.

    Candidates within 7% of one another reinforce each other. A printed-scale
    expectation can increase confidence, but never creates a dimension result on
    its own.
    """
    valid = [dict(c) for c in candidates if 5.0 <= _num(c.get("px_per_m")) <= 5000.0]
    if not valid:
        return None
    # Consensus = candidates within 7%; they all lie inside a slightly wider sorted
    # window, and the original test is applied inside it (same counts, not O(n²)).
    ordered = sorted(_num(c.get("px_per_m")) for c in valid)
    for candidate in valid:
        pxpm = _num(candidate.get("px_per_m"))
        window = ordered[bisect.bisect_left(ordered, pxpm * 0.9299):bisect.bisect_right(ordered, pxpm * 1.0701)]
        consensus = sum(1 for other in window if abs(other - pxpm) / max(pxpm, 1e-9) <= 0.07)
        candidate["consensus"] = consensus
        candidate["rank"] = _num(candidate.get("score")) + min(consensus, 4) * 2.0
        if expected_px_per_m > 0:
            rel = abs(pxpm - expected_px_per_m) / expected_px_per_m
            candidate["rank"] += 5.0 if rel <= 0.10 else (2.0 if rel <= 0.25 else 0.0)
    best = max(valid, key=lambda item: (_num(item.get("rank")), _num(item.get("score"))))
    group = [c for c in valid if abs(_num(c.get("px_per_m")) - _num(best.get("px_per_m"))) / max(_num(best.get("px_per_m")), 1e-9) <= 0.07]
    weights = [max(1.0, _num(c.get("score"), 1.0)) for c in group]
    pxpm = sum(_num(c.get("px_per_m")) * w for c, w in zip(group, weights)) / sum(weights)
    result = dict(best)
    result["px_per_m"] = round(pxpm, 4)
    result["consensus"] = len(group)
    result["confidence"] = "High" if len(group) >= 2 or _num(best.get("rank")) >= 10 else "Medium"
    return result


def detect_dimension_calibration(app: Any, page: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Read native PDF words and dimension lines to infer pixels-per-metre."""
    fitz = getattr(app, "fitz", None)
    if fitz is None:
        return None
    docs = app.lquery("SELECT path FROM documents WHERE id=?", (int(page.get("document_id") or 0),))
    if not docs:
        return None
    path = Path(str(docs[0].get("path") or ""))
    if path.suffix.lower() != ".pdf" or not path.is_file():
        return None
    page_no = int(page.get("page_no") or 0)
    if page_no <= 0:
        return None
    pdf = fitz.open(path)
    try:
        pdf_page = pdf.load_page(page_no - 1)
        words = pdf_page.get_text("words") or []
        lines = list(_iter_pdf_lines(pdf_page.get_drawings() or []))
    finally:
        pdf.close()
    if not words or not lines:
        return None

    expected = 0.0
    try:
        scale = app.auto_detect_scale(page)
        expected = _num((scale or {}).get("px_per_m"))
    except Exception:
        pass
    zoom = max(0.05, _num(page.get("render_zoom"), 1.0))
    candidates: List[Dict[str, Any]] = []
    for word in words:
        if len(word) < 5:
            continue
        real_m = _dimension_value_m(word[4])
        if real_m is None:
            continue
        box = word[:4]
        box_h = max(1.0, float(box[3]) - float(box[1]))
        near_limit = max(22.0, box_h * 3.5)
        for x1, y1, x2, y2 in lines:
            length_pt = math.hypot(x2 - x1, y2 - y1)
            if not (8.0 <= length_pt <= 1600.0):
                continue
            distance = _line_distance_to_box(x1, y1, x2, y2, box)
            if distance > near_limit:
                continue
            pxpm = length_pt * zoom / real_m
            if not (5.0 <= pxpm <= 5000.0):
                continue
            score = max(0.0, 6.0 - distance / max(near_limit / 6.0, 1.0))
            if expected > 0:
                rel = abs(pxpm - expected) / expected
                score += 4.0 if rel <= 0.10 else (1.5 if rel <= 0.25 else 0.0)
            candidates.append({
                "px_per_m": pxpm, "score": score, "dimension_m": real_m,
                "dimension_text": str(word[4]), "line_length_pt": length_pt,
            })
    return choose_dimension_calibration(candidates, expected)


def _regular_image(path_value: Any) -> Optional[Path]:
    raw = str(path_value or "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_file() else None


def _drawing_component(image_path: Path, *, elevation: bool = False) -> Optional[Dict[str, Any]]:
    """Return the dominant drawing cluster and an approximate outer contour.

    The bottom title-block band is excluded. The result is a geometry candidate,
    not a claim of measured accuracy; downstream rows remain provisional unless
    supported by explicit document quantities.
    """
    if cv2 is None:
        return None
    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if image is None or image.size == 0:
        return None
    height, width = image.shape[:2]
    y_end = max(1, int(height * (0.82 if elevation else 0.86)))
    x_start, x_end = int(width * 0.03), int(width * 0.97)
    roi = image[:y_end, x_start:x_end]
    _, ink = cv2.threshold(roi, 205, 255, cv2.THRESH_BINARY_INV)
    kernel_size = 3 if max(width, height) < 2200 else 5
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    connected = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, kernel, iterations=1)
    count, labels, stats, _ = cv2.connectedComponentsWithStats((connected > 0).astype(np.uint8), 8)
    best = None
    roi_area = float(max(1, roi.shape[0] * roi.shape[1]))
    for label_id in range(1, count):
        x, y, w, h, pixels = [int(v) for v in stats[label_id]]
        bbox_area = float(w * h)
        frac = bbox_area / roi_area
        if w < roi.shape[1] * 0.12 or h < roi.shape[0] * 0.10 or not (0.015 <= frac <= 0.78):
            continue
        density = pixels / max(bbox_area, 1.0)
        if not (0.006 <= density <= 0.45):
            continue
        score = bbox_area * (0.45 + min(density, 0.12) * 5.0)
        if best is None or score > best["score"]:
            best = {"label": label_id, "score": score, "bbox": (x + x_start, y, w, h), "density": density}
    if best is None:
        return None
    component_mask = np.zeros_like(connected)
    component_mask[labels == best["label"]] = 255
    contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    contour[:, 0, 0] += x_start
    perimeter = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, max(2.0, perimeter * 0.006), True)
    points = [[float(p[0][0]), float(p[0][1])] for p in approx]
    x, y, w, h = best["bbox"]
    return {
        "bbox": [float(x), float(y), float(w), float(h)],
        "polygon": points,
        "pixel_area": float(abs(cv2.contourArea(contour))),
        "density": float(best["density"]),
        "image_width": width,
        "image_height": height,
    }


def _page_face(text: Any, label: Any = "") -> str:
    low = f"{text or ''} {label or ''}".lower()
    for token, face in (
        ("north elevation", "rear"), ("north elev", "rear"),
        ("south elevation", "front"), ("south elev", "front"),
        ("east elevation", "right"), ("east elev", "right"),
        ("west elevation", "left"), ("west elev", "left"),
        ("front elevation", "front"), ("rear elevation", "rear"),
        ("back elevation", "rear"), ("left elevation", "left"), ("right elevation", "right"),
    ):
        if token in low:
            return face
    return ""


def _substrates_from_text(text: Any) -> List[Dict[str, str]]:
    low = str(text or "").lower()
    found: List[Dict[str, str]] = []
    for needles, code, name in _SUBSTRATE_RULES:
        if any(needle in low for needle in needles):
            found.append({"code": code, "name": name})
    # Preserve explicit EC/RBL/SOF style codes even when a project uses a custom legend.
    for code in sorted(set(re.findall(r"\b(?:EC\d+|RBL\d*|SOF\d*|FC\d+|CL\d+)\b", str(text or ""), flags=re.IGNORECASE))):
        upper = code.upper()
        if not any(item["code"] == upper for item in found):
            found.append({"code": upper, "name": upper})
    return found


def extract_unit_area_candidates(text: Any) -> List[Dict[str, Any]]:
    """Extract explicit UNIT/APARTMENT/VILLA floor areas from text/schedules."""
    lines = [re.sub(r"\s+", " ", line).strip() for line in str(text or "").splitlines() if line.strip()]
    out: List[Dict[str, Any]] = []
    used: set[str] = set()
    for idx, line in enumerate(lines):
        unit_match = _UNIT_LABEL_RE.search(line)
        if not unit_match:
            continue
        label = f"Unit {unit_match.group(1)}"
        search_lines = [line]
        if idx + 1 < len(lines):
            search_lines.append(lines[idx + 1])
        if idx > 0:
            search_lines.append(lines[idx - 1])
        area = None
        source_line = line
        for candidate_line in search_lines:
            match = _AREA_RE.search(candidate_line)
            if match:
                area = _num(match.group(1))
                source_line = candidate_line
                break
        key = label.lower()
        if area and 8.0 <= area <= 1000.0 and key not in used:
            out.append({"label": label, "area_m2": round(area, 2), "confidence": "Documented", "source": source_line})
            used.add(key)
    return out


def extract_substrate_area_candidates(text: Any) -> List[Dict[str, Any]]:
    """Read explicit substrate + m² statements from schedules/elevation notes."""
    out: List[Dict[str, Any]] = []
    for raw_line in str(text or "").splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        area_match = _AREA_RE.search(line)
        if not area_match:
            continue
        area = _num(area_match.group(1))
        if not (0.2 <= area <= 50000.0):
            continue
        subs = _substrates_from_text(line)
        if not subs:
            continue
        # A line with multiple material names is ambiguous and is left for review.
        if len(subs) == 1:
            out.append({"substrate": subs[0], "area_m2": round(area, 2), "source": line, "confidence": "Documented"})
    return out


def _pdf_word_lines(app: Any, page: Dict[str, Any]) -> List[Dict[str, Any]]:
    fitz = getattr(app, "fitz", None)
    if fitz is None:
        return []
    docs = app.lquery("SELECT path FROM documents WHERE id=?", (int(page.get("document_id") or 0),))
    if not docs:
        return []
    path = Path(str(docs[0].get("path") or ""))
    if path.suffix.lower() != ".pdf" or not path.is_file():
        return []
    pdf = fitz.open(path)
    try:
        pdf_page = pdf.load_page(int(page.get("page_no") or 1) - 1)
        words = pdf_page.get_text("words") or []
    finally:
        pdf.close()
    grouped: Dict[Tuple[int, int], List[Any]] = {}
    for word in words:
        if len(word) < 8:
            continue
        grouped.setdefault((int(word[5]), int(word[6])), []).append(word)
    lines: List[Dict[str, Any]] = []
    zoom = max(0.05, _num(page.get("render_zoom"), 1.0))
    for values in grouped.values():
        values.sort(key=lambda item: int(item[7]))
        text = " ".join(str(item[4]) for item in values)
        x0 = min(float(item[0]) for item in values) * zoom
        y0 = min(float(item[1]) for item in values) * zoom
        x1 = max(float(item[2]) for item in values) * zoom
        y1 = max(float(item[3]) for item in values) * zoom
        lines.append({"text": text, "bbox": [x0, y0, x1, y1], "center": [(x0 + x1) / 2.0, (y0 + y1) / 2.0]})
    return lines


def _unit_boundary_candidates(app: Any, page: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Detect closed unit boundaries around explicit unit labels.

    This is intentionally conservative. A contour shared by multiple unit labels
    is rejected rather than divided heuristically.
    """
    if cv2 is None or _num(page.get("px_per_m")) <= 0:
        return []
    image_path = _regular_image(page.get("image_path"))
    if image_path is None:
        return []
    lines = _pdf_word_lines(app, page)
    labels = []
    for line in lines:
        match = _UNIT_LABEL_RE.search(line["text"])
        if match:
            labels.append({"label": f"Unit {match.group(1)}", "center": line["center"]})
    if not labels:
        return []
    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return []
    height, width = image.shape[:2]
    _, ink = cv2.threshold(image, 205, 255, cv2.THRESH_BINARY_INV)
    ink[int(height * 0.88):, :] = 0  # ignore title block
    kernel = np.ones((3, 3), np.uint8)
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, kernel, iterations=1)
    contours, _ = cv2.findContours(ink, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    page_area = float(width * height)
    eligible = []
    for idx, contour in enumerate(contours):
        area = abs(float(cv2.contourArea(contour)))
        if not (page_area * 0.008 <= area <= page_area * 0.45):
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if w < width * 0.06 or h < height * 0.06 or y > height * 0.86:
            continue
        eligible.append((idx, contour, area, (x, y, w, h)))
    chosen: List[Tuple[Dict[str, Any], int, Any, float, Any]] = []
    for label in labels:
        cx, cy = label["center"]
        containing = [item for item in eligible if cv2.pointPolygonTest(item[1], (float(cx), float(cy)), False) >= 0]
        if not containing:
            continue
        # Prefer the largest plausible enclosing boundary; small inner room/text
        # loops are common around a unit label.
        item = max(containing, key=lambda candidate: candidate[2])
        chosen.append((label, item[0], item[1], item[2], item[3]))
    contour_use: Dict[int, int] = {}
    for _label, contour_id, *_rest in chosen:
        contour_use[contour_id] = contour_use.get(contour_id, 0) + 1
    pxpm = _num(page.get("px_per_m"))
    results: List[Dict[str, Any]] = []
    for label, contour_id, contour, area_px, bbox in chosen:
        if contour_use.get(contour_id, 0) != 1:
            continue
        area_m2 = area_px / (pxpm * pxpm)
        if not (8.0 <= area_m2 <= 1000.0):
            continue
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, max(2.0, perimeter * 0.005), True)
        results.append({
            "label": label["label"], "area_m2": round(area_m2, 2), "confidence": "Derived",
            "source": "Closed drawing boundary around unit label", "bbox": [float(v) for v in bbox],
            "polygon": [[float(p[0][0]), float(p[0][1])] for p in approx],
        })
    return results


def _auto_calibrate_page(app: Any, page: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    current = _num(page.get("px_per_m"))
    if current > 0 and not _is_auto_scale(page):
        return {"page_id": int(page["id"]), "method": "Manual/existing", "px_per_m": current, "confidence": "Manual"}
    detected = detect_dimension_calibration(app, page)
    if detected:
        label = f"Auto dimension {detected.get('dimension_text')} · {detected.get('confidence')} confidence"
        app.lexecute("UPDATE pages SET px_per_m=?,scale_text=? WHERE id=?", (_num(detected["px_per_m"]), label, int(page["id"])))
        return {"page_id": int(page["id"]), "method": "Dimension line", "px_per_m": _num(detected["px_per_m"]), "confidence": detected.get("confidence", "Medium")}
    try:
        from pb_raster_plan_dimension_bridge import detect_raster_plan_dimension_calibration
        raster_detected = detect_raster_plan_dimension_calibration(app, page)
    except Exception:
        raster_detected = None
    if raster_detected:
        label = f"Auto raster dimension {raster_detected.get('dimension_text')} · {raster_detected.get('confidence')} confidence"
        app.lexecute("UPDATE pages SET px_per_m=?,scale_text=? WHERE id=?", (_num(raster_detected["px_per_m"]), label, int(page["id"])))
        return {"page_id": int(page["id"]), "method": "Raster dimension", "px_per_m": _num(raster_detected["px_per_m"]), "confidence": raster_detected.get("confidence", "Medium")}
    try:
        scale = app.auto_detect_scale(page)
    except Exception:
        scale = None
    if scale and _num(scale.get("px_per_m")) > 0:
        pxpm = _num(scale.get("px_per_m"))
        label = f"Auto provisional printed scale {scale.get('source') or ''}".strip()
        app.lexecute("UPDATE pages SET px_per_m=?,scale_text=? WHERE id=?", (pxpm, label, int(page["id"])))
        return {"page_id": int(page["id"]), "method": "Printed scale", "px_per_m": pxpm, "confidence": "Provisional"}
    return None


def _detect_footprint(app: Any, pages: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    candidates = []
    for page in pages:
        if "floor" not in str(page.get("page_type") or "").lower() or _num(page.get("px_per_m")) <= 0:
            continue
        path = _regular_image(page.get("image_path"))
        if path is None:
            continue
        component = _drawing_component(path, elevation=False)
        if component is None:
            continue
        x, y, w, h = component["bbox"]
        pxpm = _num(page.get("px_per_m"))
        width_m, depth_m = w / pxpm, h / pxpm
        if not (1.0 <= width_m <= 500.0 and 1.0 <= depth_m <= 500.0):
            continue
        candidates.append({
            "page_id": int(page["id"]), "page_label": str(page.get("page_label") or ""),
            "bbox": component["bbox"], "polygon": component["polygon"],
            "width_m": round(width_m, 3), "depth_m": round(depth_m, 3),
            "px_per_m": pxpm, "density": component["density"],
        })
    if not candidates:
        return None
    # Largest floor-plan drawing cluster is the safest automatic building envelope candidate.
    return max(candidates, key=lambda item: item["width_m"] * item["depth_m"])


def _cross_calibrate_elevations(app: Any, pages: Sequence[Dict[str, Any]], footprint: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not footprint:
        return []
    results = []
    for page in pages:
        if "elevation" not in str(page.get("page_type") or "").lower():
            continue
        if _num(page.get("px_per_m")) > 0 and not _is_auto_scale(page):
            continue
        face = _page_face(page.get("extracted_text"), page.get("page_label"))
        if not face:
            continue
        path = _regular_image(page.get("image_path"))
        if path is None:
            continue
        component = _drawing_component(path, elevation=True)
        if component is None:
            continue
        real_width = footprint["width_m"] if face in {"front", "rear"} else footprint["depth_m"]
        image_width_px = _num(component["bbox"][2])
        if real_width <= 0 or image_width_px <= 0:
            continue
        pxpm = image_width_px / real_width
        if not (5.0 <= pxpm <= 5000.0):
            continue
        app.lexecute(
            "UPDATE pages SET px_per_m=?,scale_text=? WHERE id=?",
            (pxpm, f"Auto cross-reference from floor perimeter · {face}", int(page["id"])),
        )
        results.append({"page_id": int(page["id"]), "method": "Floor/elevation cross-reference", "px_per_m": round(pxpm, 4), "confidence": "Derived", "face": face})
    return results


def _takeoff_row(*, workspace_id: int, section: str, element: str, location: str, substrate: str,
                 quantity: float, status: str, source_page: str, source_reference: str,
                 confidence: str, notes: str, row_role: str = "", unit: str = "m²",
                 preserve_quantity: bool = False) -> Tuple[Any, ...]:
    # Checked before rounding, which would turn NaN into a plausible 0.0 m².
    if not _is_finite_number(quantity):
        raise takeoff_contract.TakeoffRowContractError(
            f"auto-geometry take-off quantity {quantity!r} for {source_reference!r} is not a finite number."
        )
    stamp = ""  # replaced by caller
    return (
        workspace_id, section, element, location, substrate, "To be confirmed",
        max(0.0, quantity) if preserve_quantity else round(max(0.0, quantity), 2), unit,
        status, source_page, source_reference, "INCLUSION" if row_role == "floor_area" else "PROVISIONAL",
        0, 0, 0, 0, confidence, notes, row_role, stamp, stamp,
    )


def _ceiling_review_rows_from_candidates(
    workspace_id: int,
    candidates: Sequence[Any],
) -> List[Tuple[Any, ...]]:
    """Convert only unreviewed ceiling-promotion candidates to core rows."""
    rows: List[Tuple[Any, ...]] = []
    seen_quantity_ids: set[str] = set()
    for candidate in candidates:
        item = dict(getattr(candidate, "review_row", {}) or {})
        if (
            str(item.get("origin") or "") != "AI"
            or str(item.get("quantity_status") or "") != "To review"
            or str(item.get("row_role") or "") != "ceiling_area"
        ):
            raise ValueError("ceiling promotion bypassed customer review state")
        try:
            row_workspace_id = int(item.get("workspace_id"))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("ceiling promotion has invalid workspace identity") from exc
        if row_workspace_id != int(workspace_id):
            raise ValueError("ceiling promotion belongs to another workspace")
        required = {
            name: str(item.get(name) or "").strip()
            for name in ("section", "element", "location", "substrate")
        }
        if not all(required.values()):
            raise ValueError("ceiling promotion is missing customer row identity")
        quantity_id = str(item.get("quantity_id") or "").strip()
        if not quantity_id or quantity_id in seen_quantity_ids:
            raise ValueError("ceiling promotion has duplicate or missing quantity identity")
        seen_quantity_ids.add(quantity_id)
        unit = str(item.get("unit") or "").strip().lower()
        if unit == "m2":
            unit = "m²"
        rows.append(
            _takeoff_row(
                workspace_id=int(workspace_id),
                section=required["section"],
                element=required["element"],
                location=required["location"],
                substrate=required["substrate"],
                quantity=float(item["quantity"]),
                status="To review",
                source_page=str(item.get("source_page") or "Selected PDF pages"),
                source_reference=(
                    f"{SOURCE_PREFIX} · ceiling_quantity:{quantity_id}"
                ),
                confidence="Documented",
                notes=("AI draft; " + str(item.get("notes") or "")),
                row_role="ceiling_area",
                unit=unit,
                preserve_quantity=True,
            )
        )
    return rows


# Canonical auto-geometry take-off row: the core takeoff_rows layout.
TAKEOFF_ROW_FIELDS = takeoff_contract.CORE_FIELDS
TAKEOFF_ROW_FIELD_COUNT = len(TAKEOFF_ROW_FIELDS)
_TAKEOFF_INSERT = takeoff_contract.insert_sql(TAKEOFF_ROW_FIELDS)
TakeoffRowContractError = takeoff_contract.TakeoffRowContractError


def _row_source_hint(row: Any) -> str:
    """Best-effort provenance for an invalid row, for the error message only."""
    if not isinstance(row, (tuple, list)):
        return type(row).__name__
    refs = [value for value in row if isinstance(value, str) and value.startswith("PB ")]
    return refs[0] if refs else type(row).__name__


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, numbers.Real) and not isinstance(value, bool) and math.isfinite(value)


# What an automatic row may carry: the roles _takeoff_row() assigns, text in
# every text column (required ones non-empty), and finite non-negative numbers.
AUTO_ROW_ROLES = (
    "",
    "floor_area",
    "ceiling_area",
    "external_wall",
    "internal_partition",
    "wall_finish",
)
_AUTO_REQUIRED_TEXT = ("section", "element", "location", "substrate", "unit", "quantity_status",
                       "source_reference", "inclusion_status", "confidence")
_AUTO_OPTIONAL_TEXT = ("finish_system", "source_page", "notes", "row_role")
_AUTO_NUMBERS = ("quantity", "coats", "coverage_m2_per_litre", "productivity_m2_per_hour", "rate_per_unit")


def _auto_row_problem(row: Dict[str, Any], workspace_id: int) -> Optional[str]:
    """Why a named automatic row must not be published, or None."""
    owner = row["workspace_id"]
    if isinstance(owner, bool) or not isinstance(owner, int) or owner != workspace_id:
        return f"workspace_id {owner!r} is not the workspace being published ({workspace_id})"
    for name in _AUTO_REQUIRED_TEXT + _AUTO_OPTIONAL_TEXT:
        value = row[name]
        if not isinstance(value, str) or (name in _AUTO_REQUIRED_TEXT and not value.strip()):
            return f"{name} {value!r} is not {'non-empty ' if name in _AUTO_REQUIRED_TEXT else ''}text"
    for name in _AUTO_NUMBERS:
        if not _is_finite_number(row[name]) or row[name] < 0:
            return f"{name} {row[name]!r} is not a finite, non-negative number"
    if row["unit"] not in takeoff_contract.TAKEOFF_UNITS:
        return f"unit {row['unit']!r} is not one of {takeoff_contract.TAKEOFF_UNITS}"
    if row["row_role"] not in AUTO_ROW_ROLES:
        return f"row_role {row['row_role']!r} is not an automatic role {AUTO_ROW_ROLES}"
    inclusion = "INCLUSION" if row["row_role"] == "floor_area" else "PROVISIONAL"
    if row["inclusion_status"] != inclusion:
        return f"inclusion_status {row['inclusion_status']!r} is not {inclusion!r} for row_role {row['row_role']!r}"
    if not row["source_reference"].startswith(SOURCE_PREFIX):
        return (f"source_reference {row['source_reference']!r} does not start with {SOURCE_PREFIX!r}; "
                "it would not be replaced on re-run")
    return None


def _validate_auto_rows(rows: Sequence[Any], workspace_id: int) -> None:
    """Reject, before anything is deleted, every row that is not a well-formed automatic row of this workspace.

    Each row must bind to _TAKEOFF_INSERT (TAKEOFF_ROW_FIELD_COUNT values) and pass
    _auto_row_problem(): it belongs to the workspace being replaced, its
    source_reference is owned by SOURCE_PREFIX (the only prefix
    _auto_publication() deletes, so anything else would be duplicated on
    re-run), and no field is missing, mistyped or non-finite.
    """
    for index, row in enumerate(rows):
        values = takeoff_contract.validate_values(
            row, TAKEOFF_ROW_FIELDS, index=index,
            source=f"{_row_source_hint(row)} (build rows with _takeoff_row())",
        )
        problem = _auto_row_problem(dict(zip(TAKEOFF_ROW_FIELDS, values)), workspace_id)
        if problem:
            raise TakeoffRowContractError(
                f"auto-geometry take-off row {index} ({_row_source_hint(row)}): {problem}."
            )


class _TransactionApp:
    """``app`` with lquery/lexecute bound to one open connection, never committing.

    The envelope and report writers take an app; handing them this proxy puts
    their statements in the same transaction as the take-off rows.
    """

    def __init__(self, app: Any, conn: Any) -> None:
        self._app = app
        self._conn = conn

    def __getattr__(self, name: str) -> Any:
        return getattr(self._app, name)

    def lquery(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        cursor = self._conn.execute(sql, tuple(params))
        columns = [item[0] for item in cursor.description or ()]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def lexecute(self, sql: str, params: Sequence[Any] = ()) -> int:
        return int(self._conn.execute(sql, tuple(params)).lastrowid or 0)


@contextmanager
def _auto_publication(
    app: Any,
    workspace_id: int,
    rows: Sequence[Tuple[Any, ...]],
    *,
    preserve_row_ids: Sequence[int] = (),
):
    """Replace automatic rows while retaining protected reviewed rows."""
    _validate_auto_rows(rows, int(workspace_id))
    preserved_ids: List[int] = []
    for raw_id in preserve_row_ids:
        if isinstance(raw_id, bool):
            raise TakeoffRowContractError(
                "preserved take-off row ids must be positive integers"
            )
        try:
            row_id = int(raw_id)
        except (TypeError, ValueError, OverflowError) as exc:
            raise TakeoffRowContractError(
                "preserved take-off row ids must be positive integers"
            ) from exc
        if row_id <= 0:
            raise TakeoffRowContractError(
                "preserved take-off row ids must be positive integers"
            )
        preserved_ids.append(row_id)
    if len(preserved_ids) != len(set(preserved_ids)):
        raise TakeoffRowContractError("preserved take-off row ids must be unique")

    conn = app.local_connect()
    try:
        if preserved_ids:
            placeholders = ",".join("?" for _ in preserved_ids)
            conn.execute(
                f"""DELETE FROM takeoff_rows
                    WHERE workspace_id=? AND source_reference LIKE ?
                    AND id NOT IN ({placeholders})""",
                (workspace_id, SOURCE_PREFIX + "%", *preserved_ids),
            )
        else:
            conn.execute(
                "DELETE FROM takeoff_rows WHERE workspace_id=? AND source_reference LIKE ?",
                (workspace_id, SOURCE_PREFIX + "%"),
            )
        stamp = app.now_stamp()
        values = [tuple(list(row[:-2]) + [stamp, stamp]) for row in rows]
        conn.executemany(_TAKEOFF_INSERT, values)
        yield _TransactionApp(app, conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _replace_auto_rows(app: Any, workspace_id: int, rows: Sequence[Tuple[Any, ...]]) -> None:
    with _auto_publication(app, workspace_id, rows):
        pass


def _setting_get(app: Any, workspace_id: int) -> Dict[str, Any]:
    rows = app.lquery("SELECT value FROM workspace_settings WHERE workspace_id=? AND key=?", (workspace_id, SETTING_KEY))
    return _safe_json(rows[0].get("value") if rows else "{}", {})


def _setting_set(app: Any, workspace_id: int, data: Dict[str, Any]) -> None:
    value = json.dumps(data, separators=(",", ":"))
    app.lexecute(
        """INSERT INTO workspace_settings(workspace_id,key,value,updated_at) VALUES(?,?,?,?)
           ON CONFLICT(workspace_id,key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at""",
        (workspace_id, SETTING_KEY, value, app.now_stamp()),
    )


def _runtime_coverage_source_scope(app: Any, workspace_id: Optional[int]) -> Optional[set[str]]:
    coverage = getattr(app, "_ag09_family_coverage_by_workspace", None)
    if workspace_id is None or not isinstance(coverage, Mapping):
        return None
    current = coverage.get(int(workspace_id), {})
    return set(current.get("source_sha256s", ())) if isinstance(current, Mapping) else set()


def _runtime_coverage_registry_summaries(app: Any, workspace_id: Optional[int] = None) -> List[Any]:
    """Return only live typed coverage registries explicitly attached to runtime.

    AG-09 never rebuilds a registry from customer rows or infers missing object
    identities. Authorities/extractors must supply CoverageRegistrySummaryV1
    instances directly.
    """
    from pb_takeoff_coverage_registry import CoverageRegistrySummaryV1

    candidates: List[Any] = []
    workspace_coverage = getattr(app, "_ag09_family_coverage_by_workspace", {})
    if isinstance(workspace_coverage, Mapping) and workspace_id is not None:
        current = workspace_coverage.get(int(workspace_id), {})
        if isinstance(current, Mapping):
            candidates.extend(current.get("summaries", ()))
    for attr in (
        "takeoff_coverage_registry_summaries",
        "coverage_registry_summaries",
        "coverage_registry_summaries_live",
    ):
        value = getattr(app, attr, None)
        if isinstance(value, CoverageRegistrySummaryV1):
            candidates.append(value)
        elif isinstance(value, (list, tuple)):
            candidates.extend(value)

    for attr in ("takeoff_coverage_registry_summary", "coverage_registry_summary"):
        value = getattr(app, attr, None)
        if isinstance(value, CoverageRegistrySummaryV1):
            candidates.append(value)

    for holder_name in (
        "planreader_extractor",
        "generic_planreader_extractor",
        "extractor",
    ):
        holder = getattr(app, holder_name, None)
        if holder is None:
            continue
        value = getattr(holder, "coverage_registry_summaries_live", None)
        if isinstance(value, CoverageRegistrySummaryV1):
            candidates.append(value)
        elif isinstance(value, (list, tuple)):
            candidates.extend(value)

    unique: Dict[str, Any] = {}
    source_scope = _runtime_coverage_source_scope(app, workspace_id)
    for summary in candidates:
        if not isinstance(summary, CoverageRegistrySummaryV1):
            continue
        if source_scope is not None and summary.manifest.source_sha256 not in source_scope:
            continue
        # Never let the first of two conflicting snapshots hide the second.
        key = json.dumps(summary.to_dict(), sort_keys=True, separators=(",", ":"))
        unique.setdefault(key, summary)
    return [unique[key] for key in sorted(unique)]


def _runtime_coverage_lifecycle_report(
    app: Any,
    workspace_id: int,
) -> Dict[str, Any]:
    """Build customer-safe AG-09 stage metadata from the current transaction."""
    from pb_takeoff_coverage_audit_adapter import (
        build_runtime_coverage_publication,
    )

    summaries = _runtime_coverage_registry_summaries(app, workspace_id)
    gaps: Dict[str, set[str]] = {}
    holders = [app] + [getattr(app, name, None) for name in (
        "planreader_extractor", "generic_planreader_extractor", "extractor",
    )]
    source_scope = _runtime_coverage_source_scope(app, workspace_id)
    gap_sources = []
    for holder in holders:
        if holder is None:
            continue
        holder_summaries = _runtime_coverage_registry_summaries(holder)
        if source_scope is None or any(summary.manifest.source_sha256 in source_scope for summary in holder_summaries):
            gap_sources.append(getattr(holder, "coverage_family_gaps_live", {}))
    workspace_coverage = getattr(app, "_ag09_family_coverage_by_workspace", {})
    if isinstance(workspace_coverage, Mapping):
        current = workspace_coverage.get(int(workspace_id), {})
        if isinstance(current, Mapping):
            gap_sources.append(current.get("family_gaps", {}))
    for source in gap_sources:
        if isinstance(source, Mapping):
            for category, reasons in source.items():
                gaps.setdefault(category, set()).update(reasons)
    published_rows = app.lquery(
        """SELECT id,source_reference,quantity,unit,quantity_status,row_role
           FROM takeoff_rows WHERE workspace_id=? ORDER BY id""",
        (int(workspace_id),),
    )
    return build_runtime_coverage_publication(
        summaries,
        published_takeoff_rows=[dict(row) for row in published_rows],
        family_gaps={category: sorted(reasons) for category, reasons in gaps.items()},
    )


def _build_unit_rows(app: Any, workspace_id: int, pages: Sequence[Dict[str, Any]]) -> Tuple[List[Tuple[Any, ...]], List[Dict[str, Any]]]:
    rows: List[Tuple[Any, ...]] = []
    summary: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for page in pages:
        if "floor" not in str(page.get("page_type") or "").lower():
            continue
        explicit = extract_unit_area_candidates(page.get("extracted_text"))
        provisional = _unit_boundary_candidates(app, page)
        for candidate in explicit + provisional:
            key = candidate["label"].lower()
            if key in seen:
                continue
            seen.add(key)
            documented = candidate.get("confidence") == "Documented"
            status = "Measured" if documented else "Provisional measured"
            confidence = "Documented" if documented else "Derived"
            source_ref = f"{SOURCE_PREFIX} · unit:{candidate['label']} · page:{int(page['id'])}"
            notes = (
                "Floor area read directly from the drawing/schedule." if documented
                else "Floor area derived from a unique closed boundary around the unit label. Review the highlighted unit boundary before pricing."
            )
            rows.append(_takeoff_row(
                workspace_id=workspace_id, section="Internal", element="Floor area", location=candidate["label"],
                substrate="Other", quantity=_num(candidate["area_m2"]), status=status,
                source_page=str(page.get("page_label") or ""), source_reference=source_ref,
                confidence=confidence, notes=notes, row_role="floor_area",
            ))
            item = dict(candidate)
            item.update({"page_id": int(page["id"]), "page_label": str(page.get("page_label") or ""), "quantity_status": status})
            summary.append(item)
    return rows, summary


def _physical_wall_claim_problem(claim: Any, source_sha256: str, page_indices: Sequence[int]) -> Optional[str]:
    """Check the live claim against its original publication and selected source."""
    from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim

    if type(claim) is not LivePhysicalNetWallClaim:
        return None  # Only the typed integration carries a publication contract.
    publication = claim.publication
    quantity = publication.quantity_evidence
    if (publication.status.value != "corroborated" or quantity is None or quantity.abstained
            or quantity.status != "corroborated" or not _is_finite_number(quantity.value)):
        return "original_physical_wall_quantity_unavailable"
    if (claim.quantity_id != quantity.quantity_id or claim.quantity_m2 != quantity.value
            or quantity.unit.lower() not in {"m2", "m²"}):
        return "physical_wall_claim_quantity_mismatch"
    targets = set(quantity.input_entity_ids)
    if not targets or targets != set(claim.external_wall_ids) or targets != set(publication.external_wall_ids):
        return "physical_wall_quantity_identity_mismatch"
    walls = [wall for wall in claim.canonical_walls if wall.physical_wall_id in targets]
    if len(walls) != len(targets) or any(
        not wall.physical_identity_resolved or wall.canonical_wall_id != wall.physical_wall_id
        or wall.source_sha256 != source_sha256
        or (quantity.metadata.get("revision_id") is not None
            and wall.revision_id != quantity.metadata["revision_id"])
        for wall in walls
    ):
        return "physical_wall_canonical_source_mismatch"
    selected_pages = {index + 1 for index in page_indices}
    if not claim.source_pages or not set(claim.source_pages).issubset(selected_pages):
        return "physical_wall_claim_page_scope_mismatch"
    return None


def _try_physical_net_wall_rows(
    app: Any, workspace_id: int, pages: Sequence[Dict[str, Any]], facades: Sequence[Dict[str, Any]]
) -> Optional[List[Tuple[Any, ...]]]:
    """Attempt to produce source-authenticated physical net-wall takeoff rows.

    Checks:
    1. Direct live physical net-wall authority (`collect_live_physical_net_wall_claim`),
       which replays the complete source-owned wall/opening void chain on the PDF.
    2. Sibling unified registered-wall authority (`build_registered_walls_v139`),
       which binds plan wall lengths, elevation heights, and authenticated B5 opening deductions.

    Returns canonical 21-field takeoff rows if authenticated evidence exists,
    or None to signal that the caller must fall back to gross elevation rows.
    """
    # This producer collection belongs to this workspace and this invocation.
    # A rerun cannot carry an old source's admitted objects into new coverage.
    workspace_coverage = getattr(app, "_ag09_family_coverage_by_workspace", None)
    if not isinstance(workspace_coverage, dict):
        workspace_coverage = {}
        app._ag09_family_coverage_by_workspace = workspace_coverage
    current_coverage: Dict[str, Any] = {
        "summaries": [], "family_gaps": {}, "source_sha256s": [],
        "physical_net_document_ids": [], "source_reports": [], "wall_bridge_mode": None,
        "blocked_commercial_claim_keys": [],
    }
    workspace_coverage[int(workspace_id)] = current_coverage

    opening_rows_by_workspace = getattr(
        app, "_live_opening_takeoff_rows_by_workspace", None
    )
    if not isinstance(opening_rows_by_workspace, dict):
        opening_rows_by_workspace = {}
        app._live_opening_takeoff_rows_by_workspace = opening_rows_by_workspace
    opening_rows_by_workspace[int(workspace_id)] = []

    room_area_rows_by_workspace = getattr(
        app, "_live_room_area_takeoff_rows_by_workspace", None
    )
    if not isinstance(room_area_rows_by_workspace, dict):
        room_area_rows_by_workspace = {}
        app._live_room_area_takeoff_rows_by_workspace = room_area_rows_by_workspace
    room_area_rows_by_workspace[int(workspace_id)] = []

    ceiling_rows_by_workspace = getattr(
        app, "_live_ceiling_takeoff_rows_by_workspace", None
    )
    if not isinstance(ceiling_rows_by_workspace, dict):
        ceiling_rows_by_workspace = {}
        app._live_ceiling_takeoff_rows_by_workspace = ceiling_rows_by_workspace
    ceiling_rows_by_workspace[int(workspace_id)] = []

    seen_opening_quantity_ids: set[str] = set()

    def opening_rows_for_claim(claim: Any) -> List[Tuple[Any, ...]]:
        from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim

        if type(claim) is not LivePhysicalNetWallClaim:
            return []

        openings = {
            opening.canonical_opening_id: opening
            for opening in claim.canonical_openings
            if opening.canonical_opening_id
        }
        quantities = (
            *getattr(claim, "opening_quantity_evidence", ()),
            *getattr(claim, "opening_count_quantity_evidence", ()),
        )
        rows: List[Tuple[Any, ...]] = []
        for quantity in quantities:
            if (
                quantity.quantity_id in seen_opening_quantity_ids
                or quantity.abstained
                or quantity.value is None
                or str(quantity.status or "").strip().lower()
                not in {"firm", "corroborated"}
                or not _is_finite_number(quantity.value)
                or float(quantity.value) <= 0.0
            ):
                continue

            target_ids = tuple(quantity.input_entity_ids)
            target_openings = [openings.get(entity_id) for entity_id in target_ids]
            if (
                not target_ids
                or any(opening is None for opening in target_openings)
            ):
                continue
            resolved_openings = [opening for opening in target_openings if opening is not None]
            if any(
                opening.source_sha256 != resolved_openings[0].source_sha256
                or opening.revision_id != resolved_openings[0].revision_id
                or opening.document_id != resolved_openings[0].document_id
                for opening in resolved_openings[1:]
            ):
                continue

            kinds = {
                str(opening.opening_kind or "").strip().lower()
                for opening in resolved_openings
            }
            if len(kinds) != 1 or next(iter(kinds)) not in {"door", "window"}:
                continue
            opening_kind = next(iter(kinds))
            metadata = (
                quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
            )

            if quantity.family == "opening_area":
                if metadata.get("commercial_projection_allowed") is not True:
                    continue
                element = str(
                    metadata.get("element") or f"{opening_kind.title()} area"
                )
                location = str(
                    metadata.get("location")
                    or resolved_openings[0].type_mark
                    or opening_kind.title()
                )
                unit = "m²"
            elif quantity.family == "opening_count":
                if metadata.get("schedule_corroborated") is not True:
                    continue
                mark = str(metadata.get("opening_mark") or "").strip().upper()
                if not mark:
                    continue
                element = f"{opening_kind.title()} count"
                location = mark
                unit = "ea"
            else:
                continue

            page_ids = sorted(
                {
                    str(opening.page_id)
                    for opening in resolved_openings
                    if str(opening.page_id).strip()
                },
                key=lambda value: (
                    (0, int(value)) if value.isdigit() else (1, value)
                ),
            )
            source_page = ", ".join(f"p{page_id}" for page_id in page_ids)
            source_ref = (
                f"{SOURCE_PREFIX} · opening_quantity:{quantity.quantity_id}"
            )
            notes = (
                f"Source-authenticated {quantity.family}; "
                f"formula={quantity.formula}; "
                f"canonical_openings={','.join(target_ids)}"
            )
            rows.append(
                _takeoff_row(
                    workspace_id=workspace_id,
                    section="Openings",
                    element=element,
                    location=location,
                    substrate="Other",
                    quantity=float(quantity.value),
                    status="Measured",
                    source_page=source_page or "Selected PDF pages",
                    source_reference=source_ref,
                    confidence="Documented",
                    notes=notes,
                    row_role="",
                    unit=unit,
                    preserve_quantity=True,
                )
            )
            seen_opening_quantity_ids.add(quantity.quantity_id)
        return rows

    def room_area_rows_for_claim(claim: Any) -> List[Tuple[Any, ...]]:
        """Project only source-closed room areas into AI review rows."""
        from pb_live_room_area_customer_projection import (
            project_live_room_area_customer_rows,
        )

        projected = project_live_room_area_customer_rows(
            claim,
            workspace_id=int(workspace_id),
            project_id=f"customer-workspace:{int(workspace_id)}",
        )
        rows: List[Tuple[Any, ...]] = []
        for item in projected:
            if (
                str(item.get("origin") or "") != "AI"
                or str(item.get("quantity_status") or "") != "To review"
                or str(item.get("row_role") or "") != "floor_area"
            ):
                raise ValueError("room-area projection bypassed customer review state")
            required = {
                name: str(item.get(name) or "").strip()
                for name in ("section", "element", "location", "substrate")
            }
            if not all(required.values()):
                raise ValueError("room-area projection is missing customer row identity")
            quantity_id = str(item.get("quantity_id") or "").strip()
            if not quantity_id:
                raise ValueError("room-area projection is missing quantity identity")
            unit = str(item.get("unit") or "").strip().lower()
            if unit == "m2":
                unit = "m²"
            rows.append(
                _takeoff_row(
                    workspace_id=int(workspace_id),
                    section=required["section"],
                    element=required["element"],
                    location=required["location"],
                    substrate=required["substrate"],
                    quantity=float(item["quantity"]),
                    status="To review",
                    source_page=str(item.get("source_page") or "Selected PDF pages"),
                    source_reference=(
                        f"{SOURCE_PREFIX} · room_area_quantity:{quantity_id}"
                    ),
                    confidence="Documented",
                    notes=str(item.get("notes") or ""),
                    row_role="floor_area",
                    unit=unit,
                    preserve_quantity=True,
                )
            )
        return rows

    def ceiling_rows_for_source(
        source_path: Path,
        claim_pages: Sequence[int],
        claim: Any,
    ) -> List[Tuple[Any, ...]]:
        """Project only explicit ceiling-review promotions into customer rows."""
        from pb_ceiling_lining_review_promotion import (
            collect_ceiling_lining_review_candidates,
        )

        candidates = collect_ceiling_lining_review_candidates(
            source_path,
            pages=tuple(claim_pages),
            workspace_id=int(workspace_id),
            project_id=f"customer-workspace:{int(workspace_id)}",
            authoritative_area_quantities=tuple(
                getattr(claim, "room_area_quantity_evidence", ())
            ),
        )
        return _ceiling_review_rows_from_candidates(
            int(workspace_id),
            candidates,
        )

    def record_coverage(claim: Any, row: Optional[Tuple[Any, ...]] = None) -> None:
        from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim

        if type(claim) is not LivePhysicalNetWallClaim:
            return
        try:
            from pb_live_canonical_coverage_registry import collect_live_canonical_coverage
            from pb_takeoff_output_authority import TakeoffOutputRow

            quantity = claim.publication.quantity_evidence
            quantities = [
                item
                for item in (
                    quantity,
                    *getattr(claim, "opening_quantity_evidence", ()),
                    *getattr(claim, "opening_count_quantity_evidence", ()),
                    *getattr(claim, "room_area_quantity_evidence", ()),
                )
                if item is not None
            ]
            output_rows = []
            if row is not None:
                named = dict(zip(TAKEOFF_ROW_FIELDS, row))
                output_rows.append(TakeoffOutputRow(
                    quantity_id=claim.quantity_id, description=named["element"],
                    value=named["quantity"], unit=named["unit"],
                    source_page=named["source_page"], is_publishable=False,
                ))
            # Opening and room rows are written later by the same customer
            # transaction. Do not invent pre-publication TakeoffOutputRows here:
            # the runtime lifecycle audit advances PUBLISHED only from the exact
            # rows actually present in takeoff_rows after insertion.
            summaries, family_gaps = collect_live_canonical_coverage(
                objects=(*claim.canonical_walls, *claim.canonical_openings,
                         *claim.canonical_rooms, *claim.canonical_floors),
                quantities=tuple(quantities),
                output_rows=tuple(output_rows),
                registry_run_scope=f"customer_workspace:{int(workspace_id)}",
            )
            current_coverage["summaries"].extend(summaries)
            for category, reasons in family_gaps.items():
                current_coverage["family_gaps"].setdefault(category, []).extend(reasons)
        except Exception as exc:
            current_coverage["family_gaps"].setdefault("wall", []).append(
                f"live_coverage_collection_failed:{type(exc).__name__}"
            )
    def wall_gap(reason: str) -> None:
        current_coverage["family_gaps"].setdefault("wall", []).append(reason)

    # 1. Check only selected sources. Identical bytes are the same authority
    # source; their selected page union is replayed once, without type-mark joins.
    source_groups: Dict[str, Dict[str, Any]] = {}
    if hasattr(app, "lquery"):
        try:
            doc_rows = app.lquery(
                "SELECT id, path FROM documents WHERE workspace_id=? ORDER BY id",
                (int(workspace_id),),
            )
            for d in doc_rows:
                doc_id = int(d["id"])
                page_indices = set()
                for page in pages:
                    try:
                        if int(page.get("document_id") or 0) != doc_id or page.get("selected", 1) in (0, False, "0"):
                            continue
                        page_no = str(page.get("page_no") or "").strip()
                        if page_no.isdecimal() and int(page_no) > 0:
                            page_indices.add(int(page_no) - 1)
                        else:
                            wall_gap("selected_pdf_page_number_invalid")
                    except (TypeError, ValueError, OverflowError):
                        wall_gap("selected_pdf_page_identity_invalid")
                if not page_indices:
                    continue
                p = Path(str(d.get("path") or ""))
                if p.suffix.lower() != ".pdf":
                    continue
                try:
                    sha256 = hashlib.sha256(p.read_bytes()).hexdigest()
                except OSError as exc:
                    wall_gap(f"selected_pdf_source_unreadable:{type(exc).__name__}")
                    continue
                group = source_groups.setdefault(sha256, {"path": p, "document_ids": [], "page_indices": set()})
                group["document_ids"].append(doc_id)
                group["page_indices"].update(page_indices)
        except Exception as exc:
            wall_gap(f"workspace_document_enumeration_failed:{type(exc).__name__}")
    current_coverage["source_sha256s"] = sorted(source_groups)

    accepted: List[Tuple[Any, Tuple[Any, ...], Dict[str, Any]]] = []
    for sha256, group in source_groups.items():
        source_report: Dict[str, Any] = {
            "source_sha256": sha256, "document_ids": sorted(group["document_ids"]),
            "page_indices": sorted(group["page_indices"]), "status": "unavailable",
        }
        current_coverage["source_reports"].append(source_report)
        try:
            from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim

            claim_pages = tuple(sorted(group["page_indices"]))
            claim_kwargs: Dict[str, Any] = {"pages": claim_pages}
            # Physical topology belongs only to positively source-classified
            # floor-plan sheets. Other positively titled drawing sheets remain
            # available as cross-sheet evidence, while unproven pages are never
            # removed from topology scope.
            try:
                from pb_source_floor_plan_page_scope import (
                    source_floor_plan_topology_scope,
                )

                page_scope = source_floor_plan_topology_scope(
                    group["path"], claim_pages
                )
            except Exception:
                page_scope = None
            if page_scope is not None:
                source_report["page_scope"] = page_scope.to_dict()
                topology_pages = page_scope.topology_page_indices()
                if topology_pages is not None:
                    claim_kwargs["topology_pages"] = topology_pages
            claim = collect_live_physical_net_wall_claim(
                group["path"], **claim_kwargs
            )
            from pb_takeoff_output_supersedence import blocked_commercial_claim_key
            for blocked_quantity in (
                getattr(
                    getattr(claim, "publication", None),
                    "quantity_evidence",
                    None,
                ),
                *getattr(claim, "opening_quantity_evidence", ()),
                *getattr(claim, "opening_count_quantity_evidence", ()),
                *getattr(claim, "room_area_quantity_evidence", ()),
            ):
                if blocked_quantity is None:
                    continue
                blocked_key = blocked_commercial_claim_key(
                    blocked_quantity,
                    source_sha256=sha256,
                )
                if blocked_key is not None:
                    current_coverage["blocked_commercial_claim_keys"].append(
                        blocked_key
                    )
            opening_rows_by_workspace[int(workspace_id)].extend(
                opening_rows_for_claim(claim)
            )
            try:
                room_area_rows_by_workspace[int(workspace_id)].extend(
                    room_area_rows_for_claim(claim)
                )
            except Exception as room_output_exc:
                current_coverage["family_gaps"].setdefault("floor", []).append(
                    "live_room_area_customer_projection_failed:"
                    f"{type(room_output_exc).__name__}"
                )
            try:
                ceiling_rows_by_workspace[int(workspace_id)].extend(
                    ceiling_rows_for_source(
                        group["path"],
                        claim_pages,
                        claim,
                    )
                )
            except Exception as ceiling_output_exc:
                current_coverage["family_gaps"].setdefault(
                    "ceiling", []
                ).append(
                    "live_ceiling_customer_projection_failed:"
                    f"{type(ceiling_output_exc).__name__}"
                )
            status_val = getattr(claim.status, "value", str(claim.status))
            source_report.update(status=status_val, quantity_id=claim.quantity_id,
                                 reason_codes=list(getattr(claim, "reason_codes", ())))
            if status_val == "corroborated":
                problem = _physical_wall_claim_problem(claim, sha256, group["page_indices"])
                if problem:
                    wall_gap(problem)
                    source_report.update(status="review", reason_codes=[problem])
                    record_coverage(claim)
                    continue
            if (
                status_val == "corroborated"
                and _is_finite_number(claim.quantity_m2)
                and claim.quantity_m2 > 0.0
                and claim.quantity_id
            ):
                qty = float(claim.quantity_m2)
                src_pages = claim.source_pages if hasattr(claim, "source_pages") and claim.source_pages else ()
                source_page_str = ", ".join(f"p{p}" for p in src_pages) if src_pages else "Selected PDF pages"
                source_ref = f"{SOURCE_PREFIX} · physical_net_wall:{claim.quantity_id}"
                confidence = "Documented" if getattr(claim, "confidence", 0.0) >= 0.8 else "Derived"
                notes = (
                    "External walling — source-authenticated physical net whole-wall area with proven opening voids deducted."
                )
                all_subs = [s for f in facades if f.get("document_id") in group["document_ids"]
                            for s in (f.get("substrates") or [])]
                sub_names = sorted({s.get("name") for s in all_subs if s.get("name")})
                substrate_name = sub_names[0] if len(sub_names) == 1 else "External walling"
                location_str = (
                    f"External perimeter walling · {substrate_name}"
                    if substrate_name != "External walling"
                    else "External perimeter walling · Physical net wall"
                )
                row = _takeoff_row(
                    workspace_id=workspace_id,
                    section="External",
                    element="External walls / cladding",
                    location=location_str,
                    substrate=substrate_name,
                    quantity=qty,
                    status="Measured",
                    source_page=source_page_str,
                    source_reference=source_ref,
                    confidence=confidence,
                    notes=notes,
                    row_role="external_wall",
                    preserve_quantity=True,
                )
                accepted.append((claim, row, source_report))
            else:
                record_coverage(claim)
        except Exception as exc:
            reason = f"live_physical_net_wall_collection_failed:{type(exc).__name__}"
            wall_gap(reason)
            source_report.update(status="review", reason_codes=[reason])

    quantity_sources: Dict[str, List[str]] = {}
    for claim, _, source_report in accepted:
        quantity_sources.setdefault(claim.quantity_id, []).append(source_report["source_sha256"])
    direct_rows = []
    for claim, row, source_report in accepted:
        if len(quantity_sources[claim.quantity_id]) > 1:
            wall_gap("conflicting_quantity_identity_across_sources")
            source_report.update(status="review", reason_codes=["conflicting_quantity_identity_across_sources"])
            record_coverage(claim)
            continue
        direct_rows.append(row)
        current_coverage["physical_net_document_ids"].extend(source_report["document_ids"])
        record_coverage(claim, row)
    if direct_rows:
        current_coverage["wall_bridge_mode"] = "direct"
        return direct_rows
    if any(report["status"] in {"review", "conflict", "ambiguous"}
           for report in current_coverage["source_reports"]):
        return None  # An unresolved identity cannot be rescued by a weaker path.

    # 2. Check unified registered-wall authority with verified opening deductions
    if hasattr(app, "build_registered_walls_v139") and callable(getattr(app, "build_registered_walls_v139")):
        try:
            reg_walls = app.build_registered_walls_v139(int(workspace_id))
            if reg_walls:
                has_authenticated_openings = any(
                    float(w.get("opening_deduction_m2") or 0.0) > 0.0
                    for w in reg_walls
                )
                has_verified_height = any(
                    w.get("height_confidence") in {"Verified", "High"}
                    for w in reg_walls
                )
                if has_authenticated_openings or has_verified_height:
                    if hasattr(app, "opening_detail_definitions") and hasattr(app, "building_openings"):
                        try:
                            from pb_opening_detail_definition_bridge import (
                                consolidate_opening_identities,
                                enrich_openings_with_detail_definitions,
                                apply_opening_deductions_to_walls,
                            )
                            consolidated = consolidate_opening_identities(app.building_openings)
                            enriched = enrich_openings_with_detail_definitions(
                                consolidated,
                                app.opening_detail_definitions,
                                getattr(app, "opening_mark_map", None),
                            )
                            reg_walls = apply_opening_deductions_to_walls(reg_walls, enriched)
                        except Exception:
                            pass
                    if hasattr(app, "wall_finish_callout_bindings"):
                        try:
                            from pb_bound_wall_finish_customer_bridge import apply_finish_callout_bindings_to_walls
                            reg_walls = apply_finish_callout_bindings_to_walls(reg_walls, app.wall_finish_callout_bindings)
                        except Exception:
                            pass
                    reg_rows: List[Tuple[Any, ...]] = []
                    for w_idx, w in enumerate(reg_walls):
                        net_qty = round(max(0.0, float(w.get("net_m2") or 0.0)), 2)
                        if net_qty <= 0.0:
                            continue
                        sub = str(w.get("substrate") or "External walling")
                        ref = str(w.get("wall_ref") or w.get("wall_id") or w.get("candidate_id") or w.get("id") or f"wall_{w_idx+1}")
                        side = str(w.get("side") or "Perimeter")
                        gross_val = float(w.get("gross_m2") or 0.0)
                        ded_val = float(w.get("opening_deduction_m2") or 0.0)
                        h_status = str(w.get("height_status") or "")
                        callout_note = f" Authenticated callout finish: {sub}." if w.get("callout_bound") else ""
                        ded_details = ""
                        if w.get("openings"):
                            op_summaries = []
                            for op in w.get("openings"):
                                op_mark = (
                                    (getattr(op, "type_mark", None) or getattr(op, "mark", None) or getattr(op, "opening_id", None))
                                    if hasattr(op, "type_mark") or hasattr(op, "mark")
                                    else (op.get("type_mark") or op.get("mark") or op.get("opening_id") or "opening")
                                    if isinstance(op, dict)
                                    else "opening"
                                )
                                op_area = (
                                    float(getattr(op, "area_m2", 0.0) or 0.0)
                                    if hasattr(op, "area_m2")
                                    else float(op.get("area_m2") or op.get("deduction_m2") or 0.0)
                                    if isinstance(op, dict)
                                    else 0.0
                                )
                                if op_area > 0.0:
                                    op_summaries.append(f"{op_mark} ({op_area:.2f} m²)")
                            if op_summaries:
                                ded_details = f" Deductions: {', '.join(op_summaries)}."

                        doc_provenance = ""
                        if w.get("source_document") or w.get("document_name"):
                            doc_provenance = f" Doc: {w.get('source_document') or w.get('document_name')}."

                        source_page_str = (
                            str(w.get("source_page") or "")
                            or (
                                f"Plan p.{w.get('plan_page_id')} / Elev p.{w.get('elevation_page_id')}"
                                if w.get("plan_page_id") and w.get("elevation_page_id")
                                else f"Page {w.get('plan_page_id') or w.get('page_id') or w.get('page_no')}"
                                if (w.get("plan_page_id") or w.get("page_id") or w.get("page_no"))
                                else "Registered plan/elevation geometry"
                            )
                        )

                        note_text = f"Gross {gross_val:.2f} m²; authenticated opening deductions {ded_val:.2f} m².{ded_details} {h_status}{callout_note}{doc_provenance}".strip()
                        source_ref = (
                            f"{SOURCE_PREFIX} · registered_wall:{ref} · {w.get('finish_callout_binding_id')}"
                            if w.get("callout_bound")
                            else f"{SOURCE_PREFIX} · registered_wall:{ref}"
                        )
                        reg_rows.append(_takeoff_row(
                            workspace_id=workspace_id,
                            section="External",
                            element="External walls / cladding",
                            location=f"{side} · {ref}",
                            substrate=sub,
                            quantity=net_qty,
                            status="Measured",
                            source_page=source_page_str,
                            source_reference=source_ref,
                            confidence="Documented" if (w.get("height_confidence") in {"Verified", "High"} or w.get("callout_bound")) else "Derived",
                            notes=note_text,
                            row_role="external_wall",
                        ))
                    if reg_rows:
                        current_coverage["wall_bridge_mode"] = "registered"
                        wall_gap("registered_wall_path_has_no_live_canonical_registry")
                        return reg_rows
        except Exception:
            pass

    return None


def _build_facade_rows(app: Any, workspace_id: int, pages: Sequence[Dict[str, Any]]) -> Tuple[List[Tuple[Any, ...]], List[Dict[str, Any]]]:
    rows: List[Tuple[Any, ...]] = []
    facades: List[Dict[str, Any]] = []
    for page in pages:
        if page.get("selected", 1) in (0, False, "0"):
            continue
        if "elevation" not in str(page.get("page_type") or "").lower():
            continue
        path = _regular_image(page.get("image_path"))
        pxpm = _num(page.get("px_per_m"))
        component = _drawing_component(path, elevation=True) if path else None
        face = _page_face(page.get("extracted_text"), page.get("page_label"))
        explicit = extract_substrate_area_candidates(page.get("extracted_text"))
        substrates = _substrates_from_text(page.get("extracted_text"))
        facade: Dict[str, Any] = {
            "page_id": int(page["id"]), "page_label": str(page.get("page_label") or ""), "face": face,
            "document_id": int(page.get("document_id") or 0),
            "substrates": substrates, "explicit_areas": explicit, "gross_m2": 0.0, "height_m": 0.0,
        }
        if component and pxpm > 0:
            _x, _y, w, h = component["bbox"]
            facade["width_m"] = round(w / pxpm, 3)
            facade["height_m"] = round(h / pxpm, 3)
            facade["gross_m2"] = round((w * h) / (pxpm * pxpm), 2)
            facade["bbox"] = component["bbox"]
            facade["polygon"] = component["polygon"]
        facades.append(facade)

    # 1. Prefer authenticated physical net-wall evidence where available
    physical_net_rows = _try_physical_net_wall_rows(app, workspace_id, pages, facades)
    if physical_net_rows is not None and len(physical_net_rows) > 0:
        rows.extend(physical_net_rows)
        coverage = getattr(app, "_ag09_family_coverage_by_workspace", {}).get(int(workspace_id), {})
        covered_documents = set(coverage.get("physical_net_document_ids", ()))
        for facade in facades:
            if coverage.get("wall_bridge_mode") == "registered" or facade["document_id"] in covered_documents:
                facade["superseded_by_physical_net_wall"] = True

    # 2. Fall back to explicit substrate text areas or gross calibrated elevation areas
    for facade in facades:
        if facade.get("superseded_by_physical_net_wall"):
            continue
        explicit = facade.get("explicit_areas") or []
        page_label = facade.get("page_label") or ""
        page_id = facade.get("page_id") or 0
        face = facade.get("face") or ""
        substrates = facade.get("substrates") or []

        if explicit:
            for item in explicit:
                sub = item["substrate"]
                rows.append(_takeoff_row(
                    workspace_id=workspace_id, section="External", element="External walls / cladding",
                    location=f"{face.title() if face else 'Elevation'} · {sub['name']}", substrate=sub["name"],
                    quantity=_num(item["area_m2"]), status="Measured", source_page=page_label,
                    source_reference=f"{SOURCE_PREFIX} · facade:{int(page_id)} · {sub['code']}",
                    confidence="Documented", notes=f"Substrate area read directly from drawing text: {item['source']}",
                ))
        elif facade.get("gross_m2", 0.0) > 0:
            if len(substrates) == 1:
                sub = substrates[0]
                location = f"{face.title() if face else 'Elevation'} · {sub['name']}"
                substrate = sub["name"]
                note = "Gross facade area derived from calibrated elevation drawing cluster; opening deductions and edge conditions require review."
            else:
                location = f"{face.title() if face else 'Elevation'} · Mixed external substrate"
                substrate = "Other"
                names = ", ".join(item["name"] for item in substrates) or "No reliable material label found"
                note = f"Gross calibrated facade area. Mixed substrate split requires review ({names}). No automatic split is invented."
            rows.append(_takeoff_row(
                workspace_id=workspace_id, section="External", element="External walls / cladding", location=location,
                substrate=substrate, quantity=_num(facade["gross_m2"]), status="Provisional measured",
                source_page=page_label, source_reference=f"{SOURCE_PREFIX} · facade:{int(page_id)} · gross",
                confidence="Derived", notes=note,
            ))

    return rows, facades


def _build_internal_partition_rows(
    app: Any,
    workspace_id: int,
    pages: Sequence[Dict[str, Any]],
    footprint: Optional[Dict[str, Any]],
) -> Tuple[List[Tuple[Any, ...]], List[Dict[str, Any]]]:
    """Extract evidenced internal partition walls from vector drawing geometry.

    Leverages `pb_wall_fill_internal_partition_evidence` to detect solid-fill wall bands
    and distinguish genuine internal partitions from furniture/desk symbols, title-block borders,
    or perimeter walls. Emits canonical takeoff rows in linear meters (`lm`).
    """
    rows: List[Tuple[Any, ...]] = []
    partitions: List[Dict[str, Any]] = []

    doc_paths: Dict[int, Path] = {}
    if hasattr(app, "lquery"):
        try:
            doc_rows = app.lquery(
                "SELECT id, path FROM documents WHERE workspace_id=? ORDER BY id",
                (int(workspace_id),),
            )
            for d in doc_rows:
                p = Path(str(d.get("path") or ""))
                if p.is_file() and p.suffix.lower() == ".pdf":
                    doc_paths[int(d["id"])] = p
        except Exception:
            pass

    length_m = 0.0
    width_m = 0.0
    if footprint:
        w_f = _num(footprint.get("width_m"))
        d_f = _num(footprint.get("depth_m"))
        if w_f > 0 and d_f > 0:
            length_m = max(w_f, d_f)
            width_m = min(w_f, d_f)

    for page in pages:
        ptype = str(page.get("page_type") or "").lower()
        if "floor" not in ptype and "plan" not in ptype:
            continue
        doc_id = int(page.get("document_id") or 0)
        doc_path = doc_paths.get(doc_id)
        if not doc_path:
            continue

        page_no = int(page.get("page_no") or 1)
        px_per_m = _num(page.get("px_per_m"))

        p_len_m = length_m
        p_wid_m = width_m
        if p_len_m <= 0 or p_wid_m <= 0:
            if px_per_m > 0:
                p_len_m = _num(page.get("width_px"), 1000.0) / px_per_m
                p_wid_m = _num(page.get("height_px"), 700.0) / px_per_m

        if p_len_m <= 0 or p_wid_m <= 0:
            continue

        try:
            from pb_wall_fill_internal_partition_evidence import resolve_internal_partition_length_m
            fitz_mod = getattr(app, "fitz", None)
            if fitz_mod is None:
                import fitz as fitz_mod
            doc = fitz_mod.open(doc_path)
            try:
                pdf_page = doc[page_no - 1]
                drawings = pdf_page.get_drawings()
                evidence = resolve_internal_partition_length_m(
                    drawings,
                    length_m=p_len_m,
                    width_m=p_wid_m,
                    page=pdf_page,
                )
            finally:
                doc.close()

            if evidence.status == "found" and evidence.total_length_m > 0:
                qty_lm = round(max(0.0, float(evidence.total_length_m)), 2)
                page_label = str(page.get("page_label") or f"p{page_no}")
                note = f"Internal partition length derived from vector geometry: {evidence.reason}."
                if evidence.wall_thickness_m:
                    note += f" Thickness: {evidence.wall_thickness_m:.3f} m."

                row = _takeoff_row(
                    workspace_id=workspace_id,
                    section="Internal",
                    element="Internal partitions / walls",
                    location=f"Internal partitions · {page_label}",
                    substrate="Plasterboard / partition",
                    quantity=qty_lm,
                    status="Measured",
                    source_page=page_label,
                    source_reference=f"{SOURCE_PREFIX} · internal_partition:{int(page['id'])}",
                    confidence="Documented",
                    notes=note,
                    row_role="internal_partition",
                    unit="lm",
                )
                rows.append(row)
                partitions.append({
                    "page_id": int(page["id"]),
                    "page_label": page_label,
                    "total_length_m": qty_lm,
                    "wall_thickness_m": evidence.wall_thickness_m,
                    "segment_lengths_m": list(evidence.segment_lengths_m),
                    "reason": evidence.reason,
                })
        except Exception:
            pass

    return rows, partitions


def _surface_code_for(substrates: Sequence[Dict[str, str]]) -> str:
    if len(substrates) != 1:
        return "OTHER"
    code = str(substrates[0].get("code") or "OTHER")
    if surface_v1212 is not None:
        valid = {str(item.get("code")) for item in surface_v1212.substrate_presets()}
        if code in valid:
            return code
        inferred = surface_v1212.infer_substrate(substrates[0].get("name"))
        return inferred or "OTHER"
    return code


def _refresh_auto_model(app: Any, workspace_id: int, footprint: Optional[Dict[str, Any]], facades: Sequence[Dict[str, Any]]) -> Optional[int]:
    existing = app.lquery(
        "SELECT * FROM model_masses WHERE workspace_id=? AND source_reference LIKE ? ORDER BY id",
        (workspace_id, MODEL_SOURCE_PREFIX + "%"),
    )
    if not footprint:
        return int(existing[0]["id"]) if existing else None
    heights = [_num(item.get("height_m")) for item in facades if 1.5 <= _num(item.get("height_m")) <= 100.0]
    height = float(np.median(heights)) if heights else 2.7
    width = max(0.1, _num(footprint.get("width_m")))
    depth = max(0.1, _num(footprint.get("depth_m")))
    source = f"{MODEL_SOURCE_PREFIX} · floor:{footprint.get('page_id')}"
    if existing:
        mass_id = int(existing[0]["id"])
        app.lexecute(
            "UPDATE model_masses SET label=?,x=0,y=0,z=0,width=?,depth=?,height=?,finish=?,source_reference=?,confidence=?,notes=? WHERE id=?",
            ("Automatic building envelope", width, depth, height, "External envelope", source, "Derived",
             "Bounding envelope cross-referenced from calibrated floor plan and selected elevations. Review before final quantity issue.", mass_id),
        )
        for duplicate in existing[1:]:
            app.lexecute("DELETE FROM model_openings WHERE mass_id=?", (int(duplicate["id"]),))
            app.lexecute("DELETE FROM model_masses WHERE id=?", (int(duplicate["id"]),))
    else:
        mass_id = int(app.lexecute(
            """INSERT INTO model_masses(workspace_id,label,level_name,x,y,z,width,depth,height,finish,source_reference,confidence,notes,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (workspace_id, "Automatic building envelope", "Ground", 0, 0, 0, width, depth, height, "External envelope",
             source, "Derived", "Bounding envelope cross-referenced from calibrated floor plan and selected elevations. Review before final quantity issue.", app.now_stamp()),
        ))

    # Populate face metadata without overwriting an estimator's later manual edits.
    raw = app.lquery("SELECT value FROM workspace_settings WHERE workspace_id=? AND key=?", (workspace_id, "3d_surface_editor_v1212"))
    state = _safe_json(raw[0].get("value") if raw else "{}", {})
    overrides = dict(state.get("surfaces") or {}) if isinstance(state, dict) else {}
    by_face = {str(item.get("face")): item for item in facades if item.get("face")}
    for face in ("front", "rear", "left", "right"):
        item = by_face.get(face)
        if not item:
            continue
        surface_id = f"mass:{mass_id}:{face}"
        existing_override = dict(overrides.get(surface_id) or {})
        existing_notes = str(existing_override.get("notes") or "")
        if existing_override and not existing_notes.startswith(f"[AUTO v{VERSION}]"):
            continue
        names = ", ".join(sub.get("name", "") for sub in item.get("substrates") or []) or "substrate to confirm"
        overrides[surface_id] = {
            "substrate": _surface_code_for(item.get("substrates") or []),
            "status": "Provisional",
            "progress_pct": _num(existing_override.get("progress_pct")),
            "notes": f"[AUTO v{VERSION}] {item.get('page_label') or face}: {names}; gross elevation {_num(item.get('gross_m2')):.2f} m². Review mixed-substrate splits/openings.",
        }
    app.lexecute(
        """INSERT INTO workspace_settings(workspace_id,key,value,updated_at) VALUES(?,?,?,?)
           ON CONFLICT(workspace_id,key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at""",
        (workspace_id, "3d_surface_editor_v1212", json.dumps({"surfaces": overrides, "saved_at": app.now_stamp()}, separators=(",", ":")), app.now_stamp()),
    )
    return mass_id


def _ensure_opening_evidence_v175(app: Any, workspace_id: int, pages: Sequence[Dict[str, Any]]) -> None:
    """Ensure P5 opening evidence is generated for drawing sheets automatically.

    Eliminates the requirement for an estimator to manually enter Accuracy Lab
    and press 'Run native vector analysis' before opening deductions take effect.
    Idempotent: skips any page whose opening evidence is already recorded.
    """
    if not hasattr(app, "analyse_stored_page_v130") or not callable(getattr(app, "analyse_stored_page_v130")):
        return
    for page in pages:
        pid = int(page.get("id") or 0)
        if pid <= 0:
            continue
        key = f"opening_evidence_v175_page_{pid}"
        if hasattr(app, "workspace_setting"):
            try:
                existing = app.workspace_setting(int(workspace_id), key, None)
                if existing:
                    continue
            except Exception:
                pass
        ptype = str(page.get("page_type") or "").lower()
        if any(t in ptype for t in ("floor", "plan", "elevation", "drawing", "section")):
            try:
                app.analyse_stored_page_v130(pid)
            except Exception:
                pass


def _build_bound_wall_finish_rows(
    app: Any,
    workspace_id: int,
    pages: Sequence[Dict[str, Any]],
) -> Tuple[List[Tuple[Any, ...]], List[Dict[str, Any]]]:
    """Extract source-bound wall finish rows via SourceBoundWallFinishQuantityAuthority.

    Consumes authenticated net-wall geometry directly via face/finish binding without
    reinventing or duplicating wall geometry (AG-04).
    """
    try:
        from pb_bound_wall_finish_customer_bridge import build_bound_wall_finish_rows
        return build_bound_wall_finish_rows(app, workspace_id, pages)
    except Exception:
        return [], []


def analyse_workspace(app: Any, workspace_id: int) -> Dict[str, Any]:
    """Run the automatic non-AI geometry pipeline on selected, rendered sheets."""
    pages = app.lquery(
        """SELECT p.*,d.file_name FROM pages p JOIN documents d ON d.id=p.document_id
           WHERE p.workspace_id=? AND COALESCE(p.selected,0)=1 ORDER BY p.id""",
        (int(workspace_id),),
    )
    # AG-02: Auto-generate opening evidence for drawing sheets without manual Accuracy Lab interaction
    _ensure_opening_evidence_v175(app, int(workspace_id), [dict(p) for p in pages])

    calibrations = []
    for page in pages:
        result = _auto_calibrate_page(app, dict(page))
        if result:
            calibrations.append(result)
    # Refresh page rows after calibration updates.
    pages = app.lquery(
        """SELECT p.*,d.file_name FROM pages p JOIN documents d ON d.id=p.document_id
           WHERE p.workspace_id=? AND COALESCE(p.selected,0)=1 ORDER BY p.id""",
        (int(workspace_id),),
    )
    footprint = _detect_footprint(app, [dict(p) for p in pages])
    cross = _cross_calibrate_elevations(app, [dict(p) for p in pages], footprint)
    if cross:
        calibrations.extend(cross)
        pages = app.lquery(
            """SELECT p.*,d.file_name FROM pages p JOIN documents d ON d.id=p.document_id
               WHERE p.workspace_id=? AND COALESCE(p.selected,0)=1 ORDER BY p.id""",
            (int(workspace_id),),
        )
    unit_rows, units = _build_unit_rows(app, int(workspace_id), [dict(p) for p in pages])
    facade_rows, facades = _build_facade_rows(app, int(workspace_id), [dict(p) for p in pages])
    partition_rows, partitions = _build_internal_partition_rows(app, int(workspace_id), [dict(p) for p in pages], footprint)
    finish_rows, finishes = _build_bound_wall_finish_rows(app, int(workspace_id), [dict(p) for p in pages])
    opening_rows = list(
        getattr(app, "_live_opening_takeoff_rows_by_workspace", {}).get(
            int(workspace_id), ()
        )
    )
    room_area_rows = list(
        getattr(app, "_live_room_area_takeoff_rows_by_workspace", {}).get(
            int(workspace_id), ()
        )
    )
    ceiling_rows = list(
        getattr(app, "_live_ceiling_takeoff_rows_by_workspace", {}).get(
            int(workspace_id), ()
        )
    )
    all_auto_rows = (
        unit_rows
        + facade_rows
        + opening_rows
        + room_area_rows
        + ceiling_rows
        + partition_rows
        + finish_rows
    )

    # AG-08: Collect identity-proven semantic conflicts from live runtime
    # evidence and annotate only the affected canonical takeoff rows. No
    # proximity/count heuristics and no benchmark truth are consulted here.
    from pb_semantic_conflict_guard import (
        annotate_rows_with_conflicts,
        collect_runtime_semantic_conflicts,
    )

    conflicts = collect_runtime_semantic_conflicts(
        app,
        finishes=finishes,
    )
    if conflicts:
        all_auto_rows = annotate_rows_with_conflicts(
            all_auto_rows,
            conflicts,
        )

    # Preserve only earlier source-closed output when this exact source +
    # semantic claim + physical identity is explicitly blocked by the current
    # run. Unreviewed drafts are reinserted through the core writer; estimator-
    # reviewed AI rows stay in-place so review/authority columns survive.
    # Changed sources, disappeared objects and current replacements invalidate
    # prior rows normally.
    preserved_source_closed_rows: List[Tuple[Any, ...]] = []
    retained_reviewed_source_closed_row_ids: Tuple[int, ...] = ()
    coverage = getattr(app, "_ag09_family_coverage_by_workspace", {}).get(
        int(workspace_id), {}
    )
    blocked_claim_keys = (
        coverage.get("blocked_commercial_claim_keys", ())
        if isinstance(coverage, Mapping)
        else ()
    )
    if blocked_claim_keys:
        from pb_takeoff_output_supersedence import (
            select_prior_commercial_rows_to_preserve,
            select_prior_reviewed_row_ids_to_retain,
        )

        table_info = app.lquery("PRAGMA table_info(takeoff_rows)")
        available_columns = {
            str(row.get("name") or "").strip()
            for row in table_info
            if str(row.get("name") or "").strip()
        }
        optional_columns = tuple(
            name
            for name in (
                *takeoff_contract.COMMERCIAL_AUTHORITY_FIELDS,
                *takeoff_contract.PROVENANCE_FIELDS,
            )
            if name in available_columns
        )
        selected_columns = ("id", *TAKEOFF_ROW_FIELDS, *optional_columns)
        prior_rows = app.lquery(
            f"""SELECT {','.join(selected_columns)}
                FROM takeoff_rows
                WHERE workspace_id=? AND source_reference LIKE ?
                ORDER BY id""",
            (int(workspace_id), SOURCE_PREFIX + "%"),
        )
        replacement_rows = [
            dict(zip(TAKEOFF_ROW_FIELDS, row))
            for row in all_auto_rows
        ]
        prior_named_rows = [dict(row) for row in prior_rows]
        preserved = select_prior_commercial_rows_to_preserve(
            prior_named_rows,
            blocked_claim_keys=blocked_claim_keys,
            replacement_rows=replacement_rows,
        )
        retained_reviewed_source_closed_row_ids = (
            select_prior_reviewed_row_ids_to_retain(
                prior_named_rows,
                blocked_claim_keys=blocked_claim_keys,
                replacement_rows=replacement_rows,
            )
        )
        preserved_source_closed_rows = [
            takeoff_contract.values_from_mapping(row, TAKEOFF_ROW_FIELDS)
            for row in preserved
        ]
        all_auto_rows = all_auto_rows + preserved_source_closed_rows

    # Rows, envelope and report are one publication: all commit or none do.
    # Preserve the historical three-argument call when there is nothing to
    # retain so existing wrappers/tests remain source-compatible.
    publication_context = (
        _auto_publication(
            app,
            int(workspace_id),
            all_auto_rows,
            preserve_row_ids=retained_reviewed_source_closed_row_ids,
        )
        if retained_reviewed_source_closed_row_ids
        else _auto_publication(app, int(workspace_id), all_auto_rows)
    )
    with publication_context as publication:
        mass_id = _refresh_auto_model(publication, int(workspace_id), footprint, facades)
        coverage_lifecycle = _runtime_coverage_lifecycle_report(
            publication,
            int(workspace_id),
        )
        report = {
            "version": VERSION, "analysed_at": app.now_stamp(), "selected_pages": len(pages),
            "calibrations": calibrations, "footprint": footprint, "units": units, "facades": facades,
            "partitions": partitions, "finishes": finishes,
            "opening_takeoff_rows": len(opening_rows),
            "room_area_takeoff_rows": len(room_area_rows),
            "ceiling_takeoff_rows": len(ceiling_rows),
            "preserved_source_closed_rows": len(preserved_source_closed_rows),
            "retained_reviewed_source_closed_rows": len(
                retained_reviewed_source_closed_row_ids
            ),
            "semantic_conflicts": [c.to_dict() if hasattr(c, "to_dict") else dict(c) for c in conflicts],
            "coverage_lifecycle": coverage_lifecycle,
            "auto_takeoff_rows": (
                len(all_auto_rows)
                + len(retained_reviewed_source_closed_row_ids)
            ),
            "model_mass_id": mass_id,
        }
        _setting_set(publication, int(workspace_id), report)
    return report


def auto_geometry_panel(app: Any, workspace: Dict[str, Any]) -> None:
    workspace_id = int(workspace["id"])
    report = _setting_get(app, workspace_id)
    with app.st.expander("⚙️ Automatic plan geometry", expanded=not bool(report)):
        app.st.caption(
            "No AI required. PlanReader triages sheets, self-calibrates from drawing dimensions where possible, "
            "reads documented unit floor areas, derives reviewable unit boundaries, cross-references floor/elevation geometry, "
            "and prepares the external envelope/3D face metadata. Manual measurements always take priority."
        )
        pages = app.lquery("SELECT selected,page_type FROM pages WHERE workspace_id=?", (workspace_id,))
        kept = sum(1 for row in pages if int(row.get("selected") or 0) == 1)
        discarded = len(pages) - kept
        c1, c2, c3, c4 = app.st.columns(4)
        c1.metric("Take-off sheets", kept)
        c2.metric("Auto-discarded", discarded)
        c3.metric("Unit areas found", len(report.get("units") or []))
        c4.metric("External rows", len([f for f in report.get("facades") or [] if _num(f.get("gross_m2")) > 0 or f.get("explicit_areas")]))
        coverage = report.get("coverage_lifecycle") or {}
        coverage_status = str(coverage.get("status") or "")
        stage_counts = coverage.get("stage_counts") or {}
        if coverage_status and coverage_status != "unavailable":
            stage_text = " · ".join(
                f"{stage.title()} {stage_counts.get(stage)}"
                for stage in (
                    "DETECTED",
                    "AUTHENTICATED",
                    "CANONICALIZED",
                    "QUANTIFIED",
                    "PUBLISHED",
                )
                if stage_counts.get(stage) is not None
            )
            app.st.caption(
                "Coverage lifecycle — explicit dependency links only; "
                f"family completeness remains UNKNOWN. {stage_text}"
            )
        elif report:
            app.st.caption(
                "Coverage lifecycle unavailable for object families that have not "
                "published a live coverage registry."
            )
        if app.st.button("Re-run automatic geometry", type="secondary", use_container_width=True, key=f"auto_geometry_refresh_{workspace_id}"):
            with app.st.spinner("Cross-referencing selected plans and elevations…"):
                result = analyse_workspace(app, workspace_id)
            app.st.success(
                f"Automatic geometry refreshed: {len(result.get('units') or [])} unit area(s), "
                f"{len(result.get('facades') or [])} elevation(s), {result.get('auto_takeoff_rows', 0)} take-off row(s)."
            )
            app.st.rerun()
        if report:
            methods: Dict[str, int] = {}
            for item in report.get("calibrations") or []:
                method = str(item.get("method") or "Other")
                methods[method] = methods.get(method, 0) + 1
            if methods:
                app.st.caption("Calibration: " + " · ".join(f"{name} {count}" for name, count in methods.items()))
            unresolved = [f for f in report.get("facades") or [] if len(f.get("substrates") or []) != 1 and not f.get("explicit_areas")]
            if unresolved:
                app.st.info(
                    f"{len(unresolved)} elevation(s) contain mixed/unclear substrate information. PlanReader keeps those gross areas provisional instead of inventing a material split."
                )


def apply(app: Any) -> None:
    if getattr(app, "_pb_auto_geometry_v1219_applied", False):
        return
    app._pb_auto_geometry_v1219_applied = True

    base_index = app.index_document_pages
    base_process = app.process_document

    def _auto_index_document_pages(document_id: int, *args, **kwargs):
        result = base_index(document_id, *args, **kwargs)
        try:
            auto_select_document_pages(app, int(document_id))
        except Exception:
            # Page indexing must remain usable even if an optional heuristic fails.
            pass
        return result

    def _auto_process_document(document_id: int, force: bool = False, page_ids=None, progress_cb=None):
        requested = page_ids
        if requested is None:
            indexed = app.lquery(
                "SELECT page_no FROM pages WHERE document_id=? AND COALESCE(selected,0)=1 ORDER BY page_no",
                (int(document_id),),
            )
            if indexed:
                requested = [int(row["page_no"]) for row in indexed]
        result = base_process(document_id, force=force, page_ids=requested, progress_cb=progress_cb)
        try:
            docs = app.lquery("SELECT workspace_id FROM documents WHERE id=?", (int(document_id),))
            if docs:
                analyse_workspace(app, int(docs[0]["workspace_id"]))
        except Exception:
            # Rendering a drawing must not fail because an optional automatic
            # measurement heuristic could not interpret one unusual sheet.
            pass
        return result

    app.index_document_pages = _auto_index_document_pages
    app.process_document = _auto_process_document
    app.auto_select_document_pages = lambda document_id: auto_select_document_pages(app, int(document_id))
    app.run_auto_geometry = lambda workspace_id: analyse_workspace(app, int(workspace_id))
    app.page_takeoff_relevance = page_relevance

    # The selected-page wrapper resolves this module global at runtime, so an
    # additive panel here appears in the default no-AI take-off without changing
    # its proven save/build logic.
    try:
        import pb_no_ai_takeoff_v1216 as noai
        if not getattr(noai, "_pb_auto_geometry_panel_v1219", False):
            base_panel = noai.no_ai_takeoff_panel

            def _panel_with_auto_geometry(app_obj, workspace):
                auto_geometry_panel(app_obj, workspace)
                return base_panel(app_obj, workspace)

            noai.no_ai_takeoff_panel = _panel_with_auto_geometry
            noai._pb_auto_geometry_panel_v1219 = True
    except Exception:
        pass
