from __future__ import annotations

from pb_explicit_aperture_tag_relation import build_explicit_aperture_tag_relations
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_opening_candidate_authority import IdentityState, OpeningIdentityResolver
from tests.test_source_opening_universe_evidence_v1 import (
    build_source_test_bundle,
    make_candidate,
)


def _candidate(bundle, *, geometry=(100.0, 100.0, 140.0, 140.0), viewport_id="vp_floor_plan_p1"):
    return make_candidate(
        document_id=bundle["document_id"],
        revision_id=bundle["revision_id"],
        source_sha256=bundle["source_sha256"],
        snapshot_id=bundle["snapshot_id"],
        page_id=bundle["page_id"],
        viewport_id=viewport_id,
        geometry=geometry,
        source_observation_ids=(bundle["rect_obs_id"],),
        semantic_family="doors",
    )


def test_contained_source_tag_builds_typed_relation_and_existing_resolver_binds() -> None:
    bundle = build_source_test_bundle(
        tag_text="D-7",
        tag_pt=(120.0, 120.0),
        rect_bbox=(100.0, 100.0, 140.0, 140.0),
    )
    candidate = _candidate(bundle)
    tag = bundle["tag_observation"]

    evidences = build_explicit_aperture_tag_relations(
        candidates=(candidate,),
        tags=(tag,),
        source_observation_authority=bundle["authority"],
    )

    assert len(evidences) == 1
    assert evidences[0].status == EvidenceResolutionStatus.CORROBORATED

    result = OpeningIdentityResolver.resolve_tag_binding(
        candidate=candidate,
        nearby_tags=(tag,),
        binding_evidences=evidences,
        expected_semantic_family="doors",
        viewport_authenticated=True,
        revision_authenticated=True,
        source_observation_authority=bundle["authority"],
    )
    assert result.identity_state == IdentityState.PROVEN_SAME
    assert result.bound_mark == "D7"


def test_one_tag_attaching_to_two_openings_fails_closed() -> None:
    bundle = build_source_test_bundle(
        tag_text="D2",
        tag_pt=(120.0, 120.0),
        rect_bbox=(100.0, 100.0, 140.0, 140.0),
    )
    first = _candidate(bundle, geometry=(100.0, 100.0, 140.0, 140.0))
    second = _candidate(bundle, geometry=(110.0, 100.0, 150.0, 140.0))

    evidences = build_explicit_aperture_tag_relations(
        candidates=(first, second),
        tags=(bundle["tag_observation"],),
        source_observation_authority=bundle["authority"],
    )

    assert evidences == ()


def test_tag_outside_aperture_does_not_gain_identity_authority() -> None:
    bundle = build_source_test_bundle(
        tag_text="W4",
        tag_pt=(300.0, 300.0),
        rect_bbox=(100.0, 100.0, 140.0, 140.0),
    )
    candidate = _candidate(bundle)

    evidences = build_explicit_aperture_tag_relations(
        candidates=(candidate,),
        tags=(bundle["tag_observation"],),
        source_observation_authority=bundle["authority"],
    )

    assert evidences == ()


def test_cross_viewport_tag_never_builds_relation() -> None:
    bundle = build_source_test_bundle(
        tag_text="D3",
        tag_pt=(120.0, 120.0),
        rect_bbox=(100.0, 100.0, 140.0, 140.0),
    )
    candidate = _candidate(bundle, viewport_id="vp_other")

    evidences = build_explicit_aperture_tag_relations(
        candidates=(candidate,),
        tags=(bundle["tag_observation"],),
        source_observation_authority=bundle["authority"],
    )

    assert evidences == ()
