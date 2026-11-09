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
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector

_NUMBER = re.compile(r"^\d{1,2},?\d{3}$|^\d{3}$")
TICK_TOL = 0.06
MIN_DIM_LEN_PT = 30.0
OUTLINE_W = (10.0, 160.0)
OUTLINE_H = (30.0, 90.0)
TOUCH_TOL = 0.06
AXIS_TOL = 0.05


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


# ---------------------------------------------------------------------------------------- reading

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
    if segment_ids:
        facts = source.native_paint_facts(selector(segment_ids[0]), observation_ids=segment_ids)
        by_path: dict[int, list] = {}
        for fact in facts:
            if fact.fill is not None and fact.kind == "line":
                by_path.setdefault(fact.path_index, []).append(fact)
        for path_index in sorted(by_path):
            edges = by_path[path_index]
            if any(abs(f.geometry[0] - f.geometry[2]) > AXIS_TOL and abs(f.geometry[1] - f.geometry[3]) > AXIS_TOL
                   for f in edges):
                continue                       # not an axis-aligned rectangle path
            xs = [v for f in edges for v in (f.geometry[0], f.geometry[2])]
            ys = [v for f in edges for v in (f.geometry[1], f.geometry[3])]
            fills = {tuple(round(c, 2) for c in f.fill) for f in edges}
            if len(fills) != 1:
                continue
            rects.append((min(xs), min(ys), max(xs), max(ys), next(iter(fills)),
                          tuple(sorted({f.observation_id for f in edges}))))
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
    return SourceOwnedPage(scope, str(page_id), tuple(lines), tuple(rects), tuple(words))


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
        groups = _touching_groups(local) + [[r] for r in local]
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


__all__ = ["SourceOwnedPage", "extract_views", "read_source_owned_page", "source_owned_views"]
