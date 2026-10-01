"""pb_takeoff_learning_ledger.py — PlanReader AI Takeoff, Error Taxonomy & Learning Ledger.

Implements:
  1. AI Draft Takeoff Flow: strictly provisional/draft takeoff candidates with explicit confidence,
     source region, uncertainty flags, and review requirements.
  2. Error Taxonomy: standardized taxonomy of 16 measurement and classification error reasons.
  3. Takeoff Learning Ledger: persistent audit trail of AI detections, app measurements,
     user corrections, and source-verified comparisons (future training dataset).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Error Taxonomy
# ---------------------------------------------------------------------------

class ErrorTaxonomy(str, Enum):
    SCALE_ERROR = "scale_error"
    OCR_ERROR = "ocr_error"
    WRONG_DIMENSION_SELECTED = "wrong_dimension_selected"
    OPENING_MISSED = "opening_missed"
    OPENING_DOUBLE_COUNTED = "opening_double_counted"
    WALL_FALSE_POSITIVE = "wall_false_positive"
    WALL_MISSING = "wall_missing"
    FINISH_TAG_WRONG = "finish_tag_wrong"
    SCHEDULE_ROW_MISREAD = "schedule_row_misread"
    PROJECT_MISMATCH = "project_mismatch"
    WRONG_REVISION = "wrong_revision"
    HEIGHT_UNKNOWN = "height_unknown"
    RAKED_WALL_NOT_HANDLED = "raked_wall_not_handled"
    STAIR_AREA_COMPLEX = "stair_area_complex"
    FACTORY_FINISH_EXCLUDED = "factory_finish_excluded"
    SCOPE_RULE_WRONG = "scope_rule_wrong"


# ---------------------------------------------------------------------------
# AI Draft Takeoff Models
# ---------------------------------------------------------------------------

@dataclass
class AIDraftTakeoffRow:
    draft_id: str
    section: str
    location: str
    substrate: str
    finish_tag: str
    element: str
    unit: str
    detected_quantity: float
    confidence: float
    source_page: str
    source_region: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    reasoning_summary: str
    uncertainty_flags: List[str] = field(default_factory=list)
    requires_review: bool = True
    authority_status: str = "provisional"

    def __post_init__(self) -> None:
        if not math.isfinite(self.detected_quantity) or self.detected_quantity < 0.0:
            raise ValueError("Detected quantity must be non-negative finite number")
        if self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Takeoff Learning Ledger
# ---------------------------------------------------------------------------

@dataclass
class LearningLedgerEntry:
    entry_id: str
    benchmark_or_job_id: str
    object_id: str
    object_type: str  # "wall", "room", "opening", "surface", "ceiling", "gfa"
    ai_detected_value: Optional[float]
    planreader_measured_value: Optional[float]
    user_corrected_value: Optional[float]
    approved_final_value: Optional[float]
    source_page: str
    source_region: str
    error_reason: str  # from ErrorTaxonomy
    confidence_before: float
    confidence_after: float
    project_type: str  # "townhouse", "commercial", "high_rise", "tender"
    drawing_style: str  # "cad_vector", "raster_scan", "hybrid"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TakeoffLearningLedger:
    """Manages the correction ledger and accuracy metrics for model refinement."""

    def __init__(self, entries: Optional[List[LearningLedgerEntry]] = None):
        self.entries: List[LearningLedgerEntry] = list(entries or [])

    def record_correction(
        self,
        entry_id: str,
        benchmark_or_job_id: str,
        object_id: str,
        object_type: str,
        planreader_measured_value: Optional[float],
        user_corrected_value: float,
        source_page: str,
        error_reason: str,
        confidence_before: float = 0.60,
        confidence_after: float = 1.0,
        project_type: str = "townhouse",
        drawing_style: str = "cad_vector",
        ai_detected_value: Optional[float] = None,
        notes: str = "",
    ) -> LearningLedgerEntry:
        entry = LearningLedgerEntry(
            entry_id=entry_id,
            benchmark_or_job_id=benchmark_or_job_id,
            object_id=object_id,
            object_type=object_type,
            ai_detected_value=ai_detected_value,
            planreader_measured_value=planreader_measured_value,
            user_corrected_value=user_corrected_value,
            approved_final_value=user_corrected_value,
            source_page=source_page,
            source_region="",
            error_reason=error_reason,
            confidence_before=confidence_before,
            confidence_after=confidence_after,
            project_type=project_type,
            drawing_style=drawing_style,
            notes=notes,
        )
        self.entries.append(entry)
        return entry

    def get_top_error_reasons(self, limit: int = 5) -> List[Tuple[str, int]]:
        counts: Dict[str, int] = {}
        for e in self.entries:
            counts[e.error_reason] = counts.get(e.error_reason, 0) + 1
        sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_counts[:limit]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_entries": len(self.entries),
            "top_error_reasons": self.get_top_error_reasons(),
            "entries": [e.to_dict() for e in self.entries],
        }

    def save_to_file(self, file_path: str | Path) -> None:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load_from_file(cls, file_path: str | Path) -> "TakeoffLearningLedger":
        path = Path(file_path)
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = []
        for d in data.get("entries", []):
            entries.append(LearningLedgerEntry(**d))
        return cls(entries)
