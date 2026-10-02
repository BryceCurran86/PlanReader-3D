"""Source-owned compact opening callouts on architectural floor plans.

Many Australian residential plans annotate openings directly on the floor plan
with compact size/type callouts such as ``1218 SGW`` or ``2127 STACKER``. This
module treats only an explicit four-digit size code *plus* an opening-type
descriptor as source authority. Bare dimensions never create openings.

The compact code is interpreted as ``HHWW`` in 100 mm increments. For example,
``1218`` resolves to 1200 mm high x 1800 mm wide. The interpretation is
accepted only when the resulting dimensions are physically plausible for the
explicitly classified opening kind.

This module is source-only. It has no external answer data or project-specific
production constants.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Iterable

import fitz

from pb_migration_contracts import QuantityEvidence, stable_contract_id


SOURCE_PLAN_OPENING_CALLOUT_SCHEMA_VERSION = "1.0.0"
SOURCE_PLAN_OPENING_CALLOUT_RESOLVED = "source_plan_opening_callout_resolved"
SOURCE_PLAN_OPENING_CALLOUT_UNAVAILABLE = "source_plan_opening_callout_unavailable"

_FLOOR_PLAN_RE = re.compile(r"\bfloor\s+plan\b|\bplan\s*:\s*floor\b", re.I)
_CODE_RE = re.compile(r"^\d{4}$")

# Explicit source descriptors only. These are generic architectural opening
# terms and never project-specific labels.
_WINDOW_TOKENS = {
    "AW",
    "DH",
    "FG",
    "FW",
    "SGW",
    "WINDOW",
    "WINDOWS",
}
_DOOR_TOKENS = {
    "DOOR",
    "DOORS",
    "STACK",
    "STACKER",
    "PANEL",
    "LIFT",
    "SLIDING",
    "ROLLER",
}


BBox = tuple[float, float, float, float]


def _clean_token(text: object) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(text or "").upper())


def _bbox_union(boxes: Iterable[BBox]) -> BBox:
    boxes = tuple(boxes)
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _round_bbox(box: BBox) -> tuple[float, float, float, float]:
    return tuple(round(float(value), 6) for value in box)  # type: ignore[return-value]


def _classify_descriptor(tokens: tuple[str, ...]) -> str | None:
    normalized = {_clean_token(token) for token in tokens}
    has_window = bool(normalized & _WINDOW_TOKENS)
    has_door = bool(normalized & _DOOR_TOKENS)
    if has_window == has_door:
        return None
    return "window" if has_window else "door"


def _compact_dimensions_mm(
    code: str,
    opening_kind: str,
) -> tuple[float, float] | None:
    if not _CODE_RE.fullmatch(code):
        return None
    height_mm = float(int(code[:2]) * 100)
    width_mm = float(int(code[2:]) * 100)
    if height_mm <= 0.0 or width_mm <= 0.0:
        return None
    if opening_kind == "window":
        if not (
            300.0 <= height_mm <= 3000.0
            and 300.0 <= width_mm <= 6000.0
        ):
            return None
    elif opening_kind == "door":
        if not (
            1800.0 <= height_mm <= 3600.0
            and 600.0 <= width_mm <= 10000.0
        ):
            return None
    else:
        return None
    return (width_mm, height_mm)


@dataclass(frozen=True)
class SourcePlanOpeningCallout:
    opening_id: str
    source_sha256: str
    source_page: int
    page_id: str
    bbox: BBox
    raw_callout: str
    compact_code: str
    descriptor: str
    opening_kind: str
    trade_category: str
    width_mm: float
    height_mm: float
    area_m2: float
    evidence_ids: tuple[str, ...]
    quantity_evidence: QuantityEvidence
    schema_version: str = SOURCE_PLAN_OPENING_CALLOUT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "opening_id": self.opening_id,
            "source_sha256": self.source_sha256,
            "source_page": self.source_page,
            "page_id": self.page_id,
            "bbox": list(self.bbox),
            "raw_callout": self.raw_callout,
            "compact_code": self.compact_code,
            "descriptor": self.descriptor,
            "opening_kind": self.opening_kind,
            "trade_category": self.trade_category,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "area_m2": self.area_m2,
            "evidence_ids": list(self.evidence_ids),
            "quantity_evidence": self.quantity_evidence.to_dict(),
            "schema_version": self.schema_version,
        }


def extract_source_plan_opening_callouts(
    page: fitz.Page,
    *,
    source_sha256: str,
    source_page: int,
) -> tuple[SourcePlanOpeningCallout, ...]:
    """Extract explicit compact opening callouts from one floor-plan page."""
    source_sha256 = str(source_sha256 or "").strip().lower()
    if not source_sha256:
        raise ValueError("source_sha256 must be non-empty")
    if int(source_page) <= 0:
        raise ValueError("source_page must be positive")
    page_text = page.get_text("text") or ""
    if not _FLOOR_PLAN_RE.search(page_text):
        return ()

    lines: dict[tuple[int, int], list[tuple]] = {}
    for word in page.get_text("words") or ():
        if len(word) < 8:
            continue
        lines.setdefault((int(word[5]), int(word[6])), []).append(word)

    found: list[SourcePlanOpeningCallout] = []
    for (block_no, line_no), words in sorted(lines.items()):
        ordered = sorted(words, key=lambda word: int(word[7]))
        tokens = tuple(
            str(word[4]).strip()
            for word in ordered
            if str(word[4]).strip()
        )
        if not tokens:
            continue
        code_indexes = [
            index
            for index, token in enumerate(tokens)
            if _CODE_RE.fullmatch(token)
        ]
        if len(code_indexes) != 1:
            continue
        code_index = code_indexes[0]
        code = tokens[code_index]
        descriptor_tokens = tuple(
            token
            for index, token in enumerate(tokens)
            if index != code_index
        )
        opening_kind = _classify_descriptor(descriptor_tokens)
        if opening_kind is None:
            continue
        dimensions = _compact_dimensions_mm(code, opening_kind)
        if dimensions is None:
            continue
        width_mm, height_mm = dimensions
        area_m2 = (width_mm * height_mm) / 1_000_000.0
        if not math.isfinite(area_m2) or area_m2 <= 0.0:
            continue

        boxes: list[BBox] = [
            (
                float(word[0]),
                float(word[1]),
                float(word[2]),
                float(word[3]),
            )
            for word in ordered
        ]
        bbox = _round_bbox(_bbox_union(boxes))
        raw_callout = " ".join(tokens)
        descriptor = " ".join(descriptor_tokens)
        evidence_payload = {
            "source_sha256": source_sha256,
            "source_page": int(source_page),
            "block_no": block_no,
            "line_no": line_no,
            "bbox": bbox,
            "raw_callout": raw_callout,
        }
        evidence_id = stable_contract_id(
            "source_plan_opening_callout_evidence",
            evidence_payload,
            digest_chars=32,
        )
        opening_id = stable_contract_id(
            "source_plan_opening",
            {
                **evidence_payload,
                "compact_code": code,
                "opening_kind": opening_kind,
            },
            digest_chars=32,
        )
        trade_category = (
            "windows" if opening_kind == "window" else "doors"
        )
        quantity_id = stable_contract_id(
            "source_plan_opening_area_quantity",
            {
                "opening_id": opening_id,
                "width_mm": width_mm,
                "height_mm": height_mm,
            },
            digest_chars=32,
        )
        quantity = QuantityEvidence(
            quantity_id=quantity_id,
            family="opening_area",
            semantic_key=f"opening:{opening_id}:area",
            value=area_m2,
            unit="m2",
            input_entity_ids=(opening_id,),
            formula="width_mm * height_mm / 1000000",
            formula_version="source_plan_compact_opening_callout_v1",
            evidence_ids=(evidence_id,),
            authority="source_plan_compact_opening_callout",
            status="firm",
            confidence=1.0,
            metadata={
                "source_sha256": source_sha256,
                "source_page": int(source_page),
                "bbox": list(bbox),
                "raw_callout": raw_callout,
                "compact_code": code,
                "descriptor": descriptor,
                "opening_kind": opening_kind,
                "trade_category": trade_category,
                "width_mm": width_mm,
                "height_mm": height_mm,
            },
        )
        found.append(
            SourcePlanOpeningCallout(
                opening_id=opening_id,
                source_sha256=source_sha256,
                source_page=int(source_page),
                page_id=str(int(source_page)),
                bbox=bbox,
                raw_callout=raw_callout,
                compact_code=code,
                descriptor=descriptor,
                opening_kind=opening_kind,
                trade_category=trade_category,
                width_mm=width_mm,
                height_mm=height_mm,
                area_m2=area_m2,
                evidence_ids=(evidence_id,),
                quantity_evidence=quantity,
            )
        )

    return tuple(
        sorted(
            found,
            key=lambda item: (
                item.source_page,
                item.bbox[1],
                item.bbox[0],
                item.opening_id,
            ),
        )
    )


__all__ = [
    "SOURCE_PLAN_OPENING_CALLOUT_RESOLVED",
    "SOURCE_PLAN_OPENING_CALLOUT_SCHEMA_VERSION",
    "SOURCE_PLAN_OPENING_CALLOUT_UNAVAILABLE",
    "SourcePlanOpeningCallout",
    "extract_source_plan_opening_callouts",
]
