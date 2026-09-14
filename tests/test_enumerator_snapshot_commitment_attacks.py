from __future__ import annotations

from dataclasses import replace

import pytest

from pb_authority_completeness import (
    DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
    DOMAIN_WALL_LENGTH_SCALE,
    AuthorityBindingStatus,
    build_authority_universe,
    physical_wall_identity_member,
    scale_binding_member,
)
from pb_enumerator_snapshot_commitment import (
    build_enumerator_snapshot_commitment,
    immutable_snapshot_fingerprint,
    verify_enumerator_snapshot_commitment,
)
from pb_wall_length_quantity import build_wall_length_quantity
from tests.test_completeness_authority_attacks import (
    _binding,
    _candidate_proof,
    _enumerator_proof,
    _firm_single_kwargs,
    _identity,
    _scale_proof,
    _scope,
    _wall,
)


def _snapshot_payload(domain: str, universe) -> dict[str, object]:
    return {
        "domain": domain,
        "scope": universe.scope.payload(),
        "members": tuple(
            {
                "candidate_id": item.candidate_id,
                "provenance_fingerprint": item.provenance_fingerprint,
            }
            for item in sorted(universe.members, key=lambda item: item.candidate_id)
        ),
    }


def test_c5_self_consistent_truncated_wall_universe_cannot_certify_itself() -> None:
    """Authoritative enumerator has W1+W2; caller presents valid-looking W1-only proof."""
    kwargs = _firm_single_kwargs()
    admitted_identity = kwargs["physical_identity_universe"][0]
    hidden_identity = _identity(_wall("w2", y=25.0))
    authoritative_universe = build_authority_universe(
        _scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
        (
            physical_wall_identity_member(admitted_identity),
            physical_wall_identity_member(hidden_identity),
        ),
    )
    assert authoritative_universe.fingerprint != kwargs["candidate_universe"].fingerprint
    commitment, snapshot_id, snapshot_fp, current = _enumerator_proof(
        DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
        authoritative_universe,
        snapshot_tag="real-physical-wall",
    )
    kwargs.update(
        candidate_enumerator_commitment=commitment,
        candidate_upstream_snapshot_id=snapshot_id,
        candidate_upstream_snapshot_fingerprint=snapshot_fp,
        candidate_enumerated_universe=current,
    )
    # Deliberately leave candidate_universe + candidate_manifest as the
    # caller's perfectly self-consistent W1-only pair. The public quantity
    # boundary has no authoritative upstream snapshot payload, so the result
    # must fail closed before this caller-curated subset can authorize FIRM.
    qty = build_wall_length_quantity(**kwargs)
    assert qty.abstained is True
    assert "physical_candidate_enumerator_commitment_unavailable" in qty.blocking_reasons
    assert "authoritative_upstream_snapshot_content_unavailable" in qty.blocking_reasons


def test_c1_self_consistent_truncated_scale_universe_cannot_certify_itself() -> None:
    """Authoritative scale enumeration has S1+S2; caller presents valid-looking S1 only."""
    kwargs = _firm_single_kwargs()
    admitted = kwargs["scale_bindings"][0]
    hidden = _binding(50.0, label="A102-hidden")
    authoritative_universe = build_authority_universe(
        _scope(DOMAIN_WALL_LENGTH_SCALE),
        (scale_binding_member(admitted), scale_binding_member(hidden)),
    )
    assert authoritative_universe.fingerprint != kwargs["scale_universe"].fingerprint
    commitment, snapshot_id, snapshot_fp, current = _enumerator_proof(
        DOMAIN_WALL_LENGTH_SCALE,
        authoritative_universe,
        snapshot_tag="real-scale",
    )
    kwargs.update(
        scale_enumerator_commitment=commitment,
        scale_upstream_snapshot_id=snapshot_id,
        scale_upstream_snapshot_fingerprint=snapshot_fp,
        scale_enumerated_universe=current,
    )
    qty = build_wall_length_quantity(**kwargs)
    assert qty.abstained is True
    assert "scale_enumerator_commitment_unavailable" in qty.blocking_reasons
    assert "authoritative_upstream_snapshot_content_unavailable" in qty.blocking_reasons


def test_fabricated_enumerator_commitment_with_wrong_upstream_content_is_blocked() -> None:
    kwargs = _firm_single_kwargs()
    universe = kwargs["candidate_universe"]
    real_snapshot_id = kwargs["candidate_upstream_snapshot_id"]
    real_snapshot_fp = kwargs["candidate_upstream_snapshot_fingerprint"]
    fake_snapshot_fp = immutable_snapshot_fingerprint({"forged": ["w1"]})
    assert fake_snapshot_fp != real_snapshot_fp
    forged = build_enumerator_snapshot_commitment(
        scope=universe.scope,
        enumerator_id="attacker.physical-wall",
        enumerator_version="1",
        upstream_snapshot_id=real_snapshot_id,
        upstream_snapshot_fingerprint=fake_snapshot_fp,
        candidate_universe=universe,
    )
    kwargs["candidate_enumerator_commitment"] = forged
    qty = build_wall_length_quantity(**kwargs)
    assert qty.abstained is True
    assert "physical_candidate_enumerator_commitment_unavailable" in qty.blocking_reasons


def test_candidate_added_after_enumeration_is_stale() -> None:
    kwargs = _firm_single_kwargs()
    admitted_identity = kwargs["physical_identity_universe"][0]
    added_identity = _identity(_wall("w2", y=30.0))
    current_universe, _ = _candidate_proof((admitted_identity, added_identity))
    current_payload = {
        "members": sorted(item.candidate_id for item in current_universe.members),
        "mutation": "candidate-added",
    }
    current_snapshot_fp = immutable_snapshot_fingerprint(current_payload)
    commitment = kwargs["candidate_enumerator_commitment"]
    result = verify_enumerator_snapshot_commitment(
        commitment,
        expected_scope=_scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
        current_upstream_snapshot_id=kwargs["candidate_upstream_snapshot_id"],
        current_upstream_snapshot_fingerprint=current_snapshot_fp,
        current_enumerated_universe=current_universe,
        manifest=kwargs["candidate_manifest"],
        supplied_admitted_ids=("w1",),
        current_upstream_snapshot_payload=current_payload,
    )
    assert result.status == AuthorityBindingStatus.STALE


def test_candidate_removed_after_enumeration_is_stale() -> None:
    w1 = _identity(_wall("w1"))
    w2 = _identity(_wall("w2", y=30.0))
    full_universe, full_manifest = _candidate_proof((w1, w2))
    commitment, snapshot_id, _snapshot_fp, _ = _enumerator_proof(
        DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
        full_universe,
        snapshot_tag="pre-removal",
    )
    current_universe, current_manifest = _candidate_proof((w1,))
    current_payload = {"members": ["w1"], "mutation": "candidate-removed"}
    result = verify_enumerator_snapshot_commitment(
        commitment,
        expected_scope=_scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
        current_upstream_snapshot_id=snapshot_id,
        current_upstream_snapshot_fingerprint=immutable_snapshot_fingerprint(current_payload),
        current_enumerated_universe=current_universe,
        manifest=current_manifest,
        supplied_admitted_ids=("w1",),
        current_upstream_snapshot_payload=current_payload,
    )
    assert full_manifest.authority_universe_fingerprint != current_manifest.authority_universe_fingerprint
    assert result.status == AuthorityBindingStatus.STALE


def test_commitment_is_permutation_invariant_for_same_authoritative_members() -> None:
    first = _identity(_wall("w1"))
    second = _identity(_wall("w2", y=40.0))
    forward = build_authority_universe(
        _scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
        (physical_wall_identity_member(first), physical_wall_identity_member(second)),
    )
    reverse = build_authority_universe(
        _scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
        (physical_wall_identity_member(second), physical_wall_identity_member(first)),
    )
    assert forward.fingerprint == reverse.fingerprint
    a, aid, afp, _ = _enumerator_proof(
        DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
        forward,
        snapshot_tag="ordering",
    )
    b, bid, bfp, _ = _enumerator_proof(
        DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
        reverse,
        snapshot_tag="ordering",
    )
    assert aid == bid
    assert afp == bfp
    assert a.commitment_fingerprint == b.commitment_fingerprint


def test_unrelated_viewport_candidate_does_not_poison_local_committed_scope() -> None:
    local = _identity(_wall("w1"))
    outside = _identity(_wall("w-outside", y=80.0, viewport_id="vp-other"))
    local_universe, local_manifest = _candidate_proof((local,))
    commitment, snapshot_id, snapshot_fp, current = _enumerator_proof(
        DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
        local_universe,
        snapshot_tag="scope-isolation",
    )
    result = verify_enumerator_snapshot_commitment(
        commitment,
        expected_scope=_scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
        current_upstream_snapshot_id=snapshot_id,
        current_upstream_snapshot_fingerprint=snapshot_fp,
        current_enumerated_universe=current,
        manifest=local_manifest,
        supplied_admitted_ids=("w1",),
        current_upstream_snapshot_payload=_snapshot_payload(
            DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
            local_universe,
        ),
    )
    assert outside.viewport_id == "vp-other"
    assert result.status == AuthorityBindingStatus.AUTHENTIC


@pytest.mark.parametrize(
    ("scope_field", "mutated_value"),
    (
        ("source_sha256", "e" * 64),
        ("revision_id", "R2"),
        ("evidence_snapshot_id", "evsnap-2"),
        ("graph_snapshot_id", "graphsnap-2"),
    ),
)
def test_upstream_provenance_scope_mutation_rejects_old_commitment(
    scope_field: str,
    mutated_value: str,
) -> None:
    universe, manifest = _candidate_proof((_identity(_wall("w1")),))
    commitment, snapshot_id, snapshot_fp, current = _enumerator_proof(
        DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
        universe,
        snapshot_tag="provenance",
    )
    mutated_scope = replace(
        _scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
        **{scope_field: mutated_value},
    )
    result = verify_enumerator_snapshot_commitment(
        commitment,
        expected_scope=mutated_scope,
        current_upstream_snapshot_id=snapshot_id,
        current_upstream_snapshot_fingerprint=snapshot_fp,
        current_enumerated_universe=current,
        manifest=manifest,
        supplied_admitted_ids=("w1",),
        current_upstream_snapshot_payload=_snapshot_payload(
            DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
            universe,
        ),
    )
    assert result.status in {AuthorityBindingStatus.STALE, AuthorityBindingStatus.MISMATCH}


def test_upstream_content_mutation_with_same_candidate_ids_is_stale() -> None:
    universe, manifest = _scale_proof((_binding(100.0),))
    commitment, snapshot_id, snapshot_fp, current = _enumerator_proof(
        DOMAIN_WALL_LENGTH_SCALE,
        universe,
        snapshot_tag="scale-content",
    )
    mutated_payload = {
        "same_candidate_ids": [item.candidate_id for item in current.members],
        "content": "changed",
    }
    mutated_content_fp = immutable_snapshot_fingerprint(mutated_payload)
    assert mutated_content_fp != snapshot_fp
    result = verify_enumerator_snapshot_commitment(
        commitment,
        expected_scope=_scope(DOMAIN_WALL_LENGTH_SCALE),
        current_upstream_snapshot_id=snapshot_id,
        current_upstream_snapshot_fingerprint=mutated_content_fp,
        current_enumerated_universe=current,
        manifest=manifest,
        supplied_admitted_ids=tuple(item.candidate_id for item in current.members),
        current_upstream_snapshot_payload=mutated_payload,
    )
    assert result.status == AuthorityBindingStatus.STALE
    assert "enumerator_upstream_snapshot_fingerprint_stale" in result.reasons


def test_verifier_rejects_echoed_digest_without_snapshot_payload() -> None:
    universe, manifest = _candidate_proof((_identity(_wall("w1")),))
    commitment, snapshot_id, snapshot_fp, current = _enumerator_proof(
        DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
        universe,
        snapshot_tag="missing-content",
    )
    result = verify_enumerator_snapshot_commitment(
        commitment,
        expected_scope=_scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
        current_upstream_snapshot_id=snapshot_id,
        current_upstream_snapshot_fingerprint=snapshot_fp,
        current_enumerated_universe=current,
        manifest=manifest,
        supplied_admitted_ids=("w1",),
    )
    assert result.status == AuthorityBindingStatus.UNBOUND
    assert "authoritative_upstream_snapshot_content_unavailable" in result.reasons
