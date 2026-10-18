"""Old a68 source representative must never be silently rekeyed by G17 shadow."""
from dataclasses import replace
import pytest

from pb_gptmax_source_representative_retention_shadow import (
    SourceSelectorWitness, compare_original_source_selector,
    RETAINED, ABSTAIN,
)

DOC = "live-source:10109b4b6e85e6e27af81f6399ce4b92"
REV = "source_revision_31b112fa62447a99d83fe3d10044d2bb"
SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
OID = "physical_opening_existence_a68d0b7d738b5de9a1588b4e680e1a8f"
OLD = "source_observation_119ef8ca51e38a54cfd660353d490774"
NEW = "source_observation_39961957b3140d852383b76b25574113"


def root():
    return SourceSelectorWitness(DOC, REV, SHA, "3", OID, OLD,
                                 (716.16, 429.36, 760.32, 429.36), True)


def alternative():
    return SourceSelectorWitness(DOC, REV, SHA, "3", OID, NEW,
                                 (692.4, 429.12, 716.16, 429.12), True)


def test_a68_original_representative_survives_additive_source_candidate():
    original, other = root(), alternative()
    r = compare_original_source_selector(original, (other, original))
    assert r["status"] == RETAINED
    assert r["retained_representative_observation_id"] == OLD
    assert r["competing_positive_selector_ids"] == [NEW]
    assert not any(r[key] for key in ("host_granted", "frame_granted", "quantity_granted", "count_granted"))
    assert r == compare_original_source_selector(original, (original, other))


def test_a68_representative_disappears_or_abstains_in_new_policy():
    original, other = root(), alternative()
    for changed in ((other,), (replace(original, existence_corroborated=False), other)):
        r = compare_original_source_selector(original, changed)
        assert r["status"] == ABSTAIN
        assert r["retained_representative_observation_id"] is None
        assert r["reason_codes"] == ["original_representative_no_longer_positive"]


def test_reusing_old_observation_with_different_source_geometry_abstains():
    original = root()
    newer = replace(original, geometry_pt=(692.4, 429.12, 716.16, 429.12))
    r = compare_original_source_selector(original, (newer,))
    assert r["status"] == ABSTAIN
    assert r["reason_codes"] == ["original_representative_source_geometry_changed"]


def test_duplicate_conflicting_receipt_or_foreign_identity_fails_closed():
    original = root()
    with pytest.raises(ValueError, match="contradictory"):
        compare_original_source_selector(original, (original, replace(original, existence_corroborated=False)))
    for foreign in (replace(original, source_sha256="f" * 64),
                    replace(original, revision_id="other"),
                    replace(original, page_id="5"),
                    replace(original, physical_opening_id="physical_opening_existence_" + "1" * 32)):
        with pytest.raises(ValueError, match="foreign"):
            compare_original_source_selector(original, (foreign,))


def test_malformed_witness_and_mutable_list_not_accepted():
    original = root()
    with pytest.raises(TypeError, match="tuple"):
        compare_original_source_selector(original, [original])
    with pytest.raises(ValueError, match="malformed"):
        compare_original_source_selector(replace(original, existence_corroborated=1), (original,))
    with pytest.raises(ValueError, match="positive"):
        compare_original_source_selector(replace(original, existence_corroborated=False), (original,))
    with pytest.raises(ValueError, match="malformed"):
        compare_original_source_selector(original, (replace(original, geometry_pt=(float("nan"), 0., 0., 0.)),))
