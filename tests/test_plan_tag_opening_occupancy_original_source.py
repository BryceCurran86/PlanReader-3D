"""Optional original-source regression for the opening-occupancy separation: skipped (NOT VERIFIED) unless supplied.

The drawing, its SHA, the pages and the pattern/token/quanta are test PARAMETERS taken from the environment (the same
JSON object the callout shadow's own original-source regression reads); nothing here names a project, a file, a tag or
a benchmark value, and nothing is asserted about quantities. The checks are structural invariants of the separation:
the default is unchanged, only CANDIDATE correspondences with a retained separated claimant differ, every separation
is a producer observation set disjoint from its strip and gets a caveat reason, no rival is silently dropped, grants
stay False and a replay is identical.
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
        producer_method="plan-tag-occupancy-original-test", producer_version="1",
        source_native_finish_text_shadow=bool(params.get("native_finish_text_shadow", True)))
    published = source.ingest_native_pdf_bytes(
        document_id=f"original:{params['sha256'][:32]}", source_bytes=data, source_locator="memory://original.pdf",
        page_ids=(params["plan_page"], params["elevation_page"]))
    kw = dict(
        revision_id=published.revision.revision_id, plan_page_id=params["plan_page"],
        elevation_page_id=params["elevation_page"], callout_mark_pattern=params["callout_mark_pattern"],
        panel_token=params["panel_token"], coordinate_quantum_pt=params["coordinate_quantum_pt"],
        dimension_quantum_mm=params["dimension_quantum_mm"])
    base = shadow.audit_plan_callout_to_glazing_strip_from_source(source, **kw)
    first = shadow.audit_plan_callout_to_glazing_strip_from_source(source, claimant_occupancy=True, **kw)
    again = shadow.audit_plan_callout_to_glazing_strip_from_source(source, claimant_occupancy=True, **kw)
    return params, source, published, base, first, again, kw


def test_the_flag_off_result_is_the_default_result_and_carries_no_separation(original):
    params, source, published, base, first, again, kw = original
    assert base == shadow.audit_plan_callout_to_glazing_strip_from_source(source, claimant_occupancy=False, **kw)
    assert all(c.separated_claimants == () for c in base.correspondences)
    assert "claimant_occupancy_evaluated" not in base.page_reason_codes


def test_the_occupancy_pass_ran_on_the_same_source_and_grants_nothing(original):
    params, source, published, base, first, again, kw = original
    assert first.ownership == base.ownership and first.ownership.source_sha256 == params["sha256"]
    assert first.ownership.snapshot_id == published.snapshot.snapshot_id
    assert "claimant_occupancy_evaluated" in first.page_reason_codes
    assert "claimant_occupancy_unavailable" not in first.page_reason_codes
    for name in shadow._GRANT_FLAGS:
        assert getattr(first, name) is False
    assert first.strips == base.strips and first.callout_exclusions == base.callout_exclusions


def test_only_correspondences_with_a_retained_separation_differ_and_each_is_accounted_for(original):
    params, source, published, base, first, again, kw = original
    visible = set(published.visible_observation_ids)
    before = {c.tag_observation_id: c for c in base.correspondences}
    strips = {s.strip_id: s for s in first.strips}
    for c in first.correspondences:
        old = before[c.tag_observation_id]
        if c.record_id == old.record_id:
            assert c.separated_claimants == ()
            continue
        assert c.separated_claimants, "a changed correspondence must carry the claimant it separated"
        # nothing is silently dropped: every old rival is still a rival or a retained separated claimant
        retained = set(c.rival_callout_ids)
        for x in c.separated_claimants:
            retained.add(x.word_observation_id)
            if x.entry == "exclusion":
                retained.add("exclusion:" + x.entry_id)
            if x.entry == "unresolved_word":
                retained.add("unresolved:" + x.word_observation_id)
        assert set(old.rival_callout_ids) <= retained
        for x in c.separated_claimants:
            assert x.entry in {"ring", "exclusion", "unresolved_word"}
            assert x.basis in (shadow.OCCUPANCY_BASIS_ENVELOPE, shadow.OCCUPANCY_BASIS_TEXT)
            assert x.occupied_record_id and set(x.occupied_observation_ids) <= visible
            assert x.strip_id in strips and not set(x.occupied_observation_ids) & set(strips[x.strip_id].ink_ids)
        # a separation never moves a correspondence to another strip
        if c.strip_id is not None and old.strip_id is not None:
            assert c.strip_id == old.strip_id
        if c.status is EvidenceResolutionStatus.CANDIDATE:
            assert shadow.CLAIMANT_SEPARATED_REASON in c.reason_codes and c.rival_callout_ids == ()


def test_a_replay_is_identical(original):
    params, source, published, base, first, again, kw = original
    assert first == again
    assert [c.record_id for c in first.correspondences] == [c.record_id for c in again.correspondences]
