from __future__ import annotations

from tests.test_raster_framed_opening_g17_contract import _prepare, _selector


def test_diagnose_framed_raster_g17_stage_counts() -> None:
    # Deliberate failure: expose stage counts in PR CI, then delete this file.
    producer, published = _prepare(frame_lines=2)
    authority = producer.physical_opening_authority()
    visibility = producer.authority()

    primitive_ids = published.raster_opening_primitive_observation_ids
    assert primitive_ids

    seed_result = visibility.resolve_raster_opening_primitive(
        _selector(published, primitive_ids[0])
    )
    assert seed_result.observation is not None

    records, failures = authority._raster_primitive_snapshot_records(seed_result)
    seed = seed_result.observation
    raw = authority._raster_framed_candidates_for(seed, records)
    scoped = authority._viewport_scoped_raster_candidates_for(seed, records, raw)

    raise AssertionError(
        {
            "primitive_count": len(primitive_ids),
            "record_count": len(records),
            "failure_count": len(failures),
            "kinds": {
                kind: sum(1 for record in records if record.observation_kind == kind)
                for kind in sorted({record.observation_kind for record in records})
            },
            "raw_candidate_count": len(raw),
            "raw_candidates": [
                {
                    "candidate_id": candidate.candidate_id,
                    "support_count": len(candidate.source_observation_ids),
                    "viewport_id": candidate.viewport_id,
                }
                for candidate in raw
            ],
            "scoped_candidate_count": len(scoped),
            "scoped_candidates": [
                {
                    "candidate_id": candidate.candidate_id,
                    "support_count": len(candidate.source_observation_ids),
                    "viewport_id": candidate.viewport_id,
                }
                for candidate in scoped
            ],
        }
    )
