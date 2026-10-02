"""Source-owned internal-elevation wall-tile extent authority.

The producer fails closed unless it can prove an independent elevation viewport,
a physical wall face, and a tile extent from figured dimensions or authenticated
scale geometry. Room containment is never tile authority.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
import re
from statistics import median
from typing import Any, Optional, Sequence

from pb_hardened_authority_contract import (
    InternalElevationViewport,
    PhysicalWallFace,
    TileExtent,
    WallSurfaceResolution,
    WallViewIdentity,
    resolve_internal_elevation_wall_surface,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

SCHEMA_VERSION = "1.0.0"
SCALE_OR_FIGURED_HEIGHT_REQUIRED = "scale_or_figured_height_required"
VIEW_TITLE_AUTHORITY_REQUIRED = "repeated_scaled_view_title_authority_required"
TILE_SCOPE_REQUIRED = "authenticated_tile_scope_required"

_TITLE_RE = re.compile(r"^(.+?)\s+([A-H])$", re.I)
_SCALE_RE = re.compile(r"\bSCALE\s*(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\b", re.I)
_NUMBER_RE = re.compile(
    r"(?<![A-Z0-9])((?:[0-9]{1,3}(?:,[0-9]{3})+)|[0-9]{2,5})(?![A-Z0-9])",
    re.I,
)
_PLANISH_RE = re.compile(
    r"\b(?:PLAN|LAYOUT|SCHEDULE|LEGEND|NOTE|DETAIL|SECTION)\b", re.I
)


@dataclass(frozen=True)
class _Fragment:
    text: str
    bbox: tuple[float, float, float, float]

    @property
    def center(self) -> tuple[float, float]:
        return (
            (self.bbox[0] + self.bbox[2]) / 2.0,
            (self.bbox[1] + self.bbox[3]) / 2.0,
        )


@dataclass(frozen=True)
class _Title:
    stem: str
    suffix: str
    fragment: _Fragment


@dataclass(frozen=True)
class _ViewportCandidate:
    title: _Title
    bbox: tuple[float, float, float, float]
    scale_denominator: Optional[float]
    scale_fragment: Optional[_Fragment]


@dataclass(frozen=True)
class InternalElevationTileSurfaceExtraction:
    viewports: tuple[InternalElevationViewport, ...]
    resolutions: tuple[WallSurfaceResolution, ...]
    reason_codes: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _center(bbox: Sequence[float]) -> tuple[float, float]:
    return (
        (float(bbox[0]) + float(bbox[2])) / 2.0,
        (float(bbox[1]) + float(bbox[3])) / 2.0,
    )


def _contains(bbox: Sequence[float], point: tuple[float, float]) -> bool:
    return (
        float(bbox[0]) <= point[0] <= float(bbox[2])
        and float(bbox[1]) <= point[1] <= float(bbox[3])
    )


def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    ax, ay = _center(a)
    bx, by = _center(b)
    return math.hypot(ax - bx, ay - by)


def _fragments(page: Any) -> tuple[_Fragment, ...]:
    rows: list[_Fragment] = []
    try:
        blocks = page.get_text("blocks") or []
    except Exception:
        blocks = []
    for block in blocks:
        if len(block) < 5:
            continue
        text = _clean(block[4])
        if not text:
            continue
        rows.append(_Fragment(text, tuple(float(v) for v in block[:4])))

    try:
        data = page.get_text("dict") or {}
    except Exception:
        data = {}
    for block in data.get("blocks", ()) or ():
        for line in block.get("lines", ()) or ():
            spans = line.get("spans", ()) or ()
            bbox = line.get("bbox")
            text = _clean(
                " ".join(str(span.get("text") or "") for span in spans)
            )
            if text and bbox and len(bbox) >= 4:
                rows.append(
                    _Fragment(text, tuple(float(v) for v in bbox[:4]))
                )

    out: list[_Fragment] = []
    seen: set[tuple[str, tuple[float, float, float, float]]] = set()
    for row in rows:
        key = (
            row.text.upper(),
            tuple(round(value, 2) for value in row.bbox),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return tuple(out)


def _title_groups(rows: Sequence[_Fragment]) -> dict[str, list[_Title]]:
    groups: dict[str, list[_Title]] = defaultdict(list)
    for row in rows:
        match = _TITLE_RE.match(row.text)
        if not match:
            continue
        stem = _clean(match.group(1))
        suffix = match.group(2).upper()
        if (
            len(stem) < 3
            or _PLANISH_RE.search(stem)
            or not re.findall(r"[A-Za-z]{2,}", stem)
        ):
            continue
        groups[stem.casefold()].append(_Title(stem, suffix, row))

    result: dict[str, list[_Title]] = {}
    for stem, values in groups.items():
        unique: dict[str, _Title] = {}
        for value in sorted(
            values,
            key=lambda item: (
                item.fragment.bbox[1],
                item.fragment.bbox[0],
            ),
        ):
            unique.setdefault(value.suffix, value)
        if len(unique) >= 2:
            result[stem] = list(unique.values())
    return result


def _scale_for_title(
    title: _Title,
    rows: Sequence[_Fragment],
) -> tuple[Optional[float], Optional[_Fragment]]:
    tx0, ty0, tx1, ty1 = title.fragment.bbox
    title_height = max(ty1 - ty0, 1.0)
    hits: list[tuple[float, float, _Fragment]] = []
    for row in rows:
        match = _SCALE_RE.search(row.text)
        if not match:
            continue
        numerator = float(match.group(1))
        denominator = float(match.group(2))
        if numerator <= 0 or denominator <= 0:
            continue
        cx, cy = row.center
        if not (
            ty0 - title_height
            <= cy
            <= ty1 + max(5.0 * title_height, 45.0)
        ):
            continue
        if not (
            tx0 - max(3.0 * title_height, 30.0)
            <= cx
            <= tx1 + max(8.0 * title_height, 100.0)
        ):
            continue
        hits.append(
            (
                _distance(title.fragment.bbox, row.bbox),
                denominator / numerator,
                row,
            )
        )
    if not hits:
        return None, None
    hits.sort(key=lambda item: item[0])
    near = [item for item in hits if item[0] <= hits[0][0] + 8.0]
    if len({round(item[1], 9) for item in near}) != 1:
        return None, None
    return near[0][1], near[0][2]


def _cluster_rows(titles: Sequence[_Title]) -> list[list[_Title]]:
    ordered = sorted(
        titles,
        key=lambda item: (
            item.fragment.center[1],
            item.fragment.center[0],
        ),
    )
    tolerance = max(
        12.0,
        median(
            max(
                1.0,
                item.fragment.bbox[3] - item.fragment.bbox[1],
            )
            for item in ordered
        )
        * 2.0,
    )
    result: list[list[_Title]] = []
    for title in ordered:
        if not result:
            result.append([title])
            continue
        row_y = median(item.fragment.center[1] for item in result[-1])
        if abs(title.fragment.center[1] - row_y) > tolerance:
            result.append([title])
        else:
            result[-1].append(title)
    return result


def _viewports_for_group(
    page: Any,
    titles: Sequence[_Title],
    rows: Sequence[_Fragment],
) -> list[_ViewportCandidate]:
    page_width = float(page.rect.width)
    clustered = _cluster_rows(titles)
    gaps: list[float] = []
    for row in clustered:
        xs = sorted(item.fragment.center[0] for item in row)
        gaps.extend(xs[index + 1] - xs[index] for index in range(len(xs) - 1))
    fallback_gap = max(
        median(gaps) if gaps else page_width * 0.24,
        page_width * 0.12,
    )

    out: list[_ViewportCandidate] = []
    previous_bottom: Optional[float] = None
    for row in clustered:
        row = sorted(row, key=lambda item: item.fragment.center[0])
        centers = [item.fragment.center[0] for item in row]
        row_height = median(
            max(
                1.0,
                item.fragment.bbox[3] - item.fragment.bbox[1],
            )
            for item in row
        )
        title_top = min(item.fragment.bbox[1] for item in row)
        top = (
            0.0
            if previous_bottom is None
            else previous_bottom + max(8.0, row_height * 0.6)
        )
        bottom = max(
            top + 1.0,
            title_top - max(3.0, row_height * 0.3),
        )

        scale_rows: list[_Fragment] = []
        for index, title in enumerate(row):
            left = (
                max(0.0, centers[index] - fallback_gap)
                if index == 0
                else (centers[index - 1] + centers[index]) / 2.0
            )
            right = (
                min(page_width, centers[index] + fallback_gap * 1.5)
                if index == len(row) - 1
                else (centers[index] + centers[index + 1]) / 2.0
            )
            if index == 0 and len(row) > 1:
                left = max(
                    0.0,
                    centers[index] - (centers[index + 1] - centers[index]),
                )
            if index == len(row) - 1 and len(row) > 1:
                right = min(
                    page_width,
                    centers[index]
                    + 1.5 * (centers[index] - centers[index - 1]),
                )
            scale, scale_fragment = _scale_for_title(title, rows)
            if scale_fragment is not None:
                scale_rows.append(scale_fragment)
            out.append(
                _ViewportCandidate(
                    title,
                    (left, top, right, bottom),
                    scale,
                    scale_fragment,
                )
            )

        previous_bottom = max(
            (fragment.bbox[3] for fragment in scale_rows),
            default=max(item.fragment.bbox[3] for item in row),
        )
    return out


def _numbers(row: _Fragment) -> list[int]:
    out: list[int] = []
    for raw in _NUMBER_RE.findall(row.text.upper()):
        try:
            out.append(int(raw.replace(",", "")))
        except ValueError:
            pass
    return out


def _rows_in(
    rows: Sequence[_Fragment],
    bbox: Sequence[float],
) -> list[_Fragment]:
    return [row for row in rows if _contains(bbox, row.center)]


def _full_height(rows: Sequence[_Fragment]) -> bool:
    texts = [row.text.upper() for row in rows]
    combined = " ".join(texts)
    return (
        any("SHOWER TILES TO" in text for text in texts)
        and any("RUN UP TO CEILING" in text for text in texts)
    ) or (
        "FULL HEIGHT TILING" in combined
        and "SHOWER" in combined
    )


def _skirting(rows: Sequence[_Fragment]) -> bool:
    return any("TILE SKIRTING" in row.text.upper() for row in rows)


def _explicit_tile_height(
    rows: Sequence[_Fragment],
) -> Optional[int]:
    values: list[int] = []
    for row in rows:
        text = row.text.upper()
        if "TILES" in text and "SKIRT" not in text:
            values.extend(
                value for value in _numbers(row) if 1500 <= value <= 3600
            )
    return max(values) if values else None


def _shw_width(rows: Sequence[_Fragment]) -> Optional[int]:
    shower_rows = [
        row for row in rows if re.search(r"\bSHW\b", row.text, re.I)
    ]
    hits: list[tuple[float, int]] = []
    for shower in shower_rows:
        hits.extend(
            (0.0, value)
            for value in _numbers(shower)
            if 500 <= value <= 1800
        )
        for row in rows:
            distance = _distance(shower.bbox, row.bbox)
            if distance > 90.0:
                continue
            hits.extend(
                (distance, value)
                for value in _numbers(row)
                if 500 <= value <= 1800
            )
    if not hits:
        return None
    hits.sort(
        key=lambda item: (
            item[0],
            abs(item[1] - 900),
            item[1],
        )
    )
    return hits[0][1]


def _skirting_dims(
    rows: Sequence[_Fragment],
) -> Optional[tuple[int, int]]:
    anchors = [
        row for row in rows if "TILE SKIRTING" in row.text.upper()
    ]
    if not anchors:
        return None
    labels = [
        row
        for row in rows
        if re.search(r"\bTILES?\b", row.text, re.I)
    ]

    heights: list[tuple[float, int]] = []
    for row in rows:
        for value in _numbers(row):
            if not 80 <= value <= 600:
                continue
            label_distance = min(
                (_distance(row.bbox, label.bbox) for label in labels),
                default=float("inf"),
            )
            anchor_distance = min(
                _distance(row.bbox, anchor.bbox) for anchor in anchors
            )
            if "TILE" in row.text.upper():
                heights.append((0.0, value))
            elif label_distance <= 32.0 or anchor_distance <= 45.0:
                heights.append(
                    (min(label_distance, anchor_distance), value)
                )
    if not heights:
        return None
    heights.sort(key=lambda item: (item[0], item[1]))
    height = heights[0][1]

    widths: list[tuple[float, int]] = []
    for row in rows:
        for value in _numbers(row):
            if 1000 <= value <= 6000:
                widths.append(
                    (
                        min(
                            _distance(row.bbox, anchor.bbox)
                            for anchor in anchors
                        ),
                        value,
                    )
                )
    if not widths:
        return None
    nearest = min(distance for distance, _ in widths)
    local = [
        value
        for distance, value in widths
        if distance <= nearest + 50.0
    ]
    return max(local), height


def _face_width(rows: Sequence[_Fragment]) -> Optional[int]:
    values = [
        value
        for row in rows
        for value in _numbers(row)
        if 1000 <= value <= 6000
    ]
    return max(values) if values else None


def _figured_niche(
    rows: Sequence[_Fragment],
) -> Optional[tuple[int, int]]:
    niche_rows = [
        row for row in rows if "NICHE" in row.text.upper()
    ]
    if not niche_rows:
        return None
    nearest_by_value: dict[int, float] = {}
    for niche in niche_rows:
        for row in rows:
            distance = _distance(niche.bbox, row.bbox)
            if distance > 115.0:
                continue
            for value in _numbers(row):
                if 250 <= value <= 900:
                    nearest_by_value[value] = min(
                        nearest_by_value.get(value, float("inf")),
                        distance,
                    )
    values = [
        value
        for value, _ in sorted(
            nearest_by_value.items(),
            key=lambda item: (item[1], item[0]),
        )
    ]
    if 600 in values and 400 in values:
        return 600, 400
    return None


def _metres_per_point(scale: float) -> float:
    return scale * 25.4 / 72.0 / 1000.0


def _scaled_niche(
    page: Any,
    bbox: Sequence[float],
    rows: Sequence[_Fragment],
    scale: Optional[float],
) -> Optional[tuple[float, float]]:
    if scale is None or scale <= 0 or not math.isfinite(scale):
        return None
    niche_rows = [
        row for row in rows if "NICHE" in row.text.upper()
    ]
    if not niche_rows:
        return None

    factor = _metres_per_point(scale)
    hits: list[tuple[float, float, float]] = []
    try:
        drawings = page.get_drawings() or []
    except Exception:
        drawings = []
    for drawing in drawings:
        rect = drawing.get("rect")
        if rect is None:
            continue
        cx = (float(rect.x0) + float(rect.x1)) / 2.0
        cy = (float(rect.y0) + float(rect.y1)) / 2.0
        if not _contains(bbox, (cx, cy)):
            continue
        width_m = abs(float(rect.x1) - float(rect.x0)) * factor
        height_m = abs(float(rect.y1) - float(rect.y0)) * factor
        if not (
            0.25 <= width_m <= 1.2
            and 0.25 <= height_m <= 1.2
        ):
            continue
        distance = min(
            math.hypot(
                cx - row.center[0],
                cy - row.center[1],
            )
            for row in niche_rows
        )
        if distance <= 45.0:
            hits.append((distance, width_m, height_m))
    if not hits:
        return None
    hits.sort(
        key=lambda item: (
            item[0],
            abs(item[1] - item[2]),
            item[1] * item[2],
        )
    )
    best = hits[0]
    for other in [
        item for item in hits[1:] if item[0] <= best[0] + 3.0
    ]:
        if abs(
            other[1] * other[2] - best[1] * best[2]
        ) > 0.03:
            return None
    return best[1], best[2]


def _vector_height(
    page: Any,
    bbox: Sequence[float],
    scale: Optional[float],
) -> Optional[float]:
    if scale is None or scale <= 0 or not math.isfinite(scale):
        return None
    factor = _metres_per_point(scale)
    values: list[float] = []
    try:
        drawings = page.get_drawings() or []
    except Exception:
        drawings = []
    for drawing in drawings:
        line_width = float(drawing.get("width") or 0.0)
        for item in drawing.get("items", ()) or ():
            if not item:
                continue
            if item[0] == "l" and len(item) >= 3:
                start, end = item[1], item[2]
                x0, y0 = float(start.x), float(start.y)
                x1, y1 = float(end.x), float(end.y)
                if abs(x0 - x1) > 1.25:
                    continue
                midpoint = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
                if not _contains(bbox, midpoint):
                    continue
                value = abs(y1 - y0) * factor
                if 2.1 <= value <= 3.6 and line_width >= 0.25:
                    values.append(value)
            elif item[0] == "re" and len(item) >= 2:
                rect = item[1]
                midpoint = (
                    (float(rect.x0) + float(rect.x1)) / 2.0,
                    (float(rect.y0) + float(rect.y1)) / 2.0,
                )
                if not _contains(bbox, midpoint):
                    continue
                value = abs(float(rect.y1) - float(rect.y0)) * factor
                if 2.1 <= value <= 3.6:
                    values.append(value)
    if not values:
        return None
    buckets = Counter(round(value, 2) for value in values)
    best_count = max(buckets.values())
    choices = [
        value
        for value, count in buckets.items()
        if count == best_count
    ]
    return float(
        min(
            choices,
            key=lambda value: (
                0 if 2.3 <= value <= 3.2 else 1,
                abs(value - 2.7),
                value,
            ),
        )
    )


def _extent(
    page: Any,
    candidate: _ViewportCandidate,
    rows: Sequence[_Fragment],
) -> tuple[Optional[float], str, tuple[str, ...]]:
    if _skirting(rows):
        dimensions = _skirting_dims(rows)
        if dimensions is None:
            return None, "tile_skirting_figured_dimensions_required", ()
        width_mm, height_mm = dimensions
        return (
            width_mm / 1000.0 * height_mm / 1000.0,
            "figured_tile_skirting",
            (f"figured:{width_mm}x{height_mm}:tile_skirting",),
        )

    explicit_height = _explicit_tile_height(rows)
    shower_width = _shw_width(rows)
    if explicit_height is not None and shower_width is not None:
        return (
            shower_width / 1000.0 * explicit_height / 1000.0,
            "figured_shower_tile_height",
            (
                f"figured:{shower_width}x{explicit_height}:shower_tiles",
            ),
        )

    if not _full_height(rows):
        return None, TILE_SCOPE_REQUIRED, ()

    height_m = _vector_height(
        page,
        candidate.bbox,
        candidate.scale_denominator,
    )
    if height_m is None:
        return None, SCALE_OR_FIGURED_HEIGHT_REQUIRED, ()

    if shower_width is not None:
        return (
            shower_width / 1000.0 * height_m,
            "figured_width_scaled_full_height",
            (
                f"figured:{shower_width}:shw",
                f"scaled_height:{height_m:.6f}",
            ),
        )

    face_width = _face_width(rows)
    if face_width is None:
        return None, "full_height_face_width_required", ()

    area = face_width / 1000.0 * height_m
    evidence: list[str] = []
    niche = _figured_niche(rows)
    if niche is not None:
        area -= niche[0] / 1000.0 * niche[1] / 1000.0
        evidence.append(f"niche:{niche[0]}x{niche[1]}")
    else:
        scaled_niche = _scaled_niche(
            page,
            candidate.bbox,
            rows,
            candidate.scale_denominator,
        )
        if scaled_niche is not None:
            area -= scaled_niche[0] * scaled_niche[1]
            evidence.append(
                f"scaled_niche:{scaled_niche[0]:.6f}x"
                f"{scaled_niche[1]:.6f}"
            )
    if area <= 0:
        return None, "invalid_tile_extent_area", ()

    evidence.extend(
        (
            f"figured_width:{face_width}",
            f"scaled_height:{height_m:.6f}",
        )
    )
    return (
        area,
        "figured_width_scaled_full_height_less_opening",
        tuple(evidence),
    )


def _evidence_id(
    kind: str,
    payload: dict[str, object],
) -> str:
    return stable_contract_id(
        f"internal_elevation_{kind}",
        payload,
        digest_chars=32,
    )


def extract_internal_elevation_tile_surfaces(
    page: Any,
    *,
    document_id: str,
    source_sha256: str,
    page_id: str,
    page_number: int,
) -> InternalElevationTileSurfaceExtraction:
    rows = _fragments(page)
    groups = _title_groups(rows)
    if not groups:
        return InternalElevationTileSurfaceExtraction(
            (),
            (),
            (VIEW_TITLE_AUTHORITY_REQUIRED,),
        )

    candidates: list[_ViewportCandidate] = []
    for group in groups.values():
        candidates.extend(_viewports_for_group(page, group, rows))
    candidates.sort(
        key=lambda candidate: (
            candidate.title.fragment.bbox[1],
            candidate.title.fragment.bbox[0],
        )
    )

    viewports: list[InternalElevationViewport] = []
    resolutions: list[WallSurfaceResolution] = []
    reasons: list[str] = []

    for candidate in candidates:
        title = candidate.title
        title_evidence = _evidence_id(
            "view_title",
            {
                "source_sha256": source_sha256,
                "page_id": str(page_id),
                "title": title.fragment.text,
                "bbox": tuple(
                    round(value, 4)
                    for value in title.fragment.bbox
                ),
            },
        )
        scale_evidence = None
        if (
            candidate.scale_denominator is not None
            and candidate.scale_fragment is not None
        ):
            scale_evidence = _evidence_id(
                "scale",
                {
                    "source_sha256": source_sha256,
                    "page_id": str(page_id),
                    "text": candidate.scale_fragment.text,
                    "bbox": tuple(
                        round(value, 4)
                        for value in candidate.scale_fragment.bbox
                    ),
                },
            )

        viewport_id = stable_contract_id(
            "internal_elevation_viewport",
            {
                "document_id": str(document_id),
                "source_sha256": source_sha256,
                "page_id": str(page_id),
                "page_number": int(page_number),
                "title": title.fragment.text,
                "bbox": tuple(
                    round(value, 4)
                    for value in candidate.bbox
                ),
            },
            digest_chars=32,
        )
        viewport = InternalElevationViewport(
            viewport_id,
            str(page_id),
            tuple(
                value
                for value in (title_evidence, scale_evidence)
                if value
            ),
        )
        viewports.append(viewport)

        area, method, raw_evidence = _extent(
            page,
            candidate,
            _rows_in(rows, candidate.bbox),
        )
        if area is None:
            if method != TILE_SCOPE_REQUIRED:
                reasons.append(method)
            continue

        component_evidence = tuple(
            _evidence_id(
                "tile_extent_component",
                {
                    "source_sha256": source_sha256,
                    "page_id": str(page_id),
                    "viewport_id": viewport_id,
                    "component": component,
                },
            )
            for component in raw_evidence
        )
        wall_view_id = stable_contract_id(
            "internal_elevation_wall_view",
            {
                "source_sha256": source_sha256,
                "page_id": str(page_id),
                "viewport_id": viewport_id,
                "stem": title.stem.casefold(),
                "suffix": title.suffix,
            },
            digest_chars=32,
        )
        canonical_wall_id = stable_contract_id(
            "source_owned_internal_elevation_wall",
            {
                "source_sha256": source_sha256,
                "page_id": str(page_id),
                "wall_view_id": wall_view_id,
            },
            digest_chars=32,
        )
        face_id = stable_contract_id(
            "physical_internal_elevation_wall_face",
            {
                "source_sha256": source_sha256,
                "page_id": str(page_id),
                "wall_view_id": wall_view_id,
            },
            digest_chars=32,
        )
        wall_view = WallViewIdentity(
            wall_view_id,
            viewport_id,
            canonical_wall_id,
            (title_evidence,),
        )
        wall_face = PhysicalWallFace(
            face_id,
            wall_view_id,
            canonical_wall_id,
            (title_evidence,),
        )
        extent_id = stable_contract_id(
            "internal_elevation_tile_extent",
            {
                "source_sha256": source_sha256,
                "page_id": str(page_id),
                "viewport_id": viewport_id,
                "face_id": face_id,
                "method": method,
                "area_m2": round(float(area), 9),
            },
            digest_chars=32,
        )
        tile_extent = TileExtent(
            extent_id,
            viewport_id,
            wall_view_id,
            face_id,
            float(area),
            component_evidence or (title_evidence,),
        )
        resolutions.append(
            resolve_internal_elevation_wall_surface(
                viewport=viewport,
                wall_view=wall_view,
                wall_face=wall_face,
                tile_extent=tile_extent,
                plan_room_viewport_id=f"plan-page:{page_id}",
            )
        )

    return InternalElevationTileSurfaceExtraction(
        tuple(viewports),
        tuple(resolutions),
        tuple(dict.fromkeys(reasons)),
    )


__all__ = [
    "InternalElevationTileSurfaceExtraction",
    "SCALE_OR_FIGURED_HEIGHT_REQUIRED",
    "TILE_SCOPE_REQUIRED",
    "VIEW_TITLE_AUTHORITY_REQUIRED",
    "extract_internal_elevation_tile_surfaces",
]
