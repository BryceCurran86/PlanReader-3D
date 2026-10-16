"""Read-only: LOCAL registration check around each FT3 plan mark (competing translations retained).

For a window (radius R native pts) around each mark on p11, score every candidate translation (dx, dy) by split-invariant
collinear overlap of p11 axis-parallel line-work inside the window with p7 line-work (full page, so no window-edge bias).
Candidates come from endpoint-pair votes inside the window (same idea as the global search, but local), refined +-0.1.
Reports the best, second-best distinct (> 1.0 pt away) and the ratio, plus the support at the global translation T0 = (-78, 0).
"""
import bisect
import collections
import json
import math
import sys

sys.modules["rapidocr"] = None
sys.modules["onnxruntime"] = None
sys.path.insert(0, "C:/claude-work/ft3-p11-p7")
import fitz  # noqa: E402

from pb_vector_geometry_v130 import extract_native_page  # noqa: E402

PDF = "C:/claude-work/ft3-p11-p7/documents/sources/Arch_Combined_Maryborough_Service_Station.pdf"
doc = fitz.open(PDF)
COORD_TOL, AXIS = 0.06, 0.02
R = float(sys.argv[1]) if len(sys.argv) > 1 else 250.0
MARKS = {"M1_office": (327.8, 1437.5), "M2_drystore": (324.4, 1022.3), "M3_washup": (316.3, 622.9),
         "M4_foodprep": (586.7, 642.8), "M5_foodservice": (737.0, 508.0)}


def lines(n, window=None):
    raw = {"H": collections.defaultdict(list), "V": collections.defaultdict(list)}
    for s in extract_native_page(doc[n - 1])["segments"]:
        a, b, c, d = s["x1"], s["y1"], s["x2"], s["y2"]
        if math.hypot(c - a, d - b) < 8.0:
            continue
        if abs(d - b) < AXIS:
            o, k, lo, hi = "H", b, min(a, c), max(a, c)
            mid = ((lo + hi) / 2, k)
        elif abs(c - a) < AXIS:
            o, k, lo, hi = "V", a, min(b, d), max(b, d)
            mid = (k, (lo + hi) / 2)
        else:
            continue
        if window is not None:
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
            out[o][k] = m
    return out


L7 = lines(7)
K7 = {o: sorted(L7[o]) for o in "HV"}


def overlap(a, b):
    i = j = 0
    tot = 0.0
    while i < len(a) and j < len(b):
        lo, hi = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if hi > lo:
            tot += hi - lo
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return tot


def support(L11w, dx, dy):
    tot = 0.0
    for o in "HV":
        sc, sa = (dy, dx) if o == "H" else (dx, dy)
        for k, ivs in L11w[o].items():
            c = k + sc
            sh = [(lo + sa, hi + sa) for lo, hi in ivs]
            j = bisect.bisect_left(K7[o], c - COORD_TOL)
            while j < len(K7[o]) and K7[o][j] <= c + COORD_TOL:
                tot += overlap(sh, L7[o][K7[o][j]])
                j += 1
    return tot


def candidates(L11w, window_pad=2500.0):
    """Endpoint-agnostic candidate translations: for each pair of (coordinate) in the same orientation, vote dx from interval
    starts (V/H interval lo values) and dy from line coordinates. Quantized votes, top few."""
    dxs = collections.Counter()
    dys = collections.Counter()
    # dy votes: H line coordinates 11 -> 7 ; dx votes: V line coordinates
    for o, votes in (("H", dys), ("V", dxs)):
        k7 = K7[o]
        for k, ivs in L11w[o].items():
            tot = sum(h - l for l, h in ivs)
            if tot < 20:
                continue
            for k2 in k7:
                d = k2 - k
                if abs(d) > window_pad:
                    continue
                votes[round(d / 0.04) * 0.04] += tot * 0.0 + 1
    return dxs, dys


def best_translations(L11w):
    """Peak-pick on (dx votes) x (dy votes) using total overlap support; limited to top-K of each axis by coordinate-vote counts
    refined by interval-length-weighted votes."""
    # length-weighted votes: weight = min(len11, len7 overlap potential) -> use len11 only (cheap); then verify by support().
    wx, wy = collections.Counter(), collections.Counter()
    for o, votes in (("H", wy), ("V", wx)):
        k7 = K7[o]
        for k, ivs in L11w[o].items():
            tot = sum(h - l for l, h in ivs)
            if tot < 20:
                continue
            for k2 in k7:
                d = k2 - k
                if abs(d) > 2500:
                    continue
                # weight by overlap potential of interval lengths on line k2 (cheap proxy: min(total11,total7))
                tot7 = sum(h - l for l, h in L7[o][k2])
                votes[round(d / 0.04) * 0.04] += min(tot, tot7)
    topx = [x for x, _ in wx.most_common(25)]
    topy = [y for y, _ in wy.most_common(25)]
    best = []
    for dx in topx:
        for dy in topy:
            s = support(L11w, dx, dy)
            best.append((s, dx, dy))
    best.sort(reverse=True)
    return best


results = {}
for name, (mx, my) in MARKS.items():
    L11w = lines(11, window=(mx, my, R))
    tot11 = sum(h - l for o in "HV" for ivs in L11w[o].values() for l, h in ivs)
    best = best_translations(L11w)
    s0 = support(L11w, -78.0, 0.0)
    top = best[0]
    # second distinct: > 1 pt from top in either axis
    second = next((b for b in best[1:] if abs(b[1] - top[1]) > 1.0 or abs(b[2] - top[2]) > 1.0), None)
    third_ratio = None
    results[name] = {
        "window_radius": R,
        "p11_linework_pt_in_window": round(tot11, 1),
        "support_at_global_T0_pt": round(s0, 1),
        "best_local": {"dx": round(top[1], 2), "dy": round(top[2], 2), "support_pt": round(top[0], 1)},
        "second_distinct": None if second is None else {"dx": round(second[1], 2), "dy": round(second[2], 2), "support_pt": round(second[0], 1)},
        "best_over_second": None if second is None or second[0] <= 0 else round(top[0] / second[0], 2),
        "share_of_window_at_T0": round(s0 / tot11, 4) if tot11 else None,
    }
    print(name, json.dumps(results[name]))
json.dump(results, open("C:/claude-work/audit-out/ft3/local_registration.json", "w"), indent=1)
