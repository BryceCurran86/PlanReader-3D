"""Dimension-chain extraction (generic, benchmark-only): long thin dimension lines + the short strokes that cross them."""
MM = 25.4 / 72 * 100


def _items(page, region):
    for dr in page.get_drawings():
        if dr["type"] != "s" or dr.get("color") != (0.0, 0.0, 0.0):
            continue
        w = round(dr.get("width") or 0, 2)
        for it in dr["items"]:
            if it[0] != "l":
                continue
            a, b = it[1], it[2]
            if region[0] <= min(a.x, b.x) and max(a.x, b.x) <= region[2] and region[1] <= min(a.y, b.y) and max(a.y, b.y) <= region[3]:
                yield a.x, a.y, b.x, b.y, w


def extract_chains(page, region, min_len=40.0, tick_min=2.2, tick_max=13.0, max_w=0.5):
    H, V, TV, TH = [], [], [], []
    for x0, y0, x1, y1, w in _items(page, region):
        L = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        if abs(y0 - y1) < 0.12 and L >= min_len and w <= max_w:
            H.append((y0, min(x0, x1), max(x0, x1)))
        elif abs(x0 - x1) < 0.12 and L >= min_len and w <= max_w:
            V.append((x0, min(y0, y1), max(y0, y1)))
        if abs(x0 - x1) < 0.12 and tick_min <= abs(y0 - y1) <= tick_max:
            TV.append((x0, min(y0, y1), max(y0, y1)))
        if abs(y0 - y1) < 0.12 and tick_min <= abs(x0 - x1) <= tick_max:
            TH.append((y0, min(x0, x1), max(x0, x1)))
    chains = []
    for y, xa, xb in H:
        pos = sorted({round(x, 2) for x, ya, yb in TV if xa - 1.0 <= x <= xb + 1.0 and ya - 0.4 <= y <= yb + 0.4})
        chains.append(("H", y, xa, xb, _merge(pos)))
    for x, ya, yb in V:
        pos = sorted({round(y, 2) for y, xa2, xb2 in TH if ya - 1.0 <= y <= yb + 1.0 and xa2 - 0.4 <= x <= xb2 + 0.4})
        chains.append(("V", x, ya, yb, _merge(pos)))
    # merge chains lying on the same line
    out = {}
    for kind, c, a, b, pos in chains:
        if len(pos) < 2:
            continue
        key = (kind, round(c / 0.5))
        cur = out.get(key)
        if cur:
            cur[2] = min(cur[2], a); cur[3] = max(cur[3], b); cur[4] = _merge(sorted(cur[4] + pos))
        else:
            out[key] = [kind, c, a, b, pos]
    return sorted(out.values(), key=lambda t: (t[0], t[1]))


def _merge(pos, tol=0.6):
    m = []
    for x in pos:
        if m and x - m[-1][-1] < tol:
            m[-1].append(x)
        else:
            m.append([x])
    return [sum(g) / len(g) for g in m]
