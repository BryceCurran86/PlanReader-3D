from __future__ import annotations

import fitz

from pb_physical_opening_authority import (
    NATIVE_PDF_VISIBLE_SEGMENT,
    RASTER_PDF_VISIBLE_SEGMENT,
    PhysicalOpeningAuthority,
    _canonical_line,
    _distinct_parallel_axes,
    _face_break,
    _line_geometry,
    _same_gap,
    _segment_matches,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=800, height=500)
    # One exact jamb-bounded two-face interruption.
    for a, b in (
        ((40.0, 100.0), (180.0, 100.0)),
        ((240.0, 100.0), (420.0, 100.0)),
        ((40.0, 120.0), (180.0, 120.0)),
        ((240.0, 120.0), (420.0, 120.0)),
        ((180.0, 100.0), (180.0, 120.0)),
        ((240.0, 100.0), (240.0, 120.0)),
    ):
        page.draw_line(fitz.Point(*a), fitz.Point(*b), width=1)

    # Dense unrelated geometry. These segments must not change candidate truth.
    for row in range(8):
        y = 220.0 + row * 18.0
        for col in range(12):
            x = 30.0 + col * 55.0
            page.draw_line(
                fitz.Point(x, y),
                fitz.Point(x + 30.0, y + 7.0),
                width=1,
            )
    payload = doc.tobytes()
    doc.close()
    return payload


def _reference_support_sets(seed, records):
    scoped = tuple(
        record
        for record in records
        if record.observation_kind in {
            NATIVE_PDF_VISIBLE_SEGMENT,
            RASTER_PDF_VISIBLE_SEGMENT,
        }
        and record.document_id == seed.document_id
        and record.revision_id == seed.revision_id
        and record.source_sha256 == seed.source_sha256
        and record.snapshot_id == seed.snapshot_id
        and record.page_id == seed.page_id
        and record.viewport_id is None
        and _line_geometry(record) is not None
    )
    breaks = []
    for index, first in enumerate(scoped):
        for second in scoped[index + 1 :]:
            found = _face_break(first, second)
            if found is not None:
                breaks.append(found)

    discovered = {}
    for index, first_break in enumerate(breaks):
        for second_break in breaks[index + 1 :]:
            if not _same_gap(first_break, second_break):
                continue
            if not _distinct_parallel_axes(first_break, second_break):
                continue
            left_jambs = tuple(
                record
                for record in scoped
                if _segment_matches(
                    record,
                    first_break.start_point,
                    second_break.start_point,
                )
            )
            right_jambs = tuple(
                record
                for record in scoped
                if _segment_matches(
                    record,
                    first_break.end_point,
                    second_break.end_point,
                )
            )
            for left_jamb in left_jambs:
                for right_jamb in right_jambs:
                    support = (
                        first_break.first,
                        first_break.second,
                        second_break.first,
                        second_break.second,
                        left_jamb,
                        right_jamb,
                    )
                    if len({item.observation_id for item in support}) != 6:
                        continue
                    roots = []
                    for item in support:
                        if len(item.derivation_parent_ids) != 1:
                            break
                        roots.append(item.derivation_parent_ids[0])
                    else:
                        if len(set(roots)) != 6:
                            continue
                        geometry_key = tuple(
                            sorted(_canonical_line(item) for item in support)
                        )
                        discovered[geometry_key] = frozenset(
                            item.observation_id for item in support
                        )
    return set(discovered.values())


def test_indexed_structural_search_is_semantically_identical_to_reference() -> None:
    source = SourceVisibilityProducer(
        producer_method="indexed-structural-equivalence-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="indexed-structural-equivalence",
        source_bytes=_pdf(),
        source_locator="memory://indexed-structural-equivalence.pdf",
    )
    authority = PhysicalOpeningAuthority(source.authority())

    first_id = published.visible_observation_ids[0]
    resolved = source.authority().resolve_visible(
        ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=first_id,
        )
    )
    assert resolved.observation is not None
    records, failures = authority._visible_snapshot_records(resolved)
    assert not failures

    expected = _reference_support_sets(resolved.observation, records)
    actual = {
        frozenset(candidate.source_observation_ids)
        for candidate in authority._visible_structural_candidates(
            resolved.observation, records
        )
    }
    assert actual == expected
    assert len(actual) == 1
