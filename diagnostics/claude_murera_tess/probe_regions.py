"""Research probe: generic numeric-text region proposal on a raster drawing page.

Diagnostic only. Proposes digit-sized connected-component groups (horizontal
and rotated) from a permissive ink mask with long drafting lines removed.
No target values or coordinates are used to find regions.
"""
from __future__ import annotations

import cv2
import fitz
import numpy as np

DPI = 300


def page_gray(pdf_path: str, page_index: int) -> np.ndarray:
    doc = fitz.open(pdf_path)
    pix = doc[page_index].get_pixmap(dpi=DPI, colorspace=fitz.csGRAY)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()


def ink(gray: np.ndarray, threshold: int) -> np.ndarray:
    return np.where(gray < threshold, 255, 0).astype(np.uint8)


def strip_long_lines(mask: np.ndarray, min_len: int = 120) -> np.ndarray:
    horizontal = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (min_len, 1)))
    vertical = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, min_len)))
    lines = cv2.dilate(cv2.bitwise_or(horizontal, vertical), np.ones((3, 3), np.uint8))
    return cv2.bitwise_and(mask, cv2.bitwise_not(lines))


def glyph_boxes(mask: np.ndarray, min_side: int = 18, max_side: int = 90) -> list[tuple[int, int, int, int]]:
    joined = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    count, _labels, stats, _ = cv2.connectedComponentsWithStats(joined, 8)
    boxes = []
    for i in range(1, count):
        x, y, w, h, area = stats[i]
        if area < 40:
            continue
        if max(w, h) < min_side or max(w, h) > max_side or min(w, h) < 3:
            continue
        boxes.append((int(x), int(y), int(w), int(h)))
    return boxes


def _group(boxes, horizontal: bool):
    """Chain glyphs sharing a text line: overlap across the line, small gap along it."""
    key = (lambda b: b[0]) if horizontal else (lambda b: b[1])
    remaining = sorted(boxes, key=key)
    groups = []
    used = [False] * len(remaining)
    for i, seed in enumerate(remaining):
        if used[i]:
            continue
        used[i] = True
        members = [seed]
        cur = seed
        for j in range(i + 1, len(remaining)):
            if used[j]:
                continue
            cand = remaining[j]
            if horizontal:
                size = max(cur[3], cand[3])
                overlap = min(cur[1] + cur[3], cand[1] + cand[3]) - max(cur[1], cand[1])
                gap = cand[0] - (cur[0] + cur[2])
                if overlap >= 0.55 * min(cur[3], cand[3]) and -2 <= gap <= 0.7 * size and abs(cur[3] - cand[3]) <= 0.45 * size:
                    members.append(cand); used[j] = True; cur = cand
                elif gap > 0.7 * size:
                    pass
            else:
                size = max(cur[2], cand[2])
                overlap = min(cur[0] + cur[2], cand[0] + cand[2]) - max(cur[0], cand[0])
                gap = cand[1] - (cur[1] + cur[3])
                if overlap >= 0.55 * min(cur[2], cand[2]) and -2 <= gap <= 0.7 * size and abs(cur[2] - cand[2]) <= 0.45 * size:
                    members.append(cand); used[j] = True; cur = cand
        if len(members) >= 2:
            x0 = min(b[0] for b in members); y0 = min(b[1] for b in members)
            x1 = max(b[0] + b[2] for b in members); y1 = max(b[1] + b[3] for b in members)
            groups.append(((x0, y0, x1, y1), len(members)))
    return groups


def propose(gray: np.ndarray, threshold: int = 235):
    mask = strip_long_lines(ink(gray, threshold))
    boxes = glyph_boxes(mask)
    return {
        "h": _group(boxes, horizontal=True),
        "v": _group(boxes, horizontal=False),
        "glyphs": boxes,
    }
