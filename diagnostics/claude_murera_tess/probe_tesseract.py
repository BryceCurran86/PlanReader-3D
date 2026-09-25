"""Research probe: Tesseract numeric OCR of raster dimension text (diagnostic only).

Runs on a SHA-verified source PDF page. Regions come only from the generic
proposal in probe_regions.py; every variant's raw reading is recorded. Known
drawing values are used ONLY afterwards, to report recall for this research.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from itertools import product

import cv2
import numpy as np
import pytesseract

from probe_regions import ink, page_gray, propose

PDF = sys.argv[1]
PAGE_INDEX = int(sys.argv[2])
OUT = sys.argv[3]
PT_PER_PX = 72.0 / 300.0

THRESHOLDS = (None, 235, 245)
REPAIRS = ("none", "blur")
SCALES = (3,)
WHITELIST = "0123456789,."


def prepare(crop: np.ndarray, threshold, repair: str, scale: int) -> np.ndarray:
    img = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    if repair == "blur":
        img = cv2.GaussianBlur(img, (0, 0), 1.0 * scale)
    if threshold is not None:
        img = 255 - ink(img, threshold)
        if repair == "close":
            img = cv2.erode(img, np.ones((2 * scale, 2 * scale), np.uint8))
    elif repair == "close":
        img = cv2.erode(img, np.ones((scale, scale), np.uint8))
    return cv2.copyMakeBorder(img, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255)


def read(img: np.ndarray, psm: int) -> tuple[str, float]:
    data = pytesseract.image_to_data(
        img, config=f"--psm {psm} -c tessedit_char_whitelist={WHITELIST}",
        output_type=pytesseract.Output.DICT,
    )
    tokens = [(t.strip(), float(c)) for t, c in zip(data["text"], data["conf"]) if str(t).strip()]
    if not tokens:
        return "", -1.0
    return "".join(t for t, _ in tokens), round(sum(c for _, c in tokens) / len(tokens), 1)


def ocr_region(job):
    gray_crop, meta = job
    out = []
    rotations = [None] if meta["orient"] == "h" else [cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE]
    for rot in rotations:
        base = gray_crop if rot is None else cv2.rotate(gray_crop, rot)
        rname = "0" if rot is None else ("cw" if rot == cv2.ROTATE_90_CLOCKWISE else "ccw")
        for threshold, repair, scale in product(THRESHOLDS, REPAIRS, SCALES):
            text, conf = read(prepare(base, threshold, repair, scale), 7)
            out.append({**meta, "rot": rname, "T": threshold, "repair": repair, "scale": scale, "text": text, "conf": conf})
    return out


def main() -> None:
    t0 = time.time()
    gray = page_gray(PDF, PAGE_INDEX)
    jobs = []
    for proposal_threshold in (235, 245):
        regions = propose(gray, proposal_threshold)
        for orient in ("h", "v"):
            for (x0, y0, x1, y1), n in regions[orient]:
                pad = 8
                crop = gray[max(0, y0 - pad): y1 + pad, max(0, x0 - pad): x1 + pad]
                meta = {
                    "proposal_T": proposal_threshold, "orient": orient, "glyphs": n,
                    "bbox_pt": [round(v * PT_PER_PX, 1) for v in (x0, y0, x1, y1)],
                }
                jobs.append((crop, meta))
    print(f"[{time.time()-t0:.0f}s] regions: {len(jobs)}", flush=True)
    results = []
    with ProcessPoolExecutor(max_workers=os.cpu_count() or 2) as pool:
        for chunk in pool.map(ocr_region, jobs, chunksize=4):
            results.extend(chunk)
            texts = sorted({(r["rot"], r["text"]) for r in chunk if r["text"]})
            print("REGION", chunk[0]["orient"], chunk[0]["bbox_pt"], texts, flush=True)
    print(f"[{time.time()-t0:.0f}s] region readings: {len(results)}", flush=True)

    sparse = []
    for threshold, repair, rot in product((235,), ("none",), (None, cv2.ROTATE_90_CLOCKWISE)):
        base = gray if rot is None else cv2.rotate(gray, rot)
        img = prepare(base, threshold, repair, 1)
        data = pytesseract.image_to_data(
            img, config=f"--psm 11 -c tessedit_char_whitelist={WHITELIST}",
            output_type=pytesseract.Output.DICT,
        )
        words = [
            {"text": t.strip(), "conf": float(c), "box_px": [int(l), int(tp), int(w), int(h)]}
            for t, c, l, tp, w, h in zip(data["text"], data["conf"], data["left"], data["top"], data["width"], data["height"])
            if str(t).strip()
        ]
        sparse.append({"T": threshold, "repair": repair, "rot": "0" if rot is None else "cw", "words": words})
        print(f"[{time.time()-t0:.0f}s] sparse T={threshold} repair={repair} rot={rot}: {len(words)} words", flush=True)

    json.dump({"regions": results, "sparse": sparse}, open(OUT, "w", encoding="utf-8"))

    # Research recall summary against values printed on the drawing itself.
    probes = {"18400": "overall horizontal", "10500": "overall vertical"}
    for value, label in probes.items():
        hits = [r for r in results if re.sub(r"[,.]", "", r["text"]) == value]
        variants = sorted({(r["T"], r["repair"], r["scale"], r["rot"]) for r in hits}, key=str)
        boxes = sorted({tuple(r["bbox_pt"]) for r in hits})
        sp = [(s["T"], s["repair"], s["rot"]) for s in sparse for w in s["words"] if re.sub(r"[,.]", "", w["text"]) == value]
        print(f"RECALL {value} ({label}): region_hits={len(hits)} boxes={boxes[:4]} variants={variants[:12]} sparse={sp}", flush=True)
    print(f"[{time.time()-t0:.0f}s] done", flush=True)


if __name__ == "__main__":
    main()
