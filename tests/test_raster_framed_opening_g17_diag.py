from __future__ import annotations

from pb_source_observation_authority import ObservationSelector
from tests.test_raster_framed_opening_g17_contract import _prepare


def test_dump_positive_raster_g17_geometry() -> None:
    producer, published = _prepare(frame_lines=2)
    authority = producer.physical_opening_authority()
    visibility = producer.authority()

    rows = []
    for observation_id in published.raster_opening_primitive_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        resolved = visibility.resolve_raster_opening_primitive(selector)
        if resolved.observation is not None:
            rows.append((
                resolved.observation.observation_kind,
                tuple(resolved.observation.geometry),
                resolved.observation.observation_id,
            ))

    assert rows
    seed_selector = ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=published.raster_opening_primitive_observation_ids[0],
    )
    seed_result = visibility.resolve_raster_opening_primitive(seed_selector)
    assert seed_result.observation is not None
    records, failures = authority._raster_primitive_snapshot_records(seed_result)
    candidates = authority._raster_framed_candidates_for(
        seed_result.observation,
        records,
    )
    scoped = authority._viewport_scoped_raster_candidates_for(
        seed_result.observation,
        records,
        candidates,
    )
    raise AssertionError({
        "primitive_count": len(rows),
        "primitives": rows,
        "failure_count": len(failures),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "scoped_count": len(scoped),
        "scoped": scoped,
    })
