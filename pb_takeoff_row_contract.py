"""Canonical ``takeoff_rows`` write contract: the single source of field order.

Every PlanReader writer stores take-off rows in one of three layouts, all
built from the same ordered field groups:

``core`` (21)
    ``workspace_id`` + ``EDITABLE_FIELDS`` + ``row_role`` + ``created_at``, ``updated_at``
``commercial`` (26)
    ``core`` with ``COMMERCIAL_AUTHORITY_FIELDS`` inserted before the audit stamps
``commercial_provenance`` (30)
    ``commercial`` with ``PROVENANCE_FIELDS`` inserted before the audit stamps

Producers that build positional rows away from their SQL (for example the
automatic-geometry batch fed by several wrappers) must use these layouts so
a row can never drift from the statement that binds it. Editors that save a
whole schedule use save_schedule(), which keeps each surviving row's id.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

EDITABLE_FIELDS: Tuple[str, ...] = (
    "section", "element", "location", "substrate", "finish_system", "quantity", "unit",
    "quantity_status", "source_page", "source_reference", "inclusion_status", "coats",
    "coverage_m2_per_litre", "productivity_m2_per_hour", "rate_per_unit", "confidence", "notes",
)
COMMERCIAL_AUTHORITY_FIELDS: Tuple[str, ...] = (
    "commercial_authority_status", "commercial_authority_source", "commercial_authority_reviewed_by",
    "commercial_authority_reviewed_at", "commercial_authority_fingerprint",
)
PROVENANCE_FIELDS: Tuple[str, ...] = (
    "ai_baseline_quantity", "pre_map_quantity", "pre_map_quantity_status", "origin",
)
AUDIT_FIELDS: Tuple[str, ...] = ("created_at", "updated_at")

# The estimator's take-off units (the editor's options and the QA's valid set).
TAKEOFF_UNITS: Tuple[str, ...] = ("m²", "lm", "No.", "item", "L", "allowance")

CORE_FIELDS: Tuple[str, ...] = ("workspace_id", *EDITABLE_FIELDS, "row_role", *AUDIT_FIELDS)
COMMERCIAL_FIELDS: Tuple[str, ...] = CORE_FIELDS[:-2] + COMMERCIAL_AUTHORITY_FIELDS + AUDIT_FIELDS
COMMERCIAL_PROVENANCE_FIELDS: Tuple[str, ...] = COMMERCIAL_FIELDS[:-2] + PROVENANCE_FIELDS + AUDIT_FIELDS

LAYOUTS: Dict[str, Tuple[str, ...]] = {
    "core": CORE_FIELDS,
    "commercial": COMMERCIAL_FIELDS,
    "commercial_provenance": COMMERCIAL_PROVENANCE_FIELDS,
}


class TakeoffRowContractError(ValueError):
    """A take-off row or statement does not match the canonical contract."""


def layout_of(columns: Sequence[str]) -> Optional[str]:
    """Name of the canonical layout with exactly these columns in this order, else None."""
    columns = tuple(str(column).strip() for column in columns)
    return next((name for name, fields in LAYOUTS.items() if fields == columns), None)


def insert_sql(fields: Sequence[str] = CORE_FIELDS) -> str:
    """INSERT statement binding ``fields`` positionally; refuses non-canonical layouts."""
    if layout_of(fields) is None:
        raise TakeoffRowContractError(f"not a canonical takeoff_rows layout: {tuple(fields)!r}")
    return f"INSERT INTO takeoff_rows({','.join(fields)}) VALUES({','.join('?' * len(fields))})"


def validate_values(values: Any, fields: Sequence[str] = CORE_FIELDS, *, index: Optional[int] = None,
                    source: str = "") -> Tuple[Any, ...]:
    """Return ``values`` as a tuple, or raise if it cannot bind to ``fields``."""
    if not isinstance(values, (tuple, list)) or len(values) != len(fields):
        length = len(values) if isinstance(values, (tuple, list)) else "n/a"
        where = f"row {index}" if index is not None else "row"
        raise TakeoffRowContractError(
            f"take-off {where} has {length} values; expected {len(fields)} "
            f"({', '.join(fields)}). Row source: {source or type(values).__name__}."
        )
    return tuple(values)


def values_from_mapping(row: Mapping[str, Any], fields: Sequence[str] = CORE_FIELDS) -> Tuple[Any, ...]:
    """Serialise a named row in canonical order; every field must be present."""
    missing = [name for name in fields if name not in row]
    if missing:
        raise TakeoffRowContractError(f"take-off row is missing canonical field(s): {', '.join(missing)}")
    return tuple(row[name] for name in fields)


def mapping_from_values(values: Any, fields: Sequence[str] = CORE_FIELDS) -> Dict[str, Any]:
    """Reconstruct a named row from positional values of a canonical layout."""
    return dict(zip(fields, validate_values(values, fields)))


_KEPT_ON_UPDATE = ("workspace_id", "created_at")


def update_sql(fields: Sequence[str] = CORE_FIELDS) -> str:
    """UPDATE of one workspace row from a canonical layout; workspace_id and created_at are kept."""
    if layout_of(fields) is None:
        raise TakeoffRowContractError(f"not a canonical takeoff_rows layout: {tuple(fields)!r}")
    assigned = ",".join(f"{name}=?" for name in fields if name not in _KEPT_ON_UPDATE)
    return f"UPDATE takeoff_rows SET {assigned} WHERE id=? AND workspace_id=?"


def row_id_of(value: Any) -> Optional[int]:
    """The takeoff_rows id an edited row carries; None for a new row (None, NaN, blank)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if math.isfinite(number) and number.is_integer() else None


def save_schedule(conn: Any, workspace_id: int, rows: Iterable[Tuple[Any, Sequence[Any]]],
                  fields: Sequence[str] = CORE_FIELDS) -> int:
    """Make ``workspace_id``'s take-off schedule exactly ``rows``, keeping row identity. Does not commit.

    ``rows`` are ``(row_id, values)`` pairs, ``values`` in the ``fields`` layout.
    A row carrying the id of one of this workspace's rows updates it in place
    (id and created_at kept), so measurement lines, commercial sync events and
    anything else keyed by takeoff_rows.id stay attached. Other rows - new, a
    repeated id, another workspace's id - are inserted; rows not carried are
    deleted.
    """
    insert, update = insert_sql(fields), update_sql(fields)
    owner = fields.index("workspace_id")
    existing = {int(row[0]) for row in conn.execute("SELECT id FROM takeoff_rows WHERE workspace_id=?", (workspace_id,))}
    kept: set = set()
    count = 0
    for index, (row_id, values) in enumerate(rows):
        values = validate_values(values, fields, index=index, source="take-off schedule save")
        if values[owner] != workspace_id:
            raise TakeoffRowContractError(
                f"take-off row {index} belongs to workspace {values[owner]!r}, not {workspace_id!r}."
            )
        row_id = row_id_of(row_id)
        if row_id in existing and row_id not in kept:
            named = dict(zip(fields, values))
            conn.execute(update, (*(named[name] for name in fields if name not in _KEPT_ON_UPDATE), row_id, workspace_id))
            kept.add(row_id)
        else:
            conn.execute(insert, values)
        count += 1
    for row_id in existing - kept:
        conn.execute("DELETE FROM takeoff_rows WHERE id=? AND workspace_id=?", (row_id, workspace_id))
    return count
