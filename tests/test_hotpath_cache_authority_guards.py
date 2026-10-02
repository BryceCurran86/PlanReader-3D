"""Cached geometry must still pass current source authority on every use."""
from __future__ import annotations

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_physical_scale_authority import PhysicalScaleProducer, PhysicalScaleSelector
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.test_physical_opening_page_candidate_cache_v2 import _pdf
from tests.test_physical_scale_authority import _near_agreeing_bar_pdf


def _source(payload: bytes):
    source = SourceVisibilityProducer(
        producer_method="hotpath-authority-guard-regression", producer_version="1"
    )
    published = source.ingest_native_pdf_bytes(
        document_id="cache-source", source_bytes=payload,
        source_locator="memory://cache-source.pdf",
    )
    return source, published


def _supersede(source, payload: bytes):
    with fitz.open(stream=payload, filetype="pdf") as doc:
        doc[0].insert_text(fitz.Point(20, 20), "SOURCE REVISION TWO")
        replacement = doc.tobytes()
    return source.ingest_native_pdf_bytes(
        document_id="cache-source", source_bytes=replacement,
        source_locator="memory://cache-source-revision-two.pdf",
    )


@pytest.mark.parametrize("method", (
    "prove_existence", "classify_disposition", "visible_candidate_structures",
    "assess_visible_candidate_closure",
))
@pytest.mark.parametrize("change", ("new_revision", "source_replacement"))
def test_cached_opening_outcome_cannot_outlive_source_authority(method, change):
    payload = _pdf()
    source, published = _source(payload)
    physical = PhysicalOpeningAuthority(source.authority())
    selected = ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=published.visible_observation_ids[0],
    )
    first = getattr(physical, method)(selected)
    assert first.status in {
        EvidenceResolutionStatus.CORROBORATED, EvidenceResolutionStatus.CANDIDATE,
    }
    if change == "new_revision":
        newer = _supersede(source, payload)
        assert newer.revision.revision_id != published.revision.revision_id
        expected = EvidenceResolutionStatus.ABSTAINED
    else:
        source._producer._store.source_bytes_by_revision[
            published.revision.revision_id
        ] = payload + b"changed source bytes"
        expected = EvidenceResolutionStatus.CONFLICT
    assert getattr(physical, method)(selected).status is expected


@pytest.mark.parametrize("change", ("new_revision", "source_replacement"))
def test_cached_physical_scale_cannot_outlive_source_authority(change):
    payload, _ = _near_agreeing_bar_pdf()
    source, published = _source(payload)
    producer = PhysicalScaleProducer.from_source_visibility_producer(source)
    selected = PhysicalScaleSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id, page_id="1",
    )
    assert producer.publish_scope(selected).status is EvidenceResolutionStatus.CORROBORATED
    if change == "new_revision":
        _supersede(source, payload)
        result = producer.publish_scope(selected)
        assert result.status is EvidenceResolutionStatus.ABSTAINED
        assert result.evidence is None
    else:
        source._producer._store.source_bytes_by_revision[
            published.revision.revision_id
        ] = payload + b"changed source bytes"
        with pytest.raises(RuntimeError, match="physical_scale_source_integrity_failure"):
            producer.publish_scope(selected)
