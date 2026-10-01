"""Database and Customer UI Unit Integrity Engine (AG-16).

Audit & Integrity Guarantees:
- Canonical Takeoff Units: m², lm, No., m³ (plus item, L, allowance).
- Zero silent downgrades: volumetric quantities (m³) must not be silently converted
  to 'item' or 'allowance'; area quantities (m²) must not be silently collapsed to 'lm'.
- Zero silent conversions: aliases (m2, sqm, lm, ea, m3, cum) must strictly normalize
  to their canonical glyphs without loss of precision or dimensional distortion.
- Fail-closed verification: unrecognized units raise explicit errors instead of being accepted.
- Full pipeline integrity:
  CANONICAL OBJECT -> QUANTITY -> DATABASE (SQLite) -> CUSTOMER UI & EXPORTS.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import io
import math
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pb_takeoff_row_contract as takeoff_contract


CORE_CONSTRUCTION_UNITS: Tuple[str, ...] = ("m²", "lm", "No.", "m³")
ALL_TAKEOFF_UNITS: Tuple[str, ...] = takeoff_contract.TAKEOFF_UNITS


class UnitDimension(str, Enum):
    AREA = "area"
    LINEAR = "linear"
    COUNT = "count"
    VOLUME = "volume"
    LIQUID = "liquid"
    ITEM = "item"
    ALLOWANCE = "allowance"
    UNKNOWN = "unknown"


# Mapping from normalized canonical unit to dimension
CANONICAL_UNIT_DIMENSION: Dict[str, UnitDimension] = {
    "m²": UnitDimension.AREA,
    "lm": UnitDimension.LINEAR,
    "No.": UnitDimension.COUNT,
    "m³": UnitDimension.VOLUME,
    "L": UnitDimension.LIQUID,
    "item": UnitDimension.ITEM,
    "allowance": UnitDimension.ALLOWANCE,
}

_UNIT_ALIASES: Dict[str, str] = {
    # Area
    "m2": "m²",
    "sqm": "m²",
    "sq m": "m²",
    "m²": "m²",
    "m^2": "m²",
    "square metre": "m²",
    "square metres": "m²",
    "square meter": "m²",
    "square meters": "m²",
    # Linear
    "lm": "lm",
    "lin m": "lm",
    "linm": "lm",
    "m": "lm",
    "metre": "lm",
    "metres": "lm",
    "meter": "lm",
    "meters": "lm",
    "lineal": "lm",
    "linear": "lm",
    "linear metre": "lm",
    "linear metres": "lm",
    "linear meter": "lm",
    "linear meters": "lm",
    # Count
    "no": "No.",
    "no.": "No.",
    "nos": "No.",
    "nos.": "No.",
    "ea": "No.",
    "ea.": "No.",
    "each": "No.",
    "count": "No.",
    "number": "No.",
    "nr": "No.",
    "nr.": "No.",
    # Volume
    "m3": "m³",
    "cum": "m³",
    "cu m": "m³",
    "m³": "m³",
    "m^3": "m³",
    "cumetre": "m³",
    "cumetres": "m³",
    "cumeter": "m³",
    "cumeters": "m³",
    "cubic metre": "m³",
    "cubic metres": "m³",
    "cubic meter": "m³",
    "cubic meters": "m³",
    # Liquid
    "l": "L",
    "litre": "L",
    "litres": "L",
    "liter": "L",
    "liters": "L",
    "ltr": "L",
    "lt": "L",
    # Item & Allowance
    "item": "item",
    "items": "item",
    "ls": "item",
    "lumpsum": "item",
    "lump sum": "item",
    "allowance": "allowance",
    "allow": "allowance",
    "provisional": "allowance",
}


class UnitIntegrityError(ValueError):
    """Raised when an invalid, corrupted, or unsupported unit of measure is encountered."""


def normalize_takeoff_unit(raw_unit: Any, *, strict: bool = True) -> str:
    """Strictly normalize any takeoff unit string to its canonical PlanReader representation.

    Args:
        raw_unit: Raw input string (e.g. 'm2', 'M3', 'each', 'lm').
        strict: If True, raises UnitIntegrityError on unknown units.
                If False, returns empty string on unknown units.

    Returns:
        Canonical string in ALL_TAKEOFF_UNITS.
    """
    if raw_unit in ALL_TAKEOFF_UNITS:
        return str(raw_unit)

    text = str(raw_unit or "").strip().lower()
    if not text:
        if strict:
            raise UnitIntegrityError("Takeoff unit cannot be empty.")
        return ""

    cleaned = re.sub(r"[\s\.\-_]+", "", text)

    # 1. Exact alias lookup
    if text in _UNIT_ALIASES:
        return _UNIT_ALIASES[text]
    if cleaned in _UNIT_ALIASES:
        return _UNIT_ALIASES[cleaned]

    # 2. Heuristic containment (ordered: Volume before Area before Linear)
    if "m³" in text or "m3" in text or "cubic" in text or "cum" in cleaned:
        return "m³"
    if "m²" in text or "m2" in text or "sqm" in cleaned or "square" in text:
        return "m²"
    if "lineal" in text or "linear" in text or cleaned in {"lm", "linm"}:
        return "lm"
    if cleaned in {"no", "nos", "ea", "each", "count"}:
        return "No."
    if cleaned in {"l", "litre", "litres", "ltr"}:
        return "L"
    if "item" in text or cleaned in {"ls", "lumpsum"}:
        return "item"
    if "allow" in text:
        return "allowance"

    if strict:
        raise UnitIntegrityError(f"Unsupported takeoff unit '{raw_unit}'. Allowed: {ALL_TAKEOFF_UNITS}")
    return ""


def dimension_of_unit(unit: str) -> UnitDimension:
    """Return the dimensional family of a normalized canonical unit."""
    return CANONICAL_UNIT_DIMENSION.get(unit, UnitDimension.UNKNOWN)


def detect_unit_downgrade(element: str, unit: str, notes: str = "") -> Optional[str]:
    """Detect if a quantity was silently downgraded (e.g. m³ -> item or m² -> lm).

    Returns:
        A diagnostic reason string if a silent downgrade occurred, else None.
    """
    elem_lower = str(element or "").lower()
    notes_lower = str(notes or "").lower()
    norm_u = normalize_takeoff_unit(unit, strict=False)

    # 1. Volumetric Downgrade to Item or Allowance
    is_volumetric_context = any(kw in elem_lower or kw in notes_lower for kw in [
        "concrete volume", "grout volume", "m³", "m3", "cubic metre", "cu m",
        "concrete supply", "pump & place", "supply & pump", "waist slab + steps volume",
    ])
    if is_volumetric_context and norm_u in ("item", "allowance"):
        return f"Volumetric measure detected in '{element}' or notes but unit was downgraded to '{norm_u}' instead of canonical 'm³'."

    # 2. Area Downgrade to Linear Metres without linear element scope
    is_area_context = any(kw in elem_lower for kw in [
        "wall surface", "floor area", "ceiling lining", "roof cladding", "waterproofing membrane", "wall tiling"
    ])
    if is_area_context and norm_u == "lm" and not any(kw in elem_lower for kw in ["skirting", "cornice", "perimeter", "trim"]):
        return f"Surface area element '{element}' was downgraded to linear unit '{norm_u}' instead of canonical 'm²'."

    return None


@dataclass
class RowUnitAuditResult:
    is_valid: bool
    unit: str
    dimension: UnitDimension
    quantity: float
    has_downgrade: bool
    downgrade_reason: Optional[str] = None
    issues: List[str] = field(default_factory=list)


def audit_takeoff_row_unit(
    row: Mapping[str, Any] | Sequence[Any],
    *,
    fields: Sequence[str] = takeoff_contract.CORE_FIELDS,
) -> RowUnitAuditResult:
    """Audit the unit integrity and numeric safety of a single takeoff row."""
    if isinstance(row, Mapping):
        row_dict = dict(row)
    else:
        row_dict = takeoff_contract.mapping_from_values(row, fields)

    raw_unit = row_dict.get("unit")
    element = str(row_dict.get("element") or "")
    notes = str(row_dict.get("notes") or "")
    raw_qty = row_dict.get("quantity")

    issues: List[str] = []

    # Numeric validation
    try:
        qty = float(raw_qty)
        if not math.isfinite(qty) or qty < 0.0:
            issues.append(f"Invalid quantity {raw_qty}: must be non-negative finite number.")
    except (TypeError, ValueError):
        qty = 0.0
        issues.append(f"Quantity {raw_qty!r} cannot be converted to float.")

    # Unit validation
    try:
        norm_unit = normalize_takeoff_unit(raw_unit, strict=True)
        dimension = dimension_of_unit(norm_unit)
    except UnitIntegrityError as exc:
        norm_unit = str(raw_unit or "")
        dimension = UnitDimension.UNKNOWN
        issues.append(str(exc))

    # Downgrade check
    downgrade_reason = detect_unit_downgrade(element, norm_unit, notes)
    has_downgrade = downgrade_reason is not None

    is_valid = len(issues) == 0 and not has_downgrade

    return RowUnitAuditResult(
        is_valid=is_valid,
        unit=norm_unit,
        dimension=dimension,
        quantity=qty,
        has_downgrade=has_downgrade,
        downgrade_reason=downgrade_reason,
        issues=issues,
    )


@dataclass
class DatabaseUnitAuditReport:
    workspace_id: int
    total_rows: int
    all_valid: bool
    zero_downgrades: bool
    unit_counts: Dict[str, int] = field(default_factory=dict)
    unit_sums: Dict[str, float] = field(default_factory=dict)
    dimension_sums: Dict[str, float] = field(default_factory=dict)
    downgraded_rows: List[Dict[str, Any]] = field(default_factory=list)
    invalid_rows: List[Dict[str, Any]] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)


def audit_database_unit_integrity(conn: Any, workspace_id: int) -> DatabaseUnitAuditReport:
    """Audit the SQLite takeoff_rows table for a workspace to verify unit integrity."""
    cursor = conn.cursor()

    # Verify column types
    cursor.execute("PRAGMA table_info(takeoff_rows)")
    col_info = {row[1]: row[2].upper() for row in cursor.fetchall()}

    issues: List[str] = []
    if "QUANTITY" in col_info and col_info["QUANTITY"] not in ("REAL", "FLOAT", "NUMERIC"):
        issues.append(f"Column 'quantity' has schema type {col_info['QUANTITY']}; expected REAL.")
    if "UNIT" in col_info and col_info["UNIT"] != "TEXT":
        issues.append(f"Column 'unit' has schema type {col_info['UNIT']}; expected TEXT.")

    # Fetch rows
    cursor.execute("SELECT * FROM takeoff_rows WHERE workspace_id=? ORDER BY id", (workspace_id,))
    cols = [d[0] for d in cursor.description]
    raw_rows = cursor.fetchall()

    total_rows = len(raw_rows)
    unit_counts: Dict[str, int] = {u: 0 for u in ALL_TAKEOFF_UNITS}
    unit_sums: Dict[str, float] = {u: 0.0 for u in ALL_TAKEOFF_UNITS}
    dimension_sums: Dict[str, float] = {d.value: 0.0 for d in UnitDimension}

    downgraded_rows: List[Dict[str, Any]] = []
    invalid_rows: List[Dict[str, Any]] = []

    for r in raw_rows:
        row_dict = dict(zip(cols, r))
        audit = audit_takeoff_row_unit(row_dict)

        u = audit.unit
        unit_counts[u] = unit_counts.get(u, 0) + 1
        unit_sums[u] = round(unit_sums.get(u, 0.0) + audit.quantity, 2)
        dim_str = audit.dimension.value
        dimension_sums[dim_str] = round(dimension_sums.get(dim_str, 0.0) + audit.quantity, 2)

        if audit.has_downgrade:
            downgraded_rows.append({
                "id": row_dict.get("id"),
                "element": row_dict.get("element"),
                "unit": u,
                "reason": audit.downgrade_reason,
            })
        if not audit.is_valid:
            invalid_rows.append({
                "id": row_dict.get("id"),
                "element": row_dict.get("element"),
                "unit": u,
                "issues": audit.issues,
            })

    all_valid = len(invalid_rows) == 0 and len(issues) == 0
    zero_downgrades = len(downgraded_rows) == 0

    return DatabaseUnitAuditReport(
        workspace_id=workspace_id,
        total_rows=total_rows,
        all_valid=all_valid,
        zero_downgrades=zero_downgrades,
        unit_counts=unit_counts,
        unit_sums=unit_sums,
        dimension_sums=dimension_sums,
        downgraded_rows=downgraded_rows,
        invalid_rows=invalid_rows,
        issues=issues,
    )


@dataclass
class UIUnitAuditReport:
    workspace_id: int
    dataframe_units_valid: bool
    per_level_summary_has_m3: bool
    excel_detail_units_preserved: bool
    boq_export_units_preserved: bool
    all_units_preserved: bool
    issues: List[str] = field(default_factory=list)


def audit_ui_and_export_unit_integrity(app: Any, workspace_id: int) -> UIUnitAuditReport:
    """Verify that the customer UI and export endpoints consume authoritative units without silent conversion."""
    issues: List[str] = []

    # 1. dataframe_for_takeoff
    df = app.dataframe_for_takeoff(workspace_id)
    df_valid = True
    if not df.empty:
        for u in df["unit"]:
            if u not in ALL_TAKEOFF_UNITS:
                issues.append(f"dataframe_for_takeoff returned un-normalized unit '{u}'.")
                df_valid = False

    # 2. per_level_summary
    pls = app.per_level_summary(workspace_id)
    pls_has_m3 = "m3" in pls.columns

    # 3. quote_workbook_bytes (Excel)
    excel_preserved = True
    try:
        import openpyxl
        wb_bytes = app.quote_workbook_bytes(workspace_id)
        wb = openpyxl.load_workbook(io.BytesIO(wb_bytes))
        if "Take-off Detail" in wb.sheetnames:
            detail_ws = wb["Take-off Detail"]
            header = [cell.value for cell in detail_ws[1]]
            if "unit" in header:
                unit_idx = header.index("unit") + 1
                for row_idx in range(2, detail_ws.max_row + 1):
                    val = detail_ws.cell(row=row_idx, column=unit_idx).value
                    if val is not None and str(val) not in ALL_TAKEOFF_UNITS:
                        issues.append(f"Excel row {row_idx} unit '{val}' not in TAKEOFF_UNITS.")
                        excel_preserved = False
    except Exception as exc:
        issues.append(f"Excel quote inspection failed: {exc}")
        excel_preserved = False

    # 4. BuilderEditionEngine BoQ Export
    boq_preserved = True
    try:
        from pb_builder_edition_architecture import BuilderEditionEngine
        engine = BuilderEditionEngine()
        conn = app.local_connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM takeoff_rows WHERE workspace_id=?", (workspace_id,))
            cols = [d[0] for d in cur.description]
            db_rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        finally:
            conn.close()

        if db_rows:
            estimate = engine.aggregate_and_price_workspace(db_rows, workspace_id=workspace_id)
            csv_text = engine.export_bill_of_quantities_csv(estimate)
            for pkg in estimate.packages.values():
                for item in pkg.items:
                    if item.unit not in ALL_TAKEOFF_UNITS:
                        issues.append(f"BoQ line item {item.item_no} unit '{item.unit}' not in TAKEOFF_UNITS.")
                        boq_preserved = False
    except Exception as exc:
        issues.append(f"BoQ engine inspection failed: {exc}")
        boq_preserved = False

    all_preserved = df_valid and pls_has_m3 and excel_preserved and boq_preserved and len(issues) == 0

    return UIUnitAuditReport(
        workspace_id=workspace_id,
        dataframe_units_valid=df_valid,
        per_level_summary_has_m3=pls_has_m3,
        excel_detail_units_preserved=excel_preserved,
        boq_export_units_preserved=boq_preserved,
        all_units_preserved=all_preserved,
        issues=issues,
    )
