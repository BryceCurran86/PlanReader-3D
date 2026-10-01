"""Production-neutral project identity contracts.

These models are used by PlanReader project/revision mismatch protection. They
are deliberately independent of any benchmark or scoring system.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class SourceManifest:
    """Source-identity constraints for comparison/mismatch protection."""

    benchmark_id: str
    project_name: str
    project_number: str
    client: str
    drawing_issue: str
    drawing_date: str
    source_pdf: Optional[str] = None
    source_takeoff: Optional[str] = None
    allowed_comparison_sources: list[str] = field(default_factory=list)
    rejected_comparison_sources: list[str] = field(default_factory=list)
    status: str = "source_identity"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProjectIdentity:
    """Observed or expected project identity used to fail closed on mismatches."""

    project_name: str
    address: str
    client: str
    project_number: str
    drawing_issue: str = ""
    drawing_date: str = ""
    drawing_set_title: str = ""
    number_of_units: Optional[int] = None
    number_of_levels: Optional[int] = None
    sheet_count: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
