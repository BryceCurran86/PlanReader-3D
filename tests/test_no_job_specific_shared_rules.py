"""Owner regression: shared PlanReader policies must not select one job."""
from __future__ import annotations

from pathlib import Path

from tools.audit_no_job_specific_shared_rules import (
    KNOWN_LEGACY_UNIVERSALISATION_BLOCKERS,
    SHARED_PRODUCTION_RULES,
    audit_paths,
    audit_shared_source,
)


def test_shared_original_production_rules_have_no_named_job_selectors():
    root = Path(__file__).resolve().parents[1]
    violations = audit_paths(root)
    assert not violations, (
        "Shared PlanReader geometry/customer policy cannot depend on a fixed "
        "job/source SHA; move any specific source fixture to its evidence "
        "adapter, generalize shared producer and test on unrelated drawings: "
        + repr(violations[:20])
    )


def test_direct_project_name_conditions_and_functions_are_rejected():
    source = (
        "def measure_maryborough_office(room_label):\n"
        "    if room_label == 'OFFICE' and q5446_enabled:\n"
        "        return 'Acacia'\n"
    )
    found = audit_shared_source(source, filename="pb_shared.py")
    assert {f.kind for f in found} >= {"declaration", "identifier", "constant"}
    assert any("maryborough" in f.literal for f in found)
    assert any("q5446" in f.literal for f in found)


def test_hardcoded_original_sha_cannot_turn_into_shared_algo_selector():
    source = (
        "def accept_source(source_sha256):\n"
        "    return source_sha256 == '" + "a" * 64 + "'\n"
    )
    assert any(f.kind == "constant" for f in audit_shared_source(
        source, filename="pb_generic.py",
    ))


def test_job_names_in_docstrings_and_comments_are_safe_examples():
    source = (
        '"""Original source examples: Acacia, Maryborough and Lot16."""\n'
        "def source_neutral(document):\n"
        '    """Q5446 is a test job only, not a selector."""\n'
        "    # Never hardcode a 3Laurel room identity.\n"
        "    return bool(document)\n"
    )
    assert audit_shared_source(source, filename="pb_generic.py") == ()


def test_arbitrary_source_identity_as_input_is_safe():
    source = (
        "def host_wall(document, sha, page_id, paths):\n"
        "    if not sha or not page_id:\n"
        "        return None\n"
        "    return (document, sha, paths)\n"
    )
    assert audit_shared_source(source, filename="pb_generic.py") == ()


def test_known_legacy_cross_view_maryborough_shortcuts_are_not_mistaken_for_fixes():
    assert "pb_source_cross_view_floor_correspondence_shadow.py" in (
        KNOWN_LEGACY_UNIVERSALISATION_BLOCKERS
    )
    assert not set(KNOWN_LEGACY_UNIVERSALISATION_BLOCKERS) & set(
        SHARED_PRODUCTION_RULES
    )
    root = Path(__file__).resolve().parents[1]
    # Existing legacy technical debt remains an explicit independent
    # generalisation blocker, tracked by owner issue #4594. A future fix may
    # make this empty; the test must *not* require it to remain broken.
    _found = audit_paths(root, KNOWN_LEGACY_UNIVERSALISATION_BLOCKERS)
    assert isinstance(_found, tuple)
