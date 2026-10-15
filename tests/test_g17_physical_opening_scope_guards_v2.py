from dataclasses import replace

import fitz

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_opening_authority import (
    OPENING_JAMB_BOUNDARY_KIND,
    PHYSICAL_OPENING_VIEWPORT_SCOPE_MISMATCH,
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


def _visible_opening_payload() -> bytes:
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
    return payload


def _visible_opening_fixture(payload: bytes | None = None):
    producer = SourceVisibilityProducer(
        producer_method="g17-viewport-projection-test",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="visible-opening-with-scoped-candidate",
        source_bytes=payload if payload is not None else _visible_opening_payload(),
        source_locator="memory://visible-opening-with-scoped-candidate.pdf",
    )
    physical = PhysicalOpeningAuthority(producer.authority())
    selected = selector(
        published,
        published.snapshot.snapshot_id,
        published.visible_observation_ids[0],
    )
    return physical, selected


def _live_candidate(physical, selected):
    structures = physical.visible_candidate_structures(selected)
    assert structures.status is EvidenceResolutionStatus.CANDIDATE
    assert len(structures.candidates) == 1
    return structures.candidates[0]


def _scoped(candidate, viewport_id):
    payload = {
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
    return replace(
        candidate,
        candidate_id=stable_contract_id(
            "physical_opening_candidate", payload, digest_chars=32
        ),
        viewport_id=viewport_id,
    )


def _record_id_from_own_fields(record) -> str:
    return stable_contract_id(
        "physical_opening_existence",
        {
            "document_id": record.document_id,
            "revision_id": record.revision_id,
            "source_sha256": record.source_sha256,
            "snapshot_id": record.snapshot_id,
            "page_id": record.page_id,
            "viewport_id": record.viewport_id,
            "semantic_class": record.semantic_class,
            "structural_pattern": record.structural_pattern,
            "source_observation_ids": record.source_observation_ids,
            "source_lineage_root_ids": record.source_lineage_root_ids,
        },
        digest_chars=32,
    )


def _emulate_source_authenticated_viewport(monkeypatch, physical, viewport_id):
    """Emulate a future source-native producer whose observation carries a viewport."""
    visibility = physical._source_visibility_authority
    resolve_visible = visibility.resolve_visible

    def scoped_resolve_visible(selector_):
        result = resolve_visible(selector_)
        assert result.observation is not None
        return replace(
            result, observation=replace(result.observation, viewport_id=viewport_id)
        )

    monkeypatch.setattr(visibility, "resolve_visible", scoped_resolve_visible)


def test_live_visible_physical_opening_is_page_scoped_with_recomputable_id() -> None:
    physical, selected = _visible_opening_fixture()
    assert _live_candidate(physical, selected).viewport_id is None

    result = physical.prove_existence(selected)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    record = result.existence_record
    assert record is not None
    assert record.viewport_id is None
    assert record.record_id == _record_id_from_own_fields(record)


def test_live_visible_physical_opening_record_id_is_replay_stable() -> None:
    payload = _visible_opening_payload()
    ids = []
    for _ in range(2):
        physical, selected = _visible_opening_fixture(payload)
        first = physical.prove_existence(selected).existence_record
        second = physical.prove_existence(selected).existence_record
        assert first is not None and second is not None
        assert first == second
        ids.append(first.record_id)
    assert ids[0] == ids[1]


def test_candidate_viewport_not_carried_by_source_observation_is_not_adopted(
    monkeypatch,
) -> None:
    # The live visible-geometry producer is page-scoped. A candidate asserting a
    # viewport the authenticated source observation does not carry is
    # contradictory evidence: it must neither be adopted into the record (void
    # and count authorities select scale/view class from record.viewport_id) nor
    # be silently discarded into a CORROBORATED page-scoped record.
    physical, selected = _visible_opening_fixture()
    scoped_candidate = _scoped(_live_candidate(physical, selected), "vp-1")
    monkeypatch.setattr(
        physical, "_visible_candidates_for", lambda observation, records: (scoped_candidate,)
    )

    result = physical.prove_existence(selected)

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.proposition is None
    assert result.existence_record is None
    assert result.candidate is None
    assert result.reason_codes == (PHYSICAL_OPENING_VIEWPORT_SCOPE_MISMATCH,)


def test_source_authenticated_viewport_is_preserved_when_candidate_agrees(
    monkeypatch,
) -> None:
    physical, selected = _visible_opening_fixture()
    page_scoped = physical.prove_existence(selected).existence_record
    assert page_scoped is not None
    scoped_candidate = _scoped(_live_candidate(physical, selected), "vp-1")
    monkeypatch.setattr(
        physical, "_visible_candidates_for", lambda observation, records: (scoped_candidate,)
    )
    _emulate_source_authenticated_viewport(monkeypatch, physical, "vp-1")

    result = physical.prove_existence(selected)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    record = result.existence_record
    assert record is not None
    assert record.viewport_id == "vp-1"
    assert record.record_id == _record_id_from_own_fields(record)
    assert record.record_id != page_scoped.record_id


def test_page_scoped_candidate_does_not_discard_source_authenticated_viewport(
    monkeypatch,
) -> None:
    physical, selected = _visible_opening_fixture()
    page_scoped_candidate = _live_candidate(physical, selected)
    assert page_scoped_candidate.viewport_id is None
    monkeypatch.setattr(
        physical,
        "_visible_candidates_for",
        lambda observation, records: (page_scoped_candidate,),
    )
    _emulate_source_authenticated_viewport(monkeypatch, physical, "vp-1")

    result = physical.prove_existence(selected)

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.existence_record is None
    assert result.reason_codes == (PHYSICAL_OPENING_VIEWPORT_SCOPE_MISMATCH,)
