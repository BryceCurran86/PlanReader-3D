from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

import fitz


def _point(value):
    try:
        return [round(float(value.x), 4), round(float(value.y), 4)]
    except Exception:
        try:
            return [round(float(value[0]), 4), round(float(value[1]), 4)]
        except Exception:
            return str(value)


def _item(item):
    if not item:
        return None
    kind = str(item[0])
    out = {"kind": kind}
    if kind == "l" and len(item) >= 3:
        out["p1"] = _point(item[1])
        out["p2"] = _point(item[2])
    elif kind == "re" and len(item) >= 2:
        rect = item[1]
        out["rect"] = [round(float(rect.x0),4),round(float(rect.y0),4),round(float(rect.x1),4),round(float(rect.y1),4)]
    elif kind == "qu" and len(item) >= 2:
        quad = item[1]
        out["quad"] = {
            "ul": _point(quad.ul), "ur": _point(quad.ur),
            "ll": _point(quad.ll), "lr": _point(quad.lr),
        }
    else:
        out["raw"] = str(item)[:500]
    return out


def page_stats(page, page_number: int):
    extended = page.get_drawings(extended=True) or []
    clips = []
    signatures = collections.Counter()
    for drawing in extended:
        if not isinstance(drawing, dict):
            continue
        dtype = str(drawing.get("type") or "")
        if not dtype.startswith("clip"):
            continue
        items = drawing.get("items") or []
        kinds = tuple(str(item[0]) for item in items if item)
        signatures[(dtype, int(drawing.get("level") or 0), kinds)] += 1
        if len(clips) < 30:
            sc = drawing.get("scissor")
            clips.append({
                "type": dtype,
                "level": int(drawing.get("level") or 0),
                "scissor": None if sc is None else [round(float(sc.x0),4),round(float(sc.y0),4),round(float(sc.x1),4),round(float(sc.y1),4)],
                "item_count": len(items),
                "items": [_item(item) for item in items[:12]],
            })
    return {
        "page_number": page_number,
        "extended_drawing_count": len(extended),
        "clip_count": sum(signatures.values()),
        "clip_signatures": [
            {"type": key[0], "level": key[1], "kinds": list(key[2]), "count": count}
            for key, count in signatures.most_common(50)
        ],
        "clip_samples": clips,
    }


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--pages", required=True)
    args=parser.parse_args()
    doc=fitz.open(str(args.pdf))
    try:
        pages=[int(v.strip()) for v in args.pages.split(",") if v.strip()]
        print(json.dumps({"pages":[page_stats(doc[p-1],p) for p in pages]},indent=2,sort_keys=True,default=str))
    finally:
        doc.close()
    return 0


if __name__=="__main__":
    raise SystemExit(main())
