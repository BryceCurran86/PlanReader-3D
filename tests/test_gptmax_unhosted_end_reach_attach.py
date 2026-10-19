from tools.diag_gptmax_raster_unhosted_flank_source import (
    attach_end_reach_shadow_to_unhosted_rows,
    audit_g17_unhosted_flank_original_ancestry as audit,
)
from test_gptmax_raster_unhosted_flank_source import fixture
import pytest


def test_end_reach_shadow_attaches_without_granting_host():
    source, pub, comp, *_ = fixture()
    rows = audit(source, pub, comp)
    oid = rows[0]["physical_opening_id"]
    ledger = {
        "shadow_only": True,
        "host_granted": False,
        "reason_codes": ("raster_source_band_left_source_primitive_unmapped",),
        "flanks": (),
    }
    attached = attach_end_reach_shadow_to_unhosted_rows(
        rows, {oid: ledger}
    )
    assert attached[0]["host_granted"] is False
    assert attached[0]["metric_quantity_granted"] is False
    assert attached[0]["g17_flank_w4_end_reach_shadow"]["host_granted"] is False


def test_end_reach_host_grant_attempt_fails_closed():
    source, pub, comp, *_ = fixture()
    rows = audit(source, pub, comp)
    oid = rows[0]["physical_opening_id"]
    with pytest.raises(RuntimeError, match="host grant"):
        attach_end_reach_shadow_to_unhosted_rows(
            rows, {oid: {"shadow_only": True, "host_granted": True}}
        )
