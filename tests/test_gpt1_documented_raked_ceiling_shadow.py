"""Raked ceiling m2 requires original figured plan and source pitch."""
from dataclasses import replace
import math

from pb_gpt1_figured_chain_metric_shadow import (
    FiguredPhysicalSide, measure_figured_room_edge_chain_shadow,
)
from pb_gpt1_documented_raked_ceiling_shadow import (
    DocumentedSourceCeilingPitch, measure_figured_raked_ceiling_shadow,
)
from pb_migration_contracts import EvidenceResolutionStatus


def _footprint():
    ring = ((0, 0), (10, 0), (10, 5), (0, 5))
    sides = []
    for n, start in enumerate(ring):
        value = {0: 5000, 1: 2000}.get(n)
        sides.append(FiguredPhysicalSide(
            f"wall-{n}", start, ring[(n+1) % 4], (f"ink-{n}",),
            value, f"figured-{n}" if value is not None else None,
            (f"witness-{n}-a", f"witness-{n}-b") if value is not None else (),
        ))
    return measure_figured_room_edge_chain_shadow(
        tuple(sides), source_sha256="a"*64,
        revision_id="rev1", page_id="3", physical_room_id="room-1",
    )


def _pitch(**kwargs):
    values = dict(
        physical_ceiling_surface_id="ceiling-1",
        source_pitch_evidence_ids=("original-pitch-ink",),
        source_sha256="a"*64, revision_id="rev1", page_id="3",
        slope_degrees=12.0,
    )
    values.update(kwargs)
    return DocumentedSourceCeilingPitch(**values)


def test_original_figured_roof_pitch_adjusts_horizontal_m2_only_if_present():
    result = measure_figured_raked_ceiling_shadow(_footprint(), _pitch())
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.original_plan_area_m2 == 10.0
    assert math.isclose(
        result.candidate_surface_m2, 10.0 / math.cos(math.radians(12)),
        rel_tol=1e-12,
    )
    assert result.diagnostic_only is True


def test_original_rise_and_run_independently_prove_same_pitch():
    value = math.tan(math.radians(12)) * 5000
    out = measure_figured_raked_ceiling_shadow(
        _footprint(), _pitch(documented_rise_mm=value, documented_run_mm=5000)
    )
    assert out.status is EvidenceResolutionStatus.CANDIDATE


def test_source_rise_run_without_angle_can_determine_surface_area():
    out = measure_figured_raked_ceiling_shadow(
        _footprint(), _pitch(slope_degrees=None,
                             documented_rise_mm=1000, documented_run_mm=5000)
    )
    assert out.status is EvidenceResolutionStatus.CANDIDATE
    assert math.isclose(out.candidate_surface_m2, 10 * math.sqrt(26) / 5)


def test_flat_can_be_used_only_when_source_explicitly_says_zero_pitch():
    out = measure_figured_raked_ceiling_shadow(_footprint(), _pitch(slope_degrees=0))
    assert out.status is EvidenceResolutionStatus.CANDIDATE
    assert out.candidate_surface_m2 == 10.0


def test_absent_original_pitch_stays_unmeasured_not_zero():
    out = measure_figured_raked_ceiling_shadow(_footprint(), _pitch(slope_degrees=None))
    assert out.status is EvidenceResolutionStatus.ABSTAINED
    assert out.candidate_surface_m2 is None


def test_foreign_sheet_or_revision_cannot_launder_pitch_into_ceiling():
    for bad in (
        _pitch(page_id="4"), _pitch(revision_id="old"),
        _pitch(source_sha256="b"*64),
    ):
        out = measure_figured_raked_ceiling_shadow(_footprint(), bad)
        assert out.status is EvidenceResolutionStatus.ABSTAINED


def test_competing_original_pitches_never_select_one_by_preference():
    out = measure_figured_raked_ceiling_shadow(
        _footprint(), _pitch(documented_rise_mm=1000, documented_run_mm=1000)
    )
    assert out.status is EvidenceResolutionStatus.ABSTAINED
    assert out.reason_codes == ("original_raked_pitch_competing_figures",)


def test_pitch_is_categorical_evidence_not_inferred_from_paint_or_default():
    for wrong in (None, True, "12", -1, 90, float("nan")):
        out = measure_figured_raked_ceiling_shadow(
            _footprint(), _pitch(slope_degrees=wrong)
        )
        assert out.status is EvidenceResolutionStatus.ABSTAINED
