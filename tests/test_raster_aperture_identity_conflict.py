"""Competing detector extents cannot manufacture distinct physical identities."""
import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_physical_opening_authority import (
    AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES, PhysicalOpeningAuthority,
)
from test_raster_connected_host_frame import _fixture


def _candidates(**kwargs):
    source, _composition, _frames, bound = _fixture(**kwargs)
    authority = PhysicalOpeningAuthority.from_source_visibility_producer(source)
    selector = bound[0][0]
    receipt = authority.source_visibility_authority().resolve_raster_opening_primitive(selector)
    records, failures = authority._raster_primitive_snapshot_records(receipt)
    assert not failures
    candidates = authority._raster_framed_candidates_for(receipt.observation, records)
    candidates = sorted(candidates, key=lambda c: authority._raster_candidate_gap_box_cache[c.candidate_id])
    selectors = tuple(next(row[0] for row in bound
        if row[0].observation_id in c.source_observation_ids) for c in candidates)
    return authority, candidates, selectors


@pytest.mark.parametrize('mode', ['partial', 'contained'])
@pytest.mark.parametrize('kwargs', [{}, {'rotation': 1}, {'scale': 2}, {'dx': 35, 'dy': 20}])
def test_overlapping_unequal_detector_apertures_remain_conflicting_hypotheses(kwargs, mode):
    authority, candidates, selectors = _candidates(**kwargs)
    # Inject a future detector extent variant into its derived candidate output;
    # immutable source observations/receipts stay unchanged. This is a negative
    # consumer proof, not a claim that the real source contains two overlaps.
    first = authority._raster_candidate_gap_box_cache[candidates[0].candidate_id]
    shift = min(first[2] - first[0], first[3] - first[1]) / 4
    authority._raster_candidate_gap_box_cache[candidates[1].candidate_id] = (
        first[0] + shift, first[1],
        first[2] + shift if mode == 'partial' else first[2] - shift, first[3])
    before = dict(authority._raster_candidate_gap_box_cache)
    results = tuple(authority.prove_existence(s) for s in selectors)
    assert all(r.status is Status.CONFLICT and r.existence_record is None for r in results)
    assert all(r.reason_codes == (AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES,) for r in results)
    assert {r.candidate.candidate_id for r in results} == {c.candidate_id for c in candidates}
    comparison = authority.compare_identity(*selectors)
    assert comparison.status is Status.CONFLICT and not comparison.proven_same
    assert authority._raster_candidate_gap_box_cache == before
    assert tuple(authority.prove_existence(s) for s in reversed(selectors)) == tuple(reversed(results))
    closure = authority.assess_raster_candidate_closure(selectors[0])
    assert not closure.candidate_universe_complete
    assert closure.resolved_candidate_count == 0


def test_separated_source_apertures_keep_distinct_stable_identities_and_provenance():
    authority, _candidates_, selectors = _candidates()
    before = dict(authority._raster_candidate_gap_box_cache)
    results = tuple(authority.prove_existence(s) for s in selectors)
    assert all(r.status is Status.CORROBORATED for r in results)
    assert len({r.existence_record.record_id for r in results}) == 2
    assert authority.compare_identity(*selectors).physical_opening_identity == 'physical_opening_identities_distinct'
    for s, r in zip(selectors, results):
        assert r.existence_record.source_sha256 == s.source_sha256
        assert r.existence_record.snapshot_id == s.snapshot_id
        assert s.observation_id in r.existence_record.source_observation_ids
    assert authority._raster_candidate_gap_box_cache == before
