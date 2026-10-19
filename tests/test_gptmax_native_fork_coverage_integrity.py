"""Source forks preserve complete/partial decode identity without mutation."""
from dataclasses import replace

import pytest

from pb_source_visibility_authority import SourceVisibilityProducer
from test_opening_label_dimension_authority import _pdf
from test_gptmax_source_geometry_recovery_batch import source
import tools.recover_source_preserving_openings_shadow as recovery


def test_full_document_source_fork_preserves_the_original_full_decode_identity():
    producer = SourceVisibilityProducer(producer_method="full-fork",producer_version="1")
    published = producer.ingest_native_pdf_bytes(document_id="full-source",source_bytes=_pdf(labels=()),
        source_locator="memory://full-source.pdf")
    before = producer.published_snapshot_for_revision(published.revision.revision_id)
    original = producer._producer._store.coverage_by_revision[published.revision.revision_id]
    assert original.state == "complete"
    fork, replay = producer.fork_native_source_shadow(published.revision.revision_id)
    assert replay.revision == published.revision
    assert fork._producer._store.coverage_by_revision[replay.revision.revision_id] == original
    assert producer.published_snapshot_for_revision(published.revision.revision_id) is before


@pytest.mark.parametrize("changes", [dict(document_id="foreign"),dict(revision_id="foreign"),
    dict(total_pages=True),dict(total_pages=0),dict(decoded_pages=(0,)),dict(decoded_pages=(1,1)),
    dict(decoded_pages=(2,)),dict(state="unproved"),dict(total_pages=2)])
def test_native_replay_rechecks_decode_coverage_against_exact_bytes(changes):
    producer, published = source()
    store = producer._producer._store
    revision = published.revision.revision_id
    coverage = store.coverage_by_revision[revision]
    store.coverage_by_revision[revision] = replace(coverage,**changes)
    before = producer.published_snapshot_for_revision(revision)
    with pytest.raises(ValueError): producer.fork_native_source_shadow(revision)
    assert producer.published_snapshot_for_revision(revision) is before


@pytest.mark.parametrize("policy", ["exact_nomination_shadow","source_fragment_roles_shadow",
                                    "include_revision_ancestry_shadow"])
def test_batch_policy_rejection_happens_before_any_composition(policy, monkeypatch):
    producer, published = source()
    before = producer.published_snapshot_for_revision(published.revision.revision_id)
    def forbidden(**kwargs): raise AssertionError("invalid request reached source composition")
    monkeypatch.setattr(recovery,"compose_live_wall_opening_authority",forbidden)
    with pytest.raises(ValueError,match="explicit booleans"):
        recovery.recover_source_preserving_openings_pages_shadow(producer,
            revision_id=published.revision.revision_id,page_ids=("1",),**{policy:1})
    assert producer.published_snapshot_for_revision(published.revision.revision_id) is before


def test_undecoded_page_is_rejected_before_original_issuer_augmentation(monkeypatch):
    producer, published = source()
    def forbidden(**kwargs): raise AssertionError("undecoded page reached source composition")
    monkeypatch.setattr(recovery,"compose_live_wall_opening_authority",forbidden)
    with pytest.raises(ValueError,match="not decoded"):
        recovery.recover_source_preserving_openings_pages_shadow(producer,
            revision_id=published.revision.revision_id,page_ids=("2",))
