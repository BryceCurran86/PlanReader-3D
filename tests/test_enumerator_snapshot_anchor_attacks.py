from __future__ import annotations

from pb_authority_completeness import (
    DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
    DOMAIN_WALL_LENGTH_SCALE,
)
from pb_enumerator_snapshot_commitment import (
    build_enumerator_snapshot_commitment,
    immutable_snapshot_fingerprint,
)
from pb_wall_length_quantity import build_wall_length_quantity
from tests.test_completeness_authority_attacks import _firm_single_kwargs


def test_c5_forged_commitment_plus_echoed_current_snapshot_cannot_self_certify() -> None:
    """A quantity caller must not become its own upstream wall enumerator.

    This deliberately forges *all* caller-controlled pieces consistently:
    W1-only universe, W1-only manifest, a valid commitment over that universe,
    and the same invented snapshot id/content fingerprint echoed back as the
    alleged current snapshot.  The independent upstream anchor is absent, so
    FIRM must remain impossible even though every local hash agrees.
    """
    kwargs = _firm_single_kwargs()
    universe = kwargs["candidate_universe"]
    forged_snapshot_id = "caller-invented-graph-snapshot"
    forged_snapshot_fp = immutable_snapshot_fingerprint(
        {
            "domain": DOMAIN_WALL_LENGTH_PHYSICAL_CANDIDATES,
            "caller_selected_members": [item.candidate_id for item in universe.members],
        }
    )
    forged = build_enumerator_snapshot_commitment(
        scope=universe.scope,
        enumerator_id="caller.physical-wall-enumerator",
        enumerator_version="1",
        upstream_snapshot_id=forged_snapshot_id,
        upstream_snapshot_fingerprint=forged_snapshot_fp,
        candidate_universe=universe,
    )
    kwargs.update(
        candidate_enumerator_commitment=forged,
        candidate_upstream_snapshot_id=forged_snapshot_id,
        candidate_upstream_snapshot_fingerprint=forged_snapshot_fp,
        candidate_enumerated_universe=universe,
    )

    qty = build_wall_length_quantity(**kwargs)
    assert qty.abstained is True
    assert "physical_candidate_enumerator_commitment_unavailable" in qty.blocking_reasons


def test_c1_forged_commitment_plus_echoed_current_snapshot_cannot_self_certify() -> None:
    """Same self-certification attack against the scale universe."""
    kwargs = _firm_single_kwargs()
    universe = kwargs["scale_universe"]
    forged_snapshot_id = "caller-invented-viewport-snapshot"
    forged_snapshot_fp = immutable_snapshot_fingerprint(
        {
            "domain": DOMAIN_WALL_LENGTH_SCALE,
            "caller_selected_members": [item.candidate_id for item in universe.members],
        }
    )
    forged = build_enumerator_snapshot_commitment(
        scope=universe.scope,
        enumerator_id="caller.scale-enumerator",
        enumerator_version="1",
        upstream_snapshot_id=forged_snapshot_id,
        upstream_snapshot_fingerprint=forged_snapshot_fp,
        candidate_universe=universe,
    )
    kwargs.update(
        scale_enumerator_commitment=forged,
        scale_upstream_snapshot_id=forged_snapshot_id,
        scale_upstream_snapshot_fingerprint=forged_snapshot_fp,
        scale_enumerated_universe=universe,
    )

    qty = build_wall_length_quantity(**kwargs)
    assert qty.abstained is True
    assert "scale_enumerator_commitment_unavailable" in qty.blocking_reasons
