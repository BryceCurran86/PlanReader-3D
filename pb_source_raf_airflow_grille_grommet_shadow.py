"""
pb_source_raf_airflow_grille_grommet_shadow.py

Authoritative shadow-mode extraction and takeoff for raised access floor airflow grilles,
perforated panels, opposable dampers, and cable pass-through grommets.

Non-negotiable constraints:
- Status: CANDIDATE
- commercial_projection_allowed: False
- takeoff_eligible: False
- Global snap tolerance: 2.5 pt
"""

from dataclasses import dataclass, field
from enum import Enum
import math
import re
from typing import Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5


class RAFAppurtenanceType(str, Enum):
    PERFORATED_AIRFLOW_PANEL = "PERFORATED_AIRFLOW_PANEL"
    HIGH_CFM_DIRECTIONAL_GRILLE = "HIGH_CFM_DIRECTIONAL_GRILLE"
    INTEGRATED_DAMPER_PANEL = "INTEGRATED_DAMPER_PANEL"
    BRUSH_SEAL_CABLE_GROMMET = "BRUSH_SEAL_CABLE_GROMMET"
    INTEGRAL_FLOOR_BOX = "INTEGRAL_FLOOR_BOX"


class DamperControlMechanism(str, Enum):
    OPPOSING_BLADE_DAMPER = "OPPOSING_BLADE_DAMPER"
    MANUAL_SLIDE_DAMPER = "MANUAL_SLIDE_DAMPER"
    NO_DAMPER = "NO_DAMPER"


@dataclass
class RAFAppurtenanceSpec:
    item_id: str
    appurtenance_type: RAFAppurtenanceType = RAFAppurtenanceType.PERFORATED_AIRFLOW_PANEL
    location_point: Tuple[float, float] = (0.0, 0.0)
    panel_width_mm: float = 600.0
    panel_length_mm: float = 600.0
    open_area_percent: float = 25.0
    airflow_capacity_cfm: float = 800.0
    damper_mechanism: DamperControlMechanism = DamperControlMechanism.NO_DAMPER
    level_id: str = "L01"
    room_id: Optional[str] = None
    source_callout: str = ""


@dataclass
class RAFAppurtenanceQuantities:
    total_items_count: int = 0
    total_airflow_panels_count: int = 0
    total_airflow_capacity_cfm: float = 0.0
    total_cable_grommets_count: int = 0
    total_floor_boxes_count: int = 0
    count_by_type: Dict[str, int] = field(default_factory=dict)
    count_by_damper: Dict[str, int] = field(default_factory=dict)


@dataclass
class RAFAppurtenanceExtractionResult:
    items: List[RAFAppurtenanceSpec] = field(default_factory=list)
    quantities: RAFAppurtenanceQuantities = field(default_factory=RAFAppurtenanceQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceRAFAirflowGrilleGrommetShadowAuthority:
    """Authoritative shadow evaluator for raised access floor airflow panels, grilles, and grommets."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses raised access floor appurtenance callouts.
        Example strings:
          - "600x600 56% OPEN PERFORATED AIRFLOW PANEL W/ OPPOSING BLADE DAMPER 1200 CFM"
          - "68% DIRECTIONAL HIGH CFM AIRFLOW GRILLE 1500 CFM"
          - "200mm DIA SPLIT BRUSH CABLE GROMMET"
          - "INTEGRAL 4-GANG POWER/DATA FLOOR BOX"
        """
        clean = text.upper()
        res = {
            "appurtenance_type": RAFAppurtenanceType.PERFORATED_AIRFLOW_PANEL,
            "panel_width_mm": 600.0,
            "panel_length_mm": 600.0,
            "open_area_percent": 25.0,
            "airflow_capacity_cfm": 800.0,
            "damper_mechanism": DamperControlMechanism.NO_DAMPER,
        }

        # Typology
        if "GROMMET" in clean or "BRUSH" in clean:
            res["appurtenance_type"] = RAFAppurtenanceType.BRUSH_SEAL_CABLE_GROMMET
            res["open_area_percent"] = 0.0
            res["airflow_capacity_cfm"] = 0.0
        elif "FLOOR BOX" in clean or "POWER/DATA" in clean:
            res["appurtenance_type"] = RAFAppurtenanceType.INTEGRAL_FLOOR_BOX
            res["open_area_percent"] = 0.0
            res["airflow_capacity_cfm"] = 0.0
        elif "DIRECTIONAL" in clean or "HIGH CFM" in clean or "GRILLE" in clean:
            res["appurtenance_type"] = RAFAppurtenanceType.HIGH_CFM_DIRECTIONAL_GRILLE
            res["open_area_percent"] = 68.0
            res["airflow_capacity_cfm"] = 1500.0
        elif "DAMPER" in clean:
            res["appurtenance_type"] = RAFAppurtenanceType.INTEGRATED_DAMPER_PANEL
            res["open_area_percent"] = 56.0
            res["airflow_capacity_cfm"] = 1200.0
        else:
            res["appurtenance_type"] = RAFAppurtenanceType.PERFORATED_AIRFLOW_PANEL
            res["open_area_percent"] = 25.0
            res["airflow_capacity_cfm"] = 800.0

        # Damper mechanism
        if "OPPOSING" in clean or "OPPOSABLE" in clean:
            res["damper_mechanism"] = DamperControlMechanism.OPPOSING_BLADE_DAMPER
        elif "SLIDE" in clean or "SLIDING" in clean:
            res["damper_mechanism"] = DamperControlMechanism.MANUAL_SLIDE_DAMPER
        elif "DAMPER" in clean:
            res["damper_mechanism"] = DamperControlMechanism.OPPOSING_BLADE_DAMPER
        else:
            res["damper_mechanism"] = DamperControlMechanism.NO_DAMPER

        # Open area percent: 25%, 56%, 68%
        pct_match = re.search(r'(\d{2})\s*%\s*(?:OPEN)?', clean)
        if pct_match:
            try:
                res["open_area_percent"] = float(pct_match.group(1))
            except ValueError:
                pass

        # Airflow CFM: 1200 CFM, 800 CFM, 1500CFM
        cfm_match = re.search(r'(\d{3,4})\s*CFM', clean)
        if cfm_match:
            try:
                res["airflow_capacity_cfm"] = float(cfm_match.group(1))
            except ValueError:
                pass

        # Panel dimensions: 600x600
        dim_match = re.search(r'(\d{3})\s*[xX*]\s*(\d{3})', clean)
        if dim_match:
            try:
                res["panel_width_mm"] = float(dim_match.group(1))
                res["panel_length_mm"] = float(dim_match.group(2))
            except ValueError:
                pass

        return res

    @staticmethod
    def snap_point(pt: Tuple[float, float], tolerance: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
        x, y = pt
        snapped_x = round(x / tolerance) * tolerance
        snapped_y = round(y / tolerance) * tolerance
        return (round(snapped_x, 4), round(snapped_y, 4))

    @classmethod
    def evaluate_appurtenances(
        cls,
        raw_items_data: List[Dict[str, any]],
        default_level: str = "L01"
    ) -> RAFAppurtenanceExtractionResult:
        """
        Authoritative shadow extraction for raised access floor airflow panels, grilles, and grommets.
        """
        extracted_items: List[RAFAppurtenanceSpec] = []
        tot_airflow_panels = 0
        tot_cfm = 0.0
        tot_grommets = 0
        tot_boxes = 0

        cnt_by_type: Dict[str, int] = {}
        cnt_by_damper: Dict[str, int] = {}

        for item in raw_items_data:
            item_id = item.get("item_id", f"RAF_{len(extracted_items)+1:03d}")
            raw_pt = item.get("location_point", (0.0, 0.0))
            snapped_pt = cls.snap_point(raw_pt)

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            atype_val = item.get("appurtenance_type", parsed["appurtenance_type"])
            if isinstance(atype_val, str):
                try:
                    atype = RAFAppurtenanceType(atype_val)
                except ValueError:
                    atype = RAFAppurtenanceType.PERFORATED_AIRFLOW_PANEL
            else:
                atype = atype_val

            w_mm = float(item.get("panel_width_mm", parsed["panel_width_mm"]))
            l_mm = float(item.get("panel_length_mm", parsed["panel_length_mm"]))
            open_pct = float(item.get("open_area_percent", parsed["open_area_percent"]))
            cfm = float(item.get("airflow_capacity_cfm", parsed["airflow_capacity_cfm"]))

            dtype_val = item.get("damper_mechanism", parsed["damper_mechanism"])
            if isinstance(dtype_val, str):
                try:
                    dtype = DamperControlMechanism(dtype_val)
                except ValueError:
                    dtype = DamperControlMechanism.NO_DAMPER
            else:
                dtype = dtype_val

            spec = RAFAppurtenanceSpec(
                item_id=item_id,
                appurtenance_type=atype,
                location_point=snapped_pt,
                panel_width_mm=w_mm,
                panel_length_mm=l_mm,
                open_area_percent=open_pct,
                airflow_capacity_cfm=cfm,
                damper_mechanism=dtype,
                level_id=item.get("level_id", default_level),
                room_id=item.get("room_id"),
                source_callout=callout,
            )
            extracted_items.append(spec)

            if atype in (
                RAFAppurtenanceType.PERFORATED_AIRFLOW_PANEL,
                RAFAppurtenanceType.HIGH_CFM_DIRECTIONAL_GRILLE,
                RAFAppurtenanceType.INTEGRATED_DAMPER_PANEL,
            ):
                tot_airflow_panels += 1
                tot_cfm += cfm
            elif atype == RAFAppurtenanceType.BRUSH_SEAL_CABLE_GROMMET:
                tot_grommets += 1
            elif atype == RAFAppurtenanceType.INTEGRAL_FLOOR_BOX:
                tot_boxes += 1

            t_key = atype.value
            cnt_by_type[t_key] = cnt_by_type.get(t_key, 0) + 1

            d_key = dtype.value
            cnt_by_damper[d_key] = cnt_by_damper.get(d_key, 0) + 1

        quantities = RAFAppurtenanceQuantities(
            total_items_count=len(extracted_items),
            total_airflow_panels_count=tot_airflow_panels,
            total_airflow_capacity_cfm=round(tot_cfm, 2),
            total_cable_grommets_count=tot_grommets,
            total_floor_boxes_count=tot_boxes,
            count_by_type=cnt_by_type,
            count_by_damper=cnt_by_damper,
        )

        return RAFAppurtenanceExtractionResult(
            items=extracted_items,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceRAFAirflowGrilleGrommetShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
