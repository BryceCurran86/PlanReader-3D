"""Benchmark-only, generic evidence extractor used to prepare V2 truth packages (no PlanReader code).
Usage: python extract_plan_evidence.py --maryborough PDF --q5446 PDF --out DIR
Verifies source SHA-256 first; reads text layer / vector arcs only."""
import argparse, collections, hashlib, json, math, re
from pathlib import Path
import fitz

SHA = {"maryborough": "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007",
       "q5446": "5f29aa0122d72e2cc8886b3f19239ff32865c8d705eee99f785c389ca27fb7f0"}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def maryborough_tags(pdf):
    d = fitz.open(pdf)
    tag = re.compile(r"^(D\d{2}|W\d{2})$")
    sheets = {7: "A110 floor plan", 12: "A200 elevations", 14: "building sections", 28: "A600 door schedule", 29: "A610 window elevations"}
    out = {}
    for pn, name in sheets.items():
        c = collections.Counter(w[4] for w in d[pn - 1].get_text("words") if tag.match(w[4]))
        out[f"p{pn} {name}"] = dict(sorted(c.items()))
    return out


def q5446_door_arcs(pdf, mm_per_pt=25.4 / 72 * 100):
    d = fitz.open(pdf)
    res = {}
    for pg, name in ((0, "ground floor (sheet 2.1)"), (1, "first floor (sheet 2.2)")):
        found = []
        for dr in d[pg].get_drawings():
            if dr["type"] != "s" or dr.get("color") != (0.0, 0.0, 0.0):
                continue
            its = [it for it in dr["items"] if it[0] == "l"]
            if len(its) < 8:
                continue
            pts = [its[0][1]] + [it[2] for it in its]
            xs, ys = [p.x for p in pts], [p.y for p in pts]
            w, h = max(xs) - min(xs), max(ys) - min(ys)
            if not (10 <= w <= 45 and 10 <= h <= 45 and abs(w - h) <= 4):
                continue
            r = max(w, h); chord = math.hypot(pts[0].x - pts[-1].x, pts[0].y - pts[-1].y)
            if not (0.855 * r * math.sqrt(2) <= chord <= 1.1 * r * math.sqrt(2)):
                continue
            if max(math.hypot(p.x - q.x, p.y - q.y) for p, q in zip(pts, pts[1:])) > 0.35 * r:
                continue
            found.append(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, r * mm_per_pt))
        found.sort(); ded = []
        for f in found:
            if ded and abs(f[0] - ded[-1][0]) < 1.5 and abs(f[1] - ded[-1][1]) < 1.5:
                continue
            ded.append(f)
        res[name] = [{"centre_pt": [round(a, 1), round(b, 1)], "radius_mm": round(r)} for a, b, r in ded]
    return res


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--maryborough"); ap.add_argument("--q5446"); ap.add_argument("--out", required=True)
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    if a.maryborough:
        assert sha256(a.maryborough) == SHA["maryborough"], "Maryborough source hash mismatch"
        (out / "maryborough_tag_census.json").write_text(json.dumps(maryborough_tags(a.maryborough), indent=1))
    if a.q5446:
        assert sha256(a.q5446) == SHA["q5446"], "Q5446 source hash mismatch"
        (out / "q5446_door_arc_census.json").write_text(json.dumps(q5446_door_arcs(a.q5446), indent=1))


if __name__ == "__main__":
    main()
