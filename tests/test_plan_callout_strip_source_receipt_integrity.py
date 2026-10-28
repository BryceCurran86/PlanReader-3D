"""Real producer channels cannot borrow a foreign or malformed positive receipt."""
from __future__ import annotations

from dataclasses import replace

import pytest

import pb_source_plan_glazing_strip_callout_shadow as shadow
from pb_migration_contracts import EvidenceResolutionStatus
from test_plan_callout_glazing_strip_shadow_producer import (
    _audit, _plan_sheet, _publish, _resolved_viewport,
)


@pytest.fixture
def source_case(monkeypatch):
    _resolved_viewport(monkeypatch)
    source, published = _publish(_plan_sheet())
    baseline = _audit(source, published)
    assert {c.status for c in baseline.correspondences} == {EvidenceResolutionStatus.CANDIDATE}
    return source, published, baseline


def assert_no_grants(result):
    assert all(getattr(result, flag) is False for flag in shadow._GRANT_FLAGS)


BAD_BOXES = [None, (), (1.0, 2.0, 3.0), (1.0, 2.0, 3.0, 4.0, 5.0),
             (True, 2.0, 3.0, 4.0), ("1", 2.0, 3.0, 4.0),
             (float("nan"), 2.0, 3.0, 4.0), (1.0, 2.0, float("inf"), 4.0),
             (1.0, 2.0, 10 ** 500, 4.0), (1.0, 2.0, 1.0, 4.0)]


@pytest.mark.parametrize("change", [
    {"document_id": "foreign"}, {"revision_id": "foreign"}, {"source_sha256": "0" * 64},
    {"parent_observation_id": "foreign"}, {"trusted": False}, {"raw_text": "other"},
    {"source_partition_id": "foreign"}, {"geometry": (10.0, 10.0, 20.0, 20.0)},
    *[{"geometry": box} for box in BAD_BOXES],
])
def test_text_receipt_integrity_is_checked_before_positive_use(source_case, monkeypatch, change):
    source, published, baseline = source_case
    authority = source.text_integrity_authority()
    original = authority.resolve_text

    calls = []

    def forged(self, selector):
        result = original(selector)
        if result.receipt is not None and str(result.receipt.page_id) == "1" and result.trusted_text == "W1":
            calls.append(selector.observation_id)
            return replace(result, receipt=replace(result.receipt, **change))
        return result

    with monkeypatch.context() as patch:
        patch.setattr(type(authority), "resolve_text", forged)
        result = _audit(source, published)
        assert calls, "the producer channel must actually be exercised"
        assert "source_text_inventory_incomplete" in result.page_reason_codes
        assert all(c.status is not EvidenceResolutionStatus.CANDIDATE for c in result.correspondences)
        assert_no_grants(result)
    assert _audit(source, published) == baseline


def test_foreign_owner_is_not_hidden_by_a_receipt_page_filter(source_case, monkeypatch):
    source, published, _ = source_case
    authority = source.text_integrity_authority()
    original = authority.resolve_text

    calls = []

    def forged(self, selector):
        result = original(selector)
        if result.receipt is not None and str(result.receipt.page_id) == "1" and result.trusted_text == "W1":
            calls.append(selector.observation_id)
            return replace(result, receipt=replace(result.receipt, document_id="foreign", page_id="99"))
        return result

    monkeypatch.setattr(type(authority), "resolve_text", forged)
    result = _audit(source, published)
    assert calls
    assert "source_text_inventory_incomplete" in result.page_reason_codes
    assert all(c.status is not EvidenceResolutionStatus.CANDIDATE for c in result.correspondences)


@pytest.mark.parametrize("trusted_text", [None, 1, True, "W2"])
def test_positive_text_wrapper_cannot_replace_the_receipts_exact_text(source_case, monkeypatch, trusted_text):
    source, published, _ = source_case
    authority = source.text_integrity_authority()
    original = authority.resolve_text

    calls = []

    def forged(self, selector):
        result = original(selector)
        if result.receipt is not None and str(result.receipt.page_id) == "1" and result.trusted_text == "W1":
            calls.append(selector.observation_id)
            return replace(result, trusted_text=trusted_text)
        return result

    monkeypatch.setattr(type(authority), "resolve_text", forged)
    result = _audit(source, published)
    assert calls
    assert "source_text_inventory_incomplete" in result.page_reason_codes
    assert all(c.status is not EvidenceResolutionStatus.CANDIDATE for c in result.correspondences)


def test_matching_forged_receipt_and_wrapper_cannot_replace_original_source_text(source_case, monkeypatch):
    source, published, _ = source_case
    authority = source.text_integrity_authority()
    original = authority.resolve_text
    calls = []

    def forged(self, selector):
        result = original(selector)
        if result.receipt is not None and str(result.receipt.page_id) == "1" and result.trusted_text == "W1":
            calls.append(selector.observation_id)
            return replace(result, trusted_text="W9", receipt=replace(result.receipt, raw_text="W9"))
        return result

    monkeypatch.setattr(type(authority), "resolve_text", forged)
    result = _audit(source, published)
    assert calls
    assert "source_text_inventory_incomplete" in result.page_reason_codes
    assert all(c.status is not EvidenceResolutionStatus.CANDIDATE for c in result.correspondences)


@pytest.mark.parametrize("change", [
    {"observation_id": "foreign"}, {"document_id": "foreign"}, {"revision_id": "foreign"},
    {"source_sha256": "0" * 64}, {"snapshot_id": "foreign"},
    *[{"geometry": box} for box in BAD_BOXES[:-1]],
])
def test_visible_ink_wrapper_authenticates_immutable_owner_and_geometry(source_case, monkeypatch, change):
    source, published, baseline = source_case
    authority = source.authority()
    original = authority.resolve_visible
    victim = baseline.strips[0].ink_ids[0]

    calls = []

    def forged(self, selector):
        result = original(selector)
        if selector.observation_id == victim:
            calls.append(selector.observation_id)
            return replace(result, observation=replace(result.observation, **change))
        return result

    with monkeypatch.context() as patch:
        patch.setattr(type(authority), "resolve_visible", forged)
        result = _audit(source, published)
        assert calls
        assert "source_visible_ink_inventory_incomplete" in result.page_reason_codes
        assert all(c.status is not EvidenceResolutionStatus.CANDIDATE for c in result.correspondences)
        assert_no_grants(result)
    assert _audit(source, published) == baseline


@pytest.mark.parametrize("change", [
    {"document_id": "foreign"}, {"revision_id": "foreign"}, {"source_sha256": "0" * 64},
    {"snapshot_id": "foreign"}, {"type_mark": "W2"},
    *[{"frame_bbox": box} for box in BAD_BOXES],
])
def test_elevation_record_must_belong_to_the_requested_source_and_mark(source_case, monkeypatch, change):
    from pb_opening_elevation_frame_area_authority import OpeningElevationFrameAreaAuthority

    source, published, baseline = source_case
    original = OpeningElevationFrameAreaAuthority.resolve

    def forged(self, selector):
        result = original(self, selector)
        if selector.type_mark == "W1" and result.record is not None:
            return replace(result, record=replace(result.record, **change))
        return result

    with monkeypatch.context() as patch:
        patch.setattr(OpeningElevationFrameAreaAuthority, "resolve", forged)
        result = _audit(source, published)
        victim = next(c for c in result.correspondences if c.tag_mark == "W1")
        assert victim.status is not EvidenceResolutionStatus.CANDIDATE
        assert "elevation_type_record_missing" in victim.reason_codes
        assert_no_grants(result)
    assert _audit(source, published) == baseline


@pytest.mark.parametrize("field,reason", [
    ("text_observation_ids", "source_text_inventory_incomplete"),
    ("visible_observation_ids", "source_visible_ink_inventory_incomplete"),
])
def test_duplicate_published_identity_cannot_be_counted_as_separate_source(source_case, monkeypatch, field, reason):
    source, published, baseline = source_case
    ids = getattr(published, field)
    duplicated = replace(published, **{field: (*ids, ids[0])})
    with monkeypatch.context() as patch:
        patch.setattr(source, "published_snapshot_for_revision", lambda revision: duplicated)
        result = _audit(source, published)
        assert reason in result.page_reason_codes
        assert all(c.status is not EvidenceResolutionStatus.CANDIDATE for c in result.correspondences)
        assert_no_grants(result)
    assert _audit(source, published) == baseline


@pytest.mark.parametrize("page", [1, 2])
def test_a_failed_requested_page_cannot_be_reused_as_decoded(source_case, monkeypatch, page):
    source, published, _ = source_case
    failed = replace(published, coverage=replace(published.coverage, failed_pages=(page,)))
    monkeypatch.setattr(source, "published_snapshot_for_revision", lambda revision: failed)
    with pytest.raises(ValueError, match="source pages unavailable"):
        _audit(source, published)


def test_healthy_source_replay_preserves_published_state_and_no_authority(source_case):
    source, published, baseline = source_case
    before = source.published_snapshot_for_revision(published.revision.revision_id)
    payload = source._producer._store.source_bytes_by_revision[published.revision.revision_id]
    assert _audit(source, published) == baseline
    assert source.published_snapshot_for_revision(published.revision.revision_id) == before
    assert source._producer._store.source_bytes_by_revision[published.revision.revision_id] == payload
    assert_no_grants(baseline)
