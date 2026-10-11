"""Historic verification-cache hints may expire, but source records never do."""
from dataclasses import replace

import fitz

import pb_source_observation_authority as module
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import (
    PRODUCER_INTEGRITY_FAILURE,
    ObservationSelector,
    SourceObservationProducer,
)


def test_old_snapshot_after_hint_eviction_reauthenticates_and_detects_tamper(monkeypatch):
    monkeypatch.setattr(module, "_HISTORIC_VERIFIED_CACHE_TARGET", 1)
    pdf = fitz.open()
    pdf.new_page().insert_text((30, 30), "SOURCE ORIGINAL")
    payload = pdf.tobytes()
    pdf.close()
    producer = SourceObservationProducer(
        producer_method="historical-source-proof", producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="original-doc", source_bytes=payload,
        source_locator="memory://original.pdf", page_ids=("1",),
    )
    initial = published.snapshot
    parent = initial.observation_ids[0]
    def derive(base, name, parent_id):
        return producer.publish_derived_observation(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            base_snapshot_id=base.snapshot_id, page_id="1",
            source_partition_id="page:1", observation_kind="cv_candidate",
            source_primitive_ref=name, origin_kind="cv",
            parent_observation_ids=(parent_id,),
        )
    first = derive(initial, "candidate:first", parent)
    first_derived_ids = set(first.observation_ids) - set(initial.observation_ids)
    assert len(first_derived_ids) == 1
    derived_id = first_derived_ids.pop()
    second = derive(first, "candidate:second", derived_id)
    third = derive(second, "candidate:third", derived_id)
    key = (first.snapshot_id, derived_id)
    assert key in producer._store.observations
    assert key in producer._store.record_fingerprints
    assert key not in producer._store.verified_resolution_cache
    assert (third.snapshot_id, derived_id) in producer._store.observations
    selector = ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=first.snapshot_id, observation_id=derived_id,
    )
    valid = producer.authority().resolve(selector)
    assert valid.status is EvidenceResolutionStatus.CORROBORATED
    assert key in producer._store.verified_resolution_cache
    assert valid.observation is not None
    producer._store.observations[key] = replace(valid.observation, raw_text="tampered")
    blocked = producer.authority().resolve(selector)
    assert blocked.status is EvidenceResolutionStatus.CONFLICT
    assert PRODUCER_INTEGRITY_FAILURE in blocked.reason_codes
    latest = replace(selector, snapshot_id=third.snapshot_id)
    assert producer.authority().resolve(latest).status is EvidenceResolutionStatus.CORROBORATED
