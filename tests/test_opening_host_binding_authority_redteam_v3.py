"""Host binding v3 — authenticated-prerequisite adversarial contract.

SELF-AUTHORED VALIDATOR — INDEPENDENT REVIEW REQUIRED.

V3 starts only from independently authenticated producer state:
real PDF -> SourceVisibilityProducer -> PhysicalOpeningAuthority + merged sealed
PhysicalWallCandidateAuthority -> complete host-wall universe -> unique host.

A caller cannot manufacture opening identity, wall membership, host-universe
completeness, or host uniqueness with ids, lists, booleans, radii, confidence,
tags, schedule text, OCR/CV labels, nearest/first selection, or raw geometry.
"""
from __future__ import annotations

import dataclasses
import importlib
import importlib.util
import inspect

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PHYSICAL_OPENING_IDENTITY_RESOLVED,
    PhysicalOpeningAuthority,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from tests.opening_host_binding_test_support_v3 import (
    BASE_SHA,
    FROZEN_4A_VALIDATOR_HEAD,
    HISTORICAL_360_HEAD,
    HISTORICAL_364_HEAD,
    MERGED_4A_PRODUCTION_HEAD,
    CallerHostTruth,
    make_real_host_fixture,
    wall_record_ids,
)

HOST_MODULE = "pb_opening_host_binding_authority"
HAS_HOST_V3 = importlib.util.find_spec(HOST_MODULE) is not None
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_HOST_V3,
    strict=True,
    reason="host-binding v3 production authority is not implemented on this base",
)

FORBIDDEN_SUBSET_FIELDS = {
    "walls", "wall_candidates", "candidate_walls", "candidate_wall_ids",
    "host_candidates", "host_wall_id", "wall_candidate_id", "wall_count",
    "candidate_count", "radius", "distance", "nearest_wall_id", "first_wall_id",
}
FORBIDDEN_PROOF_FIELDS = {
    "complete", "claimed_complete", "host_universe_complete", "source_complete",
    "scope_complete", "traversal_complete", "traversal_truncated", "confidence",
    "opening_span", "geometry", "path_fingerprint", "tag", "schedule_row",
    "ocr_label", "cv_label",
}


def _field_names(obj_type: type) -> set[str]:
    if dataclasses.is_dataclass(obj_type):
        return {field.name for field in dataclasses.fields(obj_type)}
    return {
        name for name in inspect.signature(obj_type).parameters
        if name not in {"self", "args", "kwargs"}
    }


def _status(result: object):
    return getattr(result, "status", None)


def _host_id(result: object) -> str | None:
    direct = getattr(result, "host_wall_id", None)
    if direct:
        return str(direct)
    record = getattr(result, "record", None)
    value = getattr(record, "host_wall_id", None) if record is not None else None
    return str(value) if value else None


def _assert_blocked(result: object) -> None:
    assert _status(result) in {
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
    }
    assert _host_id(result) is None


def _host_mod():
    assert HAS_HOST_V3, "missing host-binding v3 production module"
    mod = importlib.import_module(HOST_MODULE)
    for name in (
        "OpeningHostWallUniverseSelector",
        "OpeningHostWallUniverseProducer",
        "OpeningHostWallUniverseAuthority",
        "OpeningHostBindingSelector",
        "OpeningHostBindingProducer",
        "OpeningHostBindingAuthority",
    ):
        assert hasattr(mod, name), f"missing host v3 API: {name}"
    return mod


def _host_universe(fixture):
    mod = _host_mod()
    factory = getattr(mod.OpeningHostWallUniverseProducer, "from_physical_wall_candidate_authority")
    producer = factory(fixture.wall_authority)
    authority = producer.authority()
    selector = mod.OpeningHostWallUniverseSelector(
        document_id=fixture.document_id,
        revision_id=fixture.revision_id,
        source_sha256=fixture.source_sha256,
        snapshot_id=fixture.snapshot_id,
        page_id=fixture.page_id,
        decision_scope_id=fixture.wall_selector.decision_scope_id,
    )
    result = authority.resolve_scope(selector)
    return mod, producer, authority, selector, result


def _publish_binding(fixture, universe_authority, universe_selector):
    mod = _host_mod()
    factory = getattr(mod.OpeningHostBindingProducer, "from_authorities")
    producer = factory(
        physical_opening_authority=fixture.physical_opening_authority,
        host_wall_universe_authority=universe_authority,
    )
    signature = inspect.signature(producer.publish)
    assert "opening_record_id" not in signature.parameters
    assert "opening_span" not in signature.parameters
    assert not (FORBIDDEN_SUBSET_FIELDS & set(signature.parameters))
    assert not (FORBIDDEN_PROOF_FIELDS & set(signature.parameters))
    result = producer.publish(
        opening_left_selector=fixture.left_selector,
        opening_right_selector=fixture.right_selector,
        host_universe_selector=universe_selector,
    )
    return mod, producer, result


# Current GREEN prerequisite checks.

def test_v3_exact_base_and_dependency_heads_are_explicit() -> None:
    assert BASE_SHA == "76c7882b1c4b28764d1e6a6f467d72bb276c2e01"
    assert HISTORICAL_360_HEAD == "4231222348c9d575232097b9c4072ac3a83cfcba"
    assert HISTORICAL_364_HEAD == "931506b0b80531383c78a621ca9c09473642ed58"
    assert FROZEN_4A_VALIDATOR_HEAD == "4f9503d027b32664bbdac235289fb401d310d27e"
    assert MERGED_4A_PRODUCTION_HEAD == "082810b541bbe4072376f7328fc6064351cb383c"


def test_real_positive_fixture_proves_opening_existence_and_identity() -> None:
    fixture = make_real_host_fixture()
    existence = fixture.physical_opening_authority.prove_existence(fixture.left_selector)
    assert existence.status is EvidenceResolutionStatus.CORROBORATED
    assert existence.proposition == PHYSICAL_OPENING_EXISTS
    assert existence.existence_record is not None
    identity = fixture.physical_opening_authority.compare_identity(
        fixture.left_selector, fixture.right_selector
    )
    assert identity.status is EvidenceResolutionStatus.CORROBORATED
    assert identity.proven_same is True
    assert PHYSICAL_OPENING_IDENTITY_RESOLVED in identity.reason_codes


def test_merged_4a_wall_scope_is_real_complete_and_source_auditable() -> None:
    fixture = make_real_host_fixture()
    scope = fixture.wall_scope
    assert scope.status is EvidenceResolutionStatus.CORROBORATED
    assert scope.scope_complete is True
    assert tuple(scope.records)
    assert set(scope.source_observation_ids) == set(fixture.published.visible_observation_ids)
    assert all(record.physical_identity.usable for record in scope.records)
    assert all(record.wall_candidate_id == record.wall_candidate.candidate_id for record in scope.records)


def test_merged_4a_factory_and_selector_do_not_accept_caller_subsets() -> None:
    fields = _field_names(PhysicalWallCandidateSelector)
    assert fields == {
        "document_id", "revision_id", "source_sha256", "snapshot_id",
        "page_id", "decision_scope_id",
    }
    assert not (fields & FORBIDDEN_SUBSET_FIELDS)
    assert not (fields & FORBIDDEN_PROOF_FIELDS)
    with pytest.raises((TypeError, ValueError)):
        PhysicalWallCandidateProducer({})
    with pytest.raises((TypeError, ValueError)):
        PhysicalWallCandidateAuthority({})


def test_caller_host_truth_object_remains_only_untrusted_data() -> None:
    caller = CallerHostTruth()
    assert caller.claimed_complete is True
    assert caller.candidate_wall_ids
    assert PhysicalOpeningAuthority.capabilities()["host_binding"] is False


def test_host_void_and_net_capabilities_remain_locked_before_v3_production() -> None:
    caps = PhysicalOpeningAuthority.capabilities()
    assert caps["physical_opening_existence"] is True
    assert caps["physical_opening_identity"] is True
    assert caps["host_binding"] is False
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False


@EXPECTED_RED
def test_attack01_real_source_opening_complete_wall_universe_unique_host_may_bind() -> None:
    mod = _host_mod()  # first RED on this base must be missing host V3 production.
    fixture = make_real_host_fixture()
    _mod, _up, ua, us, universe = _host_universe(fixture)
    assert _status(universe) is EvidenceResolutionStatus.CORROBORATED
    assert getattr(universe, "scope_complete", False) is True
    _mod, producer, result = _publish_binding(fixture, ua, us)
    assert _status(result) is EvidenceResolutionStatus.CORROBORATED
    assert _host_id(result)
    assert type(producer.authority()).__name__ == "OpeningHostBindingAuthority"
    assert type(mod.OpeningHostWallUniverseAuthority).__name__ == "type"


@EXPECTED_RED
def test_attack02_public_read_selectors_are_lineage_only() -> None:
    mod = _host_mod()
    universe_fields = _field_names(mod.OpeningHostWallUniverseSelector)
    binding_fields = _field_names(mod.OpeningHostBindingSelector)
    allowed_universe = {
        "document_id", "revision_id", "source_sha256", "snapshot_id",
        "page_id", "decision_scope_id",
    }
    assert universe_fields == allowed_universe
    assert binding_fields == allowed_universe | {"opening_identity_id"}
    assert not ((FORBIDDEN_SUBSET_FIELDS | FORBIDDEN_PROOF_FIELDS) & binding_fields)
    assert set(inspect.signature(mod.OpeningHostWallUniverseAuthority.resolve_scope).parameters) <= {"self", "selector"}
    assert set(inspect.signature(mod.OpeningHostBindingAuthority.resolve).parameters) <= {"self", "selector"}


@EXPECTED_RED
def test_attack03_arbitrary_opening_identity_id_cannot_mint_binding() -> None:
    mod = _host_mod()
    fixture = make_real_host_fixture()
    _mod, _up, ua, us, universe = _host_universe(fixture)
    assert _status(universe) is EvidenceResolutionStatus.CORROBORATED
    _mod, producer, positive = _publish_binding(fixture, ua, us)
    assert _status(positive) is EvidenceResolutionStatus.CORROBORATED
    selector = mod.OpeningHostBindingSelector(
        document_id=fixture.document_id,
        revision_id=fixture.revision_id,
        source_sha256=fixture.source_sha256,
        snapshot_id=fixture.snapshot_id,
        page_id=fixture.page_id,
        decision_scope_id=fixture.wall_selector.decision_scope_id,
        opening_identity_id="record-looking-but-unproven",
    )
    _assert_blocked(producer.authority().resolve(selector))


@EXPECTED_RED
def test_attack04_tag_schedule_ocr_cv_wall_ids_and_raw_geometry_are_not_inputs() -> None:
    mod = _host_mod()
    publish_fields = set(inspect.signature(mod.OpeningHostBindingProducer.publish).parameters)
    forbidden = FORBIDDEN_SUBSET_FIELDS | FORBIDDEN_PROOF_FIELDS | {
        "opening_record_id", "host_wall_id", "wall_id",
    }
    assert not (publish_fields & forbidden), publish_fields & forbidden


@EXPECTED_RED
def test_attack05_host_universe_completeness_cannot_be_caller_certified() -> None:
    mod = _host_mod()
    producer_fields = _field_names(mod.OpeningHostWallUniverseProducer)
    selector_fields = _field_names(mod.OpeningHostWallUniverseSelector)
    assert not ((FORBIDDEN_PROOF_FIELDS | FORBIDDEN_SUBSET_FIELDS) & producer_fields)
    assert not ((FORBIDDEN_PROOF_FIELDS | FORBIDDEN_SUBSET_FIELDS) & selector_fields)
    factory = inspect.signature(mod.OpeningHostWallUniverseProducer.from_physical_wall_candidate_authority)
    assert "physical_wall_candidate_authority" in factory.parameters


@EXPECTED_RED
def test_attack06_omitted_competitor_cannot_shrink_producer_truth() -> None:
    """Omission attack: A+B exist in source; caller cannot ask for A-only complete."""
    mod = _host_mod()
    fixture = make_real_host_fixture(include_competitor=True)
    wall_ids = wall_record_ids(fixture)
    assert len(wall_ids) >= 2, "authenticated source must contain competing wall records"
    _mod, producer, _authority, selector, universe = _host_universe(fixture)
    assert _status(universe) is EvidenceResolutionStatus.CORROBORATED
    assert getattr(universe, "scope_complete", False) is True
    universe_ids = tuple(getattr(record, "wall_candidate_id") for record in universe.records)
    assert set(universe_ids) == set(wall_ids)
    assert "candidate_wall_ids" not in inspect.signature(type(producer).from_physical_wall_candidate_authority).parameters
    assert "candidate_wall_ids" not in _field_names(mod.OpeningHostWallUniverseSelector)
    with pytest.raises(TypeError):
        mod.OpeningHostWallUniverseSelector(
            document_id=fixture.document_id,
            revision_id=fixture.revision_id,
            source_sha256=fixture.source_sha256,
            snapshot_id=fixture.snapshot_id,
            page_id=fixture.page_id,
            decision_scope_id=selector.decision_scope_id,
            candidate_wall_ids=(wall_ids[0],),
        )


@EXPECTED_RED
def test_attack07_complete_authenticated_multi_host_universe_lacks_uniqueness() -> None:
    """Multi-host attack: nothing omitted; complete universe itself is non-unique."""
    _host_mod()
    fixture = make_real_host_fixture(include_competitor=True)
    wall_ids = wall_record_ids(fixture)
    assert len(wall_ids) >= 2
    _mod, _up, ua, us, universe = _host_universe(fixture)
    assert _status(universe) is EvidenceResolutionStatus.CORROBORATED
    universe_ids = tuple(getattr(record, "wall_candidate_id") for record in universe.records)
    assert set(universe_ids) == set(wall_ids), "nothing may be omitted in Attack 07"
    _mod, _producer, result = _publish_binding(fixture, ua, us)
    _assert_blocked(result)


@EXPECTED_RED
def test_attack08_radius_nearest_first_or_local_subset_cannot_be_authority() -> None:
    mod = _host_mod()
    for obj in (
        mod.OpeningHostWallUniverseSelector,
        mod.OpeningHostBindingSelector,
        mod.OpeningHostWallUniverseProducer,
        mod.OpeningHostBindingProducer,
    ):
        assert not (_field_names(obj) & FORBIDDEN_SUBSET_FIELDS)


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
def test_attack09_13_lineage_scope_laundering_blocks_resolution(field: str, wrong: str) -> None:
    mod = _host_mod()
    fixture = make_real_host_fixture()
    _mod, _up, ua, us, universe = _host_universe(fixture)
    assert _status(universe) is EvidenceResolutionStatus.CORROBORATED
    _mod, producer, positive = _publish_binding(fixture, ua, us)
    assert _status(positive) is EvidenceResolutionStatus.CORROBORATED
    kwargs = {
        "document_id": fixture.document_id,
        "revision_id": fixture.revision_id,
        "source_sha256": fixture.source_sha256,
        "snapshot_id": fixture.snapshot_id,
        "page_id": fixture.page_id,
        "decision_scope_id": fixture.wall_selector.decision_scope_id,
        "opening_identity_id": fixture.existence_record.record_id,
    }
    kwargs[field] = wrong
    _assert_blocked(producer.authority().resolve(mod.OpeningHostBindingSelector(**kwargs)))


@EXPECTED_RED
def test_attack14_host_binding_does_not_unlock_void_or_net_wall() -> None:
    _host_mod()
    fixture = make_real_host_fixture()
    _mod, _up, ua, us, universe = _host_universe(fixture)
    assert _status(universe) is EvidenceResolutionStatus.CORROBORATED
    _mod, _producer, result = _publish_binding(fixture, ua, us)
    assert _status(result) is EvidenceResolutionStatus.CORROBORATED
    caps = PhysicalOpeningAuthority.capabilities()
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False


@EXPECTED_RED
def test_attack15_host_authorities_and_producers_are_sealed() -> None:
    mod = _host_mod()
    for obj in (
        mod.OpeningHostWallUniverseProducer,
        mod.OpeningHostWallUniverseAuthority,
        mod.OpeningHostBindingProducer,
        mod.OpeningHostBindingAuthority,
    ):
        with pytest.raises((TypeError, ValueError)):
            obj({})


@EXPECTED_RED
def test_attack16_foreign_primitives_candidates_or_authorities_cannot_be_injected() -> None:
    mod = _host_mod()
    for obj in (mod.OpeningHostWallUniverseProducer, mod.OpeningHostBindingProducer):
        fields = _field_names(obj)
        assert "source_primitives" not in fields
        assert "walls" not in fields
        assert "wall_candidates" not in fields
        assert "edges_by_id" not in fields


@EXPECTED_RED
def test_attack17_unproven_wall_equivalence_cannot_be_caller_collapsed() -> None:
    mod = _host_mod()
    fields = _field_names(mod.OpeningHostWallUniverseSelector)
    assert "equivalent_wall_ids" not in fields
    assert "same_physical_wall" not in fields
    assert "path_fingerprint" not in fields


@EXPECTED_RED
def test_attack18_reversed_or_split_representation_is_not_a_caller_identity_switch() -> None:
    mod = _host_mod()
    fields = _field_names(mod.OpeningHostWallUniverseSelector)
    assert "reversed_is_distinct" not in fields
    assert "segments" not in fields
    assert "split_wall_ids" not in fields


@EXPECTED_RED
def test_attack19_truncated_scope_cannot_be_laundered_complete() -> None:
    mod = _host_mod()
    for obj in (mod.OpeningHostWallUniverseSelector, mod.OpeningHostWallUniverseProducer):
        fields = _field_names(obj)
        assert "claimed_complete" not in fields
        assert "traversal_truncated" not in fields
        assert "source_complete" not in fields


@EXPECTED_RED
def test_attack20_deterministic_replay_returns_same_immutable_binding() -> None:
    _host_mod()
    fixture = make_real_host_fixture()
    _mod, _up, ua, us, universe = _host_universe(fixture)
    assert _status(universe) is EvidenceResolutionStatus.CORROBORATED
    _mod, producer, first = _publish_binding(fixture, ua, us)
    second = producer.authority().resolve(
        _mod.OpeningHostBindingSelector(
            document_id=fixture.document_id,
            revision_id=fixture.revision_id,
            source_sha256=fixture.source_sha256,
            snapshot_id=fixture.snapshot_id,
            page_id=fixture.page_id,
            decision_scope_id=fixture.wall_selector.decision_scope_id,
            opening_identity_id=fixture.existence_record.record_id,
        )
    )
    assert first == second
