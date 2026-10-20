"""Producer-Owned Glazing U-Value and Thermal Performance Schedule Binding Shadow Authority.

Workstream C / Workstream B:
Binds physical window openings and glazed shopfronts/curtain walls to thermal
performance ratings (U-value in W/m²K, SHGC, glazing assembly, frame substrate)
extracted from fenestration schedule tables without project-specific hardcoding.

Non-negotiable invariants:
- Shadow mode: candidate status only, non-publishing, zero commercial projection.
- Fails closed on missing schedules, conflicting ratings, or non-physical thermal values.
- Preserves 2.5 pt snap tolerance and byte-for-byte customer retention.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

SCHEMA_VERSION = "1.0.0"


class GlazingAssembly(str, Enum):
    SINGLE_CLEAR = "SINGLE_CLEAR"
    SINGLE_TINTED = "SINGLE_TINTED"
    DOUBLE_CLEAR = "DOUBLE_CLEAR"
    DOUBLE_LOW_E = "DOUBLE_LOW_E"
    TRIPLE_LOW_E = "TRIPLE_LOW_E"
    LAMINATED_ACOUSTIC = "LAMINATED_ACOUSTIC"
    UNSPECIFIED = "UNSPECIFIED"


class FrameSubstrate(str, Enum):
    ALUMINIUM_STANDARD = "ALUMINIUM_STANDARD"
    ALUMINIUM_THERMALLY_BROKEN = "ALUMINIUM_THERMALLY_BROKEN"
    UPVC = "UPVC"
    TIMBER = "TIMBER"
    COMPOSITE = "COMPOSITE"
    STEEL = "STEEL"
    UNSPECIFIED = "UNSPECIFIED"


@dataclass(frozen=True)
class ThermalScheduleEntry:
    mark: str
    width_mm: float
    height_mm: float
    u_value_w_m2k: float
    shgc: float
    glazing_assembly: GlazingAssembly
    frame_substrate: FrameSubstrate
    schedule_page_id: str
    source_table_row_id: str


@dataclass(frozen=True)
class GlazingThermalBindingEvidence:
    binding_id: str
    opening_id: str
    mark: str
    u_value_w_m2k: float
    shgc: float
    glazing_assembly: GlazingAssembly
    frame_substrate: FrameSubstrate
    thermal_conductance_w_k: float
    opening_area_sqm: float
    status: EvidenceResolutionStatus
    notes: str
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "binding_id": self.binding_id,
            "opening_id": self.opening_id,
            "mark": self.mark,
            "u_value_w_m2k": round(self.u_value_w_m2k, 2),
            "shgc": round(self.shgc, 2),
            "glazing_assembly": self.glazing_assembly.value,
            "frame_substrate": self.frame_substrate.value,
            "thermal_conductance_w_k": round(self.thermal_conductance_w_k, 3),
            "opening_area_sqm": round(self.opening_area_sqm, 4),
            "status": self.status.value,
            "notes": self.notes,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


class GlazingThermalScheduleBindingShadowAuthority:
    """Binds physical window openings to thermal performance schedule data."""

    def __init__(self) -> None:
        self._entries_by_mark: Dict[str, List[ThermalScheduleEntry]] = {}

    def register_schedule_entry(self, entry: ThermalScheduleEntry) -> None:
        norm_mark = entry.mark.strip().upper()
        if norm_mark not in self._entries_by_mark:
            self._entries_by_mark[norm_mark] = []
        self._entries_by_mark[norm_mark].append(entry)

    def bind_opening(
        self,
        opening_id: str,
        mark: str,
        physical_width_m: float,
        physical_height_m: float,
    ) -> GlazingThermalBindingEvidence:
        """Binds an opening to its thermal schedule performance specifications."""
        norm_mark = mark.strip().upper()
        binding_id = stable_contract_id(
            "GLAZING_THERMAL_BINDING",
            (opening_id, norm_mark),
        )

        area_sqm = physical_width_m * physical_height_m

        if norm_mark not in self._entries_by_mark or not self._entries_by_mark[norm_mark]:
            return GlazingThermalBindingEvidence(
                binding_id=binding_id,
                opening_id=opening_id,
                mark=norm_mark,
                u_value_w_m2k=0.0,
                shgc=0.0,
                glazing_assembly=GlazingAssembly.UNSPECIFIED,
                frame_substrate=FrameSubstrate.UNSPECIFIED,
                thermal_conductance_w_k=0.0,
                opening_area_sqm=area_sqm,
                status=EvidenceResolutionStatus.ABSTAINED,
                notes=f"No thermal schedule entry found for mark '{norm_mark}'.",
            )

        entries = self._entries_by_mark[norm_mark]

        # Check for conflicting entries for the same mark
        u_values = {round(e.u_value_w_m2k, 2) for e in entries}
        shgcs = {round(e.shgc, 2) for e in entries}
        if len(u_values) > 1 or len(shgcs) > 1:
            return GlazingThermalBindingEvidence(
                binding_id=binding_id,
                opening_id=opening_id,
                mark=norm_mark,
                u_value_w_m2k=0.0,
                shgc=0.0,
                glazing_assembly=GlazingAssembly.UNSPECIFIED,
                frame_substrate=FrameSubstrate.UNSPECIFIED,
                thermal_conductance_w_k=0.0,
                opening_area_sqm=area_sqm,
                status=EvidenceResolutionStatus.ABSTAINED,
                notes=f"Conflicting thermal ratings in schedule for mark '{norm_mark}': U-values {u_values}, SHGCs {shgcs}.",
            )

        best_entry = entries[0]

        # Physical reasonableness validation: U-value in [0.5, 7.5], SHGC in [0.10, 0.90]
        if not (0.5 <= best_entry.u_value_w_m2k <= 7.5):
            return GlazingThermalBindingEvidence(
                binding_id=binding_id,
                opening_id=opening_id,
                mark=norm_mark,
                u_value_w_m2k=best_entry.u_value_w_m2k,
                shgc=best_entry.shgc,
                glazing_assembly=best_entry.glazing_assembly,
                frame_substrate=best_entry.frame_substrate,
                thermal_conductance_w_k=0.0,
                opening_area_sqm=area_sqm,
                status=EvidenceResolutionStatus.ABSTAINED,
                notes=f"Non-physical U-value {best_entry.u_value_w_m2k} outside [0.5, 7.5] W/m²K.",
            )

        if not (0.10 <= best_entry.shgc <= 0.90):
            return GlazingThermalBindingEvidence(
                binding_id=binding_id,
                opening_id=opening_id,
                mark=norm_mark,
                u_value_w_m2k=best_entry.u_value_w_m2k,
                shgc=best_entry.shgc,
                glazing_assembly=best_entry.glazing_assembly,
                frame_substrate=best_entry.frame_substrate,
                thermal_conductance_w_k=0.0,
                opening_area_sqm=area_sqm,
                status=EvidenceResolutionStatus.ABSTAINED,
                notes=f"Non-physical SHGC {best_entry.shgc} outside [0.10, 0.90].",
            )

        # Dimension tolerance check: schedule width/height vs physical geometry
        sched_w_m = best_entry.width_mm / 1000.0
        sched_h_m = best_entry.height_mm / 1000.0
        if abs(sched_w_m - physical_width_m) > 0.15 or abs(sched_h_m - physical_height_m) > 0.15:
            return GlazingThermalBindingEvidence(
                binding_id=binding_id,
                opening_id=opening_id,
                mark=norm_mark,
                u_value_w_m2k=best_entry.u_value_w_m2k,
                shgc=best_entry.shgc,
                glazing_assembly=best_entry.glazing_assembly,
                frame_substrate=best_entry.frame_substrate,
                thermal_conductance_w_k=0.0,
                opening_area_sqm=area_sqm,
                status=EvidenceResolutionStatus.ABSTAINED,
                notes=f"Dimension mismatch: schedule {sched_w_m:.2f}x{sched_h_m:.2f}m vs physical {physical_width_m:.2f}x{physical_height_m:.2f}m.",
            )

        thermal_conductance = best_entry.u_value_w_m2k * area_sqm

        return GlazingThermalBindingEvidence(
            binding_id=binding_id,
            opening_id=opening_id,
            mark=norm_mark,
            u_value_w_m2k=best_entry.u_value_w_m2k,
            shgc=best_entry.shgc,
            glazing_assembly=best_entry.glazing_assembly,
            frame_substrate=best_entry.frame_substrate,
            thermal_conductance_w_k=thermal_conductance,
            opening_area_sqm=area_sqm,
            status=EvidenceResolutionStatus.CORROBORATED,
            notes="Corroborated thermal schedule binding.",
        )
