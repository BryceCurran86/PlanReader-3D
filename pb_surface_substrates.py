"""Shared substrate labels and inference for PlanReader model metadata."""
from __future__ import annotations

import re
from typing import Any


SUBSTRATE_PRESETS: list[dict[str, str]] = [
    {"code": "EC1", "name": "Lineaboard Cladding", "color": "#A9BFD9"},
    {"code": "EC2", "name": "Textureboard Cladding", "color": "#A5B9DB"},
    {"code": "EC3", "name": "Easylap Cladding", "color": "#B7C4D5"},
    {"code": "RBL", "name": "Rendered Block", "color": "#B9C0C4"},
    {"code": "SOF", "name": "Soffits / Eaves", "color": "#D9C788"},
    {"code": "EC5", "name": "Timber Look Cladding", "color": "#A77C52"},
    {"code": "SCR", "name": "Aluminium Screens", "color": "#BEA8B5"},
    {"code": "BA1", "name": "Glass Balustrade", "color": "#B9C7C8"},
    {"code": "SHD", "name": "Sunhoods", "color": "#919B8D"},
    {"code": "BC", "name": "Cappings & Gutters", "color": "#9AA7AA"},
    {"code": "RS", "name": "Roof Sheet", "color": "#C45F74"},
    {"code": "DP", "name": "Downpipes", "color": "#84A77E"},
    {"code": "GD", "name": "Garage Doors", "color": "#7E8792"},
    {"code": "OTHER", "name": "Other / To Confirm", "color": "#80A6C9"},
]

FALLBACK_SUBSTRATES = [
    dict(preset)
    for preset in SUBSTRATE_PRESETS
    if preset["code"] in {"RBL", "SOF", "EC5", "RS", "OTHER"}
]


def substrate_presets() -> list[dict[str, str]]:
    """Return independent rows from the shared workspace palette."""
    return [dict(item) for item in SUBSTRATE_PRESETS or FALLBACK_SUBSTRATES]


def _substrate_code(text: str) -> str:
    rules = [
        (("soffit", "eave"), "SOF"),
        (("linea", "lineaboard"), "EC1"),
        (("textureboard",), "EC2"),
        (("easylap",), "EC3"),
        (("render", "blockwork", "masonry"), "RBL"),
        (("timber", "wood"), "EC5"),
        (("screen",), "SCR"),
        (("balustrade", "glass"), "BA1"),
        (("sunhood", "sun hood"), "SHD"),
        (("gutter", "capping"), "BC"),
        (("roof", "sheet"), "RS"),
        (("downpipe",), "DP"),
        (("garage",), "GD"),
    ]
    for needles, code in rules:
        if any(needle in text for needle in needles):
            return code
    return "OTHER"


def infer_substrate(finish: Any) -> str:
    text = str(finish or "").lower()
    parts = [part.strip() for part in re.split(r"\b(?:and|or)\b", text) if part.strip()]
    if len(parts) > 1:
        codes = []
        for part in parts:
            code = _substrate_code(part)
            if code != "OTHER" and code not in codes:
                codes.append(code)
        if len(codes) > 1:
            return "OTHER"
        if len(codes) == 1:
            return codes[0]
    return _substrate_code(text)
