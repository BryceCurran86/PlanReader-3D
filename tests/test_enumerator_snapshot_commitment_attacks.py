from __future__ import annotations

from pb_authority_completeness import (
    DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
    DOMAIN_WALL_LENGTH_SCALE,
    build_authority_universe,
    physical_wall_identity_member,
    scale_binding_member,
)
from pb_wall_length_quantity import build_wall_length_quantity
from tests.test_completeness_authority_attacks import (
    _binding,
    _firm_single_kwargs,
    _identity,
    _scope,
    _wall,
)


def test_c5_self_consistent_truncated_wall_universe_cannot_certify_itself() -> None:
    """Real enumerator has W1+W2; caller presents a perfectly consistent W1-only proof."""
    kwargs = _firm_single_kwargs()
    admitted_identity = kwargs["physical_identity_universe"][0]
    hidden_wall = _wall("w2", y=25.0)
    hidden_identity = _identity(hidden_wall)
    authoritative_universe = build_authority_universe(
        _scope(DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES),
        (
            physical_wall_identity_member(admitted_identity),
            physical_wall_identity_member(hidden_identity),
        ),
    )
    assert authoritative_universe.fingerprint != kwargs["candidate_universe"].fingerprint

    # Attack: the quantity caller supplies only W1 plus a self-consistent W1-only
    # AuthorityUniverseFingerprint + CompletenessManifest.  That must never be
    # sufficient evidence that the upstream enumerator contained only W1.
    qty = build_wall_length_quantity(**kwargs)
    assert qty.abstained is True
    assert "physical_candidate_enumerator_commitment_unavailable" in qty.blocking_reasons


def test_c1_self_consistent_truncated_scale_universe_cannot_certify_itself() -> None:
    """Real scale enumerator has S1+S2; caller presents a consistent S1-only proof."""
    kwargs = _firm_single_kwargs()
    admitted = kwargs["scale_bindings"][0]
    hidden = _binding(50.0, label="A102-hidden")
    authoritative_universe = build_authority_universe(
        _scope(DOMAIN_WALL_LENGTH_SCALE),
        (scale_binding_member(admitted), scale_binding_member(hidden)),
    )
    assert authoritative_universe.fingerprint != kwargs["scale_universe"].fingerprint

    qty = build_wall_length_quantity(**kwargs)
    assert qty.abstained is True
    assert "scale_enumerator_commitment_unavailable" in qty.blocking_reasons
