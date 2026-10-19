"""Original 2127 STACKER W4 fragment-role reproof, never an implicit host.

Synthetic contract tests run without private source. The exact SHA-pinned
original source test is intentionally SKIPPED (not passed) on public CI.
"""
from hashlib import sha256
import inspect
from pathlib import Path

import pytest

from tools.diag_gptmax_unmeasured_flank_capture_shadow import (
    SOURCE_SHA, _one_source_policy, replay_opt_in,
)
from tools.diag_gptmax_original_stacker_shared_pier_reproof import (
    original_shared_pier_candidate_w4_reproof,
)


ORIGINAL = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")


@pytest.mark.parametrize("foreign", (None, 1, "True", [], (), object()))
def test_source_fragment_policy_requires_literal_boolean(foreign):
    with pytest.raises(ValueError, match="explicit boolean"):
        replay_opt_in(b"", source_fragment_roles_shadow=foreign)


def test_fragment_roles_require_isolated_original_opening_capture():
    with pytest.raises(ValueError, match="require isolated original G17"):
        _one_source_policy(
            b"", SOURCE_SHA, shadow=False,
            source_fragment_roles_shadow=True,
        )


def test_baseline_source_policy_cannot_use_fragment_role_experiment():
    body = inspect.getsource(replay_opt_in)
    assert "pdf, expected_sha256, shadow=False," in body
    assert "pdf, expected_sha256, shadow=True," in body
    assert "source_fragment_roles_shadow=source_fragment_roles_shadow" in body
    capture = inspect.getsource(_one_source_policy)
    assert "raster_paired_outer_faces_shadow=shadow" in capture
    assert "include_unmeasured_ink_closed_flanks_shadow=shadow" in capture
    assert "source_fragment_roles_shadow=source_fragment_roles_shadow" in capture


def test_altered_bytes_cannot_run_a_positive_fragment_w4_experiment():
    with pytest.raises(ValueError, match="original Lot16 source SHA mismatch"):
        replay_opt_in(
            b"not-authenticated-original-source",
            source_fragment_roles_shadow=True,
        )


def test_original_lot16_fragment_roles_capture_reports_all_release_blocks():
    if not ORIGINAL.is_file():
        pytest.skip(
            "PRIVATE ORIGINAL SOURCE UNAVAILABLE: exact W4 fragment replay unverified"
        )
    payload = ORIGINAL.read_bytes()
    assert sha256(payload).hexdigest() == SOURCE_SHA
    # The existing real original authority composes G17, W2/W3/W4,
    # physical host equivalence, signed quantity and customer verification.
    report = replay_opt_in(payload, source_fragment_roles_shadow=True)
    assert report["source_sha256"] == SOURCE_SHA
    assert report["opt_in_source_fragment_roles_evaluated"] is True
    assert report["source_fragment_host_authority_requires_original_reproof"] is True
    assert report["stacker_2127_native_image_frame_source"][
        "single_native_image_frame_proven"
    ] is True
    assert report["new_metric_handoff_granted"] is False
    assert report["new_signed_area_granted"] is False
    assert report["new_benchmark_match_granted"] is False
    source_piers = report["source_owned_shared_g17_pier_w4_reproof"]
    assert source_piers["all_g17_face_and_parent_ids_reproven_from_current_source"]
    assert source_piers["source_sha256"] == SOURCE_SHA
    assert source_piers["shared_pier_structural_wall_role_proven"] is False
    assert source_piers["shared_pier_host_equivalence_proven"] is False
    assert source_piers["opening_host_or_frame_publication_granted"] is False
    assert source_piers["metric_or_count_publication_granted"] is False
    for pair in source_piers["source_sharing_pairs"]:
        assert pair["wall_host_granted"] is False if "wall_host_granted" in pair else True
        if pair["source_closed_pier_candidate"]:
            assert pair["isolated_original_W2_W3_W4_source_graph"] is not None
    comparison = report["original_change_receipt_parity"]
    assert comparison["signed_snapshot_rekey_approved"] is False
    assert comparison["new_benchmark_match_granted"] is False
    assert len(report["duplicate_original_physical_source_ids"]) == 0


@pytest.mark.parametrize("spoofed_source,spoofed_composition", [
    ({}, {}),
    (None, None),
    ({"snapshot_id": "forged"}, ["not a physical composition"]),
])
def test_shared_pier_source_reader_cannot_consume_caller_json(
        spoofed_source, spoofed_composition):
    with pytest.raises(TypeError, match="published source composition"):
        original_shared_pier_candidate_w4_reproof(
            spoofed_source, spoofed_composition
        )
