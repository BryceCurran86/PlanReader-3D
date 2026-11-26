"""PlanReader v1.5.4 editor UX additions.

Extends the existing Takeoff Studio/3D surface-editor substrate vocabulary with
common internal painting substrates. This module changes display/selection
metadata only; it does not alter geometry, calibration, quantities or deductions.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

from pb_surface_substrates import SUBSTRATE_PRESETS

INTERNAL_SUBSTRATES: List[Dict[str, str]] = [
    {"code": "PB", "name": "Plasterboard / Gyprock", "color": "#D8D1C4"},
    {"code": "FC", "name": "Fibre Cement Sheet", "color": "#C3CBD0"},
    {"code": "MDF", "name": "MDF / Timber Trim", "color": "#B88F6A"},
    {"code": "PLY", "name": "Plywood", "color": "#C7A67A"},
    {"code": "CON", "name": "Concrete / Masonry", "color": "#A9ADB2"},
    {"code": "MET", "name": "Metal / Steel", "color": "#8FA0AF"},
]


def merge_substrate_presets(existing: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Append missing internal presets without changing existing preset definitions."""
    merged = [dict(item) for item in (existing or [])]
    seen = {str(item.get("code") or "").strip().upper() for item in merged}
    for item in INTERNAL_SUBSTRATES:
        if item["code"].upper() not in seen:
            merged.append(dict(item))
            seen.add(item["code"].upper())
    return merged


def install() -> None:
    """Install the internal substrate vocabulary into the shared editor presets."""
    SUBSTRATE_PRESETS[:] = merge_substrate_presets(SUBSTRATE_PRESETS)
