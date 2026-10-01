from dataclasses import replace

import fitz

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_opening_authority import (
    OPENING_JAMB_BOUNDARY_KIND,
    WALL_FACE_INTERRUPTION_KIND,
    PhysicalOpeningAuthority,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.g17_phase2_test_support import make_base, publish, selector


def _publish_structure(*, left_x: float = 100.0, jamb_viewport: str = "vp-1", jamb_page: str = "1"):
    producer, published, _, physical, roots = make_base()
    specs = (
        ("face-a", WALL_FACE_INTERRUPTION_KIND, (100.0, 100.0, 140.0, 100.0), roots[0], "vp-1", "1"),
        ("face-b", WALL_FACE_INTERRUPTION_KIND, (100.0, 110.0, 140.0, 110.0), roots[1], "vp-1", "1"),
        ("jamb-left", OPENING_JAMB_BOUNDARY_KIND, (left_x, 100.0, left_x, 110.0), roots[2], jamb_viewport, jamb_page),
        ("jamb-right", OPENING_JAMB_BOUNDARY_KIND, (140.0, 100.0, 140.0, 110.0), roots[3], "vp-1", "1"),
    )
    snapshot_id = published.snapshot.snapshot_id
    for observation_id, kind, geometry, root_id, viewport_id, page_id in specs:
        snapshot_id = publish(
            producer,
            published,
            snapshot_id=snapshot_id,
            root_id=root_id,
            observation_id=observation_id,
            kind=kind,
            geometry=geometry,
            viewport_id=viewport_id,
            page_id=page_id,
        ).snapshot_id
    return published, physical, snapshot_id


def _assert_not_resolved(published, physical, snapshot_id: str) -> None:
    result = physical.prove_existence(selector(published, snapshot_id, "face-a"))
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.proposition is None
    assert result.existence_record is None


def test_nearby_jamb_does_not_self_assemble_by_proximity() -> None:
    _assert_not_resolved(*_publish_structure(left_x=100.01))


def test_cross_viewport_structural_evidence_does_not_combine() -> None:
    _assert_not_resolved(*_publish_structure(jamb_viewport="vp-other"))


def test_cross_page_structural_evidence_does_not_combine() -> None:
    _assert_not_resolved(*_publish_structure(jamb_page="2"))


def _visible_opening_fixture():
    doc = fitz.open()
    page = doc.new_page(width=300, height=220)
    for start, end in (
        ((20.0, 100.0), (100.0, 100.0)),
        ((140.0, 100.0), (220.0, 100.0)),
        ((20.0, 110.0), (100.0, 110.0)),
        ((140.0, 110.0), (220.0, 110.0)),
        ((100.0, 100.0), (100.0, 110.0)),
        ((140.0, 100.0), (140.0, 110.0)),
    ):
        page.draw_line(fitz.Point(*start), fitz.Point(*end), color=(0, 0, 0), width=1)
    payload = doc.tobytes()
    doc.close()

    producer = SourceVisibilityProducer(
        producer_method="g17-viewport-projection-test",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="visible-opening-with-scoped-candidate",
        source_bytes=payload,
        source_locator="memory://visible-opening-with-scoped-candidate.pdf",
    )
    return published, PhysicalOpeningAuthority(producer.authority())


def test_resolved_physical_opening_preserves_authenticated_viewport_id(monkeypatch) -> None:
    published, physical = _visible_opening_fixture()
    selected = selector(
        published,
        published.snapshot.snapshot_id,
        published.visible_observation_ids[0],
    )
    structures = physical.visible_candidate_structures(selected)
    assert structures.status is EvidenceResolutionStatus.CANDIDATE
    assert len(structures.candidates) == 1

    # The live visible-geometry producer is currently page-scoped.  Emulate only
    # the narrow output of a future authenticated viewport-scoped semantic
    # producer while retaining the real source-visible opening proof above.
    candidate = structures.candidates[0]
    viewport_id = "vp-1"
    candidate_payload = {
        "document_id": candidate.document_id,
        "revision_id": candidate.revision_id,
        "source_sha256": candidate.source_sha256,
        "snapshot_id": candidate.snapshot_id,
        "page_id": candidate.page_id,
        "viewport_id": viewport_id,
        "structural_pattern": candidate.structural_pattern,
        "source_observation_ids": candidate.source_observation_ids,
        "source_lineage_root_ids": candidate.source_lineage_root_ids,
    }
    scoped_candidate = replace(
        candidate,
        candidate_id=stable_contract_id(
            "physical_opening_candidate", candidate_payload, digest_chars=32
        ),
        viewport_id=viewport_id,
    )
    monkeypatch.setattr(
        physical,
        "_visible_candidates_for",
        lambda observation, records: (scoped_candidate,),
    )

    result = physical.prove_existence(selected)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.existence_record is not None
    assert result.existence_record.viewport_id == viewport_id
