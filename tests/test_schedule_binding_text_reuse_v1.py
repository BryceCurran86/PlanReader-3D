"""Within one composer loop the schedule binder reads a snapshot's trusted text once; outside it nothing changes.

Synthetic PDFs through the real producers. Reuse is only taken while the snapshot and every text receipt are the same objects as
when the text was read, so an upgraded or replaced receipt forces a new read and the result a direct call would give.
"""
from __future__ import annotations

import dataclasses

import pytest

import pb_schedule_opening_instance_binding_authority as binding
from pb_migration_contracts import EvidenceResolutionStatus
from pb_schedule_opening_instance_binding_authority import (
    BINDING_NO_CONTAINED_TAG,
    ScheduleOpeningInstanceBindingProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.test_schedule_opening_instance_binding_authority_v1 import SCOPE, _ingest, _opening_selector, _tag_pdf


def _case(payload, name):
    source = SourceVisibilityProducer(producer_method=f"text-reuse-{name}", producer_version="1.0")
    published = _ingest(source, payload, name)
    selector = _opening_selector(published, source.authority())
    published = source.published_snapshot_for_revision(published.revision.revision_id)
    return source, published, selector


def _binder(source):
    return ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(source)


@pytest.fixture()
def reads(monkeypatch):
    """One entry per full read of a snapshot's trusted text (the number of words read)."""
    calls = []
    original = binding._read_trusted_text

    def counted(text_integrity, published, opening):
        calls.append(len(published.text_observation_ids))
        return original(text_integrity, published, opening)

    monkeypatch.setattr(binding, "_read_trusted_text", counted)
    return calls


@pytest.mark.parametrize("kwargs", [
    {},
    {"tag_text": "ZZ"},
    {"schedule_rows": (("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100"), ("W1", "1200", "2100"))},
])
def test_reuse_gives_the_same_result_as_a_direct_call(kwargs):
    source, _published, selector = _case(_tag_pdf(**kwargs), "same")
    direct = _binder(source).publish_scope(opening_selector=selector, decision_scope_id=SCOPE)
    binder = _binder(source)
    with binder.reusing_page_text():
        first = binder.publish_scope(opening_selector=selector, decision_scope_id=SCOPE)
        second = binder.publish_scope(opening_selector=selector, decision_scope_id=SCOPE + ":again")
    assert (first.status, first.reason_codes, first.record) == (direct.status, direct.reason_codes, direct.record)
    assert (second.status, second.reason_codes) == (direct.status, direct.reason_codes)


def test_the_text_is_read_once_inside_the_block_and_every_time_outside(reads):
    source, published, selector = _case(_tag_pdf(), "count")
    words = len(published.text_observation_ids)
    assert words > 3
    binder = _binder(source)
    binder.publish_scope(opening_selector=selector, decision_scope_id=SCOPE)
    binder.publish_scope(opening_selector=selector, decision_scope_id=SCOPE + ":b")
    assert reads == [words, words]
    reads.clear()
    with binder.reusing_page_text():
        for n in range(4):
            binder.publish_scope(opening_selector=selector, decision_scope_id=f"{SCOPE}:{n}")
    assert reads == [words]
    reads.clear()
    binder.publish_scope(opening_selector=selector, decision_scope_id=SCOPE + ":after")
    assert reads == [words]


def test_a_receipt_changed_between_openings_is_read_again_and_seen(reads):
    source, published, selector = _case(_tag_pdf(), "change")
    snapshot = published.snapshot.snapshot_id
    binder = _binder(source)
    with binder.reusing_page_text():
        first = binder.publish_scope(opening_selector=selector, decision_scope_id=SCOPE)
        assert first.status is EvidenceResolutionStatus.CORROBORATED
        tag_id = first.record.tag_observation_id
        key = (snapshot, tag_id)
        original = source._text_integrity_receipts[key]
        source._text_integrity_receipts[key] = dataclasses.replace(original)  # equal, but a different object
        reads.clear()
        binder.publish_scope(opening_selector=selector, decision_scope_id=SCOPE + ":same")
        assert reads == [len(published.text_observation_ids)]
        source._text_integrity_receipts[key] = dataclasses.replace(original, trusted=False)
        blocked = binder.publish_scope(opening_selector=selector, decision_scope_id=SCOPE + ":untrusted")
    direct = _binder(source).publish_scope(opening_selector=selector, decision_scope_id=SCOPE + ":direct")
    assert blocked.reason_codes == direct.reason_codes == (BINDING_NO_CONTAINED_TAG,)
    source._text_integrity_receipts[key] = original


def test_leaving_the_block_even_by_an_error_forgets_the_text(reads):
    source, published, selector = _case(_tag_pdf(), "error")
    words = len(published.text_observation_ids)
    binder = _binder(source)
    with pytest.raises(RuntimeError, match="boom"):
        with binder.reusing_page_text():
            binder.publish_scope(opening_selector=selector, decision_scope_id=SCOPE)
            raise RuntimeError("boom")
    reads.clear()
    binder.publish_scope(opening_selector=selector, decision_scope_id=SCOPE + ":next")
    assert reads == [words]


def test_a_nested_block_shares_the_outer_one(reads):
    source, published, selector = _case(_tag_pdf(), "nested")
    binder = _binder(source)
    with binder.reusing_page_text():
        binder.publish_scope(opening_selector=selector, decision_scope_id=SCOPE)
        with binder.reusing_page_text():
            binder.publish_scope(opening_selector=selector, decision_scope_id=SCOPE + ":inner")
        binder.publish_scope(opening_selector=selector, decision_scope_id=SCOPE + ":outer")
    assert reads == [len(published.text_observation_ids)]


def test_two_snapshots_never_share_text(reads):
    first_source, first_published, first = _case(_tag_pdf(), "one")
    second_source, second_published, second = _case(_tag_pdf(tag_text="W2", schedule_rows=(
        ("MARK", "WIDTH", "HEIGHT"), ("W2", "1500", "2100"))), "two")
    a, b = _binder(first_source), _binder(second_source)
    with a.reusing_page_text(), b.reusing_page_text():
        left = a.publish_scope(opening_selector=first, decision_scope_id=SCOPE)
        right = b.publish_scope(opening_selector=second, decision_scope_id=SCOPE)
    assert (left.record.tag_mark, right.record.tag_mark) == ("W1", "W2")
    assert reads == [len(first_published.text_observation_ids), len(second_published.text_observation_ids)]


def test_the_receipt_accessor_returns_the_stored_objects_and_none_for_unknown_ids():
    source, published, _selector = _case(_tag_pdf(), "accessor")
    snapshot = published.snapshot.snapshot_id
    ids = published.text_observation_ids[:3]
    got = source.text_integrity_authority().receipt_objects(snapshot, [*ids, "unknown"])
    assert all(r is source._text_integrity_receipts[(snapshot, i)] for r, i in zip(got, ids)) and got[-1] is None


def test_a_republished_snapshot_object_is_read_again(reads):
    source, published, selector = _case(_tag_pdf(), "republished")
    binder = _binder(source)
    with binder.reusing_page_text():
        binder.publish_scope(opening_selector=selector, decision_scope_id=SCOPE)
        source._published_by_revision[published.revision.revision_id] = dataclasses.replace(published)
        binder.publish_scope(opening_selector=selector, decision_scope_id=SCOPE + ":again")
    assert len(reads) == 2
