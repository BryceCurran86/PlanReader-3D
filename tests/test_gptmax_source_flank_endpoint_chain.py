"""Six original-source G17/W2/W4 near-flank witnesses must never mint hosts."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.diag_gptmax_source_flank_endpoint_chain import original_flank_endpoint_census

ROOT=Path(__file__).resolve().parents[1]
LEDGER=ROOT/"docs/engineering/gptmax_lot16_host_source_queue_20261016.json"
SOURCE_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"


@pytest.fixture
def archived():
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def call(data):
    return original_flank_endpoint_census(data,expected_source_sha=SOURCE_SHA)


def test_original_six_cases_source_and_immutable_grants(archived):
    result=call(archived)
    assert result["status"]=="original_source_host_flank_endpoint_chain_shadow"
    assert len(result["source_rows"])==6
    assert {r["first_unmapped_flank"] for r in result["source_rows"]}=={
        "raster_source_band_left_source_primitive_unmapped",
        "raster_source_band_right_source_primitive_unmapped",
    }
    for row in result["source_rows"]:
        assert set(row["original_flanks"])=={"left","right"}
        assert row["original_W4_host_record_granted"] is False
        assert row["measured_width_height_granted"] is False
        assert row["customer_quantity_granted"] is False
        for side in row["original_flanks"].values():
            assert side["all_competing_w4_identities_preserved"]
            assert not side["physical_local_wall_ownership_proven"]
            for source in side["reported_parent_candidates"]:
                assert source["host_publication_allowed"] is False
                assert not source["positive_local_original_w4_chain_corroborated"]
    assert result["original_pdf_reauthenticated_by_this_function"] is False
    assert result["archived_ledger_only_not_fresh_producer_receipt"] is True
    assert not any(result[k] for k in ("host_authority_granted",
        "frame_authority_granted","opening_count_granted",
        "ordered_dimensions_granted","customer_quantity_granted"))


def test_deterministic_case_order_and_g17_source_order(archived):
    first=call(archived)
    mutated=deepcopy(archived)
    mutated["case_evidence"].reverse()
    for c in mutated["case_evidence"]:
        c["source_g17_observations"].reverse()
        c["source_w4_ancestry_audit"]["diagnostic_local_raster_lines"].reverse()
    assert call(mutated)==first


def test_original_w4_competitors_retained_not_nearest(archived):
    result=call(archived)
    rows=[r for r in result["source_rows"] if r["opening_identity_id"].endswith("c1acf90b")]
    assert len(rows)==1
    candidates=[p for side in rows[0]["original_flanks"].values()
                for p in side["reported_parent_candidates"]]
    w4s={w for p in candidates for w in p["all_original_w4_candidate_addresses"]}
    # The same raw W2 parent has multiple physical W4 identities.
    assert len(w4s)>=2
    assert rows[0]["original_W4_host_record_granted"] is False


@pytest.mark.parametrize("corrupt",[
    lambda d:d.update(source_sha256="0"*64),
    lambda d:d.update(snapshot_id=""),
    lambda d:d["baseline_summary"].update(authenticated_hosts=16),
    lambda d:d["current_main_sealed_handoff"].update(quantity_count=9),
    lambda d:d["authority_grants"].update(new_host=True),
    lambda d:d["case_evidence"][0]["host_binding"].update(record_id="injected-host"),
    lambda d:d["case_evidence"][0].update(physical_opening_id="other"),
    lambda d:d["case_evidence"][0]["source_g17_observations"][0].update(
        geometry_pdf_pts=[float("nan"),1,2,3]),
    lambda d:d["case_evidence"][0]["source_g17_observations"][1].update(
        observation_id=d["case_evidence"][0]["source_g17_observations"][0]["observation_id"]),
    lambda d:d["case_evidence"][0]["source_w4_ancestry_audit"][
        "diagnostic_local_raster_lines"][0][
        "w2_source_fragment_geometry_by_w4_candidate"][0].update(
            wall_candidate_id="forged-W4"),
])
def test_tampered_source_parent_host_or_signed_identity_fails(archived,corrupt):
    modified=deepcopy(archived)
    corrupt(modified)
    with pytest.raises((ValueError, KeyError, TypeError)):
        call(modified)


def test_original_fragment_near_gap_never_supplies_width_or_height(archived):
    result=call(archived)
    for row in result["source_rows"]:
        for flank in row["original_flanks"].values():
            for candidate in flank["reported_parent_candidates"]:
                for fragment in candidate["original_w2_fragments"]:
                    assert fragment["original_w4_wall_id"] in (
                        candidate["all_original_w4_candidate_addresses"])
                    assert "original_fragment_axis_interval_pt" in fragment
    assert result["ordered_dimensions_granted"] is False
