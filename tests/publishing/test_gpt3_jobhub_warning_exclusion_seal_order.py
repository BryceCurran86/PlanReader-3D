"""Full-evidence JobHub seal must ignore arrival order, not source content.

Synthetic FIRM rows exercise SQLite gate mechanics only: no original-PDF,
customer release or frozen V2 authority is established by these tests.
"""
from copy import deepcopy

import pytest

from pb_jobhub_publishing_contract import (
    ExcludedScopePayload,
    PublishingMode,
    PublishingWarningPayload,
    validate_publishing_gate,
)
from pb_jobhub_publishing_pipeline import (
    build_publishing_package_from_workspace,
    execute_jobhub_publishing,
)
from test_publishing_pipeline_e2e import test_dbs  # noqa: F401


def _firm_source_neutral_row(conn):
    conn.execute(
        """
        INSERT INTO takeoff_rows (
            id, workspace_id, section, location, substrate, finish_tag,
            element, unit, quantity, rate, total_price,
            commercial_authority_status, commercial_authority_source,
            commercial_authority_reviewed_by
        ) VALUES (
            1, 1, 'Internal walls', 'Level 1', 'Plasterboard', 'PB01',
            'Measured wall', 'm2', 1.25, 20.0, 25.0, 'firm',
            'documented_dimension', 'Estimator A'
        )
        """
    )
    conn.commit()


def _package(conn, *, mode=PublishingMode.COMMERCIAL):
    package = build_publishing_package_from_workspace(
        conn, 1, mode,
        preflight_fingerprint="source-neutral-warning-multiset",
        acting_user="Estimator A",
    )
    # The distinct exclusions intentionally share an item code. Sorting only
    # by item_code leaves their original arrival order in the full SHA.
    package.excluded_items = [
        ExcludedScopePayload(
            item_code="X1", description="Roof soffit", reason="Explicit source exclusion",
            trade="Roofing",
        ),
        ExcludedScopePayload(
            item_code="X1", description="External sealant", reason="Separate source exclusion",
            trade="Sealants",
        ),
    ]
    package.warnings = [
        PublishingWarningPayload(
            code="SOURCE_NOTE_A", severity="Info",
            message="First source-neutral advisory", source_family="drawings",
        ),
        PublishingWarningPayload(
            code="SOURCE_NOTE_B", severity="Warning",
            message="Second source-neutral advisory", source_family="finish",
        ),
    ]
    package.payload_hash = package.compute_payload_hash()
    return package


@pytest.mark.parametrize("reverse_warnings,reverse_exclusions", [
    (False, True), (True, False), (True, True),
])
def test_same_full_evidence_multiset_deduplicates_in_real_jobhub(
    test_dbs, reverse_warnings, reverse_exclusions,
):
    planreader, jobhub, bridge = test_dbs
    _firm_source_neutral_row(planreader)
    original = _package(planreader)
    reordered = deepcopy(original)
    if reverse_warnings:
        reordered.warnings.reverse()
    if reverse_exclusions:
        reordered.excluded_items.reverse()

    before_original = original.to_dict()
    before_reordered = reordered.to_dict()
    assert original.compute_payload_hash() == reordered.compute_payload_hash()
    assert original.payload_hash == reordered.payload_hash
    assert validate_publishing_gate(original).is_publishable
    assert validate_publishing_gate(reordered).is_publishable

    receipt = execute_jobhub_publishing(original, bridge, "Estimator A")
    assert receipt["status"] == "Published"
    assert receipt["total_lines"] == 1
    assert original.to_dict() == before_original
    assert reordered.to_dict() == before_reordered
    with pytest.raises(RuntimeError, match="Duplicate package"):
        execute_jobhub_publishing(reordered, bridge, "Estimator A")
    assert jobhub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_packages"
    ).fetchone()[0] == 1
    assert jobhub.execute(
        "SELECT COUNT(*) FROM painting_takeoff_package_lines"
    ).fetchone()[0] == 1


@pytest.mark.parametrize("field,value", [
    ("warning_message", "A genuinely different original advisory"),
    ("warning_severity", "Blocker"),
    ("warning_source_family", "different-source-family"),
    ("excluded_reason", "Changed original exclusion evidence"),
    ("excluded_trade", "Other trade"),
    ("excluded_description", "Changed physical excluded scope"),
])
def test_content_mutation_still_invalidates_sealed_full_evidence(
    test_dbs, field, value,
):
    planreader, jobhub, bridge = test_dbs
    _firm_source_neutral_row(planreader)
    package = _package(planreader)
    original_hash = package.payload_hash
    if field == "warning_message":
        package.warnings[0].message = value
    elif field == "warning_severity":
        package.warnings[0].severity = value
    elif field == "warning_source_family":
        package.warnings[0].source_family = value
    elif field == "excluded_reason":
        package.excluded_items[0].reason = value
    elif field == "excluded_trade":
        package.excluded_items[0].trade = value
    else:
        package.excluded_items[0].description = value

    assert package.compute_payload_hash() != original_hash
    gate = validate_publishing_gate(package)
    assert not gate.is_publishable
    assert any("TOCTOU violation" in reason for reason in gate.blocking_reasons)
    with pytest.raises(RuntimeError, match="Publishing blocked"):
        execute_jobhub_publishing(package, bridge, "Estimator A")
    assert jobhub.execute("SELECT COUNT(*) FROM painting_takeoff_packages").fetchone()[0] == 0


def test_repeated_identical_warning_and_exclusion_remain_sealed(test_dbs):
    planreader, _, _ = test_dbs
    _firm_source_neutral_row(planreader)
    package = _package(planreader)
    original_hash = package.payload_hash
    package.warnings.append(deepcopy(package.warnings[0]))
    assert package.compute_payload_hash() != original_hash
    package.payload_hash = package.compute_payload_hash()
    one_more = package.payload_hash
    package.excluded_items.append(deepcopy(package.excluded_items[0]))
    assert package.compute_payload_hash() != one_more


def test_commercial_blocker_still_abstains_and_draft_warning_remains_visible(test_dbs):
    planreader, jobhub, bridge = test_dbs
    _firm_source_neutral_row(planreader)
    commercial = _package(planreader)
    commercial.warnings[0].severity = "Blocker"
    commercial.payload_hash = commercial.compute_payload_hash()
    gate = validate_publishing_gate(commercial)
    assert not gate.is_publishable
    assert any("Unresolved commercial source issue" in x for x in gate.blocking_reasons)
    with pytest.raises(RuntimeError, match="Publishing blocked"):
        execute_jobhub_publishing(commercial, bridge, "Estimator A")
    assert jobhub.execute("SELECT COUNT(*) FROM painting_takeoff_packages").fetchone()[0] == 0

    draft = _package(planreader, mode=PublishingMode.DRAFT)
    draft.warnings[0].severity = "Blocker"
    draft.payload_hash = draft.compute_payload_hash()
    draft_gate = validate_publishing_gate(draft)
    assert draft_gate.is_publishable
    assert any("SOURCE_NOTE_A" in w for w in draft_gate.warnings)
    receipt = execute_jobhub_publishing(draft, bridge, "Estimator A")
    assert receipt["status"] == "Draft"
