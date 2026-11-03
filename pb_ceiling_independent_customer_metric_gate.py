"""Customer gate: source-authenticated RCP MATERIAL is not ceiling AREA.

The original room-floor metric may be correct while a distinct RCP zone has
different physical boundaries. An original ceiling area requires its own
producer-owned source metric quantity and source evidence; a copied numeric
room area and a matching ceiling-finish mark never grant saleable m².
This module does not measure geometry or alter frozen benchmark truth.
"""
from __future__ import annotations

from collections.abc import Mapping

from pb_migration_contracts import QuantityEvidence


_BORROWED_CEILING_FORMULAS = frozenset({
    "reuse_firm_documented_room_area_with_authenticated_rcp_finish",
    "reuse exact firm documented room area on canonical ceiling",
    "reuse exact firm scaled room area on canonical ceiling",
})


def independently_sourced_ceiling_customer_metric(
    quantity: QuantityEvidence,
) -> bool:
    """True only for an independently issued original RCP ceiling metric.

    Missing/false material source permission stays false; never invent it
    at the customer projector. The source ceiling area receipt must be
    physically distinct from the original room FLOOR area receipt. Source
    importers need their own byte-authentication and geometry validation
    before they may issue such a positive record.
    """
    if type(quantity) is not QuantityEvidence:
        return False
    if (
        quantity.family != "ceiling_lining"
        or quantity.abstained
        or quantity.value is None
        or quantity.blocking_reasons
        or type(quantity.formula) is not str
        or quantity.formula in _BORROWED_CEILING_FORMULAS
        # A renamed floor-reuse formula is not an independent source
        # measurement. No generic, unknown or model-derived formula may
        # bypass a missing original RCP ceiling-area issuer.
        or quantity.formula
        != "authenticated_independent_rcp_ceiling_area_from_original_figures"
        or not isinstance(quantity.metadata, Mapping)
    ):
        return False
    metadata = quantity.metadata
    if (
        metadata.get("commercial_projection_allowed") is not True
        or (
            "quantity_handoff_only" in metadata
            and metadata["quantity_handoff_only"] is not False
        )
        or (
            "shadow_only" in metadata
            and metadata["shadow_only"] is not False
        )
    ):
        return False

    # An issuer's two independent source receipts are mandatory: one
    # quantity ID for the ceiling-zone metric and one original RCP
    # evidence witness. Merely copying the room-area issuer's ID or
    # two floor dimensions must not authorize the ceiling.
    original_ceiling_id = metadata.get("independent_rcp_ceiling_area_quantity_id")
    original_rcp_evidence = metadata.get("independent_rcp_ceiling_area_evidence_id")
    room_floor_area_id = metadata.get("upstream_room_area_quantity_id")
    if any(
        type(value) is not str
        or not value
        or value != value.strip()
        for value in (
            original_ceiling_id, original_rcp_evidence, room_floor_area_id,
        )
    ):
        return False
    if (
        original_ceiling_id == room_floor_area_id
        or original_rcp_evidence not in quantity.evidence_ids
        or original_rcp_evidence == room_floor_area_id
    ):
        return False
    # Both original RCP area and its material occurrence must refer to
    # the SAME source sheet/viewport. A floor sheet is not silently treated
    # as the independent RCP geometry authority.
    for area_key, support_key in (
        ("independent_rcp_ceiling_area_page_id", "support_page_id"),
        ("independent_rcp_ceiling_area_viewport_id", "support_viewport_id"),
    ):
        area_value = metadata.get(area_key)
        support_value = metadata.get(support_key)
        if (
            type(area_value) is not str
            or not area_value
            or area_value != area_value.strip()
            or type(support_value) is not str
            or support_value != area_value
        ):
            return False
    return True


__all__ = ["independently_sourced_ceiling_customer_metric"]
