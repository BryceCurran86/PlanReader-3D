"""Read-only: p11 -> p7 registration from NON-GRID W4 wall evidence only (typed KIND_GRID separators excluded by the producer's own
typed negative evidence), so the periodic tile-grid alias hypotheses cannot contribute support.

Evidence per page = source primitives of W4 candidates that are NOT `grid_fully_opposed` (faces.json, production producers unchanged).
Score(T) = min(H_support, V_support) of split-invariant collinear interval overlap (coordinate tolerance 0.06 pt).
"""
import bisect
import collections
import json
import math
import random
import sys

sys.modules["rapidocr"] = None
sys.modules["onnxruntime"] = None
sys.path.insert(0, "C:/claude-work/ft3-p11-p7")
import fitz  # noqa: E402

from pb_vector_geometry_v130 import extract_native_page  # noqa: E402

D = "C:/claude-work/audit-out/ft3/"
PDF = "C:/claude-work/ft3-p11-p7/documents/sources/Arch_Combined_Maryborough_Service_Station.pdf"
doc = fitz.open(PDF)
faces = json.load(open(D + "faces.json"))
S = {s["tag"]: s for s in faces["scopes"]}
COORD_TOL, AXIS = 0.06, 0.02
WINDOW = tuple(float(v) for v in sys.argv[1:4]) if len(sys.argv) >= 4 else None


def native(n):
    return {s["id"]: s for s in extract_native_page(doc[n - 1])["segments"]}


NS = {7: native(7), 11: native(11)}


def merge(ivs):
    out = []
    for lo, hi in sorted(ivs):
        if out and lo <= out[-1][1] + 1e-6:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return [(a, b) for a, b in out]


def lines_from(page, scope, include_grid, window=None):
    ids = set()
    ng = g = 0
    for rec in scope["w4_records"]:
        if rec["grid_fully_opposed"] and not include_grid:
            g += 1
            continue
        ng += 0 if rec["grid_fully_opposed"] else 1
        ids.update(rec["source_primitive_ids"])
    raw = {"H": collections.defaultdict(list), "V": collections.defaultdict(list)}
    for pid in ids:
        s = NS[page].get(pid)
        if s is None:
            continue
        a, b, c, d = s["x1"], s["y1"], s["x2"], s["y2"]
        if math.hypot(c - a, d - b) < 3.0:
            continue
        if abs(d - b) < AXIS:
            mid = ((a + c) / 2, b)
            ok = True if window is None else (abs(mid[0] - window[0]) <= window[2] and abs(mid[1] - window[1]) <= window[2])
            if ok:
                raw["H"][round(b, 2)].append((min(a, c), max(a, c)))
        elif abs(c - a) < AXIS:
            mid = (a, (b + d) / 2)
            ok = True if window is None else (abs(mid[0] - window[0]) <= window[2] and abs(mid[1] - window[1]) <= window[2])
            if ok:
                raw["V"][round(a, 2)].append((min(b, d), max(b, d)))
    return {o: {k: merge(v) for k, v in raw[o].items()} for o in "HV"}, g, ng


W7, g7, n7 = lines_from(7, S["p7_viewport"], include_grid=False)
W11, g11, n11 = lines_from(11, S["p11_page"], include_grid=False, window=WINDOW)
W7all, _, _ = lines_from(7, S["p7_viewport"], include_grid=True)
W11all, _, _ = lines_from(11, S["p11_page"], include_grid=True)
K7 = {o: sorted(W7[o]) for o in "HV"}
tot = lambda L: sum(h - l for o in "HV" for ivs in L[o].values() for l, h in ivs)
print("W4 records p7 viewport: %d grid-opposed excluded, %d kept | p11 page: %d excluded, %d kept" % (g7, n7, g11, n11))
print("non-grid wall line-work: p7 %.0f pt (all W4: %.0f) | p11 %.0f pt (all W4: %.0f)" % (tot(W7), tot(W7all), tot(W11), tot(W11all)))


def overlap(a, b):
    i = j = 0
    t = 0.0
    while i < len(a) and j < len(b):
        lo, hi = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if hi > lo:
            t += hi - lo
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return t


def transform(L, mat):
    a, b, c, d = mat
    out = {"H": collections.defaultdict(list), "V": collections.defaultdict(list)}
    for o in "HV":
        for k, ivs in L[o].items():
            for lo, hi in ivs:
                p = [(lo, k), (hi, k)] if o == "H" else [(k, lo), (k, hi)]
                q = [(a * x + b * y, c * x + d * y) for x, y in p]
                (x1, y1), (x2, y2) = q
                if abs(y2 - y1) < 1e-6:
                    out["H"][round(y1, 3)].append((min(x1, x2), max(x1, x2)))
                else:
                    out["V"][round(x1, 3)].append((min(y1, y2), max(y1, y2)))
    return {o: {k: merge(v) for k, v in out[o].items()} for o in "HV"}


def axis_support(T11, o, dx, dy):
    sc, sa = (dy, dx) if o == "H" else (dx, dy)
    s = 0.0
    for k, ivs in T11[o].items():
        c = k + sc
        sh = [(lo + sa, hi + sa) for lo, hi in ivs]
        j = bisect.bisect_left(K7[o], c - COORD_TOL)
        while j < len(K7[o]) and K7[o][j] <= c + COORD_TOL:
            s += overlap(sh, W7[o][K7[o][j]])
            j += 1
    return s


def score(T11, dx, dy):
    h, v = axis_support(T11, "H", dx, dy), axis_support(T11, "V", dx, dy)
    return min(h, v), h, v


D4 = {"identity": (1, 0, 0, 1), "rot90": (0, -1, 1, 0), "rot180": (-1, 0, 0, -1), "rot270": (0, 1, -1, 0),
      "mirror_x": (-1, 0, 0, 1), "mirror_y": (1, 0, 0, -1), "transpose": (0, 1, 1, 0), "anti_transpose": (0, -1, -1, 0)}


def candidate_shifts(T11, topn=30):
    wx, wy = collections.Counter(), collections.Counter()
    for o, votes in (("H", wy), ("V", wx)):
        for k, ivs in T11[o].items():
            t11 = sum(h - l for l, h in ivs)
            for k2 in K7[o]:
                d = k2 - k
                if abs(d) > 3000:
                    continue
                t7 = sum(h - l for l, h in W7[o][k2])
                votes[round(d / 0.04) * 0.04] += min(t11, t7)
    return [x for x, _ in wx.most_common(topn)], [y for y, _ in wy.most_common(topn)]


rows = []
for name, mat in D4.items():
    if WINDOW is not None and name != "identity":
        continue
    for s in ((1.0,) if (name != "identity" or WINDOW is not None) else (0.5, 0.75, 1.0, 1.25, 2.0)):
        T11 = transform(W11, tuple(s * v for v in mat))
        xs, ys = candidate_shifts(T11)
        pool = []
        for dx in xs:
            for dy in ys:
                sc, h, v = score(T11, dx, dy)
                pool.append((sc, dx, dy, h, v))
        pool.sort(reverse=True)
        refined = []
        for sc, dx, dy, h, v in pool[:3]:
            bb = (sc, dx, dy, h, v)
            for ddx in (-0.08, -0.04, 0.0, 0.04, 0.08):
                for ddy in (-0.08, -0.04, 0.0, 0.04, 0.08):
                    s2, h2, v2 = score(T11, dx + ddx, dy + ddy)
                    if s2 > bb[0]:
                        bb = (s2, dx + ddx, dy + ddy, h2, v2)
            refined.append(bb)
        refined.sort(reverse=True)
        top = refined[0]
        second = next((p for p in pool if abs(p[1] - top[1]) > 1.0 or abs(p[2] - top[2]) > 1.0), None)
        rows.append({"orientation": name, "scale": s, "dx": round(top[1], 2), "dy": round(top[2], 2), "min_support_pt": round(top[0], 1),
                     "h_pt": round(top[3], 1), "v_pt": round(top[4], 1),
                     "next_distinct_shift": None if second is None else [round(second[1], 2), round(second[2], 2)],
                     "next_distinct_min_support_pt": None if second is None else round(second[0], 1)})
rows.sort(key=lambda r: -r["min_support_pt"])
for r in rows:
    print(r)
T_id = transform(W11, D4["identity"])
print("frame (0,0) identity min/h/v:", [round(v, 1) for v in score(T_id, 0.0, 0.0)])
print("alias (-78,136.08) min/h/v:", [round(v, 1) for v in score(T_id, -78.0, 136.08)])
random.seed(20261014)
null = sorted(score(T_id, random.uniform(-1500, 1500), random.uniform(-2000, 2000))[0] for _ in range(300))
print("null max %.1f p99 %.1f median %.1f ; best/null_max = %.1f ; best/second-best-hypothesis = %.2f" % (
    null[-1], null[int(0.99 * 300)], null[150], rows[0]["min_support_pt"] / max(null[-1], 1e-9), rows[0]["min_support_pt"] / max(rows[1]["min_support_pt"], 1e-9)))
if WINDOW is None:
    json.dump({"rows": rows, "null_max": null[-1], "null_p99": null[int(0.99 * 300)],
               "p7_nongrid_pt": tot(W7), "p11_nongrid_pt": tot(W11)}, open(D + "wall_registration_nongrid.json", "w"), indent=1)
