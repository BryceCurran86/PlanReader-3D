"""Source-owned input path for the elevation vertical witness shadow (default off, authority-free).

The pure core (``pb_elevation_door_vertical_witness_shadow``) needs three kinds of facts about one elevation page:
dimension linework, drawn outlines and printed words. This adapter reads them ONLY from producer-owned authorities
and carries the observation ids that drew each fact, so a witness result names its receipts:

* segments: ``SourceVisibilityAuthority`` visible native observations for the exact revision and snapshot;
* outlines: ``SourceVisibilityProducer.native_paint_facts`` (authenticated paint provenance); the four edges of one
  filled path share a ``path_index``, so a filled rectangle is rebuilt from the edges that actually draw it;
* words: ``PdfTextIntegrityAuthority`` receipts (the same acceptance rule as the opening label authority).

It asserts no role: a rectangle is not called a door, a window or a frame here. It never publishes a host, kind,
frame, quantity or customer value, and nothing in production imports it. Pure functions at the bottom
(``extract_views``) take plain tuples so they can be tested without a PDF; line, rect and word tuples may carry
optional receipt ids as the last element.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional, Sequence

from pb_elevation_door_vertical_witness_shadow import (
    DatumLevel, ElevOutline, ElevationDatum, Scope, TEXT_CORROBORATED, TEXT_RAW_UNVERIFIED,
)
from pb_elevation_label_kind_proposal_shadow import (
    KindProposal, LabelBlock, NO_KIND_TOKEN, OutlineBox, StrokeSegment, label_kind, propose_kind_from_leader,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector

_NUMBER = re.compile(r"^\d{1,2},?\d{3}$|^\d{3}$")
TICK_TOL = 0.06
MIN_DIM_LEN_PT = 30.0
OUTLINE_W = (10.0, 160.0)
OUTLINE_H = (30.0, 90.0)
TOUCH_TOL = 0.06
AXIS_TOL = 0.05
THIN_FILL_PT = 0.3     # a fill thinner than a stroke is an edge line drawn as a fill, not a part of a leaf
OPAQUE = 0.99          # a leader must be opaque stroke ink
SAME_LINE_GAP = 1.5    # words closer than this many text heights on one line belong to one label
STACK_GAP = 0.6        # text lines closer than this many text heights, with overlapping extent, belong to one label


def _approved_raw_reasons() -> frozenset:
    from pb_pdf_text_integrity_authority import TEXT_CLIP_STATE_UNRESOLVED, TEXT_GLYPH_MAPPING_UNVERIFIED
    return frozenset({TEXT_GLYPH_MAPPING_UNVERIFIED, TEXT_CLIP_STATE_UNRESOLVED})


RAW_TEXT_APPROVED_REASONS = _approved_raw_reasons()


@dataclass(frozen=True)
class SourceOwnedPage:
    scope: Scope
    page_id: str
    lines: tuple[tuple, ...]        # (x0, y0, x1, y1, observation_id)
    rects: tuple[tuple, ...]        # (x0, y0, x1, y1, fill, (observation_id, ...))
    words: tuple[tuple, ...]        # (x0, y0, x1, y1, text, observation_id, trust)
    strokes: tuple[tuple, ...] = ()  # (x0, y0, x1, y1, observation_id): opaque stroke-only line segments (no fill)


# ---------------------------------------------------------------------------------------- reading

def is_stroke_ink(fact) -> bool:
    """A native line painted ONLY as an opaque stroke: no fill, so not an edge of a painted shape, and not translucent."""
    return bool(fact.fill is None and fact.kind == "line" and fact.stroke_color is not None
                and fact.stroke_opacity is not None and fact.stroke_opacity >= OPAQUE and len(fact.geometry) == 4)


def read_source_owned_page(source, *, revision_id: str, page_id: str) -> Optional[SourceOwnedPage]:
    """Authenticated page facts for one exact revision and snapshot, or ``None`` if the lineage is not intact."""
    published = source.published_snapshot_for_revision(revision_id)
    if published is None:
        return None
    scope = Scope(published.revision.document_id, published.revision.revision_id, published.revision.source_sha256,
                  published.snapshot.snapshot_id)
    visibility = source.authority()

    def selector(observation_id: str) -> ObservationSelector:
        return ObservationSelector(document_id=scope.document_id, revision_id=scope.revision_id,
                                   source_sha256=scope.source_sha256, snapshot_id=scope.snapshot_id,
                                   observation_id=observation_id)

    segment_ids = []
    lines = []
    for observation_id in sorted(visibility.visible_observation_ids_for_snapshot(scope.snapshot_id)):
        resolved = visibility.resolve_visible(selector(observation_id))
        observation = resolved.observation
        if (resolved.status is not EvidenceResolutionStatus.CORROBORATED or observation is None
                or str(observation.page_id) != str(page_id) or len(observation.geometry) != 4):
            continue
        g = tuple(float(v) for v in observation.geometry)
        segment_ids.append(observation_id)
        lines.append((*g, observation_id))
    rects = []
    strokes = []
    if segment_ids:
        facts = source.native_paint_facts(selector(segment_ids[0]), observation_ids=segment_ids)
        for fact in facts:
            if is_stroke_ink(fact):
                strokes.append((*(float(v) for v in fact.geometry), fact.observation_id))
        by_path: dict[int, list] = {}
        for fact in facts:
            if fact.fill is not None and fact.kind == "line":
                by_path.setdefault(fact.path_index, []).append(fact)
        for path_index in sorted(by_path):
            rects.extend(rectangle_components([
                (*(float(v) for v in f.geometry), tuple(round(c, 2) for c in f.fill), f.observation_id, int(f.item_index))
                for f in by_path[path_index]]))
    words = []
    integrity = source.text_integrity_authority()
    for observation_id in published.text_observation_ids:
        resolved = integrity.resolve_text(selector(observation_id))
        receipt = resolved.receipt
        if receipt is None or str(receipt.page_id) != str(page_id) or len(receipt.geometry) != 4:
            continue
        text, trust = None, None
        if resolved.status is EvidenceResolutionStatus.CORROBORATED and resolved.trusted_text:
            text, trust = str(resolved.trusted_text), TEXT_CORROBORATED
        else:
            # Raw fallback is DIAGNOSTIC provenance only and needs a NON-EMPTY approved reason set: an empty set is a
            # subset of every set, so a word with no stated reason must never pass this test.
            reasons = set(receipt.reason_codes or ())
            if (resolved.status is EvidenceResolutionStatus.ABSTAINED and not receipt.trusted
                    and reasons and reasons <= RAW_TEXT_APPROVED_REASONS
                    and str(receipt.raw_text or "").strip()):
                text, trust = str(receipt.raw_text).strip(), TEXT_RAW_UNVERIFIED
        if text is None:
            continue
        g = tuple(float(v) for v in receipt.geometry)
        words.append((*g, text, str(receipt.parent_observation_id or observation_id), trust))
    return SourceOwnedPage(scope, str(page_id), tuple(lines), tuple(rects), tuple(words), tuple(sorted(strokes)))


POINT_TOL = 0.01      # two edge ends are the same corner when they agree to this (pt)
SUB_FLOOR_PT = 0.5    # the producer drops native line edges shorter than this (pb_vector_geometry_v130), so a thinner strip loses its short sides


def _is_one_closed_strip(e0: dict, e1: dict, along: int) -> bool:
    """Do two lone parallel sides (same extent, less than the floor apart) come from ONE closed subpath whose short sides the producer dropped?

    Geometry alone cannot say: two independent open strokes of one fill and extent a hair apart look identical, yet an open two-point
    subpath fills nothing. The producer's own facts can: a closed strip is drawn side, short side, side, so its two long sides are
    items ``k`` and ``k + 2`` of one drawing (the dropped short side between them) and run in OPPOSITE directions. With equal extents
    opposite directions is the same fact as "the first's end meets the second's start across the gap". Sides with no item index,
    several indices, both directions, adjacent or distant items, or the same direction are NOT read as a strip."""
    if len(e0["items"]) != 1 or len(e1["items"]) != 1 or len(e0["dirs"]) != 1 or len(e1["dirs"]) != 1:
        return False
    i0, i1 = next(iter(e0["items"])), next(iter(e1["items"]))
    if i0 is None or i1 is None or abs(i0 - i1) != 2:
        return False
    (start0, _end0), (_start1, end1) = next(iter(e0["dirs"])), next(iter(e1["dirs"]))
    return start0[along] == end1[along]


def rectangle_components(edges: Sequence[tuple]) -> list[tuple]:
    """The closed axis-aligned rectangles actually drawn by the edges of ONE filled path.

    ``edges`` are ``(x0, y0, x1, y1, fill, observation_id)``. A path may hold several subpaths (a compound path), so edges are
    grouped by exact shared corners into connected components, and a component is a rectangle only when it is exactly the four
    sides of one box: one simple closed loop of axis-aligned edges (a side may be split into collinear pieces) with exactly four
    corners on two distinct x and two distinct y values, one fill. Disjoint components stay separate rectangles; any other cycle
    (an L-shaped or concave outline, a figure eight, rectangles touching at a corner) is NOT a rectangle and yields nothing. Each rectangle carries only the observation
    ids of its own four edges. Duplicate edges (a closing edge drawn twice) are one edge.

    One exception follows from the producer, not from geometry: it drops native line edges shorter than ``SUB_FLOOR_PT``, so a filled
    strip thinner than that arrives as its two long sides only. Exactly two lone parallel sides of one fill with the same extent and
    less than ``SUB_FLOOR_PT`` apart, that ``_is_one_closed_strip`` shows to be one closed subpath (optional 7th element of an edge:
    its item index in the drawing), are read as that strip (a rectangle carrying those two observation ids). Three or more such
    sides in one cluster are an ambiguous pairing and yield nothing; a lone side, sides of different extent or fill, sides with no
    item identity or from separate subpaths, and sides ``SUB_FLOOR_PT`` or more apart (whose short sides the producer would have
    kept) are not rectangles. Residual: a tiny (< ``SUB_FLOOR_PT``) segment that is not their connecting side, placed exactly
    between two sides that otherwise form a strip, cannot be told apart because the producer drops it.
    """
    def key(x, y):
        return (round(x / POINT_TOL), round(y / POINT_TOL))

    unique: dict[tuple, dict] = {}
    for edge in edges:
        x0, y0, x1, y1, fill, oid = edge[:6]
        item = edge[6] if len(edge) > 6 else None      # the edge's index within its drawing, when the caller knows it
        a, b = key(x0, y0), key(x1, y1)
        if a == b:
            continue                                   # a zero-length edge draws nothing
        entry = unique.setdefault((min(a, b), max(a, b)),
                                  {"geom": (x0, y0, x1, y1), "fills": set(), "ids": set(), "items": set(), "dirs": set()})
        entry["fills"].add(fill)
        entry["ids"].add(oid)
        entry["items"].add(item)
        entry["dirs"].add((a, b))                      # oriented as drawn: needed to tell a closed strip from two open strokes
    items = list(unique.items())
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owner: dict[tuple, int] = {}
    for i, ((a, b), _entry) in enumerate(items):
        for point in (a, b):
            if point in owner:
                parent[find(i)] = find(owner[point])
            else:
                owner[point] = i
    groups: dict[int, list] = {}
    for i, item in enumerate(items):
        groups.setdefault(find(i), []).append(item)
    rects = []
    lone_sides: dict[tuple, list] = {}                 # (horizontal, lo, hi) -> [(across, entry)] of single axis-aligned edges
    for group in groups.values():
        adjacency: dict[tuple, list] = {}
        axis_ok = True
        for (a, b), _entry in group:
            if a[0] != b[0] and a[1] != b[1]:
                axis_ok = False                        # a diagonal edge: not a rectangle
            adjacency.setdefault(a, []).append(b)
            adjacency.setdefault(b, []).append(a)
        if axis_ok and len(group) == 1:
            (a, b), entry = group[0]
            horizontal = a[1] == b[1]
            lo, hi = (a[0], b[0]) if horizontal else (a[1], b[1])          # (a, b) is already ordered: the key is (min, max)
            lone_sides.setdefault((horizontal, lo, hi), []).append((a[1] if horizontal else a[0], entry))
        if not axis_ok or any(len(n) != 2 for n in adjacency.values()):
            continue                                   # a diagonal edge, an open end or a junction: not one simple closed loop
        start = min(adjacency)
        cycle, previous, here = [start], None, start
        while True:
            nxt = [n for n in adjacency[here] if n != previous] or adjacency[here]
            step = nxt[0] if previous is not None or len(nxt) == 1 else min(nxt)
            if step == start:
                break
            cycle.append(step)
            previous, here = here, step
            if len(cycle) > len(group):
                break
        if len(cycle) != len(group):
            continue                                   # two loops or a figure eight
        def heading(p, q):
            return ((q[0] > p[0]) - (q[0] < p[0]), (q[1] > p[1]) - (q[1] < p[1]))
        corners = [cycle[i] for i in range(len(cycle))
                   if heading(cycle[i - 1], cycle[i]) != heading(cycle[i], cycle[(i + 1) % len(cycle)])]
        if len(corners) != 4 or len({c[0] for c in corners}) != 2 or len({c[1] for c in corners}) != 2:
            continue                                   # an L-shaped or other concave loop
        fills = {f for _pair, entry in group for f in entry["fills"]}
        if len(fills) != 1:
            continue
        gx = [v for _pair, entry in group for v in (entry["geom"][0], entry["geom"][2])]
        gy = [v for _pair, entry in group for v in (entry["geom"][1], entry["geom"][3])]
        rects.append((min(gx), min(gy), max(gx), max(gy), next(iter(fills)),
                      tuple(sorted({i for _pair, entry in group for i in entry["ids"]}))))
    # A filled strip thinner than the producer's edge floor arrives as its two long sides only (its short sides are dropped).
    # Two lone parallel sides of one fill with the SAME extent and less than that floor apart are that strip; a cluster of three or
    # more such sides is an ambiguous pairing and is never guessed, and a lone side is no rectangle.
    for (horizontal, _lo, _hi), members in lone_sides.items():
        members = sorted(members, key=lambda m: m[0])
        clusters: list[list] = [[members[0]]]
        for member in members[1:]:
            if (member[0] - clusters[-1][-1][0]) * POINT_TOL < SUB_FLOOR_PT:
                clusters[-1].append(member)
            else:
                clusters.append([member])
        for cluster in clusters:
            if len(cluster) != 2:
                continue
            (c0, e0), (c1, e1) = cluster
            fills = e0["fills"] | e1["fills"]
            if len(fills) != 1:
                continue
            if not _is_one_closed_strip(e0, e1, 0 if horizontal else 1):
                continue
            gx = [v for e in (e0, e1) for v in (e["geom"][0], e["geom"][2])]
            gy = [v for e in (e0, e1) for v in (e["geom"][1], e["geom"][3])]
            rects.append((min(gx), min(gy), max(gx), max(gy), next(iter(fills)),
                          tuple(sorted(e0["ids"] | e1["ids"]))))
    return sorted(rects)


def source_owned_views(page: SourceOwnedPage) -> list[dict]:
    return extract_views(page.lines, page.rects, page.words)


# ------------------------------------------------------------------------------- pure extraction

def _number(text: str) -> Optional[float]:
    t = str(text).strip()
    return float(t.replace(",", "")) if _NUMBER.match(t) else None


def _rid(item, index: int) -> tuple[str, ...]:
    value = item[index] if len(item) > index else ()
    return (value,) if isinstance(value, str) and value else tuple(value) if value else ()


def extract_views(lines: Sequence[tuple], rects: Sequence[tuple], words: Sequence[tuple]) -> list[dict]:
    """One view per figured datum chain (FFL shared by at least two figured vertical dimensions). Pure, deterministic.

    lines ``(x0, y0, x1, y1[, id])``; rects ``(x0, y0, x1, y1, fill[, ids])``; words ``(x0, y0, x1, y1, text[, id])``.
    """
    vertical: dict[tuple, set] = {}
    for a in lines:
        if abs(a[0] - a[2]) <= AXIS_TOL and abs(a[1] - a[3]) >= MIN_DIM_LEN_PT:
            vertical.setdefault((round(a[0], 2), round(min(a[1], a[3]), 2), round(max(a[1], a[3]), 2)), set()).update(_rid(a, 4))
    horizontal = [(round(a[1], 2), min(a[0], a[2]), max(a[0], a[2]), _rid(a, 4)) for a in lines
                  if abs(a[1] - a[3]) <= AXIS_TOL and abs(a[0] - a[2]) >= 6.0]

    def ticks(x, y):
        return [r for hy, xa, xb, r in horizontal if abs(hy - y) <= TICK_TOL and xa - 0.5 <= x <= xb + 0.5]

    dims = []
    for (x, ya, yb), v_ids in sorted(vertical.items()):
        top, bottom = ticks(x, ya), ticks(x, yb)
        if not top or not bottom:
            continue
        found = [(_number(w[4]), _rid(w, 5), (w[6] if len(w) > 6 else "")) for w in words
                 if (w[3] - w[1]) > 1.5 * (w[2] - w[0]) and _number(w[4]) is not None
                 and abs((w[0] + w[2]) / 2 - x) <= 12.0 and ya - 6.0 <= (w[1] + w[3]) / 2 <= yb + 6.0]
        if len(found) == 1:
            ids = set(v_ids) | {i for r in top for i in r} | {i for r in bottom for i in r} | set(found[0][1])
            bottom_ids = {i for r in bottom for i in r}
            dims.append((x, ya, yb, found[0][0], tuple(sorted(ids)), tuple(sorted(bottom_ids)), found[0][2]))
    by_bottom: dict[float, list] = {}
    for d in dims:
        by_bottom.setdefault(round(d[2], 1), []).append(d)
    filled = sorted({(round(r[0], 2), round(r[1], 2), round(r[2], 2), round(r[3], 2), tuple(round(v, 2) for v in r[4]),
                      _rid(r, 5)) for r in rects if r[4] is not None})
    views = []
    for _, chain in sorted(by_bottom.items()):
        if len(chain) < 2:
            continue
        ffl_y = sum(d[2] for d in chain) / len(chain)
        levels = tuple(DatumLevel(f"L{int(d[3])}", d[1], d[3], d[4], d[6]) for d in sorted(chain, key=lambda d: d[1]))
        ffl_receipts = tuple(sorted({i for d in chain for i in d[5]}))
        x_max = max(d[0] for d in chain)
        y_lo, y_hi = min(d[1] for d in chain) - 15.0, ffl_y + 12.0
        local = [r for r in filled if r[0] > x_max + 5.0 and r[1] >= y_lo and r[3] <= y_hi
                 and (r[2] - r[0]) <= OUTLINE_W[1] and (r[3] - r[1]) <= 100.0]
        solid = [r for r in local if min(r[2] - r[0], r[3] - r[1]) >= THIN_FILL_PT]
        groups = _touching_groups(solid) + [[r] for r in solid]
        outlines = {}
        for g in groups:
            x0, y0 = min(r[0] for r in g), min(r[1] for r in g)
            x1, y1 = max(r[2] for r in g), max(r[3] for r in g)
            if not (OUTLINE_W[0] <= x1 - x0 <= OUTLINE_W[1] and OUTLINE_H[0] <= y1 - y0 <= OUTLINE_H[1]):
                continue
            frame_base, frame_ids = None, ()
            enclosing = [r for r in local if r[0] <= x0 + 0.01 and r[2] >= x1 - 0.01 and r[3] >= y1 - 0.01
                         and (r[2] - r[0]) - (x1 - x0) <= 8.0 and (r[0], r[1], r[2], r[3]) != (x0, y0, x1, y1)]
            if enclosing:
                best = min(enclosing, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))
                frame_base, frame_ids = best[3], best[5]
            ids = tuple(sorted({i for r in g for i in r[5]} | set(frame_ids)))
            key = (round(x0, 2), round(x1, 2), round(y0, 2), round(y1, 2), frame_base)
            outlines[key] = tuple(sorted(set(outlines.get(key, ())) | set(ids)))
        ordered = sorted(outlines.items())
        views.append({
            "datum": ElevationDatum(ffl_y, levels, ffl_receipts),
            "outlines": tuple(ElevOutline(f"e{i}", k[0], k[1], k[2], k[3], k[4], None, ids) for i, (k, ids) in enumerate(ordered)),
            "chain_x": x_max,
        })
    return views


def _touching_groups(rects: Sequence[tuple]) -> list[list[tuple]]:
    """Connected groups of same-fill rects that touch or overlap (a leaf drawn in parts)."""
    remaining = list(rects)
    groups = []
    while remaining:
        seed = remaining.pop()
        group, frontier = [seed], [seed]
        while frontier:
            cur = frontier.pop()
            for other in list(remaining):
                if other[4] == cur[4] and not (
                    other[0] > cur[2] + TOUCH_TOL or other[2] < cur[0] - TOUCH_TOL
                    or other[1] > cur[3] + TOUCH_TOL or other[3] < cur[1] - TOUCH_TOL
                ):
                    remaining.remove(other)
                    group.append(other)
                    frontier.append(other)
        groups.append(group)
    return groups


# ------------------------------------------------------------------------------- label -> kind proposal

def label_blocks(words: Sequence[tuple]) -> list[LabelBlock]:
    """Printed labels that carry an explicit door or window token. Pure, deterministic, order-invariant.

    Words on one text line join when they are within ``SAME_LINE_GAP`` text heights; text lines join into one label when
    their extents overlap and they are within ``STACK_GAP`` text heights. Block trust is the worst of its words.
    """
    items = []
    for w in words:
        x0, y0, x1, y1 = (float(v) for v in w[:4])
        text = str(w[4]).strip()
        if not text or not all(v == v and abs(v) != float("inf") for v in (x0, y0, x1, y1)) or y1 <= y0 or x1 < x0:
            continue
        items.append({"b": (x0, y0, x1, y1), "t": text, "r": _rid(w, 5), "k": (w[6] if len(w) > 6 else "")})
    items.sort(key=lambda i: (i["b"], i["t"]))
    n = len(items)

    def height(i):
        return i["b"][3] - i["b"][1]

    def find(parent, i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    line_parent, block_parent = list(range(n)), list(range(n))

    def union(parent, a, b):
        ra, rb = find(parent, a), find(parent, b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    for a in range(n):
        for b in range(a + 1, n):
            ba, bb = items[a]["b"], items[b]["b"]
            h = max(height(items[a]), height(items[b]))
            cya, cyb = (ba[1] + ba[3]) / 2, (bb[1] + bb[3]) / 2
            gap_x = max(bb[0] - ba[2], ba[0] - bb[2])
            if abs(cya - cyb) <= 0.35 * h and gap_x <= SAME_LINE_GAP * h:
                union(line_parent, a, b)
                union(block_parent, a, b)
                continue
            gap_y = max(bb[1] - ba[3], ba[1] - bb[3])
            overlap_x = min(ba[2], bb[2]) - max(ba[0], bb[0])
            if -0.2 * h <= gap_y <= STACK_GAP * h and overlap_x > 0 and abs(cya - cyb) > 0.35 * h:
                union(block_parent, a, b)
    # lines may need joining through a stacked neighbour: reading order is by line cluster, then x
    blocks: dict[int, list[int]] = {}
    for i in range(n):
        blocks.setdefault(find(block_parent, i), []).append(i)
    out = []
    for members in blocks.values():
        lines: dict[int, list[int]] = {}
        for i in members:
            lines.setdefault(find(line_parent, i), []).append(i)
        ordered_lines = sorted(lines.values(), key=lambda ids: (sum((items[i]["b"][1] + items[i]["b"][3]) / 2 for i in ids) / len(ids)))
        text = " ".join(" ".join(items[i]["t"] for i in sorted(ids, key=lambda i: items[i]["b"][0])) for ids in ordered_lines)
        kind, problem = label_kind(text)
        if problem == NO_KIND_TOKEN:
            continue
        x0 = min(items[i]["b"][0] for i in members)
        y0 = min(items[i]["b"][1] for i in members)
        x1 = max(items[i]["b"][2] for i in members)
        y1 = max(items[i]["b"][3] for i in members)
        trusts = [items[i]["k"] for i in members]
        trust = TEXT_CORROBORATED if trusts and all(t == TEXT_CORROBORATED for t in trusts) else TEXT_RAW_UNVERIFIED
        receipts = tuple(sorted({r for i in members for r in items[i]["r"]}))
        out.append(LabelBlock(f"blk@{x0:.2f},{y0:.2f}", text, (x0, y0, x1, y1), receipts, trust))
    return sorted(out, key=lambda b: b.block_id)


def kind_proposal_for_outline(record_id: str, outline_id: str, outlines: Sequence[ElevOutline],
                              strokes: Sequence[tuple], words: Sequence[tuple]) -> KindProposal:
    """Propose the kind of the physical opening whose witnessed elevation outline is ``outline_id``.

    A proposal only (CANDIDATE, receipts, never an authority); the opening kind authority is untouched.
    """
    boxes = [OutlineBox(o.outline_id, o.x0, o.y_head, o.x1, o.y_base_leaf, tuple(o.receipt_ids)) for o in outlines]
    segs = [StrokeSegment(float(t[0]), float(t[1]), float(t[2]), float(t[3]), (t[4] if len(t) > 4 else "")) for t in strokes]
    return propose_kind_from_leader(record_id, outline_id, boxes, label_blocks(words), segs)


def label_text_trust(statuses: Sequence) -> str:
    """``corroborated`` only when there is at least one word and EVERY word is text-integrity CORROBORATED."""
    statuses = list(statuses)
    if not statuses:
        return ""
    return TEXT_CORROBORATED if all(s is EvidenceResolutionStatus.CORROBORATED for s in statuses) else TEXT_RAW_UNVERIFIED


def plan_label_width(source, composition, opening_identity_id: str):
    """``(width_mm, text_trust, receipt_ids)`` of one plan opening's single printed width, else ``(None, "", ())``.

    The width comes from the existing opening label authority; its own text acceptance may include a raw fallback, so
    the trust of EVERY word it used is re-checked here against the text-integrity authority. Two printed figures
    (a width and a height) are not a single width and are refused.
    """
    from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer

    trace = next((t for t in composition.opening_bindings if t.opening_identity_id == opening_identity_id), None)
    selector = composition.binding_selectors.get(opening_identity_id)
    if trace is None or selector is None:
        return None, "", ()
    obs = ObservationSelector(document_id=selector.document_id, revision_id=selector.revision_id,
                              source_sha256=selector.source_sha256, snapshot_id=selector.snapshot_id,
                              observation_id=trace.representative_observation_id)
    result = OpeningLabelDimensionProducer.from_source_visibility_producer(source).publish_scope(obs)
    evidence = getattr(result, "evidence", None)
    if (result.status is not EvidenceResolutionStatus.CORROBORATED or evidence is None
            or len(evidence.dimension_values_mm) != 1):
        return None, "", ()
    integrity = source.text_integrity_authority()
    statuses = [
        integrity.resolve_text(ObservationSelector(
            document_id=selector.document_id, revision_id=selector.revision_id, source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id, observation_id=oid)).status
        for oid in evidence.source_text_observation_ids
    ]
    receipts = tuple(sorted({*evidence.source_text_observation_ids, evidence.evidence_id}))
    return float(evidence.dimension_values_mm[0]), label_text_trust(statuses), receipts


__all__ = ["SourceOwnedPage", "extract_views", "label_text_trust", "plan_label_width", "read_source_owned_page",
           "source_owned_views"]
