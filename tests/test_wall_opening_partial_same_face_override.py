"""Opening-proven SAME wall faces survive non-wall jamb filtering."""
from __future__ import annotations

from types import SimpleNamespace

import fitz

import pb_physical_wall_candidate_authority as module
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer


def _source():
    doc = fitz.open()
    try:
        page = doc.new_page(width=500, height=500)
        y = 70.0
        for first, second in (
            ((50, y), (180, y)),
            ((50, y + 18), (180, y + 18)),
            ((180, y), (180, y + 18)),
            ((220, y), (360, y)),
            ((220, y + 18), (360, y + 18)),
            ((220, y), (220, y + 18)),
        ):
            page.draw_line(first, second, width=1)
        payload = doc.tobytes(garbage=4, deflate=True)
    finally:
        doc.close()

    source = SourceVisibilityProducer(
        producer_method="partial-opening-wall-equivalence-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="partial-opening-wall-equivalence-test",
        source_bytes=payload,
        source_locator="memory://partial-opening-wall-equivalence-test.pdf",
    )
    return source, published


def _unique_native_rows(source, published):
    rows = list(
        module._visible_observations_by_page(
            source_producer=source,
            published=published,
        )["1"]
    )
    native = []
    seen_geometry = set()
    for observation_id, observation in rows:
        if not str(observation.source_primitive_ref).startswith("visible:segment:"):
            continue
        geometry = tuple(float(value) for value in observation.geometry)
        forward = (geometry[0], geometry[1], geometry[2], geometry[3])
        reverse = (geometry[2], geometry[3], geometry[0], geometry[1])
        key = min(forward, reverse)
        if key in seen_geometry:
            continue
        seen_geometry.add(key)
        native.append((observation_id, observation))
    assert len(native) == 6
    return rows, native


def _same_raw_pairs(native):
    raw_lines = {
        str(observation.source_primitive_ref)[len("visible:segment:") :]:
            module._line(observation.geometry)
        for _observation_id, observation in native
    }
    same_pairs = {
        pair
        for pair, classifications in module._opening_raw_relation_sets(
            raw_lines
        ).items()
        if classifications == {
            module.PhysicalEquivalenceClass.SAME_PHYSICAL_WALL
        }
    }
    assert len(same_pairs) == 2
    return same_pairs


def _opening_authority(source, published, native):
    from pb_source_observation_authority import ObservationSelector
    authority = source.physical_opening_authority()
    records = []
    for observation_id, _ in native:
        result = authority.prove_existence(ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id, observation_id=observation_id,
        ))
        assert result.status is EvidenceResolutionStatus.CORROBORATED
        assert result.existence_record is not None
        records.append(result.existence_record)
    assert len({record.record_id for record in records}) == 1
    assert set(records[0].source_observation_ids) == {i for i, _ in native}
    return authority


def _record(wall_id: str, raw_id: str):
    return SimpleNamespace(
        wall_candidate_id=wall_id,
        physical_identity=SimpleNamespace(
            source_primitive_ids=(raw_id,),
        ),
    )


def test_same_face_pairs_survive_when_jambs_are_not_wall_candidates():
    source, published = _source()
    rows, native = _unique_native_rows(source, published)
    same_pairs = _same_raw_pairs(native)
    face_raw_ids = sorted({raw for pair in same_pairs for raw in pair})

    records = tuple(
        _record(f"wall-{raw_id}", raw_id)
        for raw_id in face_raw_ids
    ) + (
        _record("unrelated-wall-0", "unrelated-raw-0"),
        _record("unrelated-wall-1", "unrelated-raw-1"),
    )

    result = module._producer_opening_relation_overrides(
        source_producer=source,
        published=published,
        page_id="1",
        records=records,
        resolved_visible_observations=rows,
        physical_opening_authority=_opening_authority(source, published, native),
    )

    expected = {
        tuple(sorted((f"wall-{left}", f"wall-{right}"))):
            module.PhysicalEquivalenceClass.SAME_PHYSICAL_WALL
        for left, right in same_pairs
    }
    assert result == expected
    assert all(
        value is module.PhysicalEquivalenceClass.SAME_PHYSICAL_WALL
        for value in result.values()
    )


def test_competing_face_owner_blocks_only_that_partial_same_relation():
    source, published = _source()
    rows, native = _unique_native_rows(source, published)
    same_pairs = sorted(_same_raw_pairs(native))
    face_raw_ids = sorted({raw for pair in same_pairs for raw in pair})
    competing_raw = same_pairs[0][0]

    records = [
        _record(f"wall-{raw_id}", raw_id)
        for raw_id in face_raw_ids
    ]
    records.extend(
        (
            _record("competing-owner", competing_raw),
            _record("unrelated-wall-0", "unrelated-raw-0"),
            _record("unrelated-wall-1", "unrelated-raw-1"),
        )
    )

    result = module._producer_opening_relation_overrides(
        source_producer=source,
        published=published,
        page_id="1",
        records=tuple(records),
        resolved_visible_observations=rows,
        physical_opening_authority=_opening_authority(source, published, native),
    )

    blocked = tuple(
        sorted(
            (
                f"wall-{same_pairs[0][0]}",
                f"wall-{same_pairs[0][1]}",
            )
        )
    )
    safe = tuple(
        sorted(
            (
                f"wall-{same_pairs[1][0]}",
                f"wall-{same_pairs[1][1]}",
            )
        )
    )
    assert blocked not in result
    assert result == {
        safe: module.PhysicalEquivalenceClass.SAME_PHYSICAL_WALL
    }
