"""Secondary footprint / verandah width — independent red-team / test-first suite.

Base: origin/main da7a62fad2aae51bf5f35e890c14f05c4bfab8f9

Production files changed: 0.

Axes stay separate:
  F.23 width evidence ≠ authenticated secondary-footprint authority
  ≠ compound footprint CONFIRMED ≠ DPC envelope ≠ commercial publish.

EXPECTED_RED asserts eventual sealed secondary-footprint width authority and
must remain red until a reviewed production implementation lands.
Fail-closed / poison / firewall tests are expected GREEN on current main.

No benchmark IDs, project names, or expected BOQ values are used as inputs.
"""
from __future__ import annotations

import importlib.util
import re

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_multi_space_footprint_geometry import FootprintStatus
from tests.secondary_footprint_authority_test_support import (
    BASE_SHA,
    CallerSecondaryWidthProbe,
    SecondaryFootprintSelector,
    assert_no_authority_module,
    build_compound_with_caller_width,
    dpc_envelope_from_footprint,
    evaluate_redteam_attack,
    resolve_authenticated_secondary_width,
    resolve_f23_width,
    verandah_plan_pdf_bytes,
)


EXPECTED_RED = pytest.mark.xfail(
    strict=True,
    reason="SecondaryFootprintAuthority not implemented on main da7a62f",
)

SHA = "a" * 64


def _selector(**overrides: object) -> SecondaryFootprintSelector:
    kwargs = dict(
        document_id="doc-sec",
        revision_id="R1",
        source_sha256=SHA,
        snapshot_id="snap-1",
        page_id="page-1",
        viewport_id="vp_1",
        secondary_space_id="verandah-1",
    )
    kwargs.update(overrides)
    return SecondaryFootprintSelector(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Fail-closed / observed poison — GREEN on current main
# ---------------------------------------------------------------------------


def test_branch_bound_to_current_main() -> None:
    assert BASE_SHA == "da7a62fad2aae51bf5f35e890c14f05c4bfab8f9"


def test_secondary_footprint_authority_module_absent() -> None:
    assert_no_authority_module()


def test_attack_f23_evidence_resolves_without_minting_authority_module() -> None:
    """F.23 can nominate width; that is not sealed authority."""

    evidence = resolve_f23_width(verandah_plan_pdf_bytes(depth_text="1800"))
    assert evidence is not None
    assert evidence.width_m == pytest.approx(1.8)
    assert_no_authority_module()


def test_attack_caller_width_float_currently_confirms_compound_poison() -> None:
    """Document live gap: builder accepts caller float → CONFIRMED compound."""

    footprint = build_compound_with_caller_width(verandah_width_m=2.0)
    assert footprint.status == FootprintStatus.CONFIRMED.value
    assert footprint.component_areas["verandah_2"] == pytest.approx(32.0)
    envelope = dpc_envelope_from_footprint(footprint)
    assert envelope.status == "confirmed_external"
    assert_no_authority_module()


def test_attack_missing_width_stays_partial_not_guessed() -> None:
    footprint = build_compound_with_caller_width(verandah_width_m=None)
    assert footprint.status == FootprintStatus.PARTIAL_MISSING_COMPONENTS.value
    envelope = dpc_envelope_from_footprint(footprint)
    assert envelope.status != "confirmed_external"
    assert envelope.source == "wall_perimeter_fallback" or envelope.status == "fallback_wall"


def test_attack_caller_probe_flags_cannot_self_certify() -> None:
    probe = CallerSecondaryWidthProbe(
        width_m=2.0,
        label="VERANDAH",
        page_id="page-1",
        document_id="doc-sec",
        revision_id="R1",
        source_sha256=SHA,
        is_authenticated=True,
        complete=True,
        snapshot_id="snap-forged",
    )
    assert probe.is_authenticated is True
    assert_no_authority_module()


def test_attack_regex_prose_alone_is_not_f23_evidence() -> None:
    pdf = verandah_plan_pdf_bytes(
        include_depth=False,
        regex_only_prose="2,000mm wide verandah",
    )
    # Without orthogonal witnesses, F.23 must fail closed.
    assert resolve_f23_width(pdf) is None
    text = "2,000mm wide verandah"
    assert re.search(r"wide\s*veranda", text, flags=re.I)
    assert_no_authority_module()


def test_attack_one_sided_witness_fails_closed_in_f23() -> None:
    pdf = verandah_plan_pdf_bytes(omit_main_boundary_witness=True)
    assert resolve_f23_width(pdf) is None


def test_attack_competing_depths_fail_closed_in_f23() -> None:
    pdf = verandah_plan_pdf_bytes(depth_text="1800", second_depth_text="2400")
    assert resolve_f23_width(pdf) is None


def test_attack_parallel_thickness_not_width_in_f23() -> None:
    evidence = resolve_f23_width(
        verandah_plan_pdf_bytes(depth_text="1800", parallel_thickness_text="200")
    )
    assert evidence is not None
    assert evidence.width_m == pytest.approx(1.8)
    assert evidence.width_m != pytest.approx(0.2)


# ---------------------------------------------------------------------------
# EXPECTED RED — sealed secondary-footprint authority
# ---------------------------------------------------------------------------


@EXPECTED_RED
def test_attack01_authenticated_f23_width_may_resolve() -> None:
    evidence = resolve_f23_width(verandah_plan_pdf_bytes(depth_text="1800"))
    assert evidence is not None
    outcome = resolve_authenticated_secondary_width(
        selector=_selector(),
        evidence=evidence,
    )
    status = getattr(outcome, "status", None)
    assert status in {
        EvidenceResolutionStatus.CORROBORATED,
        "CORROBORATED",
        "authenticated",
    }
    assert float(getattr(outcome, "width_m", 0.0)) == pytest.approx(1.8)


@EXPECTED_RED
def test_attack02_caller_float_cannot_mint_authenticated_width() -> None:
    outcome = resolve_authenticated_secondary_width(
        selector=_selector(),
        probe=CallerSecondaryWidthProbe(
            width_m=2.0,
            label="VERANDAH",
            page_id="page-1",
            document_id="doc-sec",
            revision_id="R1",
            source_sha256=SHA,
            is_authenticated=True,
            complete=True,
        ),
    )
    status = getattr(outcome, "status", None)
    assert status not in {
        EvidenceResolutionStatus.CORROBORATED,
        "CORROBORATED",
        "authenticated",
    }
    assert getattr(outcome, "width_m", None) in (None, 0, 0.0)


@EXPECTED_RED
def test_attack03_regex_only_cannot_authenticate() -> None:
    pdf = verandah_plan_pdf_bytes(
        include_depth=False,
        regex_only_prose="2.0 m wide verandah",
    )
    outcome = evaluate_redteam_attack(
        attack_id="03_regex_only_blocked",
        selector=_selector(),
        pdf_bytes=pdf,
        regex_width_m=2.0,
    )
    assert getattr(outcome, "status", None) not in {
        EvidenceResolutionStatus.CORROBORATED,
        "CORROBORATED",
        "authenticated",
    }


@EXPECTED_RED
def test_attack04_one_sided_witness_blocked_by_authority() -> None:
    pdf = verandah_plan_pdf_bytes(omit_outer_boundary_witness=True)
    evidence = resolve_f23_width(pdf)
    outcome = resolve_authenticated_secondary_width(
        selector=_selector(),
        evidence=evidence,
        pdf_bytes=pdf,
    )
    assert getattr(outcome, "status", None) in {
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
        "ABSTAINED",
        "blocked",
        "incomplete",
    }


@EXPECTED_RED
def test_attack05_competing_orthogonal_depths_conflict() -> None:
    pdf = verandah_plan_pdf_bytes(depth_text="1800", second_depth_text="2400")
    outcome = evaluate_redteam_attack(
        attack_id="05_competing_depths_conflict",
        selector=_selector(),
        pdf_bytes=pdf,
    )
    assert getattr(outcome, "status", None) in {
        EvidenceResolutionStatus.CONFLICT,
        EvidenceResolutionStatus.ABSTAINED,
        "CONFLICT",
        "ABSTAINED",
        "blocked",
    }


@EXPECTED_RED
def test_attack06_mapping_keyed_width_is_not_authority() -> None:
    forged = {_selector().secondary_space_id: 2.0, "width_m": 2.0}
    outcome = evaluate_redteam_attack(
        attack_id="06_mapping_not_authority",
        selector=_selector(),
        width_mapping=forged,
    )
    assert getattr(outcome, "status", None) not in {
        EvidenceResolutionStatus.CORROBORATED,
        "CORROBORATED",
        "authenticated",
    }


@EXPECTED_RED
def test_attack07_compound_confirmed_requires_authenticated_width() -> None:
    """Authority must refuse CONFIRMED compound from caller float alone."""

    outcome = evaluate_redteam_attack(
        attack_id="07_compound_needs_authenticated_width",
        selector=_selector(),
        caller_verandah_width_m=2.0,
        main_length_m=16.0,
        main_width_m=8.0,
    )
    assert getattr(outcome, "footprint_status", None) != FootprintStatus.CONFIRMED.value
    assert getattr(outcome, "dpc_envelope_status", None) != "confirmed_external"


@EXPECTED_RED
def test_attack08_partial_verandah_never_promotes_dpc_compound() -> None:
    outcome = evaluate_redteam_attack(
        attack_id="08_partial_blocks_dpc_compound",
        selector=_selector(),
        caller_verandah_width_m=None,
        label_present=True,
    )
    assert getattr(outcome, "dpc_envelope_status", None) != "confirmed_external"


@EXPECTED_RED
def test_attack09_page_revision_laundering_blocked() -> None:
    evidence = resolve_f23_width(verandah_plan_pdf_bytes(depth_text="1800"))
    assert evidence is not None
    outcome = resolve_authenticated_secondary_width(
        selector=_selector(revision_id="R-OLD", page_id="page-9", source_sha256="b" * 64),
        evidence=evidence,
    )
    assert getattr(outcome, "status", None) not in {
        EvidenceResolutionStatus.CORROBORATED,
        "CORROBORATED",
        "authenticated",
    }


@EXPECTED_RED
def test_attack10_viewport_laundering_blocked() -> None:
    evidence = resolve_f23_width(verandah_plan_pdf_bytes(depth_text="1800"))
    assert evidence is not None
    outcome = resolve_authenticated_secondary_width(
        selector=_selector(viewport_id="vp_child"),
        evidence=evidence,
    )
    assert getattr(outcome, "status", None) not in {
        EvidenceResolutionStatus.CORROBORATED,
        "CORROBORATED",
        "authenticated",
    }


@EXPECTED_RED
def test_attack11_input_order_determinism() -> None:
    evidence = resolve_f23_width(verandah_plan_pdf_bytes(depth_text="1800"))
    assert evidence is not None
    results = []
    for seed in (1, 2, 3, 7, 11):
        outcome = evaluate_redteam_attack(
            attack_id="11_input_order_determinism",
            selector=_selector(),
            evidence=evidence,
            shuffle_seed=seed,
        )
        results.append(
            (
                getattr(outcome, "status", None),
                getattr(outcome, "width_m", None),
            )
        )
    assert len(set(results)) == 1


@EXPECTED_RED
def test_attack12_metamorphic_translate_scale_preserves_structure() -> None:
    widths = []
    for dx, dy, scale in ((0.0, 0.0, 1.0), (40.0, -20.0, 1.0), (0.0, 0.0, 1.5)):
        evidence = resolve_f23_width(
            verandah_plan_pdf_bytes(depth_text="1800", dx=dx, dy=dy, scale=scale)
        )
        assert evidence is not None
        outcome = resolve_authenticated_secondary_width(
            selector=_selector(snapshot_id=f"snap-{dx}-{scale}"),
            evidence=evidence,
        )
        widths.append(float(getattr(outcome, "width_m")))
    assert all(w == pytest.approx(1.8) for w in widths)


@EXPECTED_RED
def test_attack13_downstream_firewall_after_authenticated_width() -> None:
    evidence = resolve_f23_width(verandah_plan_pdf_bytes(depth_text="1800"))
    assert evidence is not None
    outcome = resolve_authenticated_secondary_width(
        selector=_selector(),
        evidence=evidence,
    )
    assert getattr(outcome, "status", None) in {
        EvidenceResolutionStatus.CORROBORATED,
        "CORROBORATED",
        "authenticated",
    }
    # Even after authenticated width, these stay closed unless separately authorized.
    caps = getattr(outcome, "downstream_capabilities", None) or {}
    for key in (
        "commercial_publish",
        "jobhub_publish",
        "firm_floor_area",
        "firm_dpc_without_envelope_review",
    ):
        assert caps.get(key, False) is False
    mod = importlib.util.find_spec("pb_secondary_footprint_authority")
    assert mod is not None
    authority = importlib.import_module("pb_secondary_footprint_authority")
    for method in (
        "publish_firm_quantity",
        "publish_commercial",
        "publish_to_jobhub",
    ):
        assert not hasattr(authority, method)
