"""End-reach original attach refuses host grant and wires census attach."""
from __future__ import annotations

from tools.diag_gptmax_raster_unhosted_flank_source import (
    attach_end_reach_shadow_to_unhosted_rows,
)


def test_census_attach_rejects_host_grant_in_ledger():
    ancestry = [{
        "physical_opening_id": "op-1",
        "host_granted": False,
    }]
    try:
        attach_end_reach_shadow_to_unhosted_rows(
            ancestry,
            {"op-1": {"host_granted": True, "shadow_only": True}},
        )
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "host grant" in str(exc).lower()


def test_census_attach_keeps_host_denied():
    ancestry = [{
        "physical_opening_id": "op-1",
        "host_granted": False,
    }]
    out = attach_end_reach_shadow_to_unhosted_rows(
        ancestry,
        {"op-1": {
            "host_granted": False,
            "shadow_only": True,
            "flanks": (),
        }},
    )
    assert out[0]["host_granted"] is False
    assert out[0]["g17_flank_w4_end_reach_shadow"]["shadow_only"] is True
