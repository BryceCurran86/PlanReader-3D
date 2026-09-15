from __future__ import annotations

import fitz

from pb_physical_opening_authority import (
    OPENING_JAMB_BOUNDARY_KIND,
    WALL_FACE_INTERRUPTION_KIND,
    PhysicalOpeningAuthority,
)
from pb_source_observation_authority import ObservationSelector, SourceObservationProducer


def make_base(line_count: int = 12):
    doc = fitz.open()
    page = doc.new_page(width=320, height=240)
    for index in range(line_count):
        y = 20.0 + index * 6.0
        page.draw_line(fitz.Point(180.0, y), fitz.Point(205.0, y))
    payload = doc.tobytes()
    doc.close()

    producer = SourceObservationProducer(
        producer_method="g17-phase2-test",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="doc-g17-phase2",
        source_bytes=payload,
        source_locator="memory://g17-phase2.pdf",
    )
    source = producer.authority()
    physical = PhysicalOpeningAuthority(source)
    roots = []
    for observation_id in published.snapshot.observation_ids:
        result = source.resolve(selector(published, published.snapshot.snapshot_id, observation_id))
        if result.observation and result.observation.observation_kind == "native_pdf_segment":
            roots.append(observation_id)
    assert len(roots) >= line_count
    return producer, published, source, physical, roots


def selector(published, snapshot_id: str, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=snapshot_id,
        observation_id=observation_id,
    )


def publish(
    producer,
    published,
    *,
    snapshot_id: str,
    root_id: str,
    observation_id: str,
    kind: str,
    geometry: tuple[float, float, float, float],
    viewport_id: str | None = "vp-1",
    page_id: str = "1",
):
    return producer.publish_derived_observation(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        base_snapshot_id=snapshot_id,
        page_id=page_id,
        source_partition_id="page:1",
        observation_kind=kind,
        source_primitive_ref=f"structural:{observation_id}",
        origin_kind="derived",
        parent_observation_ids=(root_id,),
        geometry=geometry,
        viewport_id=viewport_id,
        observation_id=observation_id,
    )


def make_resolved(*, shared_face_root: bool = False, duplicate_face: bool = False):
    producer, published, source, physical, roots = make_base()
    specs = [
        ("face-a", WALL_FACE_INTERRUPTION_KIND, (100.0, 100.0, 140.0, 100.0), roots[0]),
        ("face-b", WALL_FACE_INTERRUPTION_KIND, (100.0, 110.0, 140.0, 110.0), roots[0] if shared_face_root else roots[1]),
        ("jamb-left", OPENING_JAMB_BOUNDARY_KIND, (100.0, 100.0, 100.0, 110.0), roots[2]),
        ("jamb-right", OPENING_JAMB_BOUNDARY_KIND, (140.0, 100.0, 140.0, 110.0), roots[3]),
    ]
    snapshot_id = published.snapshot.snapshot_id
    for observation_id, kind, geometry, root_id in specs:
        snapshot_id = publish(
            producer,
            published,
            snapshot_id=snapshot_id,
            root_id=root_id,
            observation_id=observation_id,
            kind=kind,
            geometry=geometry,
        ).snapshot_id
    if duplicate_face:
        snapshot_id = publish(
            producer,
            published,
            snapshot_id=snapshot_id,
            root_id=roots[0],
            observation_id="face-a-duplicate",
            kind=WALL_FACE_INTERRUPTION_KIND,
            geometry=(100.0, 100.0, 140.0, 100.0),
        ).snapshot_id
    return producer, published, source, physical, roots, snapshot_id
