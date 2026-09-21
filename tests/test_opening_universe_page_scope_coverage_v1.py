from __future__ import annotations

from dataclasses import dataclass

from pb_opening_universe_completeness_authority import OpeningUniverseCompletenessProducer
from pb_source_observation_authority import SourceDecodeCoverageRecord


@dataclass(frozen=True)
class _Primitive:
    primitive_id: str
    page_id: str
    geometry: tuple[float, float, float, float]
    layer: str = ""
    clip_known: bool = True
    clip_present: bool = False
    clip: None = None


def _publish(*, coverage: SourceDecodeCoverageRecord, page_ids: tuple[str, ...]):
    primitive = _Primitive(
        primitive_id="opening:1",
        page_id=page_ids[0],
        geometry=(10.0, 10.0, 20.0, 10.0),
    )
    producer = OpeningUniverseCompletenessProducer(
        producer_method="test",
        producer_version="1",
    )
    return producer.publish_enumeration(
        decision_scope_id="scope:pages",
        decision_scope_kind="pages",
        document_id="doc",
        revision_id="rev",
        source_sha256="sha",
        snapshot_id="snap",
        page_ids=page_ids,
        viewport_id=None,
        coverage=coverage,
        source_primitives=(primitive,),
        enumerated_primitives=(primitive,),
        optional_content_state="known_visible",
        xobject_traversal_truncated=False,
        semantic_enumeration_proven=True,
    )


def test_page_scope_uses_requested_decode_coverage_not_whole_document_size() -> None:
    record = _publish(
        coverage=SourceDecodeCoverageRecord(
            document_id="doc",
            revision_id="rev",
            total_pages=5,
            decoded_pages=(1, 2, 4, 5),
            failed_pages=(3,),
            state="partial",
        ),
        page_ids=("2", "4"),
    )
    assert record.source_decode_complete is True
    assert record.semantic_enumeration_complete is True
    assert record.decision_scope_complete is True


def test_page_scope_fails_closed_when_requested_page_failed_decode() -> None:
    record = _publish(
        coverage=SourceDecodeCoverageRecord(
            document_id="doc",
            revision_id="rev",
            total_pages=5,
            decoded_pages=(1, 2, 4, 5),
            failed_pages=(3,),
            state="partial",
        ),
        page_ids=("2", "3"),
    )
    assert record.source_decode_complete is False
    assert record.decision_scope_complete is False
