"""Source-backed physical-wall candidate authority prerequisite red-team v1.

TEST-ONLY / EXPECTED-RED / SELF-AUTHORED / INDEPENDENT REVIEW REQUIRED.

This contract fills the exact prerequisite identified by host-binding v3: a
caller must not be able to bless arbitrary WallCandidate objects. Candidate
scope must be derived from the complete producer-owned visibility inventory for
one exact source/page scope, then passed through existing W2/W3/W4 geometry and
reviewed physical-wall identity/equivalence machinery.
"""
from __future__ import annotations

import dataclasses
import importlib
import importlib.util
import inspect

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


BASE_SHA = "90406f5849733469cab57c43150f299fd61380cb"
MODULE = "pb_physical_wall_candidate_authority"
HAS_MODULE = importlib.util.find_spec(MODULE) is not None
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_MODULE,
    strict=True,
    reason="sealed source-backed physical-wall candidate producer is not implemented",
)

_FORBIDDEN_PUBLIC_INPUT_NAMES = {
    "walls",
    "wall",
    "wall_candidates",
    "wall_candidate",
    "segments",
    "segment",
    "edges",
    "edge",
    "edges_by_id",
    "graph",
    "candidate_ids",
    "candidate_id",
    "candidate_count",
    "wall_count",
    "bounding_box",
    "bbox",
    "radius",
    "claimed_complete",
    "complete",
    "source_complete",
    "scope_complete",
    "traversal_complete",
    "traversal_truncated",
    "confidence",
}


def _pdf_bytes(*, second_wall: bool = False) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=300.0, height=220.0)
        shape = page.new_shape()
        # Source-native wall linework. Backend path normalization is allowed to
        # produce more visible primitives than the number of draw_line calls.
        bands = [(60.0, 80.0)]
        if second_wall:
            bands.append((130.0, 150.0))
        for y0, y1 in bands:
            for start, end in (
                ((30.0, y0), (270.0, y0)),
                ((30.0, y1), (270.0, y1)),
                ((30.0, y0), (30.0, y1)),
                ((270.0, y0), (270.0, y1)),
            ):
                shape.draw_line(fitz.Point(*start), fitz.Point(*end))
        shape.finish(width=1.0)
        shape.commit()
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _source(*, second_wall: bool = False, document_id: str = "doc-wall-authority-v1"):
    producer = SourceVisibilityProducer(
        producer_method="physical-wall-authority-validator",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=_pdf_bytes(second_wall=second_wall),
        source_locator=f"memory://{document_id}.pdf",
    )
    return producer, published


def _field_names(obj_type: type) -> set[str]:
    if dataclasses.is_dataclass(obj_type):
        return {field.name for field in dataclasses.fields(obj_type)}
    return {
        name
        for name in inspect.signature(obj_type).parameters
        if name not in {"self", "args", "kwargs"}
    }


def _mod():
    assert HAS_MODULE, "production physical-wall candidate authority module is absent"
    return importlib.import_module(MODULE)


def _wall_producer(mod, source_producer):
    return mod.PhysicalWallCandidateProducer.from_source_visibility_producer(
        source_producer
    )


def _selector(mod, published, **overrides):
    values = {
        "document_id": published.revision.document_id,
        "revision_id": published.revision.revision_id,
        "source_sha256": published.revision.source_sha256,
        "snapshot_id": published.snapshot.snapshot_id,
        "page_id": "1",
        "decision_scope_id": "wall-source:page-1",
    }
    values.update(overrides)
    return mod.PhysicalWallCandidateSelector(**values)


def _assert_no_caller_truth_parameters(callable_obj) -> None:
    names = {
        name.lower()
        for name in inspect.signature(callable_obj).parameters
        if name not in {"self", "cls"}
    }
    assert not (names & _FORBIDDEN_PUBLIC_INPUT_NAMES)


# Current-state / fixture checks stay ordinary green on the validator base.

def test_exact_base_is_current_takeover_main() -> None:
    assert BASE_SHA == "90406f5849733469cab57c43150f299fd61380cb"


def test_real_pdf_visibility_fixture_is_producer_owned_and_complete_for_page() -> None:
    producer, published = _source()
    assert published.coverage.failed_pages == ()
    assert published.coverage.decoded_pages == (1,)
    assert published.visible_observation_ids

    authority = producer.authority()
    resolved_ids = []
    for observation_id in published.visible_observation_ids:
        result = authority.resolve_visible(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        assert result.status is EvidenceResolutionStatus.CORROBORATED
        assert result.observation is not None
        resolved_ids.append(result.observation.observation_id)

    # Proves the whole producer-owned accepted set is resolvable; it does not
    # hard-code a PyMuPDF primitive count.
    assert set(resolved_ids) == set(published.visible_observation_ids)


def test_two_wall_fixture_has_larger_producer_owned_visible_scope() -> None:
    _producer, one = _source(second_wall=False, document_id="doc-one-wall")
    _producer2, two = _source(second_wall=True, document_id="doc-two-walls")
    assert len(two.visible_observation_ids) > len(one.visible_observation_ids)


def test_current_public_source_authority_does_not_expose_caller_scope_completeness_switch() -> None:
    fields = _field_names(
        type(
            SourceVisibilityProducer(
                producer_method="shape-check", producer_version="1"
            ).authority()
        )
    )
    assert "claimed_complete" not in fields
    assert "scope_complete" not in fields


@EXPECTED_RED
def test_attack01_required_module_and_sealed_factory_exist() -> None:
    assert HAS_MODULE, "source-backed physical-wall candidate authority is not implemented"
    mod = importlib.import_module(MODULE)
    factory = getattr(
        mod.PhysicalWallCandidateProducer,
        "from_source_visibility_producer",
        None,
    )
    assert callable(factory)
    parameters = {
        name
        for name in inspect.signature(factory).parameters
        if name not in {"self", "cls"}
    }
    assert parameters == {"source_visibility_producer"}


@EXPECTED_RED
def test_attack02_real_complete_source_scope_resolves_wall_candidates() -> None:
    mod = _mod()
    producer, published = _source()
    wall_producer = _wall_producer(mod, producer)
    authority = wall_producer.authority()
    result = authority.resolve_scope(_selector(mod, published))

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.scope_complete is True
    assert tuple(result.records)
    assert all(record.physical_identity is not None for record in result.records)
    assert all(record.physical_identity.usable for record in result.records)


@EXPECTED_RED
def test_attack03_public_selector_is_lineage_only_not_candidate_truth() -> None:
    mod = _mod()
    fields = _field_names(mod.PhysicalWallCandidateSelector)
    assert fields == {
        "document_id",
        "revision_id",
        "source_sha256",
        "snapshot_id",
        "page_id",
        "decision_scope_id",
    }


@EXPECTED_RED
def test_attack04_authority_resolve_is_selector_only() -> None:
    mod = _mod()
    signature = inspect.signature(mod.PhysicalWallCandidateAuthority.resolve_scope)
    assert set(signature.parameters) == {"self", "selector"}


@EXPECTED_RED
def test_attack05_no_public_input_can_self_certify_wall_truth_or_completeness() -> None:
    mod = _mod()
    _assert_no_caller_truth_parameters(
        mod.PhysicalWallCandidateProducer.from_source_visibility_producer
    )
    _assert_no_caller_truth_parameters(mod.PhysicalWallCandidateProducer.authority)
    _assert_no_caller_truth_parameters(mod.PhysicalWallCandidateAuthority.resolve_scope)

    # A separate public writer API would reopen the same trust boundary.
    assert not hasattr(mod.PhysicalWallCandidateProducer, "publish_scope")


@pytest.mark.parametrize(
    ("field", "wrong"),
    [
        ("revision_id", "wrong-revision"),
        ("source_sha256", "f" * 64),
        ("snapshot_id", "wrong-snapshot"),
        ("page_id", "999"),
        ("decision_scope_id", "wall-source:page-999"),
    ],
)
@EXPECTED_RED
def test_attack06_10_lineage_or_scope_laundering_fails(field: str, wrong: str) -> None:
    mod = _mod()
    producer, published = _source()
    authority = _wall_producer(mod, producer).authority()
    result = authority.resolve_scope(_selector(mod, published, **{field: wrong}))

    assert result.status in {
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
    }
    assert not tuple(getattr(result, "records", ()) or ())


@EXPECTED_RED
def test_attack11_foreign_or_caller_created_state_cannot_mint_trusted_producer() -> None:
    mod = _mod()
    producer, published = _source()
    factory = mod.PhysicalWallCandidateProducer.from_source_visibility_producer

    # Only the real already-ingested SourceVisibilityProducer is acceptable.
    # A caller-created/caller-held snapshot, read authority, dictionary,
    # segment collection or wall-candidate collection cannot establish trust.
    rejected = (
        published,
        producer.authority(),
        {"segments": [{"x1": 0, "y1": 0, "x2": 1, "y2": 0}]},
        {"wall_candidates": [object()]},
        {"source_observation_ids": published.visible_observation_ids},
    )
    for value in rejected:
        with pytest.raises((TypeError, ValueError, AttributeError)):
            factory(value)


@EXPECTED_RED
def test_attack12_caller_omission_cannot_shrink_complete_source_scope() -> None:
    mod = _mod()
    producer, published = _source(second_wall=True, document_id="doc-two-hosts")
    wall_producer = _wall_producer(mod, producer)
    authority = wall_producer.authority()
    complete = authority.resolve_scope(_selector(mod, published))

    assert complete.status is EvidenceResolutionStatus.CORROBORATED
    assert complete.scope_complete is True
    ids = tuple(record.wall_candidate_id for record in complete.records)
    assert len(ids) >= 2

    # There is no public selection/subset input by which a downstream caller
    # can say "use only A" and still receive scope_complete=True.
    _assert_no_caller_truth_parameters(
        mod.PhysicalWallCandidateProducer.from_source_visibility_producer
    )
    _assert_no_caller_truth_parameters(mod.PhysicalWallCandidateAuthority.resolve_scope)


@EXPECTED_RED
def test_attack13_identical_scope_replay_and_output_order_are_deterministic() -> None:
    mod = _mod()
    producer, published = _source(second_wall=True, document_id="doc-determinism")
    authority = _wall_producer(mod, producer).authority()
    selector = _selector(mod, published)

    first = authority.resolve_scope(selector)
    second = authority.resolve_scope(selector)
    assert first == second

    source_ids = tuple(first.source_observation_ids)
    assert source_ids == tuple(sorted(source_ids))
    wall_ids = tuple(record.wall_candidate_id for record in first.records)
    assert wall_ids == tuple(sorted(wall_ids))


@EXPECTED_RED
def test_attack14_authority_and_producer_direct_construction_are_sealed() -> None:
    mod = _mod()
    with pytest.raises((TypeError, ValueError)):
        mod.PhysicalWallCandidateAuthority({})
    with pytest.raises((TypeError, ValueError)):
        mod.PhysicalWallCandidateProducer({})


@EXPECTED_RED
def test_attack15_successful_scope_retains_exact_producer_source_membership() -> None:
    mod = _mod()
    producer, published = _source(document_id="doc-source-audit")
    result = _wall_producer(mod, producer).authority().resolve_scope(
        _selector(mod, published)
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.scope_complete is True
    assert set(result.source_observation_ids) == set(published.visible_observation_ids)
    assert result.source_sha256 == published.revision.source_sha256
    assert result.snapshot_id == published.snapshot.snapshot_id
    assert result.document_id == published.revision.document_id
    assert result.revision_id == published.revision.revision_id
    assert result.page_id == "1"
