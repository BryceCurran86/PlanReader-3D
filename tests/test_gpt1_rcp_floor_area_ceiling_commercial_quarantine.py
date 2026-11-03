"""Original RCP finish marks do not independently measure ceiling square metres.

The source-neutral fixture proves the real cross-view issuer can authenticate a
GRID mark and still remain commercially blocked in the live application until
an independent RCP ceiling-zone area exists. This is NOT original Maryborough
source acceptance, and does not change the frozen four-project benchmark.
"""
from dataclasses import replace

import pytest

from pb_live_physical_net_wall_integration import (
    _rcp_ceiling_floor_area_reuse_blockers,
)
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_gpt2_malformed_ceiling_quantity_result_quarantine import (
    _issued,
)


def test_real_firm_cross_view_rcp_material_does_not_prove_independent_ceiling_area():
    source = _issued()
    # The old cross-view issuer retains a genuine room-area and RCP mark.
    # A FIRM quantity from its borrowed source is not a separately measured
    # ceiling surface and must never enter the live customer claim.
    assert source.status is EvidenceResolutionStatus.CORROBORATED
    assert len(source.records) == len(source.quantities) == 1
    original = source.quantities[0]
    assert original.value == 9.05352
    assert (
        original.formula
        == "reuse_firm_documented_room_area_with_authenticated_rcp_finish"
    )
    assert _rcp_ceiling_floor_area_reuse_blockers(source) == (
        ("physical-room-1", "independent_rcp_ceiling_metric_area_unproven"),
    )
    assert source.quantities[0] == original


def test_no_rcp_material_candidate_reports_no_borrowed_ceiling_area():
    source = _issued()
    no_claim = replace(
        source,
        records=(),
        status=EvidenceResolutionStatus.ABSTAINED,
        unresolved_physical_room_ids=("physical-room-1",),
    )
    assert _rcp_ceiling_floor_area_reuse_blockers(no_claim) == ()
    assert no_claim.quantities == ()


@pytest.mark.parametrize("formula", (
    "", "independent_ceiling_area_claimed_without_source",
    "reuse_firm_documented_room_area_with_authenticated_rcp_finish ",
))
def test_reconstructed_unknown_rcp_formula_never_grants_ceiling_commercial_authority(
    formula,
):
    source = _issued()
    original_record = source.records[0]
    quantity = replace(original_record.quantity, formula=formula)
    forged = replace(source, records=(
        replace(original_record, quantity=quantity),
    ))
    assert forged.quantities == ()
    assert _rcp_ceiling_floor_area_reuse_blockers(forged) == (
        ("physical-room-1", "independent_rcp_ceiling_metric_issuer_unavailable"),
    )


def test_source_metric_failure_receipts_do_not_contain_synthesized_ceiling_quantities():
    from dataclasses import fields
    from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim

    names = {field.name for field in fields(LivePhysicalNetWallClaim)}
    assert "ceiling_metric_first_failure_codes" in names
    assert LivePhysicalNetWallClaim.__dataclass_fields__[
        "ceiling_metric_first_failure_codes"
    ].default == ()
