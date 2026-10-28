"""Optional original-source regression: skipped (NOT VERIFIED) unless a private drawing is supplied.

The drawing, its SHA, the pages and the pattern/token/quanta are test PARAMETERS taken from the environment;
nothing here names a project, a file or a benchmark value, and nothing is asserted about quantities. The checks
are structural: ownership, exclusivity, grant flags, and that every CANDIDATE is a multi-panel strip whose
other window types support through the module's own quantum-derived tolerance.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

import pb_source_plan_glazing_strip_callout_shadow as shadow
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer

_ENV = "PLANREADER_PLAN_CALLOUT_STRIP_ORIGINAL"       # JSON: {"pdf","sha256","plan_page","elevation_page",...}


def _parameters():
    raw = os.environ.get(_ENV)
    if not raw:
        pytest.skip(f"NOT VERIFIED: set {_ENV} to a JSON parameter object to run the original-source regression")
    params = json.loads(raw)
    path = Path(params["pdf"])
    if not path.is_file():
        pytest.skip("NOT VERIFIED: the original drawing is not present on this machine")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != params["sha256"]:
        pytest.fail("the supplied drawing does not match the pinned SHA-256")
    return params, data


@pytest.fixture(scope="module")
def original():
    params, data = _parameters()
    source = SourceVisibilityProducer(
        producer_method="plan-callout-strip-original-test", producer_version="1",
        source_native_finish_text_shadow=bool(params.get("native_finish_text_shadow", True)))
    published = source.ingest_native_pdf_bytes(
        document_id=f"original:{params['sha256'][:32]}", source_bytes=data, source_locator="memory://original.pdf",
        page_ids=(params["plan_page"], params["elevation_page"]))
    result = shadow.audit_plan_callout_to_glazing_strip_from_source(
        source, revision_id=published.revision.revision_id, plan_page_id=params["plan_page"],
        elevation_page_id=params["elevation_page"], callout_mark_pattern=params["callout_mark_pattern"],
        panel_token=params["panel_token"], coordinate_quantum_pt=params["coordinate_quantum_pt"],
        dimension_quantum_mm=params["dimension_quantum_mm"])
    return params, source, published, result


def test_ownership_grants_and_evidence_ids_belong_to_the_producer(original):
    params, source, published, result = original
    assert result.ownership.source_sha256 == params["sha256"] == published.revision.source_sha256
    assert result.ownership.snapshot_id == published.snapshot.snapshot_id
    visible = set(published.visible_observation_ids)
    assert all(set(s.ink_ids) <= visible for s in result.strips)
    assert all(set(c.ring.ink_ids) <= visible for c in result.correspondences)
    assert all(getattr(result, flag) is False for flag in shadow._GRANT_FLAGS)


def test_every_candidate_is_a_multi_panel_strip_with_exclusive_ownership_and_cross_window_support(original):
    _, _, _, result = original
    strips = {s.strip_id: s for s in result.strips}
    candidates = [c for c in result.correspondences if c.status is EvidenceResolutionStatus.CANDIDATE]
    assert len({c.strip_id for c in candidates}) == len(candidates)          # no strip is shared
    for c in candidates:
        strip = strips[c.strip_id]
        assert strip.panel_count >= 2 and strip.extent_complete
        numbers = dict(c.numbers)
        assert numbers["scale_supporting_pairs"] >= 1
        assert all(state == shadow.PASSED for _, state in c.conditions)
        assert c.rival_callout_ids == ()


def test_a_single_panel_callout_never_becomes_a_candidate(original):
    _, _, _, result = original
    for c in result.correspondences:
        if "single_panel_fingerprint_unmeasurable" in c.reason_codes:
            assert c.status is EvidenceResolutionStatus.ABSTAINED and c.strip_id is None


def test_the_original_source_replay_is_stable(original):
    params, source, published, result = original
    again = shadow.audit_plan_callout_to_glazing_strip_from_source(
        source, revision_id=published.revision.revision_id, plan_page_id=params["plan_page"],
        elevation_page_id=params["elevation_page"], callout_mark_pattern=params["callout_mark_pattern"],
        panel_token=params["panel_token"], coordinate_quantum_pt=params["coordinate_quantum_pt"],
        dimension_quantum_mm=params["dimension_quantum_mm"])
    assert again == result
