"""Supplemental fail-closed control for host ambiguity repair.

TEST-ONLY / DO NOT MERGE.
"""
from pb_migration_contracts import EvidenceResolutionStatus
import pb_opening_host_binding_authority as host

from tests.test_host_binding_remote_ambiguity_gpt2_redteam_v1 import (
    OPENING,
    _base_records,
    _equivalence,
)


def test_relevant_ambiguous_id_without_pair_explanation_fails_closed() -> None:
    """A repair must not turn incomplete equivalence metadata into authority."""
    records = _base_records()
    result = host._resolve_host_bands(
        records,
        OPENING,
        _equivalence(
            records,
            pairs=(),
            ambiguous_ids=("left-top",),
        ),
    )

    assert result.status in {
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
    }
    assert result.bands == ()
    assert set(result.reason_codes) & {
        host.HOST_EQUIVALENCE_AMBIGUOUS,
        host.HOST_EQUIVALENCE_UNAVAILABLE,
    }
