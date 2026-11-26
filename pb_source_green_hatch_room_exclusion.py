"""Source-native, project-neutral hatch-to-physical-room exclusion authority.

Green diagonal vector hatch is not a wall and does not create a floor polygon.
Only existing unique physical room faces on the *same original PDF* can own it.
The witness is audit evidence; ordinary finish quantities are quarantined
without changing any original room measurement or specialty schedule item.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
import hashlib
import math

import fitz

from pb_layered_wall_doorway_room_ring_shadow import _owner_excluded_green_ink
from pb_migration_contracts import QuantityEvidence, stable_contract_id


@dataclass(frozen=True)
class SourceGreenHatchRoomWitness:
    witness_id: str
    canonical_floor_id: str
    physical_floor_surface_id: str
    source_room_face_record_id: str
    source_sha256: str
    page_id: str
    native_path_ids: tuple[int, ...]
    status: str = "SOURCE_HATCH_EXCLUSION_CANDIDATE"
    commercial_quantity_allowed: bool = False


def _inside(x: float, y: float, points: Sequence[tuple[float, float]]) -> bool:
    inside = False
    for (x0, y0), (x1, y1) in zip(points, (*points[1:], points[0])):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def _source_polygon_is_simple(points: Sequence[tuple[float, float]]) -> bool:
    """A fabricated self-crossing or zero-area region cannot own an exclusion."""
    polygon = tuple(points[:-1] if len(points) > 3 and points[0] == points[-1]
                    else points)
    n = len(polygon)
    if n < 3 or len(set(polygon)) != n:
        return False
    twice_area = sum(
        polygon[i][0] * polygon[(i+1) % n][1]
        - polygon[(i+1) % n][0] * polygon[i][1]
        for i in range(n)
    )
    if abs(twice_area) < 1.e-6:
        return False
    def orient(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
    for i in range(n):
        a, b = polygon[i], polygon[(i+1) % n]
        for j in range(i+2, n):
            if i == 0 and j == n-1:
                continue
            c, d = polygon[j], polygon[(j+1) % n]
            if orient(a,b,c)*orient(a,b,d) < 0 and orient(c,d,a)*orient(c,d,b) < 0:
                return False
    return True


def _diagonals(page: fitz.Page) -> list[tuple[float, float, float, int, int]]:
    strokes = []
    for idx, row in enumerate(page.get_drawings()):
        # Only actual green LINE paint can author a crossed region.
        # Green fill with unrelated dark outlines is not hatch evidence.
        if not _owner_excluded_green_ink(row.get("color")):
            continue
        for item in row.get("items", ()):
            if len(item) < 3 or item[0] != "l":
                continue
            try:
                x0, y0 = float(item[1].x), float(item[1].y)
                x1, y1 = float(item[2].x), float(item[2].y)
            except (AttributeError, ValueError, TypeError):
                continue
            dx, dy = x1 - x0, y1 - y0
            if (not all(math.isfinite(v) for v in (x0, y0, x1, y1))
                    or abs(dx) < 2 or abs(dy) < 2
                    or not .45 <= abs(dy / dx) <= 2.2):
                continue
            strokes.append(((x0 + x1) / 2, (y0 + y1) / 2,
                            math.hypot(dx, dy), idx, 1 if dx * dy > 0 else -1))
    return sorted(strokes, key=lambda s: (s[0], s[3]))


from collections import OrderedDict
import threading

_GREEN_DIAGONALS_CACHE_MAX = 8
_GREEN_DIAGONALS_CACHE: "OrderedDict[tuple[str, int], tuple[tuple[float, float, float, int, int], ...]]" = OrderedDict()
_GREEN_DIAGONALS_CACHE_LOCK = threading.Lock()


def _diagonals_cached(
    source_sha256: str, page_index: int, page: fitz.Page
) -> tuple[tuple[float, float, float, int, int], ...]:
    """Return immutable green-ink diagonal hatch strokes with bounded SHA-256+page LRU reuse."""
    key = (source_sha256, int(page_index))
    with _GREEN_DIAGONALS_CACHE_LOCK:
        cached = _GREEN_DIAGONALS_CACHE.get(key)
        if cached is not None:
            _GREEN_DIAGONALS_CACHE.move_to_end(key)
            return cached
    strokes = tuple(_diagonals(page))
    with _GREEN_DIAGONALS_CACHE_LOCK:
        _GREEN_DIAGONALS_CACHE[key] = strokes
        _GREEN_DIAGONALS_CACHE.move_to_end(key)
        while len(_GREEN_DIAGONALS_CACHE) > _GREEN_DIAGONALS_CACHE_MAX:
            _GREEN_DIAGONALS_CACHE.popitem(last=False)
    return strokes


def collect_native_green_hatch_exclusions(
    source_pdf_bytes: bytes, canonical_floors: Sequence[object],
) -> tuple[SourceGreenHatchRoomWitness, ...]:
    """Match a broad native diagonal hatch against unique actual room polygons.

    A title block, green door stroke, site symbol, color name or nonphysical
    rectangle cannot create an exclusion. No drawing name, page, fixed room,
    source hash or benchmark value is used to decide hatch semantics.
    """
    if type(source_pdf_bytes) is not bytes or not source_pdf_bytes:
        raise ValueError("source_pdf_bytes_required")
    if not canonical_floors:
        return ()
    digest = hashlib.sha256(source_pdf_bytes).hexdigest()
    floor_counts = Counter(getattr(f, "canonical_floor_id", None) for f in canonical_floors)
    face_counts = Counter(getattr(f, "source_room_face_record_id", None) for f in canonical_floors)
    result = []
    with fitz.open(stream=source_pdf_bytes, filetype="pdf") as pdf:
        by_page = {}
        for floor in canonical_floors:
            page_id = getattr(floor, "page_id", None)
            polygon = getattr(floor, "polygon_pdf_pts", ())
            if (type(page_id) is not str or not page_id.isdigit()
                    or not 1 <= int(page_id) <= len(pdf)
                    or getattr(floor, "source_sha256", None) != digest
                    or getattr(floor, "geometry_complete", None) is not True
                    or getattr(floor, "physical_floor_surface_identity_resolved", None) is not True
                    or floor_counts[getattr(floor, "canonical_floor_id", None)] != 1
                    or face_counts[getattr(floor, "source_room_face_record_id", None)] != 1
                    or type(polygon) not in (tuple, list) or len(polygon) < 3):
                continue
            try:
                valid = all(
                    len(p) == 2 and all(type(v) in (int, float)
                                        and math.isfinite(v) for v in p)
                    for p in polygon
                )
            except (TypeError, ValueError):
                valid = False
            if valid and _source_polygon_is_simple(tuple(polygon)):
                by_page.setdefault(int(page_id) - 1, []).append(floor)
        for index, floors in by_page.items():
            strokes = _diagonals_cached(digest, index, pdf[index])
            xpos = [s[0] for s in strokes]
            for floor in floors:
                polygon = tuple(floor.polygon_pdf_pts)
                xs, ys = zip(*polygon)
                left, right = min(xs), max(xs)
                top, bottom = min(ys), max(ys)
                width, height = right - left, bottom - top
                if min(width, height) < 15:
                    continue
                min_length = max(4, .08 * min(width, height))
                local = [
                    row for row in strokes[
                        bisect_left(xpos, left):bisect_right(xpos, right)
                    ]
                    if (top <= row[1] <= bottom and row[2] >= min_length
                        and _inside(row[0], row[1], polygon))
                ]
                if not local:
                    continue
                dominant = Counter(s[4] for s in local).most_common(1)[0][0]
                parallel = [s for s in local if s[4] == dominant]
                ids = tuple(sorted({s[3] for s in parallel}))
                if (len(ids) < 5 or len(parallel) < 6
                        or len(parallel) < .7 * len(local)
                        or max(s[0] for s in parallel) - min(s[0] for s in parallel) < .25 * width
                        or max(s[1] for s in parallel) - min(s[1] for s in parallel) < .25 * height):
                    continue
                evidence_id = stable_contract_id("source_native_green_hatch", {
                    "source_sha256": digest, "page_id": floor.page_id,
                    "canonical_floor_id": floor.canonical_floor_id,
                    "source_room_face_record_id": floor.source_room_face_record_id,
                    "source_native_paths": ids,
                }, digest_chars=24)
                result.append(SourceGreenHatchRoomWitness(
                    witness_id=evidence_id,
                    canonical_floor_id=floor.canonical_floor_id,
                    physical_floor_surface_id=floor.physical_floor_surface_id,
                    source_room_face_record_id=floor.source_room_face_record_id,
                    source_sha256=digest, page_id=floor.page_id,
                    native_path_ids=ids,
                ))
    return tuple(sorted(result, key=lambda r: (r.page_id, r.canonical_floor_id)))


def quarantine_ordinary_hatched_floor_quantities(
    quantities: Sequence[QuantityEvidence],
    witnesses: Sequence[SourceGreenHatchRoomWitness],
) -> tuple[QuantityEvidence, ...]:
    """Source hatch vetoes ordinary FIRM floor finishes, never specialty claims.

    A separately proven specialty schedule keeps its independent authority.
    A mere epoxy-sounding room label is not a specialty-source permission.
    """
    by_owner = {}
    conflicts = set()
    for w in witnesses:
        if type(w) is not SourceGreenHatchRoomWitness:
            raise TypeError("untyped green hatch physical source witness")
        if w.canonical_floor_id in by_owner:
            conflicts.add(w.canonical_floor_id)
        by_owner[w.canonical_floor_id] = w
    output = []
    for quantity in quantities:
        if (type(quantity) is not QuantityEvidence
                or quantity.family != "floor_finish_area"
                or quantity.abstained or len(quantity.input_entity_ids) != 1):
            output.append(quantity)
            continue
        owner = quantity.input_entity_ids[0]
        w = by_owner.get(owner)
        if w is None or owner in conflicts:
            output.append(quantity)
            continue
        meta = quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
        if (meta.get("source_sha256") not in (None, w.source_sha256)
                or ("source_page_id" in meta and str(meta["source_page_id"]) != w.page_id)):
            output.append(quantity)
            continue
        output.append(replace(
            quantity, value=None, status="abstained", abstained=True,
            blocking_reasons=tuple(dict.fromkeys((
                *quantity.blocking_reasons,
                "source_green_hatched_physical_room_ordinary_finish_excluded",
            ))),
            evidence_ids=tuple(dict.fromkeys((*quantity.evidence_ids, w.witness_id))),
            metadata={**dict(meta), "inclusion_status": "EXCLUSION",
                      "commercial_projection_allowed": False,
                      "source_green_hatch_witness_id": w.witness_id},
        ))
    return tuple(output)


def quarantine_ordinary_hatched_ceiling_quantities(
    quantities: Sequence[QuantityEvidence],
    ceilings: Sequence[object],
    floors: Sequence[object],
    witnesses: Sequence[SourceGreenHatchRoomWitness],
) -> tuple[QuantityEvidence, ...]:
    """Exclude ordinary ceilings only through exact original physical room identity.

    The source-floor page and RCP page may differ. Same room label alone never
    grants ownership; original document/revision/SHA and canonical room bind.
    Independently source-authorized specialty ceilings remain separate.
    """
    floor_by_id = {getattr(f, "canonical_floor_id", None): f for f in floors}
    room_counts = Counter(getattr(f, "room_entity_id", None) for f in floors)
    ceiling_counts = Counter(getattr(c, "canonical_ceiling_id", None) for c in ceilings)
    ceilings_by_id = {getattr(c, "canonical_ceiling_id", None): c for c in ceilings}
    rooms = {}
    for witness in witnesses:
        if type(witness) is not SourceGreenHatchRoomWitness:
            raise TypeError("untyped_source_hatch_witness")
        floor = floor_by_id.get(witness.canonical_floor_id)
        if (floor is None
                or getattr(floor, "source_sha256", None) != witness.source_sha256
                or getattr(floor, "physical_floor_surface_id", None) != witness.physical_floor_surface_id
                or getattr(floor, "geometry_complete", None) is not True):
            continue
        room = getattr(floor, "room_entity_id", None)
        if type(room) is str and room and room_counts[room] == 1:
            rooms[room] = (floor, witness)
    output = []
    for q in quantities:
        if (type(q) is not QuantityEvidence or q.family != "ceiling_lining"
                or q.abstained or len(q.input_entity_ids) != 1):
            output.append(q)
            continue
        ceiling_id = q.input_entity_ids[0]
        ceiling = ceilings_by_id.get(ceiling_id)
        if ceiling is None or ceiling_counts[ceiling_id] != 1:
            output.append(q)
            continue
        match = rooms.get(getattr(ceiling, "room_entity_id", None))
        if match is None or getattr(ceiling, "geometry_complete", None) is not True:
            output.append(q)
            continue
        floor, witness = match
        if (ceiling.source_sha256 != witness.source_sha256
                or ceiling.document_id != floor.document_id
                or ceiling.revision_id != floor.revision_id):
            output.append(q)
            continue
        metadata = q.metadata if isinstance(q.metadata, Mapping) else {}
        if metadata.get("source_sha256") not in (None, witness.source_sha256):
            output.append(q)
            continue
        output.append(replace(
            q, value=None, status="abstained", abstained=True,
            blocking_reasons=tuple(dict.fromkeys((
                *q.blocking_reasons,
                "source_green_hatched_physical_room_ordinary_ceiling_excluded",
            ))),
            evidence_ids=tuple(dict.fromkeys((*q.evidence_ids, witness.witness_id))),
            metadata={**dict(metadata), "inclusion_status": "EXCLUSION",
                      "commercial_projection_allowed": False,
                      "source_green_hatch_witness_id": witness.witness_id},
        ))
    return tuple(output)
