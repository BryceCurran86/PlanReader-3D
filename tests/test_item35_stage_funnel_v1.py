"""Item 35 stage funnel: diagnostic-only, gold-free, never an authority.

The funnel consumes the dict returned by ``collect_item35_authority_shadow``.
These tests pin what it may report (only stages the shadow exposes), what it
must leave unobserved (per-opening existence / identity / host binding), and
that it can neither run an authority nor unlock commercial output.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import MappingProxyType

import fitz
import pytest

from pb_generic_opening_count_authority import (
    GENERIC_OPENING_COUNT_COMPLETENESS_NOT_SOURCE_AUTHENTICATED,
    GENERIC_OPENING_COUNT_RESOLVED,
    GENERIC_OPENING_COUNT_VIEWPORT_CLASS_UNAVAILABLE,
)
from pb_item35_production_authority_shadow import (
    ITEM35_PRODUCTION_SHADOW_SCHEMA_VERSION,
    collect_item35_authority_shadow,
    empty_item35_authority_shadow,
)
from pb_item35_stage_funnel import (
    NOT_OBSERVED_IDENTITY_NOT_EXPOSED,
    NOT_OBSERVED_SEMANTIC_RECORD_ABSENT,
    NOT_OBSERVED_SHADOW_NOT_COLLECTED,
    NOT_OBSERVED_SHADOW_SCOPE_ABSENT,
    OBSERVABLE_STAGES,
    REVIEWED_ITEM35_SHADOW_KEYS,
    STAGE_GENERIC_COUNT_PUBLICATION,
    STAGE_OPENING_HOST_BINDING,
    STAGE_PHYSICAL_OPENING_EXISTENCE,
    STAGE_PHYSICAL_OPENING_IDENTITY,
    STAGE_PHYSICAL_OPENING_UNIVERSE_COMPLETENESS,
    STAGE_SEMANTIC_OPENING_ENUMERATION,
    STAGE_SOURCE_VISIBILITY,
    STAGE_STRUCTURAL_ENUMERATION_COMPLETENESS,
    STATUS_NOT_EXPOSED,
    SUPPORTED_ITEM35_SHADOW_SCHEMA_VERSIONS,
    UNOBSERVED_IDENTITY_STAGES,
    Item35StageFunnel,
    StageObservation,
    aggregate_item35_stage_funnels,
    build_item35_stage_funnel,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_provider_gold_isolation import (
    FORBIDDEN_MODULES,
    FORBIDDEN_NAME_FRAGMENTS,
    walk_local_import_graph,
)
from pb_semantic_opening_enumeration_authority import (
    SEMANTIC_OPENING_CANDIDATE_UNIVERSE_COMPLETE,
    SEMANTIC_OPENING_NO_VISIBLE_SEGMENTS,
    SEMANTIC_OPENING_PHYSICAL_CONFLICT,
    SEMANTIC_OPENING_RESIDUAL_SOURCE_EVIDENCE,
    SEMANTIC_OPENING_SOURCE_COVERAGE_INCOMPLETE,
    SEMANTIC_OPENING_STRUCTURAL_ENUMERATION_COMPLETE,
    SEMANTIC_OPENING_UNIVERSE_EXHAUSTIVENESS_UNPROVEN,
)
from scripts import item35_stage_funnel_report as report_script

REPO = Path(__file__).resolve().parents[1]
FUNNEL_MODULE = "pb_item35_stage_funnel"
ABSTAINED = EvidenceResolutionStatus.ABSTAINED
CONFLICT = EvidenceResolutionStatus.CONFLICT
CORROBORATED = EvidenceResolutionStatus.CORROBORATED


# ---------------------------------------------------------------- fixtures
def _record_shadow(**overrides):
    """A coherent shadow with a semantic record (complete, count published)."""
    shadow = empty_item35_authority_shadow(reason="semantic_inventory_resolved")
    shadow.update(
        {
            "status": "evidence_present",
            "document_id": "doc-1",
            "revision_id": "rev-1",
            "source_sha256": "a" * 64,
            "snapshot_id": "snap-1",
            "visible_observation_count": 6,
            "semantic_opening_count": 1,
            "support_observation_count": 6,
            "residual_visible_observation_count": 0,
            "structural_enumeration_complete": True,
            "physical_opening_universe_complete": True,
            "semantic_reason_codes": [
                SEMANTIC_OPENING_STRUCTURAL_ENUMERATION_COMPLETE,
                SEMANTIC_OPENING_CANDIDATE_UNIVERSE_COMPLETE,
            ],
            "semantic_record_id": "semantic_opening_enumeration_x",
            "semantic_opening_record_ids": ["opening-1"],
            "representative_observation_ids": ["obs-1"],
            "generic_count_status": "corroborated",
            "generic_count_reason_codes": [GENERIC_OPENING_COUNT_RESOLVED],
            "generic_count": 1,
            "commercial_count_unlocked": True,
        }
    )
    shadow.update(overrides)
    return shadow


def _generic_abstained(**overrides):
    values = {
        "generic_count_status": "abstained",
        "generic_count_reason_codes": [
            GENERIC_OPENING_COUNT_COMPLETENESS_NOT_SOURCE_AUTHENTICATED
        ],
        "generic_count": None,
        "commercial_count_unlocked": False,
    }
    values.update(overrides)
    return values


def _universe_incomplete_shadow():
    """Structure complete, but candidate closure did not prove the universe."""
    return _record_shadow(
        physical_opening_universe_complete=False,
        semantic_reason_codes=[
            SEMANTIC_OPENING_STRUCTURAL_ENUMERATION_COMPLETE,
            SEMANTIC_OPENING_UNIVERSE_EXHAUSTIVENESS_UNPROVEN,
        ],
        **_generic_abstained(),
    )


def _residual_shadow():
    return _record_shadow(
        visible_observation_count=9,
        support_observation_count=6,
        residual_visible_observation_count=3,
        structural_enumeration_complete=False,
        physical_opening_universe_complete=False,
        semantic_reason_codes=[
            SEMANTIC_OPENING_UNIVERSE_EXHAUSTIVENESS_UNPROVEN,
            SEMANTIC_OPENING_RESIDUAL_SOURCE_EVIDENCE,
        ],
        **_generic_abstained(),
    )


def _conflict_shadow():
    return _record_shadow(
        status="conflict",
        structural_enumeration_complete=False,
        physical_opening_universe_complete=False,
        semantic_reason_codes=[
            SEMANTIC_OPENING_PHYSICAL_CONFLICT,
            SEMANTIC_OPENING_UNIVERSE_EXHAUSTIVENESS_UNPROVEN,
        ],
        **_generic_abstained(generic_count_status="conflict"),
    )


def _no_record_shadow():
    """Scope ids exist (source ingested) but the semantic authority had no record."""
    shadow = empty_item35_authority_shadow(reason="semantic_inventory_unavailable")
    shadow.update(
        {
            "document_id": "doc-1",
            "revision_id": "rev-1",
            "source_sha256": "a" * 64,
            "snapshot_id": "snap-1",
            "semantic_reason_codes": [SEMANTIC_OPENING_SOURCE_COVERAGE_INCOMPLETE],
            **_generic_abstained(),
        }
    )
    return shadow


def _shell(reason="source_unavailable"):
    return empty_item35_authority_shadow(reason=reason)


def _row(funnel, stage):
    return next(
        row
        for row in funnel.stages + funnel.unobserved_identity_stages
        if row.stage == stage
    )


# ------------------------------------------------- determinism / stable IDs
def test_funnel_is_deterministic_with_a_recomputable_stable_record_id():
    shadow = _residual_shadow()
    first = build_item35_stage_funnel(shadow)
    second = build_item35_stage_funnel(copy.deepcopy(shadow))

    assert first == second
    assert first.record_id == second.record_id
    assert json.dumps(first.to_dict(), sort_keys=True) == json.dumps(
        second.to_dict(), sort_keys=True
    )
    payload = first.to_dict()
    record_id = payload.pop("record_id")
    assert record_id.startswith("item35_stage_funnel_")
    assert record_id == stable_contract_id("item35_stage_funnel", payload, digest_chars=32)


def test_record_id_tracks_content_and_rejects_tampering():
    base = build_item35_stage_funnel(_residual_shadow())
    changed = build_item35_stage_funnel(_residual_shadow() | {"visible_observation_count": 10})
    other_scope = build_item35_stage_funnel(_residual_shadow() | {"document_id": "doc-2"})
    assert len({base.record_id, changed.record_id, other_scope.record_id}) == 3

    with pytest.raises(ValueError, match="record_id"):
        dataclasses.replace(base, document_id="forged")
    with pytest.raises(ValueError, match="record_id"):
        dataclasses.replace(base, shadow_reason="forged")


def test_reason_code_order_and_duplicates_do_not_affect_output():
    forward = _residual_shadow()
    reordered = _residual_shadow()
    reordered["semantic_reason_codes"] = [
        SEMANTIC_OPENING_RESIDUAL_SOURCE_EVIDENCE,
        SEMANTIC_OPENING_UNIVERSE_EXHAUSTIVENESS_UNPROVEN,
        SEMANTIC_OPENING_RESIDUAL_SOURCE_EVIDENCE,
    ]
    forward["generic_count_reason_codes"] = ["z_code", "a_code"]
    reordered["generic_count_reason_codes"] = ["a_code", "z_code", "a_code"]

    left = build_item35_stage_funnel(forward)
    right = build_item35_stage_funnel(reordered)
    assert left == right
    assert left.record_id == right.record_id
    for row in left.stages:
        assert row.reason_codes == tuple(sorted(set(row.reason_codes)))


# ------------------------------------------------- explicit unobserved stages
def test_identity_stages_are_always_reported_unobserved():
    shadows = [
        _record_shadow(),
        _residual_shadow(),
        _conflict_shadow(),
        _no_record_shadow(),
        _shell(),
        {"status": "abstained", "reason": "not_collected", "commercial_count_unlocked": False},
    ]
    for shadow in shadows:
        funnel = build_item35_stage_funnel(shadow)
        assert tuple(row.stage for row in funnel.unobserved_identity_stages) == (
            STAGE_PHYSICAL_OPENING_EXISTENCE,
            STAGE_PHYSICAL_OPENING_IDENTITY,
            STAGE_OPENING_HOST_BINDING,
        )
        for row in funnel.unobserved_identity_stages:
            assert row.observed is False
            assert row.not_observed_reason == NOT_OBSERVED_IDENTITY_NOT_EXPOSED
            assert row.status is None
            assert row.input_count is None and row.output_count is None
            assert row.complete is None and row.blocking is None
            assert row.reason_codes == ()
        assert funnel.first_blocker_stage not in UNOBSERVED_IDENTITY_STAGES
        assert not set(funnel.blocking_stages) & set(UNOBSERVED_IDENTITY_STAGES)


def test_an_identity_stage_cannot_be_constructed_as_observed():
    for stage in UNOBSERVED_IDENTITY_STAGES:
        with pytest.raises(ValueError, match="observed=False"):
            StageObservation(stage=stage, observed=True, blocking=False)


def test_a_fully_passing_shadow_still_leaves_identity_unobserved():
    funnel = build_item35_stage_funnel(_record_shadow())
    assert funnel.blocking_stages == ()
    assert funnel.first_blocker_stage is None
    assert funnel.first_unobserved_stage is None
    assert all(not row.observed for row in funnel.unobserved_identity_stages)
    summary = aggregate_item35_stage_funnels([funnel])
    assert summary["no_observed_blocker_funnel_count"] == 1
    assert summary["undetermined_funnel_count"] == 0
    assert summary["unobserved_identity_stages"] == list(UNOBSERVED_IDENTITY_STAGES)


def test_shell_defaults_are_not_reported_as_observations():
    for reason in (
        "source_unavailable",
        "document_id_unavailable",
        "page_scope_unavailable",
        "shadow_exception:ValueError",
    ):
        funnel = build_item35_stage_funnel(_shell(reason))
        assert funnel.shadow_reason == reason
        assert funnel.document_id is None and funnel.semantic_record_id is None
        assert tuple(row.stage for row in funnel.stages) == OBSERVABLE_STAGES
        for row in funnel.stages:
            assert row.observed is False
            assert row.not_observed_reason == NOT_OBSERVED_SHADOW_SCOPE_ABSENT
            # The shell's False flags, 0 counts and "abstained" count status are
            # placeholders, not observations.
            assert row.complete is None
            assert row.status is None
            assert row.input_count is None and row.output_count is None
            assert row.blocking is None
        assert funnel.blocking_stages == ()
        assert funnel.first_blocker_stage is None
        assert funnel.first_unobserved_stage == STAGE_SOURCE_VISIBILITY


def test_extractor_not_collected_placeholder_is_all_unobserved():
    placeholder = {
        "status": "abstained",
        "reason": "not_collected",
        "commercial_count_unlocked": False,
    }
    funnel = build_item35_stage_funnel(placeholder)
    assert funnel.shadow_schema_version is None
    assert funnel.shadow_reason == "not_collected"
    assert all(
        row.not_observed_reason == NOT_OBSERVED_SHADOW_NOT_COLLECTED
        for row in funnel.stages
    )
    # An arbitrary schema-less mapping is not this placeholder.
    with pytest.raises(ValueError, match="schema_version"):
        build_item35_stage_funnel({"status": "abstained", "reason": "other"})
    with pytest.raises(ValueError, match="schema_version"):
        build_item35_stage_funnel(placeholder | {"generic_count": 3})


def test_absent_semantic_record_leaves_completeness_stages_unobserved_not_false():
    funnel = build_item35_stage_funnel(_no_record_shadow())

    source = _row(funnel, STAGE_SOURCE_VISIBILITY)
    assert source.observed and source.blocking is False
    assert source.output_count is None  # the shell's 0 is not a visible count

    semantic = _row(funnel, STAGE_SEMANTIC_OPENING_ENUMERATION)
    assert semantic.observed
    assert semantic.status is ABSTAINED and semantic.blocking is True
    assert semantic.output_count is None and semantic.input_count is None
    assert semantic.reason_codes == (SEMANTIC_OPENING_SOURCE_COVERAGE_INCOMPLETE,)

    for stage in (
        STAGE_STRUCTURAL_ENUMERATION_COMPLETENESS,
        STAGE_PHYSICAL_OPENING_UNIVERSE_COMPLETENESS,
    ):
        row = _row(funnel, stage)
        assert row.observed is False
        assert row.not_observed_reason == NOT_OBSERVED_SEMANTIC_RECORD_ABSENT
        assert row.complete is None and row.blocking is None

    generic = _row(funnel, STAGE_GENERIC_COUNT_PUBLICATION)
    assert generic.observed and generic.status is ABSTAINED and generic.blocking

    assert funnel.first_blocker_stage == STAGE_SEMANTIC_OPENING_ENUMERATION
    assert funnel.first_unobserved_stage == STAGE_STRUCTURAL_ENUMERATION_COMPLETENESS


# ---------------------------------------------------- authority preservation
def test_semantic_conflict_remains_conflict():
    funnel = build_item35_stage_funnel(_conflict_shadow())
    semantic = _row(funnel, STAGE_SEMANTIC_OPENING_ENUMERATION)
    assert funnel.shadow_status == "conflict"
    assert semantic.status is CONFLICT
    assert semantic.blocking is True
    assert SEMANTIC_OPENING_PHYSICAL_CONFLICT in semantic.reason_codes
    assert funnel.first_blocker_stage == STAGE_SEMANTIC_OPENING_ENUMERATION
    # Nothing downstream promotes it.
    for row in funnel.stages:
        assert row.status is not CORROBORATED
    assert _row(funnel, STAGE_GENERIC_COUNT_PUBLICATION).status is CONFLICT


def test_incomplete_physical_opening_universe_remains_abstained():
    funnel = build_item35_stage_funnel(_universe_incomplete_shadow())
    structural = _row(funnel, STAGE_STRUCTURAL_ENUMERATION_COMPLETENESS)
    physical = _row(funnel, STAGE_PHYSICAL_OPENING_UNIVERSE_COMPLETENESS)

    assert structural.complete is True and structural.blocking is False
    assert physical.complete is False
    assert physical.status is ABSTAINED
    assert physical.blocking is True
    # An unproven universe has no count: one enumerated opening is a lower
    # bound, and unknown is never reported as a total.
    assert physical.output_count is None
    assert physical.reason_codes == (SEMANTIC_OPENING_UNIVERSE_EXHAUSTIVENESS_UNPROVEN,)
    assert funnel.first_blocker_stage == STAGE_PHYSICAL_OPENING_UNIVERSE_COMPLETENESS


def test_incomplete_structure_abstains_and_carries_only_its_gating_codes():
    funnel = build_item35_stage_funnel(_residual_shadow())
    structural = _row(funnel, STAGE_STRUCTURAL_ENUMERATION_COMPLETENESS)
    physical = _row(funnel, STAGE_PHYSICAL_OPENING_UNIVERSE_COMPLETENESS)
    semantic = _row(funnel, STAGE_SEMANTIC_OPENING_ENUMERATION)

    assert structural.status is ABSTAINED and structural.complete is False
    assert structural.reason_codes == (SEMANTIC_OPENING_RESIDUAL_SOURCE_EVIDENCE,)
    assert dict(structural.detail_counts) == {"residual_visible_observation_count": 3}
    assert structural.input_count == 9
    assert physical.reason_codes == (SEMANTIC_OPENING_UNIVERSE_EXHAUSTIVENESS_UNPROVEN,)
    # The semantic row keeps the whole record list verbatim.
    assert semantic.reason_codes == tuple(sorted(_residual_shadow()["semantic_reason_codes"]))
    assert dict(semantic.detail_counts) == {"support_observation_count": 6}
    assert funnel.first_blocker_stage == STAGE_STRUCTURAL_ENUMERATION_COMPLETENESS
    assert funnel.blocking_stages == (
        STAGE_STRUCTURAL_ENUMERATION_COMPLETENESS,
        STAGE_PHYSICAL_OPENING_UNIVERSE_COMPLETENESS,
        STAGE_GENERIC_COUNT_PUBLICATION,
    )


def test_unrecognised_semantic_codes_are_kept_on_the_semantic_row_only():
    shadow = _residual_shadow()
    shadow["semantic_reason_codes"].append("semantic_opening_future_code")
    funnel = build_item35_stage_funnel(shadow)
    assert "semantic_opening_future_code" in _row(
        funnel, STAGE_SEMANTIC_OPENING_ENUMERATION
    ).reason_codes
    for stage in (
        STAGE_STRUCTURAL_ENUMERATION_COMPLETENESS,
        STAGE_PHYSICAL_OPENING_UNIVERSE_COMPLETENESS,
    ):
        assert "semantic_opening_future_code" not in _row(funnel, stage).reason_codes


def test_generic_count_abstention_is_preserved_even_when_upstream_is_complete():
    funnel = build_item35_stage_funnel(
        _record_shadow(
            **_generic_abstained(
                generic_count_reason_codes=[
                    GENERIC_OPENING_COUNT_VIEWPORT_CLASS_UNAVAILABLE,
                    "viewport_view_class_unavailable",
                ]
            )
        )
    )
    generic = _row(funnel, STAGE_GENERIC_COUNT_PUBLICATION)
    assert generic.status is ABSTAINED
    assert generic.output_count is None
    assert generic.blocking is True
    assert generic.reason_codes == (
        GENERIC_OPENING_COUNT_VIEWPORT_CLASS_UNAVAILABLE,
        "viewport_view_class_unavailable",
    )
    # Upstream completeness does not turn an abstained count into a pass.
    assert _row(funnel, STAGE_STRUCTURAL_ENUMERATION_COMPLETENESS).blocking is False
    assert _row(funnel, STAGE_PHYSICAL_OPENING_UNIVERSE_COMPLETENESS).blocking is False
    assert funnel.first_blocker_stage == STAGE_GENERIC_COUNT_PUBLICATION
    assert funnel.shadow_reported_commercial_count_unlocked is False


def test_generic_count_only_passes_when_corroborated_with_a_published_count():
    published = build_item35_stage_funnel(_record_shadow())
    generic = _row(published, STAGE_GENERIC_COUNT_PUBLICATION)
    assert generic.status is CORROBORATED and generic.output_count == 1
    assert generic.blocking is False

    # Corroborated status without a count is never a pass.
    odd = build_item35_stage_funnel(
        _record_shadow(generic_count=None, commercial_count_unlocked=False)
    )
    assert _row(odd, STAGE_GENERIC_COUNT_PUBLICATION).blocking is True


def test_completeness_stages_assert_no_positive_status_of_their_own():
    funnel = build_item35_stage_funnel(_record_shadow())
    semantic = _row(funnel, STAGE_SEMANTIC_OPENING_ENUMERATION)
    structural = _row(funnel, STAGE_STRUCTURAL_ENUMERATION_COMPLETENESS)
    physical = _row(funnel, STAGE_PHYSICAL_OPENING_UNIVERSE_COMPLETENESS)
    # The shadow collapses every non-conflict record status into
    # "evidence_present" and exposes no status for the completeness flags, so
    # the funnel can only preserve or lower authority, never raise it.
    assert semantic.status is None and semantic.blocking is False
    assert structural.status is None and structural.complete is True
    assert physical.status is None and physical.complete is True
    assert physical.output_count == 1
    assert [row.status for row in funnel.stages if row.status is CORROBORATED] == [
        _row(funnel, STAGE_GENERIC_COUNT_PUBLICATION).status
    ]


# --------------------------------------------- commercial output stays locked
def test_funnel_never_grants_commercial_authority_even_when_shadow_reports_unlock():
    shadow = _record_shadow()
    assert shadow["commercial_count_unlocked"] is True
    funnel = build_item35_stage_funnel(shadow)

    assert funnel.shadow_reported_commercial_count_unlocked is True  # verbatim report
    assert funnel.commercial_authority_granted is False
    assert funnel.to_dict()["commercial_authority_granted"] is False
    summary = aggregate_item35_stage_funnels([funnel])
    assert summary["commercial_authority_granted"] is False
    assert summary["shadow_reported_commercial_count_unlocked_count"] == 1

    with pytest.raises(ValueError, match="never grants commercial authority"):
        dataclasses.replace(funnel, commercial_authority_granted=True)
    with pytest.raises(ValueError, match="never grants commercial authority"):
        Item35StageFunnel(
            **{
                **{f.name: getattr(funnel, f.name) for f in dataclasses.fields(funnel)},
                "commercial_authority_granted": True,
            }
        )


def _pb_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return {name for name in found if name.startswith(("pb_", "scripts"))}


def test_funnel_module_imports_no_authority_publisher_or_commercial_module():
    path = REPO / f"{FUNNEL_MODULE}.py"
    assert _pb_imports(path) == {
        "pb_migration_contracts",
        "pb_semantic_opening_enumeration_authority",
    }
    # The semantic authority is imported for its reason-code constants only.
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "pb_semantic_opening_enumeration_authority"
        ):
            for alias in node.names:
                assert re.fullmatch(r"SEMANTIC_OPENING_[A-Z_]+", alias.name), alias.name


def test_report_script_imports_only_the_shadow_and_the_funnel():
    imports = _pb_imports(REPO / "scripts" / "item35_stage_funnel_report.py")
    assert imports == {"pb_item35_production_authority_shadow", "pb_item35_stage_funnel"}


def test_funnel_and_script_are_gold_free():
    for module in (FUNNEL_MODULE,):
        visited, findings = walk_local_import_graph(module)
        assert findings == ()
        assert not set(visited) & FORBIDDEN_MODULES
    for path in (
        REPO / f"{FUNNEL_MODULE}.py",
        REPO / "scripts" / "item35_stage_funnel_report.py",
    ):
        source = path.read_text(encoding="utf-8").lower()
        for fragment in FORBIDDEN_NAME_FRAGMENTS:
            assert fragment not in source, (path.name, fragment)
        assert "benchmarks/" not in source and "benchmarks\\" not in source


def test_funnel_runs_no_authority(monkeypatch):
    """Building and aggregating must not touch any authority (one execution path)."""
    import pb_generic_opening_count_authority as generic
    import pb_physical_opening_authority as physical
    import pb_semantic_opening_enumeration_authority as semantic
    import pb_source_visibility_authority as visibility

    def boom(*_args, **_kwargs):
        raise AssertionError("the funnel must not execute an authority")

    for owner, name in (
        (physical.PhysicalOpeningAuthority, "prove_existence"),
        (physical.PhysicalOpeningAuthority, "compare_identity"),
        (physical.PhysicalOpeningAuthority, "classify_disposition"),
        (semantic.SemanticOpeningEnumerationProducer, "publish_document_scope"),
        (semantic.SemanticOpeningEnumerationProducer, "publish_page_scope"),
        (generic.GenericOpeningCountProducer, "publish"),
        (visibility.SourceVisibilityProducer, "ingest_native_pdf_bytes"),
    ):
        monkeypatch.setattr(owner, name, boom)

    funnels = [
        build_item35_stage_funnel(shadow)
        for shadow in (_record_shadow(), _residual_shadow(), _no_record_shadow(), _shell())
    ]
    assert aggregate_item35_stage_funnels(funnels)["funnel_count"] == 4


def test_no_production_module_imports_the_diagnostic():
    needle = FUNNEL_MODULE
    offenders = []
    for path in sorted(REPO.rglob("*.py")):
        relative = path.relative_to(REPO)
        if relative.parts[0] in {"tests", "scripts", ".git"} or path.name == f"{needle}.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if needle not in text:
            continue
        offenders.append(str(relative))
    assert offenders == []


def test_importing_the_live_extractor_does_not_load_the_diagnostic():
    code = (
        "import sys\n"
        "import pb_planreader_pdf_extractor, pb_item35_production_authority_shadow\n"
        f"sys.exit(1 if {FUNNEL_MODULE!r} in sys.modules else 0)\n"
    )
    env = {**os.environ, "PYTHONPATH": str(REPO)}
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO, env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr[-2000:]


# ------------------------------------------------------------- no mutation
@pytest.mark.parametrize(
    "factory",
    [
        _record_shadow,
        _residual_shadow,
        _universe_incomplete_shadow,
        _conflict_shadow,
        _no_record_shadow,
        _shell,
    ],
)
def test_input_shadow_is_not_mutated_or_aliased(factory):
    shadow = factory()
    snapshot = copy.deepcopy(shadow)
    funnel = build_item35_stage_funnel(shadow)
    assert shadow == snapshot

    # The result owns its data: changing the input afterwards changes nothing.
    before = funnel.to_dict()
    for value in shadow.values():
        if isinstance(value, list):
            value.append("late-mutation")
    shadow["document_id"] = "mutated"
    assert funnel.to_dict() == before

    # to_dict returns fresh containers every time.
    exported = funnel.to_dict()
    exported["stages"][0]["stage"] = "mutated"
    exported["blocking_stages"].append("mutated")
    assert funnel.to_dict() == before


def test_a_read_only_mapping_is_accepted():
    shadow = _residual_shadow()
    assert build_item35_stage_funnel(MappingProxyType(shadow)) == build_item35_stage_funnel(shadow)


# ------------------------------------------------------- input validation
def test_unreviewed_or_incoherent_shadows_are_rejected_not_guessed():
    with pytest.raises(TypeError):
        build_item35_stage_funnel(["not", "a", "mapping"])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unsupported shadow schema_version"):
        build_item35_stage_funnel(_record_shadow(schema_version="9.9.9"))

    shadow = _record_shadow()
    del shadow["generic_count_status"]
    with pytest.raises(ValueError, match="generic_count_status"):
        build_item35_stage_funnel(shadow)

    bad = {
        "unknown status": _record_shadow(status="corroborated"),
        "partial scope": _record_shadow(snapshot_id=None),
        "unlocked without count": _record_shadow(commercial_count_unlocked=False),
        "count without corroboration": _record_shadow(generic_count_status="abstained"),
        "unknown count status": _record_shadow(generic_count_status="firm"),
        "bool count": _record_shadow(visible_observation_count=True),
        "negative count": _record_shadow(visible_observation_count=-1),
        "universe without structure": _record_shadow(
            structural_enumeration_complete=False, physical_opening_universe_complete=True
        ),
        "record with abstained status": _record_shadow(status="abstained"),
        "id list length mismatch": _record_shadow(semantic_opening_record_ids=[]),
        "text list wrong type": _record_shadow(semantic_reason_codes="a_code"),
        "flags without a record": _no_record_shadow() | {"structural_enumeration_complete": True},
        "counts without a record": _no_record_shadow() | {"visible_observation_count": 4},
        "evidence_present without a record": _no_record_shadow() | {"status": "evidence_present"},
        "conflict without a record": _no_record_shadow() | {"status": "conflict"},
        "shell with data": _shell() | {"semantic_reason_codes": ["semantic_opening_x"]},
        "shell with count": _shell()
        | {"generic_count_status": "corroborated", "generic_count": 2, "commercial_count_unlocked": True},
        "record without scope": _record_shadow(document_id=None, revision_id=None, source_sha256=None, snapshot_id=None),
    }
    for label, shadow in bad.items():
        try:
            build_item35_stage_funnel(shadow)
        except ValueError:
            continue
        pytest.fail(f"accepted an incoherent shadow: {label}")


def test_shadow_schema_is_pinned_to_what_the_funnel_reviewed():
    assert ITEM35_PRODUCTION_SHADOW_SCHEMA_VERSION in SUPPORTED_ITEM35_SHADOW_SCHEMA_VERSIONS
    shell = _shell()
    # The shadow must emit exactly the keys the funnel reviewed: a new key is a
    # schema change that needs review here, not a field to ignore silently.
    assert set(shell) == REVIEWED_ITEM35_SHADOW_KEYS
    funnel = build_item35_stage_funnel(shell)
    assert funnel.shadow_schema_version == shell["schema_version"]
    # Removing any key the shadow emits must be noticed, never defaulted.
    for key in shell:
        trimmed = {name: value for name, value in shell.items() if name != key}
        with pytest.raises(ValueError):
            build_item35_stage_funnel(trimmed)


def test_stage_observation_invariants():
    with pytest.raises(ValueError, match="unknown funnel stage"):
        StageObservation(stage="made_up", observed=False, not_observed_reason="x")
    with pytest.raises(ValueError, match="must say why"):
        StageObservation(stage=STAGE_SOURCE_VISIBILITY, observed=False)
    with pytest.raises(ValueError, match="carries no observations"):
        StageObservation(
            stage=STAGE_SOURCE_VISIBILITY,
            observed=False,
            output_count=0,
            not_observed_reason="x",
        )
    with pytest.raises(ValueError, match="whether it blocks"):
        StageObservation(stage=STAGE_SOURCE_VISIBILITY, observed=True)
    with pytest.raises(ValueError, match="sorted"):
        StageObservation(
            stage=STAGE_SOURCE_VISIBILITY, observed=True, blocking=False, reason_codes=("b", "a")
        )
    with pytest.raises(TypeError):
        StageObservation(
            stage=STAGE_SOURCE_VISIBILITY, observed=True, blocking=False, status="abstained"  # type: ignore[arg-type]
        )


# --------------------------------------------------------------- aggregation
def test_aggregate_is_order_invariant_and_reports_ties_without_choosing():
    funnels = [
        build_item35_stage_funnel(_residual_shadow()),  # structural
        build_item35_stage_funnel(_residual_shadow() | {"document_id": "doc-b"}),  # structural
        build_item35_stage_funnel(_record_shadow(**_generic_abstained())),  # generic
        build_item35_stage_funnel(_record_shadow(**_generic_abstained()) | {"document_id": "doc-c"}),  # generic
        build_item35_stage_funnel(_conflict_shadow()),  # semantic
        build_item35_stage_funnel(_record_shadow()),  # no observed blocker
        build_item35_stage_funnel(_shell()),  # undetermined
        build_item35_stage_funnel(_no_record_shadow()),  # semantic
    ]
    forward = aggregate_item35_stage_funnels(funnels)
    backward = aggregate_item35_stage_funnels(list(reversed(funnels)))
    assert forward == backward
    assert forward["record_id"] == backward["record_id"]
    assert json.dumps(forward, sort_keys=True) == json.dumps(backward, sort_keys=True)

    assert forward["funnel_count"] == 8
    assert forward["first_blocker_stage_counts"] == {
        STAGE_GENERIC_COUNT_PUBLICATION: 2,
        STAGE_SEMANTIC_OPENING_ENUMERATION: 2,
        STAGE_STRUCTURAL_ENUMERATION_COMPLETENESS: 2,
    }
    # A three-way tie: every tied stage is reported, none is picked.
    assert forward["dominant_first_blocker_stages"] == sorted(
        [
            STAGE_GENERIC_COUNT_PUBLICATION,
            STAGE_SEMANTIC_OPENING_ENUMERATION,
            STAGE_STRUCTURAL_ENUMERATION_COMPLETENESS,
        ]
    )
    assert forward["undetermined_funnel_count"] == 1
    assert forward["no_observed_blocker_funnel_count"] == 1
    assert forward["first_unobserved_stage_counts"] == {
        STAGE_SOURCE_VISIBILITY: 1,
        STAGE_STRUCTURAL_ENUMERATION_COMPLETENESS: 1,
    }
    assert forward["first_blocker_reason_code_counts"][
        STAGE_STRUCTURAL_ENUMERATION_COMPLETENESS
    ] == {SEMANTIC_OPENING_RESIDUAL_SOURCE_EVIDENCE: 2}
    structural = forward["per_stage"][STAGE_STRUCTURAL_ENUMERATION_COMPLETENESS]
    assert structural["observed"] == 6 and structural["unobserved"] == 2
    assert structural["complete_true"] + structural["complete_false"] == 6
    assert structural["status_counts"]["abstained"] == structural["complete_false"]
    assert structural["status_counts"][STATUS_NOT_EXPOSED] == structural["complete_true"]
    for stage in UNOBSERVED_IDENTITY_STAGES:
        assert forward["per_stage"][stage]["observed"] == 0
        assert forward["per_stage"][stage]["unobserved"] == 8
    assert forward["shadow_reason_counts"]["source_unavailable"] == 1


def test_aggregate_edge_cases():
    empty = aggregate_item35_stage_funnels([])
    assert empty["funnel_count"] == 0
    assert empty["dominant_first_blocker_stages"] == []
    assert empty["record_id"] == aggregate_item35_stage_funnels(iter(()))["record_id"]
    assert empty["commercial_authority_granted"] is False
    with pytest.raises(TypeError):
        aggregate_item35_stage_funnels([{"not": "a funnel"}])  # type: ignore[list-item]


# ----------------------------------------- contract with the real shadow
def _draw_opening(page: fitz.Page, top: float = 100.0) -> None:
    for first, second in (
        ((20.0, top), (100.0, top)),
        ((140.0, top), (220.0, top)),
        ((20.0, top + 10), (100.0, top + 10)),
        ((140.0, top + 10), (220.0, top + 10)),
        ((100.0, top), (100.0, top + 10)),
        ((140.0, top), (140.0, top + 10)),
    ):
        page.draw_line(fitz.Point(*first), fitz.Point(*second), color=(0, 0, 0), width=1)


def _write_pdf(path: Path, *, title: bool, opening: bool, pages: int = 1) -> Path:
    doc = fitz.open()
    for index in range(pages):
        page = doc.new_page(width=700, height=650)
        if title:
            page.insert_text(fitz.Point(40, 40), "GROUND FLOOR PLAN", color=(0, 0, 0))
        if opening and index == 0:
            _draw_opening(page)
    doc.save(path)
    doc.close()
    return path


def test_real_shadow_complete_drawing_funnel(tmp_path):
    pdf = _write_pdf(tmp_path / "plan.pdf", title=True, opening=True)
    shadow = collect_item35_authority_shadow(pdf, document_id="funnel-test")
    funnel = build_item35_stage_funnel(shadow)

    assert all(row.observed for row in funnel.stages)
    assert funnel.document_id == shadow["document_id"]
    assert funnel.source_sha256 == shadow["source_sha256"]
    assert funnel.semantic_record_id == shadow["semantic_record_id"]
    assert _row(funnel, STAGE_SOURCE_VISIBILITY).output_count == shadow["visible_observation_count"]
    assert _row(funnel, STAGE_SEMANTIC_OPENING_ENUMERATION).output_count == 1
    generic = _row(funnel, STAGE_GENERIC_COUNT_PUBLICATION)
    assert generic.status is CORROBORATED and generic.output_count == shadow["generic_count"]
    assert funnel.blocking_stages == ()
    assert funnel.shadow_reported_commercial_count_unlocked is shadow["commercial_count_unlocked"]
    assert funnel.commercial_authority_granted is False
    assert all(not row.observed for row in funnel.unobserved_identity_stages)


def test_real_shadow_without_floor_plan_title_blocks_at_generic_count(tmp_path):
    pdf = _write_pdf(tmp_path / "untitled.pdf", title=False, opening=True)
    funnel = build_item35_stage_funnel(
        collect_item35_authority_shadow(pdf, document_id="funnel-test")
    )
    assert funnel.first_blocker_stage == STAGE_GENERIC_COUNT_PUBLICATION
    generic = _row(funnel, STAGE_GENERIC_COUNT_PUBLICATION)
    assert generic.status is ABSTAINED and generic.output_count is None
    assert GENERIC_OPENING_COUNT_VIEWPORT_CLASS_UNAVAILABLE in generic.reason_codes
    assert _row(funnel, STAGE_PHYSICAL_OPENING_UNIVERSE_COMPLETENESS).complete is True
    assert funnel.shadow_reported_commercial_count_unlocked is False


def test_real_shadow_blank_page_blocks_at_structural_completeness(tmp_path):
    pdf = _write_pdf(tmp_path / "blank.pdf", title=False, opening=False)
    funnel = build_item35_stage_funnel(
        collect_item35_authority_shadow(pdf, document_id="funnel-test")
    )
    structural = _row(funnel, STAGE_STRUCTURAL_ENUMERATION_COMPLETENESS)
    assert _row(funnel, STAGE_SOURCE_VISIBILITY).output_count == 0  # observed zero
    assert funnel.first_blocker_stage == STAGE_STRUCTURAL_ENUMERATION_COMPLETENESS
    assert structural.status is ABSTAINED
    assert SEMANTIC_OPENING_NO_VISIBLE_SEGMENTS in structural.reason_codes
    physical = _row(funnel, STAGE_PHYSICAL_OPENING_UNIVERSE_COMPLETENESS)
    assert physical.status is ABSTAINED and physical.output_count is None
    generic = _row(funnel, STAGE_GENERIC_COUNT_PUBLICATION)
    assert generic.status is ABSTAINED
    assert GENERIC_OPENING_COUNT_COMPLETENESS_NOT_SOURCE_AUTHENTICATED in generic.reason_codes


def test_funnel_reads_the_extractors_own_shadow_without_changing_predictions(tmp_path):
    from pb_planreader_pdf_extractor import GenericPlanReaderExtractor

    pdf = _write_pdf(tmp_path / "live.pdf", title=True, opening=True)
    extractor = GenericPlanReaderExtractor()
    predictions = extractor.extract_from_pdf(pdf)
    predictions_before = repr(predictions)
    shadow_before = copy.deepcopy(extractor.item35_authority_shadow)
    status_before = copy.deepcopy(extractor.extraction_status)

    funnel = build_item35_stage_funnel(extractor.item35_authority_shadow)

    assert extractor.item35_authority_shadow == shadow_before
    assert extractor.extraction_status == status_before
    assert repr(predictions) == predictions_before
    assert not [p for p in predictions if p.trade_type in {"doors", "windows"}]
    assert funnel.commercial_authority_granted is False
    assert _row(funnel, STAGE_GENERIC_COUNT_PUBLICATION).output_count == extractor.item35_authority_shadow["generic_count"]

    # Re-extracting after the funnel ran gives the same predictions.
    assert repr(GenericPlanReaderExtractor().extract_from_pdf(pdf)) == predictions_before

    # The extractor's pre-collection placeholder is understood, not guessed at.
    fresh = GenericPlanReaderExtractor()
    placeholder = build_item35_stage_funnel(fresh.item35_authority_shadow)
    assert all(not row.observed for row in placeholder.stages)


# --------------------------------------------------------------- the script
def test_script_document_id_is_content_derived_so_names_and_paths_do_not_matter(tmp_path):
    first = _write_pdf(tmp_path / "one.pdf", title=True, opening=True)
    (tmp_path / "sub").mkdir()
    second = tmp_path / "sub" / "completely_different_name.pdf"
    second.write_bytes(first.read_bytes())

    report = report_script.build_report([first, second])
    ids = {entry["funnel"]["record_id"] for entry in report["entries"]}
    assert len(ids) == 1
    assert {entry["label"] for entry in report["entries"]} == {
        "one.pdf",
        "completely_different_name.pdf",
    }
    assert all(
        entry["funnel"]["document_id"].startswith("item35_funnel:")
        for entry in report["entries"]
    )


def test_script_report_is_deterministic_and_argument_order_invariant(tmp_path):
    complete = _write_pdf(tmp_path / "a.pdf", title=True, opening=True)
    untitled = _write_pdf(tmp_path / "b.pdf", title=False, opening=True)
    missing = tmp_path / "missing.pdf"

    forward = report_script.build_report([complete, untitled, missing])
    backward = report_script.build_report([missing, untitled, complete])
    assert json.dumps(forward, sort_keys=True) == json.dumps(backward, sort_keys=True)
    assert forward["summary"]["funnel_count"] == 3
    assert forward["summary"]["shadow_reason_counts"]["source_unavailable"] == 1
    assert forward["summary"]["commercial_authority_granted"] is False
    assert forward["summary"]["undetermined_funnel_count"] == 1


def test_script_mirrors_the_extractors_exception_shell(tmp_path):
    pdf = _write_pdf(tmp_path / "two.pdf", title=True, opening=True, pages=2)
    shadow, digest = report_script.collect_shadow(pdf, pages=[7])  # page out of range
    assert digest is not None
    assert shadow["reason"] == "shadow_exception:ValueError"
    funnel = build_item35_stage_funnel(shadow)
    assert funnel.first_blocker_stage is None
    assert funnel.first_unobserved_stage == STAGE_SOURCE_VISIBILITY

    missing_shadow, missing_digest = report_script.collect_shadow(tmp_path / "nope.pdf")
    assert missing_digest is None
    assert missing_shadow["reason"] == "source_unavailable"


def test_script_calls_the_shadow_exactly_once_per_pdf_and_nothing_else(tmp_path, monkeypatch):
    first = _write_pdf(tmp_path / "a.pdf", title=True, opening=True)
    second = _write_pdf(tmp_path / "b.pdf", title=False, opening=True)
    calls = []

    def stub(pdf_path, *, document_id=None, pages=None):
        calls.append((Path(pdf_path).name, document_id, pages))
        return _record_shadow(document_id=document_id)

    monkeypatch.setattr(report_script, "collect_item35_authority_shadow", stub)
    report = report_script.build_report([first, second], pages=[0])

    assert sorted(name for name, _, _ in calls) == ["a.pdf", "b.pdf"]
    assert all(pages == [0] for _, _, pages in calls)
    assert all(doc and doc.startswith("item35_funnel:") for _, doc, _ in calls)
    assert report["summary"]["funnel_count"] == 2
    assert [entry["pages_requested"] for entry in report["entries"]] == [[0], [0]]


def test_script_cli(tmp_path, capsys):
    (tmp_path / "pdfs").mkdir()
    _write_pdf(tmp_path / "pdfs" / "x.pdf", title=True, opening=True)
    out = tmp_path / "out" / "report.json"
    assert report_script.main([str(tmp_path / "pdfs"), "--output", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["summary"]["funnel_count"] == 1
    assert payload["summary"]["commercial_authority_granted"] is False

    assert report_script.main([str(tmp_path / "pdfs")]) == 0
    assert json.loads(capsys.readouterr().out)["summary"]["funnel_count"] == 1

    empty = tmp_path / "empty"
    empty.mkdir()
    assert report_script.main([str(empty)]) == 2
    with pytest.raises(SystemExit) as excinfo:
        report_script.main([str(tmp_path / "pdfs"), "--pages", "a,b"])
    assert excinfo.value.code == 2
    with pytest.raises(SystemExit):
        report_script.main([str(tmp_path / "pdfs"), "--pages", "-1"])
