"""Original stacker paired physical, shared-pier and signed issuer replay."""
import inspect
import pytest
from tools.diag_gptmax_unmeasured_flank_capture_shadow import (
    SOURCE_SHA, replay_opt_in, _one_source_policy,
)

def test_exact_source_producer_also_uses_paired_physical_not_only_raster_capture():
    body=inspect.getsource(_one_source_policy)
    assert "raster_paired_outer_faces_shadow=shadow" in body
    assert "include_unmeasured_ink_closed_flanks_shadow=shadow" in body
    assert "page_ids=(3,5) if elevation_witness_shadow else (3,)" in body
    assert 'page_ids=("3",)' in body
    assert 'evidence_page_ids=("5",) if elevation_witness_shadow else ()' in body

@pytest.mark.parametrize("elevation",[None,1,"True",(),object()])
def test_elevation_source_witness_policy_requires_exact_boolean(elevation):
    with pytest.raises(ValueError,match="explicit boolean"):
        replay_opt_in(b"",elevation_witness_shadow=elevation)

def test_original_nonmatching_bytes_cannot_claim_any_host_or_quantity():
    with pytest.raises(ValueError,match="SHA mismatch"):
        replay_opt_in(b"not the source",expected_sha256=SOURCE_SHA)
