"""Retain previous opening identities; source-gated 22 finish reconciliation."""
from __future__ import annotations
import importlib
import json
from pathlib import Path

from pb_customer_output_verification import verify_sealed_customer_output
from pb_three_laurel_22_finish_combined_customer import issue_original_three_laurel_22_finish_customer_rows
from tools.report_gpt3_four_project_evidence import FROZEN_ROOT, _load_unchanged_frozen_modules
from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel

ROOT = Path(__file__).resolve().parents[1]
(
    _, load_suite_manifests, identity_map_from_dict,
    reconcile_sealed_run_v2, _,
) = _load_unchanged_frozen_modules()
evaluate_development_project_v2 = importlib.import_module(
    "_gpt3_four_project_frozen_v2.development_scoreboard"
).evaluate_development_project_v2
PRIOR = ROOT / "docs/engineering/3laurel_production_identity_map_20261106/identity_map.json"
EXTENDED = ROOT / "docs/engineering/3laurel_production_identity_map_20261120/identity_map.json"


def _maps():
    return json.loads(PRIOR.read_text()), json.loads(EXTENDED.read_text())


def _manifest():
    return next(m for m in load_suite_manifests(FROZEN_ROOT) if m.project_id == "au_qld_3laurel")


def test_exact_identity_map_adds_22_distinct_source_finished_surfaces():
    old, new = _maps()
    assert old["project_id"] == new["project_id"] == "au_qld_3laurel"
    assert old["source_sha256s"] == new["source_sha256s"] == [ORIGINAL_SHA256]
    before = {b["benchmark_item_id"]: b for b in old["bindings"]}
    after = {b["benchmark_item_id"]: b for b in new["bindings"]}
    assert len(before) == 23 and len(after) == 45
    assert all(after[k] == v for k, v in before.items())
    additional = [b for k, b in after.items() if k not in before]
    assert len(additional) == 22
    assert sum(b["production_family"] == "floor_finish_area" for b in additional) == 7
    assert sum(b["production_family"] == "wall_finish_area" for b in additional) == 8
    assert sum(b["production_family"] == "ceiling_lining" for b in additional) == 7
    truth = {item.item_id: item for item in _manifest().verified_items}
    allowed = {
        "floor_finish_area": {"flooring", "tiling"},
        "wall_finish_area": {"tiling"},
        "ceiling_lining": {"ceilings"},
    }
    for binding in additional:
        target = truth[binding["benchmark_item_id"]]
        assert target.denominator_eligible
        assert target.trade_category in allowed[binding["production_family"]]
        assert set(binding["production_object_identity_refs"]) == set(target.expected_object_refs)
    identity_map_from_dict(new)


def test_private_original_source_seal_customer_and_frozen_exact_22():
    original = require_original_3laurel()
    issued = issue_original_three_laurel_22_finish_customer_rows(original, workspace_id=1)
    assert issued.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert issued.sealed_run is not None
    assert issued.family_counts == (3, 4, 8, 7)
    assert len(issued.customer_rows) == 22
    verified = verify_sealed_customer_output(issued.sealed_run, issued.customer_rows)
    assert verified.valid_quantity_count == verified.customer_row_count == 22
    manifest = _manifest()
    produced = reconcile_sealed_run_v2(
        manifest, issued.sealed_run.to_dict(), identity_map_from_dict(_maps()[1]),
    )
    assert len(produced) == 22
    result = evaluate_development_project_v2(manifest, produced, execution_present=True)
    assert result.truth_denominator == 63
    assert result.matched_within_tolerance == 22
    assert result.matched_outside_tolerance == 0
    assert result.missed == 41
    assert result.unsupported_extra == 0
    assert result.lineage_conflicts == 0
    assert manifest.status == "INCOMPLETE"  # No official 120 score publication
