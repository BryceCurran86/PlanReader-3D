"""Tests for cavity slider vs push-pull paired door discriminator shadow (Item 19)."""
from __future__ import annotations

import math
from pathlib import Path
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
import pb_source_cavity_slider_vs_push_pull_shadow as cspp
from tools.audit_no_job_specific_shared_rules import audit_shared_source

_SHA = "4" * 64


def _rot(pt: tuple[float, float], deg: float, dx: float, dy: float) -> tuple[float, float]:
    rad = math.radians(deg)
    c, s = math.cos(rad), math.sin(rad)
    return (pt[0] * c - pt[1] * s + dx, pt[0] * s + pt[1] * c + dy)


def _obs(**kwargs) -> cspp.DoorApertureSymbolObservation:
    base = dict(
        opening_id="op-1",
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256=_SHA,
        page_id="7",
        viewport_id="vp-plan",
        host_wall_id="wall-1",
        jamb_a=(100.0, 200.0),
        jamb_b=(140.0, 200.0),
        wall_thickness_pt=6.0,
    )
    base.update(kwargs)
    return cspp.DoorApertureSymbolObservation(**base)


def test_single_and_biparting_cavity_slider_detected_with_rotation_invariance() -> None:
    single = _obs(
        opening_id="op-csd-1",
        leaf_segments=(((102.0, 200.0), (138.0, 200.0)),),
        pocket_recess_segments=(((60.0, 200.0), (100.0, 200.0)),),
        text_cues=("CSD",),
    )
    res = cspp.classify_door_operation_cues(single)
    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert res.classification == cspp.CLASS_CAVITY_SLIDER
    assert res.subtype == cspp.SUBTYPE_SINGLE_CAVITY_SLIDER
    assert res.pocket_side_count == 1
    assert res.retains_wall_continuity_over_pocket is True
    assert res.wall_cut_excludes_pocket is True
    assert res.commercial_authority_granted is False
    assert res.opening_kind_authority_granted is False

    # Metamorphic rotation & translation invariance across 90/180/270 degrees
    for deg, dx, dy in ((90.0, 50.0, 10.0), (180.0, 300.0, 250.0), (270.0, -40.0, 120.0)):
        rotated = _obs(
            opening_id="op-csd-1",
            jamb_a=_rot((100.0, 200.0), deg, dx, dy),
            jamb_b=_rot((140.0, 200.0), deg, dx, dy),
            leaf_segments=((_rot((102.0, 200.0), deg, dx, dy), _rot((138.0, 200.0), deg, dx, dy)),),
            pocket_recess_segments=((_rot((60.0, 200.0), deg, dx, dy), _rot((100.0, 200.0), deg, dx, dy)),),
            text_cues=("CSD",),
        )
        r_out = cspp.classify_door_operation_cues(rotated)
        assert r_out == res

    # Bi-parting double cavity slider (pockets on both sides)
    bipart = _obs(
        opening_id="op-csd-2",
        leaf_segments=(((101.0, 200.0), (120.0, 200.0)), ((120.0, 200.0), (139.0, 200.0))),
        pocket_recess_segments=(
            ((75.0, 200.0), (100.0, 200.0)),
            ((140.0, 200.0), (165.0, 200.0)),
        ),
    )
    r_bi = cspp.classify_door_operation_cues(bipart)
    assert r_bi.classification == cspp.CLASS_CAVITY_SLIDER
    assert r_bi.subtype == cspp.SUBTYPE_BIPARTING_CAVITY_SLIDER
    assert r_bi.pocket_side_count == 2


def test_push_pull_paired_and_double_action_doors_separated_from_sliders() -> None:
    paired = _obs(
        opening_id="op-pair-1",
        leaf_segments=(
            ((100.0, 200.0), (100.0, 220.0)),
            ((140.0, 200.0), (140.0, 220.0)),
        ),
        swing_arcs=(
            cspp.SwingArcCue("a1", (100.0, 200.0), (114.0, 214.0), 20.0, 90.0),
            cspp.SwingArcCue("a2", (140.0, 200.0), (126.0, 214.0), 20.0, 90.0),
        ),
        text_cues=("PUSH/PULL",),
    )
    res_pair = cspp.classify_door_operation_cues(paired)
    assert res_pair.status == EvidenceResolutionStatus.CORROBORATED
    assert res_pair.classification == cspp.CLASS_PUSH_PULL_PAIRED
    assert res_pair.subtype == cspp.SUBTYPE_PAIRED_DOUBLE_SWING
    assert res_pair.retains_wall_continuity_over_pocket is False
    assert res_pair.wall_cut_excludes_pocket is False

    # Double-action push/pull swinging to BOTH sides (+n and -n)
    double_action = _obs(
        opening_id="op-da-1",
        swing_arcs=(
            cspp.SwingArcCue("a1", (100.0, 200.0), (125.0, 225.0), 36.0, 90.0),
            cspp.SwingArcCue("a2", (100.0, 200.0), (125.0, 175.0), 36.0, 90.0),
        ),
    )
    res_da = cspp.classify_door_operation_cues(double_action)
    assert res_da.classification == cspp.CLASS_PUSH_PULL_PAIRED
    assert res_da.subtype == cspp.SUBTYPE_DOUBLE_ACTION_PUSH_PULL
    assert res_da.swing_sides_occupied == 2


def test_hybrid_text_contradiction_and_text_only_negatives_fail_closed() -> None:
    # Hybrid pocket + swing arc -> CONFLICT
    hybrid = _obs(
        leaf_segments=(((102.0, 200.0), (138.0, 200.0)),),
        pocket_recess_segments=(((60.0, 200.0), (100.0, 200.0)),),
        swing_arcs=(cspp.SwingArcCue("a1", (100.0, 200.0), (125.0, 225.0), 36.0, 90.0),),
    )
    res_h = cspp.classify_door_operation_cues(hybrid)
    assert res_h.status == EvidenceResolutionStatus.CONFLICT
    assert "hybrid_slider_and_swing_cues_conflict" in res_h.reason_codes

    # Slider geometry with contradicting PUSH/PULL text -> CONFLICT
    clash = _obs(
        leaf_segments=(((102.0, 200.0), (138.0, 200.0)),),
        pocket_recess_segments=(((60.0, 200.0), (100.0, 200.0)),),
        text_cues=("PUSH/PULL",),
    )
    res_c = cspp.classify_door_operation_cues(clash)
    assert res_c.status == EvidenceResolutionStatus.CONFLICT
    assert "text_vs_geometry_operation_conflict" in res_c.reason_codes

    # Text cue alone without geometry -> ABSTAINED
    text_only = _obs(text_cues=("CAVITY SLIDER",))
    res_t = cspp.classify_door_operation_cues(text_only)
    assert res_t.status == EvidenceResolutionStatus.ABSTAINED
    assert res_t.classification == cspp.CLASS_ABSTAINED

    mod_path = Path(cspp.__file__)
    assert audit_shared_source(mod_path.read_text(encoding="utf-8"), filename=mod_path.name) == ()
