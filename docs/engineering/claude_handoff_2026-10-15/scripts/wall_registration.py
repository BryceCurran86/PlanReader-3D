"""Read-only: registration p11 -> p7 derived ONLY from W4 wall-candidate source primitives of both pages.

Both pages' wall evidence comes from the same producer path (PhysicalWallCandidateProducer.resolve_scope; scopes_p7_p11.json).
Score(T) = min(H_support, V_support), where each support is the split-invariant collinear interval overlap of the transformed
p11 wall primitives with the p7 wall primitives. A translation that aligns only one axis (sliding along long lines, or aliasing
a periodic tile grid) therefore cannot win. D4 orientation families and a random-translation null are scored the same way.

Usage: wall_registration.py [window_cx window_cy window_r]   (window restricts p11 primitives by midpoint, native pts)
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

PDF = "C:/claude-work/ft3-p11-p7/documents/sources/Arch_Combined_Maryborough_Service_Station.pdf"
doc = fitz.open(PDF)
scopes = json.load(open("C:/claude-work/audit-out/ft3/scopes_p7_p11.json"))
COORD_TOL, AXIS = 0.06, 0.02
window = tuple(float(v) for v in sys.argv[1:4]) if len(sys.argv) >= 4 else None


def native(n):
    return {s["id"]: s for s in extract_native_page(doc[n - 1])["segments"]}


NS = {7: native(7), 11: native(11)}


def wall_lines(page, use_window=False):
    ids = set()
    for rec in scopes["pages"][str(page)]["records"]:
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
            o, k, lo, hi = "H", b, min(a, c), max(a, c)
            mid = ((lo + hi) / 2, k)
        elif abs(c - a) < AXIS:
            o, k, lo, hi = "V", a, min(b, d), max(b, d)
            mid = (k, (lo + hi) / 2)
        else:
            continue
        if use_window and window is not None:
            cx, cy, r = window
            if abs(mid[0] - cx) > r or abs(mid[1] - cy) > r:
                continue
        raw[o][round(k, 2)].append((lo, hi))
    out = {}
    for o in "HV":
        out[o] = {}
        for k, ivs in raw[o].items():
            ivs.sort()
            m = []
            for lo, hi in ivs:
                if m and lo <= m[-1][1] + 1e-6:
                    m[-1][1] = max(m[-1][1], hi)
                else:
                    m.append([lo, hi])
            out[o][k] = [(x, y) for x, y in m]
    return out


W7 = wall_lines(7)
W11 = wall_lines(11, use_window=True)
K7 = {o: sorted(W7[o]) for o in "HV"}
tot = lambda L: sum(h - l for o in "HV" for ivs in L[o].values() for l, h in ivs)
print("wall-primitive line-work (collinear union): p7 %.0f pt, p11%s %.0f pt" % (tot(W7), " (window)" if window else "", tot(W11)))


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
    for o in "HV":
        for k in list(out[o]):
            ivs = sorted(out[o][k])
            m = []
            for lo, hi in ivs:
                if m and lo <= m[-1][1] + 1e-6:
                    m[-1][1] = max(m[-1][1], hi)
                else:
                    m.append([lo, hi])
            out[o][k] = [(x, y) for x, y in m]
    return out


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
    T11 = transform(W11, mat)
    xs, ys = candidate_shifts(T11)
    best = None
    pool = []
    for dx in xs:
        for dy in ys:
            s, h, v = score(T11, dx, dy)
            pool.append((s, dx, dy, h, v))
    pool.sort(reverse=True)
    # refine top 3 by +-0.1 grid
    refined = []
    for s, dx, dy, h, v in pool[:3]:
        bb = (s, dx, dy, h, v)
        for ddx in (-0.08, -0.04, 0.0, 0.04, 0.08):
            for ddy in (-0.08, -0.04, 0.0, 0.04, 0.08):
                s2, h2, v2 = score(T11, dx + ddx, dy + ddy)
                if s2 > bb[0]:
                    bb = (s2, dx + ddx, dy + ddy, h2, v2)
        refined.append(bb)
    refined.sort(reverse=True)
    top = refined[0]
    second = next((p for p in pool if abs(p[1] - top[1]) > 1.0 or abs(p[2] - top[2]) > 1.0), None)
    rows.append({"orientation": name, "dx": round(top[1], 2), "dy": round(top[2], 2), "min_support_pt": round(top[0], 1),
                 "h_pt": round(top[3], 1), "v_pt": round(top[4], 1),
                 "next_distinct_min_support_pt": None if second is None else round(second[0], 1),
                 "next_distinct_shift": None if second is None else [round(second[1], 2), round(second[2], 2)]})
rows.sort(key=lambda r: -r["min_support_pt"])
for r in rows:
    print(r)

# frame-aligned alternative (0,0) identity, retained as a named competing hypothesis
T_id = transform(W11, D4["identity"])
fr = score(T_id, 0.0, 0.0)
print("frame (0,0) identity min/h/v:", [round(v, 1) for v in fr])

# null: random translations, identity orientation
random.seed(20261014)
null = []
for _ in range(300):
    null.append(score(T_id, random.uniform(-1500, 1500), random.uniform(-2000, 2000))[0])
null.sort()
best_pt = rows[0]["min_support_pt"]
print("null(300 random translations) max %.1f p99 %.1f median %.1f ; best/null_max = %.1f" % (null[-1], null[int(0.99 * 300)], null[150], best_pt / max(null[-1], 1e-9)))
json.dump({"window": window, "rows": rows, "frame00": fr, "null_max": null[-1], "null_p99": null[int(0.99 * 300)], "null_median": null[150],
           "p7_wall_linework_pt": tot(W7), "p11_wall_linework_pt": tot(W11)},
          open("C:/claude-work/audit-out/ft3/wall_registration%s.json" % ("_window" if window else ""), "w"), indent=1)
