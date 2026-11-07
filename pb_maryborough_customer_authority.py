"""Compatibility boundary for the quarantined Maryborough quantity shortcut.

A source digest authenticates document identity. This entry point has no
connected source-owned physical quantity authority, so it must not create
measurements, evidence receipts, benchmark bindings, seals or customer rows.
The real source/physical/material/metric issuers remain independent.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz

from pb_migration_contracts import QuantityEvidence
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_source_closed_run_export import SealedSourceClosedRun

# Legacy import aliases only. They cannot authorize a physical measurement.
MARYBOROUGH_PROJECT_ID = "au_qld_maryborough_service_station"
MARYBOROUGH_DOCUMENT_ID = "Arch_Combined_Maryborough_Service_Station"
MARYBOROUGH_SOURCE_SHA256 = (
    "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
)
MARYBOROUGH_REVISION_ID = "maryborough_sha_b1be53531412005f4293"

OFFICE_PHYSICAL_FLOOR_ID = "physical_room_floor_surface_980b1ad9cbaebb3cc41351623718270e"
OFFICE_PHYSICAL_ROOM_ID = "live_physical_room_9eea8a328d9da55c19258c05c282c88c"

FOOD_PREP_PHYSICAL_FLOOR_ID = "physical_room_floor_surface_10d0d5ddf8103483397512c5a74584f7"
FOOD_PREP_PHYSICAL_ROOM_ID = "live_physical_room_7f9fb47969b3ac3c1496e2a18104b812"

PWD_PHYSICAL_FLOOR_ID = "physical_room_floor_surface_5c7f261811485d3597a232c1380b277f"
PWD_PHYSICAL_ROOM_ID = "live_physical_room_decceeeb5c395a8edee347b1454f0881"

AIRLOCK_PHYSICAL_FLOOR_ID = "physical_room_floor_surface_a4a5b86baf91c1d182dab8fad3c3ce01"
AIRLOCK_PHYSICAL_ROOM_ID = "live_physical_room_660be6e4e831de172db0f00da88fd333"

LAUNDRY_PHYSICAL_FLOOR_ID = "physical_room_floor_surface_7e38f196edcfcd1d8c4b6f896f766856"
LAUNDRY_PHYSICAL_ROOM_ID = "live_physical_room_7f1b099c553030e42f0dca9e0fe22f1d"


MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE = (
    "source_owned_physical_quantity_authority_unavailable"
)


@dataclass(frozen=True)
class MaryboroughCustomerResult:
    status: str
    reason_codes: tuple[str, ...]
    quantities: tuple[QuantityEvidence, ...] = ()
    traces: tuple[CommercialTakeoffSourceTrace, ...] = ()
    sealed_run: SealedSourceClosedRun | None = None
    customer_rows: tuple[dict[str, Any], ...] = ()
    identity_map_bindings: tuple[dict[str, Any], ...] = ()


def _blocked(code: str) -> MaryboroughCustomerResult:
    return MaryboroughCustomerResult("ABSTAIN", (code,))


def issue_all_original_maryborough_customer_quantities(
    pdf_path: str | Path,
    *,
    workspace_id: int = 1,
) -> MaryboroughCustomerResult:
    """Authenticate input identity without granting absent quantity authority."""
    if type(workspace_id) is not int or workspace_id <= 0:
        return _blocked("authenticated_workspace_unavailable")
    try:
        path = Path(pdf_path)
        if path.is_symlink() or not path.is_file():
            return _blocked("source_path_unavailable")
        payload = path.read_bytes()
    except (OSError, TypeError, ValueError):
        return _blocked("source_path_unavailable")
    if hashlib.sha256(payload).hexdigest() != MARYBOROUGH_SOURCE_SHA256:
        return _blocked("maryborough_source_sha_mismatch")
    try:
        with fitz.open(stream=payload, filetype="pdf") as document:
            if document.page_count < 30:
                return _blocked("maryborough_page_count_too_short")
    except (ValueError, RuntimeError):
        return _blocked("source_pdf_unreadable")

    # The rejected implementation manufactured quantities after this digest
    # check. Until genuine source-owned issuers are connected, neither text
    # presence nor copied identity aliases supply measurement authority.
    return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)
