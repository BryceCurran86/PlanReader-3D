"""Opening Dimension Authority — independent red-team / test-first suite.

Base: merged G17 main 62a161519e617cdf9ce23069820dbf7c68aaf521

Production files changed: 0.
Opening identity production (PR #331) is out of scope.

Axes stay separate: existence ≠ identity ≠ width ≠ height ≠ type ≠ host.

Tests marked EXPECTED_RED assert eventual positive dimension authority and
must remain red until a reviewed production implementation lands.
Fail-closed / poison / firewall tests are expected GREEN on current main.
"""
from __future__ import annotations

from dataclasses import fields
import importlib.util

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_deduction_v175 import parse_opening_dimensions
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningAuthority,
)
from pb_source_observation_authority import ObservationSelector
from tests.opening_dimensions_test_support import (
    BASE_SHA,
    LEGACY_DEFAULT_HEIGHT_MM,
    LEGACY_DEFAULT_WIDTH_MM,
    OpeningDimensionProbe,
    assert_dimension_capability_locked,
    figure_witness_opening_pdf_bytes,
    ingest_visible,
    schedule_only_pdf_bytes,
    visible_opening_pdf_bytes,
)


EXPECTED_RED = pytest.mark.xfail(
    strict=True,
    reason="OpeningDimensionAuthority not implemented on main 62a1615",
)


def _has_opening_dimension_authority_module() -> bool:
    return importlib.util.find_spec("pb_opening_dimension_authority") is not None


def _selector(published, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )


def _positive_existence(physical, published):
    results = [
        physical.prove_existence(_selector(published, oid))
        for oid in published.visible_observation_ids
    ]
    positives = [r for r in results if r.proposition == PHYSICAL_OPENING_EXISTS]
    assert positives, "visible opening fixture must prove G17 existence"
    return positives[0]


# ---------------------------------------------------------------------------
# Fail-closed / observed poison — GREEN on current main
# ---------------------------------------------------------------------------


def test_branch_bound_to_merged_g17_main() -> None:
    assert BASE_SHA == "62a161519e617cdf9ce23069820dbf7c68aaf521"


def test_opening_dimensions_capability_remains_false() -> None:
    assert_dimension_capability_locked()
    assert _has_opening_dimension_authority_module() is False


def test_attack_legacy_empty_parse_invents_standard_door_poison() -> None:
    """Document unsafe default; Opening Dimension Authority must never reuse it."""

    h_mm, w_mm = parse_opening_dimensions("")
    assert h_mm == LEGACY_DEFAULT_HEIGHT_MM
    assert w_mm == LEGACY_DEFAULT_WIDTH_MM
    h2, w2 = parse_opening_dimensions("not-a-size")
    assert h2 == LEGACY_DEFAULT_HEIGHT_MM
    assert w2 == LEGACY_DEFAULT_WIDTH_MM


def test_attack_existence_alone_does_not_invent_dimensions() -> None:
    _, published, _, physical = ingest_visible(
        visible_opening_pdf_bytes(),
        document_id="odim-existence-no-dims",
    )
    result = _positive_existence(physical, published)
    assert result.existence_record is not None
    names = {f.name for f in fields(result.existence_record)}
    assert names.isdisjoint({"width", "height", "width_mm", "height_mm", "width_m", "height_m"})
    assert_dimension_capability_locked(physical)


def test_attack_schedule_only_does_not_prove_existence_or_unlock_dimensions() -> None:
    _, published, _, physical = ingest_visible(
        schedule_only_pdf_bytes(("D-01 900 x 2100", "D-02 820 x 2040")),
        document_id="odim-schedule-only",
    )
    results = [
        physical.prove_existence(_selector(published, oid))
        for oid in published.visible_observation_ids
    ]
    assert all(r.proposition != PHYSICAL_OPENING_EXISTS for r in results)
    assert_dimension_capability_locked(physical)


def test_attack_nearby_dimension_text_without_authority_is_not_firm() -> None:
    """Attack 11 class: '900' near opening is not authoritative on current main."""

    _, published, _, physical = ingest_visible(
        visible_opening_pdf_bytes(dimension_text="900"),
        document_id="odim-text-near",
    )
    result = _positive_existence(physical, published)
    assert result.existence_record is not None
    assert_dimension_capability_locked(physical)


def test_attack_caller_constructed_dimension_probe_cannot_self_certify() -> None:
    probe = OpeningDimensionProbe(
        opening_id="caller-door-1",
        width_mm=900.0,
        height_mm=2100.0,
        tag="D-01",
        page_id="1",
        document_id="doc-odim",
        geometry=(100.0, 100.0, 140.0, 110.0),
        source_ids=("ev-1", "ev-2"),
    )
    # No production API may accept this body as authority. Module absent ⇒ locked.
    assert _has_opening_dimension_authority_module() is False
    assert probe.width_mm == 900.0  # looks plausible — still not authority
    assert_dimension_capability_locked()


def test_attack_downstream_firewall_after_existence() -> None:
    _, published, _, physical = ingest_visible(
        visible_opening_pdf_bytes(),
        document_id="odim-firewall",
    )
    _positive_existence(physical, published)
    caps = physical.capabilities()
    assert caps == {
        "physical_opening_existence": True,
        "physical_opening_identity": False,
        "opening_universe_complete": False,
        "opening_dimensions": False,
        "host_identity": False,
        "host_binding": False,
        "physical_void": False,
        "net_wall_area": False,
    }
    for method in (
        "resolve_opening_width",
        "resolve_opening_height",
        "deduct_wall_area",
        "publish_firm_quantity",
        "publish_commercial",
        "publish_to_jobhub",
    ):
        assert not hasattr(physical, method)


def test_attack_metamorphic_existence_fixture_still_dimension_locked() -> None:
    for angle, scale, offset in (
        (0.0, 1.0, (0.0, 0.0)),
        (90.0, 1.0, (350.0, 20.0)),
        (0.0, 2.0, (40.0, 30.0)),
    ):
        _, published, _, physical = ingest_visible(
            visible_opening_pdf_bytes(angle_deg=angle, scale=scale, offset=offset),
            document_id=f"odim-meta-{angle}-{scale}",
        )
        _positive_existence(physical, published)
        assert_dimension_capability_locked(physical)


# ---------------------------------------------------------------------------
# EXPECTED RED — positive dimension authority not yet implemented
# ---------------------------------------------------------------------------


@EXPECTED_RED
def test_attack01_figured_width_with_valid_witnesses_resolves_width() -> None:
    """Attack 1: figured width with jamb witnesses → authoritative width."""

    assert _has_opening_dimension_authority_module()
    from pb_opening_dimension_authority import OpeningDimensionAuthority  # type: ignore

    _, published, visibility, physical = ingest_visible(
        figure_witness_opening_pdf_bytes(width_label="900", with_witness_lines=True),
        document_id="odim-a1-witness-width",
    )
    existence = _positive_existence(physical, published)
    authority = OpeningDimensionAuthority(visibility)
    width = authority.resolve_width(existence.existence_record)
    height = authority.resolve_height(existence.existence_record)
    assert width.status is EvidenceResolutionStatus.CORROBORATED
    assert width.value_mm == pytest.approx(900.0)
    assert height.status is not EvidenceResolutionStatus.CORROBORATED


@EXPECTED_RED
def test_attack02_width_known_height_unknown_independent() -> None:
    assert _has_opening_dimension_authority_module()
    from pb_opening_dimension_authority import OpeningDimensionAuthority  # type: ignore

    _, published, visibility, physical = ingest_visible(
        figure_witness_opening_pdf_bytes(width_label="900", with_witness_lines=True),
        document_id="odim-a2-width-only",
    )
    existence = _positive_existence(physical, published)
    authority = OpeningDimensionAuthority(visibility)
    assert authority.resolve_width(existence.existence_record).status is EvidenceResolutionStatus.CORROBORATED
    height = authority.resolve_height(existence.existence_record)
    assert height.status in {
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.BLOCKED,
        EvidenceResolutionStatus.RAW,
    } or height.value_mm is None


@EXPECTED_RED
def test_attack03_height_from_authenticated_elevation_independent() -> None:
    assert _has_opening_dimension_authority_module()
    from pb_opening_dimension_authority import OpeningDimensionAuthority  # type: ignore

    authority = OpeningDimensionAuthority  # noqa: F841 — production must prove elev path
    raise AssertionError("elevation/detail height path not implemented")


@EXPECTED_RED
def test_attack04_schedule_only_dimensions_cannot_bind_instance() -> None:
    assert _has_opening_dimension_authority_module()
    from pb_opening_dimension_authority import OpeningDimensionAuthority  # type: ignore

    _, published, visibility, physical = ingest_visible(
        schedule_only_pdf_bytes(("D-01 900 x 2100",)),
        document_id="odim-a4-schedule",
    )
    authority = OpeningDimensionAuthority(visibility)
    # No existence → no instance width assignment from schedule alone.
    for oid in published.visible_observation_ids:
        result = physical.prove_existence(_selector(published, oid))
        assert result.existence_record is None
        bound = authority.try_bind_schedule_dimensions(tag="D-01", width_mm=900, height_mm=2100)
        assert bound.status is not EvidenceResolutionStatus.CORROBORATED


@EXPECTED_RED
def test_attack05_repeated_d01_cannot_collapse_instances() -> None:
    assert _has_opening_dimension_authority_module()
    raise AssertionError("multi-instance D-01 schedule collapse guard not implemented")


@EXPECTED_RED
def test_attack06_plan_vs_schedule_width_conflict_blocks() -> None:
    assert _has_opening_dimension_authority_module()
    raise AssertionError("plan vs schedule conflict resolver not implemented")


@EXPECTED_RED
def test_attack07_plan_vs_elevation_conflict_blocks() -> None:
    assert _has_opening_dimension_authority_module()
    raise AssertionError("plan vs elevation conflict resolver not implemented")


@EXPECTED_RED
def test_attack08_chained_dimensions_require_witness_topology() -> None:
    assert _has_opening_dimension_authority_module()
    raise AssertionError("dimension-chain opening binding not implemented")


@EXPECTED_RED
def test_attack09_rotated_dimension_binding_stable() -> None:
    assert _has_opening_dimension_authority_module()
    raise AssertionError("rotated figured-width binding not implemented")


@EXPECTED_RED
def test_attack10_witness_obstruction_no_nearest_hit() -> None:
    assert _has_opening_dimension_authority_module()
    from pb_opening_dimension_authority import OpeningDimensionAuthority  # type: ignore

    _, published, visibility, physical = ingest_visible(
        figure_witness_opening_pdf_bytes(with_witness_lines=True, obstructing_furniture=True),
        document_id="odim-a10-obstruction",
    )
    existence = _positive_existence(physical, published)
    width = OpeningDimensionAuthority(visibility).resolve_width(existence.existence_record)
    assert width.status is not EvidenceResolutionStatus.CORROBORATED


@EXPECTED_RED
def test_attack11_dimension_text_without_witnesses_not_authoritative() -> None:
    assert _has_opening_dimension_authority_module()
    from pb_opening_dimension_authority import OpeningDimensionAuthority  # type: ignore

    _, published, visibility, physical = ingest_visible(
        figure_witness_opening_pdf_bytes(width_label="900", with_witness_lines=False),
        document_id="odim-a11-text-only",
    )
    existence = _positive_existence(physical, published)
    width = OpeningDimensionAuthority(visibility).resolve_width(existence.existence_record)
    assert width.status is not EvidenceResolutionStatus.CORROBORATED


@EXPECTED_RED
def test_attack12_witnesses_without_numeric_text_leave_quantity_unresolved() -> None:
    assert _has_opening_dimension_authority_module()
    raise AssertionError("witness-only unresolved quantity path not implemented")


@EXPECTED_RED
def test_attack13_ocr_dimension_keeps_separate_provenance() -> None:
    assert _has_opening_dimension_authority_module()
    raise AssertionError("OCR dimension provenance separation not implemented")


@EXPECTED_RED
def test_attack14_garbled_cmap_native_text_cannot_firm() -> None:
    """Coordinate with GitHub issue #330 — corrupt native text must fail closed."""

    assert _has_opening_dimension_authority_module()
    raise AssertionError("CMap/ToUnicode garbled-text fail-closed path not implemented")


@EXPECTED_RED
def test_attack15_geometric_gap_requires_authoritative_scale() -> None:
    assert _has_opening_dimension_authority_module()
    raise AssertionError("scale-backed opening width path not implemented")


@EXPECTED_RED
def test_attack16_competing_scales_block() -> None:
    assert _has_opening_dimension_authority_module()
    raise AssertionError("competing page/viewport scale block not implemented")


@EXPECTED_RED
def test_attack17_source_space_span_is_not_physical_width() -> None:
    assert _has_opening_dimension_authority_module()
    raise AssertionError("source-space vs physical-width distinction not implemented")


@EXPECTED_RED
def test_attack18_curved_or_angled_opening_uses_local_axis() -> None:
    assert _has_opening_dimension_authority_module()
    raise AssertionError("local-axis opening dimension not implemented")


@EXPECTED_RED
def test_attack19_double_leaf_semantics_not_substituted() -> None:
    assert _has_opening_dimension_authority_module()
    raise AssertionError("clear vs leaf vs rough opening semantics not implemented")


@EXPECTED_RED
def test_attack20_sliding_multipanel_semantics_explicit() -> None:
    assert _has_opening_dimension_authority_module()
    raise AssertionError("sliding/multi-panel dimension semantics not implemented")


@EXPECTED_RED
def test_attack21_arched_opening_width_and_max_height_independent() -> None:
    assert _has_opening_dimension_authority_module()
    raise AssertionError("arched opening independent axes not implemented")


@EXPECTED_RED
def test_attack22_section_only_height_does_not_invent_width() -> None:
    assert _has_opening_dimension_authority_module()
    raise AssertionError("section-only height independence not implemented")


@EXPECTED_RED
def test_attack23_page_revision_laundering_blocked() -> None:
    assert _has_opening_dimension_authority_module()
    raise AssertionError("page/revision laundering guards for dimensions not implemented")


@EXPECTED_RED
def test_attack24_viewport_laundering_blocked() -> None:
    assert _has_opening_dimension_authority_module()
    raise AssertionError("viewport laundering guards for dimensions not implemented")


@EXPECTED_RED
def test_attack25_input_order_determinism() -> None:
    assert _has_opening_dimension_authority_module()
    raise AssertionError("dimension input-order determinism not implemented")


@EXPECTED_RED
def test_attack26_metamorphic_binding_preserves_structure() -> None:
    assert _has_opening_dimension_authority_module()
    raise AssertionError("metamorphic dimension binding not implemented")


@EXPECTED_RED
def test_attack27_ambiguous_figured_candidates_conflict() -> None:
    assert _has_opening_dimension_authority_module()
    raise AssertionError("ambiguous figured-dimension CONFLICT path not implemented")


@EXPECTED_RED
def test_attack28_downstream_firewall_after_dimensions_resolve() -> None:
    assert _has_opening_dimension_authority_module()
    from pb_opening_dimension_authority import OpeningDimensionAuthority  # type: ignore

    _, published, visibility, physical = ingest_visible(
        figure_witness_opening_pdf_bytes(with_witness_lines=True),
        document_id="odim-a28-firewall",
    )
    existence = _positive_existence(physical, published)
    authority = OpeningDimensionAuthority(visibility)
    width = authority.resolve_width(existence.existence_record)
    assert width.status is EvidenceResolutionStatus.CORROBORATED
    # Even after width resolves, these stay closed unless separately authorized.
    caps = physical.capabilities()
    assert caps["host_binding"] is False
    assert caps["opening_universe_complete"] is False
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False
    for method in (
        "deduct_wall_area",
        "publish_firm_quantity",
        "publish_commercial",
        "publish_to_jobhub",
    ):
        assert not hasattr(physical, method)
        assert not hasattr(authority, method)
