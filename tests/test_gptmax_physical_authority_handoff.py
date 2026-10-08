from __future__ import annotations

import hashlib

import pytest

from test_raster_framed_opening_g17_contract import _pdf
from tools.diag_gptmax_physical_authority_handoff import candidate_handoff, physical_handoff


def test_handoff_reuses_production_identity_and_publishes_no_measurements():
    payload = _pdf(frame_lines=2)
    before = bytes(payload)
    result = physical_handoff(payload, page_ids=("1",))
    assert payload == before
    assert result["source_sha256"] == hashlib.sha256(payload).hexdigest()
    assert result["primitive_safety_cap"] == 20_000
    assert result["summary"]["physical_openings"] == 1
    opening = result["physical_openings"][0]["existence"]
    assert opening["document_id"] == "live-source:" + result["source_sha256"][:32]
    assert opening["source_sha256"] == result["source_sha256"]
    assert opening["snapshot_id"] == result["snapshot_id"]
    assert opening["source_observation_ids"]
    assert result["raster_candidate_audits"][0]["candidate_universe_complete"]
    assert "quantities" not in result
    assert "width_m" not in opening
    assert "height_m" not in opening
    assert "count" not in opening
    replay = physical_handoff(payload, page_ids=("1",))
    assert replay == result


def test_handoff_retains_weak_gap_and_missing_source_page_is_rejected():
    payload = _pdf(frame_lines=0)
    result = physical_handoff(payload, page_ids=("1",))
    assert result["physical_openings"] == []
    audit = result["raster_candidate_audits"][0]
    assert not audit["candidate_universe_complete"]
    assert audit["unresolved_candidate_ids"]
    assert audit["unresolved_observation_ids"]
    with pytest.raises(ValueError):
        physical_handoff(payload, page_ids=("99",))


def test_candidate_only_inventory_does_not_claim_host_or_quantity_authority():
    payload = _pdf(frame_lines=2)
    result = candidate_handoff(payload, page_ids=("1",))
    assert result == candidate_handoff(payload, page_ids=("1",))
    assert result["summary"]["physical_openings"] == 1
    assert result["raster_audit_available"]
    assert result["raster_candidate_audits"][0]["candidate_universe_complete"]
    assert result["physical_openings"][0]["source_sha256"] == hashlib.sha256(payload).hexdigest()
    assert "host_bindings" not in result["summary"]
    assert "quantities" not in result
    assert "width_m" not in result["physical_openings"][0]
    weak = candidate_handoff(_pdf(frame_lines=0), page_ids=("1",))
    assert not weak["raster_candidate_audits"][0]["candidate_universe_complete"]
    assert weak["raster_candidate_audits"][0]["unresolved_candidate_ids"]
