"""v1.2.21 documented unit-area block matching.

Prevents a unit from inheriting the previous unit's m² when several unit records
are close together in extracted PDF text.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

import pb_auto_geometry_v1219 as auto
import pb_unit_floor_area_v1221 as unit


def extract_unit_area_candidates(text: Any) -> List[Dict[str, Any]]:
    lines = [re.sub(r"\s+", " ", line).strip() for line in str(text or "").splitlines() if line.strip()]
    labelled = [(idx, unit._match_unit_label(line, allow_short=True)) for idx, line in enumerate(lines)]
    labelled = [(idx, label) for idx, label in labelled if label]
    out: List[Dict[str, Any]] = []
    used: set[str] = set()

    for pos, (idx, label) in enumerate(labelled):
        previous_idx = labelled[pos - 1][0] if pos > 0 else -1
        next_idx = labelled[pos + 1][0] if pos + 1 < len(labelled) else len(lines)

        # Prefer the label line and the lines that belong to this unit until the
        # next unit starts. This is how most schedules/plan annotations read.
        forward_end = min(next_idx, idx + 4)
        # A neighbouring unit's area is outside this span. Look backward only
        # when this unit's own lines contain no area.
        backward_start = max(previous_idx + 1, idx - 3)

        def _areas_at(indexes: List[int]) -> List[tuple]:
            found: List[tuple] = []
            for line_idx in indexes:
                if not (0 <= line_idx < len(lines)):
                    continue
                for match in auto._AREA_RE.finditer(lines[line_idx]):
                    value = auto._num(match.group(1))
                    if 8.0 <= value <= 1000.0:
                        found.append((round(value, 2), lines[line_idx]))
            return found

        forward = list(range(idx, forward_end))
        areas = _areas_at(forward)
        if not areas:
            areas = _areas_at(list(range(idx - 1, backward_start - 1, -1)))
        distinct = {value for value, _source in areas}
        key = str(label).lower()
        if len(distinct) == 1 and key not in used:
            area = next(iter(distinct))
            source = next(item_source for value, item_source in areas if value == area)
            out.append({"label": label, "area_m2": area, "confidence": "Documented", "source": source})
            used.add(key)
    return out


def apply(app: Any) -> None:
    if getattr(app, "_pb_unit_floor_area_textfix_v1221_applied", False):
        return
    app._pb_unit_floor_area_textfix_v1221_applied = True
    auto.extract_unit_area_candidates = extract_unit_area_candidates
    app.extract_documented_unit_areas = extract_unit_area_candidates
