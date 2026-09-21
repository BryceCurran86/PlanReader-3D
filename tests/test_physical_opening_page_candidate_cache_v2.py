from __future__ import annotations

import fitz

from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=400, height=250)
    for first, second in (
        ((25.0, 60.0), (110.0, 60.0)),
        ((150.0, 60.0), (275.0, 60.0)),
        ((25.0, 75.0), (110.0, 75.0)),
        ((150.0, 75.0), (275.0, 75.0)),
        ((110.0, 60.0), (110.0, 75.0)),
        ((150.0, 60.0), (150.0, 75.0)),
    ):
        page.draw_line(
            fitz.Point(*first),
            fitz.Point(*second),
            color=(0, 0, 0),
            width=1,
        )
    payload = doc.tobytes()
    doc.close()
    return payload


def test_visible_candidate_discovery_is_memoized_per_source_page(monkeypatch) -> None:
    source = SourceVisibilityProducer(
        producer_method="candidate-cache-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="candidate-cache",
        source_bytes=_pdf(),
        source_locator="memory://candidate-cache.pdf",
    )
    physical = PhysicalOpeningAuthority(source.authority())

    original = PhysicalOpeningAuthority._visible_all_structural_candidates
    calls = {"count": 0}

    def counted(seed, records):
        calls["count"] += 1
        return original(seed, records)

    monkeypatch.setattr(
        PhysicalOpeningAuthority,
        "_visible_all_structural_candidates",
        staticmethod(counted),
    )

    for observation_id in published.visible_observation_ids:
        physical.prove_existence(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )

    assert len(published.visible_observation_ids) == 6
    assert calls["count"] == 1
