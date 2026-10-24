"""tests/geometry/test_page_scale_calibration_authority.py — Per-page scale calibration status
and conflict handling.

Covers: each page carrying its own isolated ScaleCalibration record, ratio-to-px_per_m
conversion, conflict detection across disagreeing scale sources, the fail-closed status
taxonomy (valid/provisional/unknown/conflicting/manual_required/user_approved/blocked),
the resulting measurement-authority gate, and issue-list preservation for downstream
publish gates.
"""
from __future__ import annotations

import math

import pytest

from pb_geometry_takeoff_model import AuthorityStatus, ScaleCalibration
from pb_page_scale_calibration_authority import (
    POINTS_PER_METRE_AT_1_1,
    PageScaleCalibrationRegistry,
    ScaleCalibrationStatus,
    ScaleSourceReading,
    ScaleSourceType,
    approve_page_scale_calibration,
    check_calibration_freshness,
    measurement_authority_for_page_scale,
    px_per_m_from_ratio,
    resolve_page_scale_calibration,
    unknown_calibration,
)


# ---------------------------------------------------------------------------
# Ratio -> px_per_m conversion, per page, no leakage
# ---------------------------------------------------------------------------

class TestRatioConversionAndIsolation:
    def test_page1_scale_1_100_converts_correctly(self):
        calib = resolve_page_scale_calibration(
            page_no=1,
            sheet_label="A-101",
            readings=[ScaleSourceReading(source_type=ScaleSourceType.SCALE_BAR.value, scale_text="1:100", ratio=100.0, confidence=0.95)],
        )
        assert calib.page_no == 1
        assert calib.ratio_str == "1:100"
        assert calib.px_per_m == pytest.approx(POINTS_PER_METRE_AT_1_1 / 100.0)

    def test_page2_scale_1_50_converts_correctly(self):
        calib = resolve_page_scale_calibration(
            page_no=2,
            sheet_label="A-102",
            readings=[ScaleSourceReading(source_type=ScaleSourceType.SCALE_BAR.value, scale_text="1:50", ratio=50.0, confidence=0.95)],
        )
        assert calib.page_no == 2
        assert calib.ratio_str == "1:50"
        assert calib.px_per_m == pytest.approx(POINTS_PER_METRE_AT_1_1 / 50.0)

    def test_page1_scale_does_not_leak_to_page2(self):
        registry = PageScaleCalibrationRegistry()
        calib1 = resolve_page_scale_calibration(
            page_no=1,
            sheet_label="A-101",
            readings=[ScaleSourceReading(source_type=ScaleSourceType.SCALE_BAR.value, scale_text="1:100", ratio=100.0, confidence=0.95)],
        )
        registry.set(1, calib1)

        # Page 2 has never been given a reading.
        assert registry.get(2) is None

        calib2 = resolve_page_scale_calibration(
            page_no=2,
            sheet_label="A-102",
            readings=[ScaleSourceReading(source_type=ScaleSourceType.SCALE_BAR.value, scale_text="1:50", ratio=50.0, confidence=0.95)],
        )
        registry.set(2, calib2)

        assert registry.get(1).px_per_m == pytest.approx(POINTS_PER_METRE_AT_1_1 / 100.0)
        assert registry.get(2).px_per_m == pytest.approx(POINTS_PER_METRE_AT_1_1 / 50.0)
        assert registry.get(1).px_per_m != registry.get(2).px_per_m

        # Mutating page 1's record must not be visible through page 2's.
        registry.set(1, unknown_calibration(page_no=1, sheet_label="A-101"))
        assert registry.get(1).status == ScaleCalibrationStatus.UNKNOWN.value
        assert registry.get(2).status == ScaleCalibrationStatus.VALID.value


class TestPxPerMFromRatio:
    def test_ratio_100_matches_established_precedent(self):
        # 28.35 px/m at 1:100 is the value already used in test_scale_and_figured_dimensions.py.
        assert px_per_m_from_ratio(100.0) == pytest.approx(28.35, abs=0.01)

    @pytest.mark.parametrize("bad_ratio", [0.0, -50.0, math.nan, math.inf, -math.inf])
    def test_invalid_ratio_raises(self, bad_ratio):
        with pytest.raises(ValueError):
            px_per_m_from_ratio(bad_ratio)


# ---------------------------------------------------------------------------
# Unknown scale blocks commercial measurement
# ---------------------------------------------------------------------------

class TestUnknownScaleBlocks:
    def test_no_readings_produces_unknown_status(self):
        calib = resolve_page_scale_calibration(page_no=3, sheet_label="A-103", readings=[])
        assert calib.status == ScaleCalibrationStatus.UNKNOWN.value

    def test_unknown_page_scale_blocks_commercial_measurement(self):
        calib = resolve_page_scale_calibration(page_no=3, sheet_label="A-103", readings=[])
        assert measurement_authority_for_page_scale(calib) == AuthorityStatus.BLOCKED.value


# ---------------------------------------------------------------------------
# Conflicting sources -> manual_required
# ---------------------------------------------------------------------------

class TestConflictHandling:
    def test_conflicting_title_block_and_scale_bar_produce_manual_required(self):
        calib = resolve_page_scale_calibration(
            page_no=4,
            sheet_label="A-104",
            readings=[
                ScaleSourceReading(source_type=ScaleSourceType.TITLE_BLOCK.value, scale_text="1:100", ratio=100.0, confidence=0.6),
                ScaleSourceReading(source_type=ScaleSourceType.SCALE_BAR.value, scale_text="1:50", ratio=50.0, confidence=0.9),
            ],
        )
        assert calib.status == ScaleCalibrationStatus.MANUAL_REQUIRED.value
        assert calib.ratio_str == "UNKNOWN"
        assert calib.px_per_m == 0.0
        assert measurement_authority_for_page_scale(calib) == AuthorityStatus.BLOCKED.value
        assert len(calib.issues) >= 1

    def test_agreeing_sources_within_tolerance_resolve_valid(self):
        calib = resolve_page_scale_calibration(
            page_no=5,
            sheet_label="A-105",
            readings=[
                ScaleSourceReading(source_type=ScaleSourceType.TITLE_BLOCK.value, scale_text="1:100", ratio=100.0, confidence=0.6),
                ScaleSourceReading(source_type=ScaleSourceType.SCALE_BAR.value, scale_text="1:101", ratio=101.0, confidence=0.9),
            ],
        )
        assert calib.status == ScaleCalibrationStatus.VALID.value

    def test_conflicting_inferred_only_sources_produce_conflicting_not_manual_required(self):
        calib = resolve_page_scale_calibration(
            page_no=6,
            sheet_label="A-106",
            readings=[
                ScaleSourceReading(source_type=ScaleSourceType.INFERRED.value, scale_text="~1:100", ratio=100.0, confidence=0.3),
                ScaleSourceReading(source_type=ScaleSourceType.INFERRED.value, scale_text="~1:150", ratio=150.0, confidence=0.3),
            ],
        )
        assert calib.status == ScaleCalibrationStatus.CONFLICTING.value
        assert measurement_authority_for_page_scale(calib) == AuthorityStatus.BLOCKED.value


# ---------------------------------------------------------------------------
# Valid title-block scale is still only provisional for measurement
# ---------------------------------------------------------------------------

class TestTitleBlockAlwaysProvisional:
    def test_valid_title_block_scale_produces_provisional_measurement(self):
        calib = resolve_page_scale_calibration(
            page_no=7,
            sheet_label="A-107",
            readings=[ScaleSourceReading(source_type=ScaleSourceType.TITLE_BLOCK.value, scale_text="1:100", ratio=100.0, confidence=0.7)],
        )
        assert calib.status == ScaleCalibrationStatus.VALID.value
        assert measurement_authority_for_page_scale(calib) == AuthorityStatus.PROVISIONAL.value

    def test_valid_scale_bar_scale_can_be_firm(self):
        calib = resolve_page_scale_calibration(
            page_no=8,
            sheet_label="A-108",
            readings=[ScaleSourceReading(source_type=ScaleSourceType.SCALE_BAR.value, scale_text="1:100", ratio=100.0, confidence=0.95)],
        )
        assert calib.status == ScaleCalibrationStatus.VALID.value
        assert measurement_authority_for_page_scale(calib) == AuthorityStatus.FIRM.value


# ---------------------------------------------------------------------------
# User-approved calibration authority
# ---------------------------------------------------------------------------

class TestUserApproval:
    def test_user_approved_calibration_produces_approved_authority_status(self):
        conflicted = resolve_page_scale_calibration(
            page_no=9,
            sheet_label="A-109",
            readings=[
                ScaleSourceReading(source_type=ScaleSourceType.TITLE_BLOCK.value, scale_text="1:100", ratio=100.0, confidence=0.6),
                ScaleSourceReading(source_type=ScaleSourceType.SCALE_BAR.value, scale_text="1:50", ratio=50.0, confidence=0.9),
            ],
        )
        assert conflicted.status == ScaleCalibrationStatus.MANUAL_REQUIRED.value

        approved = approve_page_scale_calibration(
            conflicted, approved_ratio=100.0, approved_by="Estimator A"
        )
        assert approved.status == ScaleCalibrationStatus.USER_APPROVED.value
        assert approved.approved_by == "Estimator A"
        assert measurement_authority_for_page_scale(approved) == AuthorityStatus.FIRM.value

    def test_approval_preserves_original_issue_list(self):
        conflicted = resolve_page_scale_calibration(
            page_no=10,
            sheet_label="A-110",
            readings=[
                ScaleSourceReading(source_type=ScaleSourceType.TITLE_BLOCK.value, scale_text="1:100", ratio=100.0, confidence=0.6),
                ScaleSourceReading(source_type=ScaleSourceType.SCALE_BAR.value, scale_text="1:50", ratio=50.0, confidence=0.9),
            ],
        )
        original_issues = list(conflicted.issues)
        approved = approve_page_scale_calibration(conflicted, approved_ratio=100.0, approved_by="Estimator A")
        for issue in original_issues:
            assert issue in approved.issues

    @pytest.mark.parametrize("bad_ratio", [0.0, -1.0, math.nan, math.inf])
    def test_approval_rejects_invalid_ratio(self, bad_ratio):
        calib = unknown_calibration(page_no=11, sheet_label="A-111")
        with pytest.raises(ValueError):
            approve_page_scale_calibration(calib, approved_ratio=bad_ratio, approved_by="Estimator A")


# ---------------------------------------------------------------------------
# NaN / inf / zero scale readings block
# ---------------------------------------------------------------------------

class TestNonFiniteScaleBlocks:
    @pytest.mark.parametrize("bad_ratio", [math.nan, math.inf, -math.inf, 0.0, -100.0])
    def test_nan_inf_zero_negative_ratio_blocks(self, bad_ratio):
        calib = resolve_page_scale_calibration(
            page_no=12,
            sheet_label="A-112",
            readings=[ScaleSourceReading(source_type=ScaleSourceType.SCALE_BAR.value, scale_text="bad", ratio=bad_ratio, confidence=0.9)],
        )
        assert calib.status == ScaleCalibrationStatus.BLOCKED.value
        assert measurement_authority_for_page_scale(calib) == AuthorityStatus.BLOCKED.value
        assert len(calib.issues) >= 1


# ---------------------------------------------------------------------------
# Stale / revision-mismatched calibration blocks
# ---------------------------------------------------------------------------

class TestStaleRevisionBlocks:
    def test_stale_revision_mismatch_blocks(self):
        calib = resolve_page_scale_calibration(
            page_no=13,
            sheet_label="A-113",
            readings=[ScaleSourceReading(source_type=ScaleSourceType.SCALE_BAR.value, scale_text="1:100", ratio=100.0, confidence=0.95)],
            revision_id="Rev-A",
        )
        assert calib.status == ScaleCalibrationStatus.VALID.value

        fresh = check_calibration_freshness(calib, current_revision_id="Rev-A")
        assert fresh.status == ScaleCalibrationStatus.VALID.value

        stale = check_calibration_freshness(calib, current_revision_id="Rev-B")
        assert stale.status == ScaleCalibrationStatus.BLOCKED.value
        assert measurement_authority_for_page_scale(stale) == AuthorityStatus.BLOCKED.value
        assert any("stale" in issue.lower() or "revision" in issue.lower() for issue in stale.issues)

    def test_unknown_current_revision_does_not_force_stale(self):
        calib = resolve_page_scale_calibration(
            page_no=14,
            sheet_label="A-114",
            readings=[ScaleSourceReading(source_type=ScaleSourceType.SCALE_BAR.value, scale_text="1:100", ratio=100.0, confidence=0.95)],
            revision_id=None,
        )
        unchanged = check_calibration_freshness(calib, current_revision_id="Rev-Z")
        assert unchanged.status == ScaleCalibrationStatus.VALID.value


# ---------------------------------------------------------------------------
# Issue list is preserved for downstream publish gates
# ---------------------------------------------------------------------------

class TestIssueListPreservedForPublishGates:
    def test_conflict_issue_list_survives_registry_round_trip(self):
        registry = PageScaleCalibrationRegistry()
        calib = resolve_page_scale_calibration(
            page_no=15,
            sheet_label="A-115",
            readings=[
                ScaleSourceReading(source_type=ScaleSourceType.TITLE_BLOCK.value, scale_text="1:100", ratio=100.0, confidence=0.6),
                ScaleSourceReading(source_type=ScaleSourceType.SCALE_BAR.value, scale_text="1:50", ratio=50.0, confidence=0.9),
            ],
        )
        registry.set(15, calib)
        fetched = registry.get(15)
        assert fetched.issues == calib.issues
        assert len(fetched.issues) >= 1

    def test_every_calibration_record_carries_required_fields(self):
        calib = resolve_page_scale_calibration(
            page_no=16,
            sheet_label="A-116 Floor Plan",
            readings=[ScaleSourceReading(source_type=ScaleSourceType.SCALE_BAR.value, scale_text="1:100", ratio=100.0, confidence=0.95)],
        )
        assert isinstance(calib, ScaleCalibration)
        assert calib.page_no == 16
        assert calib.sheet_label == "A-116 Floor Plan"
        assert calib.scale_text == "1:100"
        assert calib.ratio_str == "1:100"
        assert 0.0 <= calib.confidence <= 1.0
        assert calib.source_type in {s.value for s in ScaleSourceType}
        assert calib.status in {s.value for s in ScaleCalibrationStatus}
        assert isinstance(calib.issues, list)


# ---------------------------------------------------------------------------
# Selection must never depend on input order; unknown sources and degenerate inputs never reach FIRM
# ---------------------------------------------------------------------------

import copy
from decimal import Decimal
from itertools import permutations

from pb_page_scale_calibration_authority import scale_calibration_fingerprint

SB, TB = ScaleSourceType.SCALE_BAR.value, ScaleSourceType.TITLE_BLOCK.value
MAN, INF = ScaleSourceType.MANUAL.value, ScaleSourceType.INFERRED.value


def _r(source, ratio, confidence=1.0, text=None):
    return ScaleSourceReading(source, text if text is not None else f"1:{ratio:g}", ratio, confidence)


def _resolve(readings, **kwargs):
    return resolve_page_scale_calibration(page_no=1, sheet_label="A-101", readings=list(readings), **kwargs)


def _authority(calibration):
    return measurement_authority_for_page_scale(calibration)


class TestEqualConfidenceTiesAreNeverOrderedByInput:
    @pytest.mark.parametrize(
        "readings",
        [
            [_r(TB, 100.0, 0.9), _r(SB, 104.0, 0.9)],                       # was PROVISIONAL or FIRM by order
            [_r(INF, 100.0), _r(SB, 104.0)],
            [_r(TB, 100.0), _r(SB, 100.0)],                                 # agreeing ratios, different sources
            [_r(TB, 100.0, 0.9), _r(SB, 102.0, 0.9), _r(INF, 101.0, 0.9)],
            [_r(SB, 100.0), _r(SB, 104.0)],                                 # was FIRM 1:100 or FIRM 1:104 by order
            [_r(MAN, 100.0), _r(MAN, 104.0)],
        ],
    )
    def test_every_permutation_gives_the_identical_blocked_record(self, readings):
        records = [_resolve(list(order)) for order in permutations(readings)]
        assert all(record == records[0] for record in records)
        assert len({scale_calibration_fingerprint(record) for record in records}) == 1
        first = records[0]
        assert first.status in {ScaleCalibrationStatus.MANUAL_REQUIRED.value, ScaleCalibrationStatus.CONFLICTING.value}
        assert first.px_per_m == 0.0 and first.ratio_str == "UNKNOWN"
        assert _authority(first) == AuthorityStatus.BLOCKED.value
        assert any("depend on input order" in issue for issue in first.issues)

    @pytest.mark.parametrize(
        "readings",
        [
            [_r(SB, 100.0), _r(MAN, 100.0)],                       # both FIRM at the same ratio: the choice cannot matter
            [_r(SB, 100.0, text="1:100"), _r(SB, 100.0, text="1 : 100")],
        ],
    )
    def test_ties_that_give_the_same_firm_authority_and_scale_are_ordered_deterministically(self, readings):
        records = [_resolve(list(order)) for order in permutations(readings)]
        assert all(record == records[0] for record in records)
        assert _authority(records[0]) == AuthorityStatus.FIRM.value
        assert records[0].px_per_m == pytest.approx(POINTS_PER_METRE_AT_1_1 / 100.0)

    @pytest.mark.parametrize("order", [(0, 1), (1, 0)])
    def test_title_block_plus_an_inferred_reading_stays_provisional_in_either_order(self, order):
        # Neither can be FIRM and both map to PROVISIONAL, so the pick cannot change the authority (an existing
        # behaviour pinned by test_figured_span_scale_shadow).
        readings = [_r(TB, 100.0), _r(INF, 100.0)]
        record = _resolve([readings[i] for i in order])
        assert record.status in {ScaleCalibrationStatus.VALID.value, ScaleCalibrationStatus.PROVISIONAL.value}
        assert _authority(record) == AuthorityStatus.PROVISIONAL.value
        assert record.px_per_m == pytest.approx(POINTS_PER_METRE_AT_1_1 / 100.0)

    def test_a_tie_involving_an_authoritative_source_needs_manual_resolution(self):
        assert _resolve([_r(TB, 100.0), _r(SB, 104.0)]).status == ScaleCalibrationStatus.MANUAL_REQUIRED.value

    def test_a_tie_between_non_authoritative_sources_is_conflicting(self):
        record = _resolve([_r(INF, 100.0), _r(ScaleSourceType.UNKNOWN.value, 101.0)])
        assert record.status == ScaleCalibrationStatus.CONFLICTING.value

    def test_a_blocked_tie_is_resolved_by_estimator_approval_not_by_order(self):
        blocked = _resolve([_r(SB, 100.0), _r(SB, 104.0)])
        approved = approve_page_scale_calibration(blocked, 100.0, "estimator")
        assert _authority(approved) == AuthorityStatus.FIRM.value

    @pytest.mark.parametrize("order", [(0, 1), (1, 0)])
    def test_a_real_confidence_difference_still_selects_the_stronger_reading(self, order):
        readings = [_r(SB, 100.0, 0.9), _r(TB, 102.0, 0.6)]
        record = _resolve([readings[i] for i in order])
        assert record.status == ScaleCalibrationStatus.VALID.value
        assert record.source_type == SB and record.ratio_str == "1:100"
        assert _authority(record) == AuthorityStatus.FIRM.value

    @pytest.mark.parametrize("order", [(0, 1), (1, 0)])
    def test_equivalent_readings_with_different_labels_give_one_record(self, order):
        readings = [_r(SB, 100.0, text="1:100"), _r(SB, 100.0, text="1 : 100")]
        record = _resolve([readings[i] for i in order])
        assert record == _resolve(readings)
        assert _authority(record) == AuthorityStatus.FIRM.value and record.px_per_m == pytest.approx(
            POINTS_PER_METRE_AT_1_1 / 100.0
        )

    def test_same_source_non_firm_ties_keep_their_existing_provisional_result(self):
        # Inferred and title-block readings can never be FIRM, and the production producers (cross-view room area,
        # raster plan dimensions, viewport conflict readings) rely on this exact outcome, so it is preserved.
        inferred = _resolve([_r(INF, 100.0), _r(INF, 101.0)])
        assert inferred.status == ScaleCalibrationStatus.PROVISIONAL.value
        assert inferred.ratio_str == "1:100" and _authority(inferred) == AuthorityStatus.PROVISIONAL.value
        title_block = _resolve([_r(TB, 100.0, 0.5), _r(TB, 102.0, 0.5)])
        assert title_block.status == ScaleCalibrationStatus.VALID.value
        assert title_block.ratio_str == "1:100" and _authority(title_block) == AuthorityStatus.PROVISIONAL.value

    def test_beyond_tolerance_conflict_label_is_deterministic_on_a_confidence_tie(self):
        readings = [_r(TB, 50.0), _r(SB, 100.0)]
        records = [_resolve(list(order)) for order in permutations(readings)]
        assert {record.status for record in records} == {ScaleCalibrationStatus.MANUAL_REQUIRED.value}
        assert {record.source_type for record in records} == {SB}
        assert {_authority(record) for record in records} == {AuthorityStatus.BLOCKED.value}

    def test_single_producer_shaped_readings_are_unchanged(self):
        bridge = _resolve([_r(SB, 100.0, 1.0, text="1:100")])
        assert bridge.status == ScaleCalibrationStatus.VALID.value and _authority(bridge) == AuthorityStatus.FIRM.value
        viewport = _resolve([_r(TB, 100.0, 0.5)])
        assert viewport.status == ScaleCalibrationStatus.VALID.value
        assert _authority(viewport) == AuthorityStatus.PROVISIONAL.value

    def test_resolution_is_deterministic_and_does_not_mutate_the_readings(self):
        readings = [_r(TB, 100.0, 0.9), _r(SB, 104.0, 0.9)]
        before = copy.deepcopy(readings)
        assert _resolve(readings) == _resolve(readings)
        assert readings == before


class TestUnrecognisedSourcesNeverReachFirm:
    @pytest.mark.parametrize("source", ["ai", "default", "assumed", "Title_Block", "TITLE_BLOCK", "ocr_text", "", " scale_bar", None, 5])
    def test_a_single_reading_from_an_unknown_source_is_blocked(self, source):
        record = _resolve([ScaleSourceReading(source, "1:100", 100.0, 1.0)])
        assert record.status == ScaleCalibrationStatus.BLOCKED.value
        assert _authority(record) == AuthorityStatus.BLOCKED.value
        assert record.px_per_m == 0.0
        assert any("unrecognised source type" in issue for issue in record.issues)

    @pytest.mark.parametrize("source", list(ScaleSourceType))
    def test_every_known_source_is_still_accepted_as_a_string_or_enum_member(self, source):
        for value in (source.value, source):
            record = _resolve([ScaleSourceReading(value, "1:100", 100.0, 1.0)])
            assert not any("unrecognised" in issue for issue in record.issues)
            assert record.px_per_m == pytest.approx(POINTS_PER_METRE_AT_1_1 / 100.0)

    def test_known_sources_keep_their_authority_mapping(self):
        expected = {
            SB: AuthorityStatus.FIRM.value,
            MAN: AuthorityStatus.FIRM.value,
            TB: AuthorityStatus.PROVISIONAL.value,
            INF: AuthorityStatus.PROVISIONAL.value,
            ScaleSourceType.UNKNOWN.value: AuthorityStatus.BLOCKED.value,
        }
        for source, authority in expected.items():
            assert _authority(_resolve([_r(source, 100.0)])) == authority, source

    def test_an_unknown_source_never_takes_part_in_a_comparison(self):
        for order in permutations([_r("ai", 100.0, 1.0), _r(TB, 100.0, 0.5)]):
            record = _resolve(list(order))
            assert record.source_type == TB and _authority(record) == AuthorityStatus.PROVISIONAL.value
            assert any("unrecognised source type" in issue for issue in record.issues)


class TestNonFiniteConfidenceAndToleranceFailClosed:
    @pytest.mark.parametrize("confidence", [float("nan"), float("inf"), float("-inf"), True, None, "0.9"])
    def test_a_reading_with_an_unusable_confidence_is_rejected_in_every_order(self, confidence):
        bad = _r(TB, 100.0, confidence)
        good = _r(SB, 102.0, 0.9)
        records = [_resolve(list(order)) for order in permutations([bad, good])]
        assert records[0].issues == records[1].issues and records[0].ratio_str == records[1].ratio_str
        assert all(record.source_type == SB and _authority(record) == AuthorityStatus.FIRM.value for record in records)
        assert any("non-finite confidence" in issue for issue in records[0].issues)

    def test_a_lone_reading_with_a_nan_confidence_is_blocked(self):
        record = _resolve([_r(SB, 100.0, float("nan"))])
        assert record.status == ScaleCalibrationStatus.BLOCKED.value
        assert _authority(record) == AuthorityStatus.BLOCKED.value

    @pytest.mark.parametrize("tolerance", [float("nan"), float("inf"), -0.1, True, None, "0.05"])
    def test_an_unusable_comparison_tolerance_blocks_instead_of_accepting_disagreeing_sources(self, tolerance):
        record = _resolve([_r(SB, 50.0), _r(SB, 100.0, 0.5)], max_delta_ratio=tolerance)
        assert record.status == ScaleCalibrationStatus.BLOCKED.value
        assert _authority(record) == AuthorityStatus.BLOCKED.value
        assert any("comparison tolerance" in issue for issue in record.issues)

    def test_the_tolerance_is_irrelevant_for_a_single_reading_and_zero_means_exact_agreement(self):
        assert _authority(_resolve([_r(SB, 100.0)], max_delta_ratio=float("nan"))) == AuthorityStatus.FIRM.value
        exact = _resolve([_r(SB, 100.0), _r(SB, 100.0, 0.5)], max_delta_ratio=0)
        assert _authority(exact) == AuthorityStatus.FIRM.value
        loose = _resolve([_r(SB, 100.0), _r(SB, 101.0, 0.5)], max_delta_ratio=0)
        assert loose.status == ScaleCalibrationStatus.MANUAL_REQUIRED.value


class TestDegenerateRatiosFailClosed:
    @pytest.mark.parametrize("ratio", [1e-310, 5e-324, True, Decimal("100"), "100", 1 + 2j])
    def test_a_degenerate_or_non_real_ratio_is_rejected(self, ratio):
        record = _resolve([ScaleSourceReading(SB, "1:100", ratio, 1.0)])
        assert record.status == ScaleCalibrationStatus.BLOCKED.value
        assert _authority(record) == AuthorityStatus.BLOCKED.value
        assert record.px_per_m == 0.0

    @pytest.mark.parametrize("ratio", [1e-310, 5e-324, True])
    def test_px_per_m_from_ratio_refuses_degenerate_input(self, ratio):
        with pytest.raises(ValueError):
            px_per_m_from_ratio(ratio)

    def test_approval_with_a_degenerate_ratio_is_refused(self):
        with pytest.raises(ValueError):
            approve_page_scale_calibration(_resolve([_r(SB, 100.0)]), 1e-310, "estimator")

    def test_numpy_scalars_remain_valid_ratios(self):
        numpy = pytest.importorskip("numpy")
        record = _resolve([ScaleSourceReading(SB, "1:100", numpy.float64(100.0), numpy.float64(1.0))])
        assert _authority(record) == AuthorityStatus.FIRM.value
        assert record.px_per_m == pytest.approx(POINTS_PER_METRE_AT_1_1 / 100.0)
