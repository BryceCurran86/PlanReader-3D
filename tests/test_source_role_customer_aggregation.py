"""Cross-document customer bijection using real seals and adapters."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from pb_combine_source_closed_runs import load_verified_sealed_run
from pb_customer_output_verification import verify_sealed_customer_output
from pb_quantity_takeoff_adapter import (
    CommercialMeasurementAuthority, CommercialTakeoffSourceTrace,
    quantity_evidence_to_takeoff_output_row,
)
from pb_source_closed_run_export import seal_source_closed_run
from tests.test_gpt3_owner_all_source_role_handoff import _fake_sources
from tests.test_source_closed_project_handoff import _quantity
from tools import gpt3_owner_all_source_role_handoff as roles


def _run(tmp_path, monkeypatch, corruption=None):
    project, root, docs = _fake_sources(tmp_path, monkeypatch)
    seen = []

    def produce(command, repo, logfile, **kwargs):
        index = len(seen)
        seen.append(command)
        dest = Path(command[command.index("--output-dir") + 1])
        q = replace(_quantity("role-quantity-" + str(index), "floor_area"),
                    input_entity_ids=("floor-" + str(index),))
        trace = CommercialTakeoffSourceTrace(
            workspace_id=1, project_id=project, document_id="doc-" + str(index),
            source_sha256=docs[index]["sha256"], source_page="1", viewport_id="vp-1",
            revision_id="rev-1", current_revision_id="rev-1",
            evidence_ids=q.evidence_ids, canonical_entity_ids=q.input_entity_ids,
        )
        sealed = seal_source_closed_run((q,), project_id=project, traces_by_quantity_id={q.quantity_id: trace})
        seal_path = dest / (project + ".json")
        seal_path.write_text(sealed.to_json())
        row = quantity_evidence_to_takeoff_output_row(q, trace=trace, authority=CommercialMeasurementAuthority(
            method="figured_dimension", figured_dimension_ids=("horizontal-" + str(index), "vertical-" + str(index)),
        ))
        rows = [row]
        path = dest / "verified_customer_rows.json"
        summary = {"status": "sealed", "combined_run_file": str(seal_path),
                   "customer_rows_verified": True, "customer_rows_file": str(path),
                   "family_counts": {"floor_area": 1}}
        if index == 1:
            if corruption == "duplicate":
                rows.append(row)
            elif corruption == "value":
                row["quantity"] = 77
            elif corruption == "foreign":
                row["quantity_id"] = "role-quantity-0"
            elif corruption == "manual_extra":
                rows.append({"element": "manual row"})
            elif corruption == "unverified":
                summary["customer_rows_verified"] = False
            elif corruption == "outside":
                path = tmp_path / "verified_customer_rows.json"
                summary["customer_rows_file"] = str(path)
        if not (index == 1 and corruption == "missing"):
            path.write_text(json.dumps(rows))
            if index == 1 and corruption == "duplicate_key":
                encoded = json.dumps(rows)
                path.write_text(encoded.replace('"quantity": 1.0', '"quantity": 77, "quantity": 1.0'))
        # Identical family-only files must never be globbed into the union.
        (dest / "verified_floor_finish_customer_rows.json").write_text(json.dumps(rows))
        (dest / "production_summary.json").write_text(json.dumps(summary))
        return 0, "COMPLETED", {}

    monkeypatch.setattr(roles, "run_logged", produce)
    dest = tmp_path / "output"
    result = roles.produce_all_source_roles(project_id=project, source_dir=root, output_dir=dest)
    return result, dest


def test_complete_role_rows_match_exact_combined_seal_once(tmp_path, monkeypatch):
    result, dest = _run(tmp_path, monkeypatch)
    assert result["source_role_coverage_verified"] is True
    assert result["customer_bijection_verified"] is True
    assert result["status"] == "ALL_ROLES_SEALED_CUSTOMER_VERIFIED_V2_PENDING"
    run = load_verified_sealed_run(dest / "ALL_SOURCE_ROLES.sealed.json")
    rows = json.loads((dest / "ALL_SOURCE_ROLES.customer_rows.json").read_text())
    assert len(rows) == 2
    assert verify_sealed_customer_output(run, rows).customer_row_count == 2
    assert all(row["customer_bijection_verified"] for row in result["roles"])
    assert result["benchmark_score_granted"] is False
    assert result["official_four_project_accuracy"] is None


@pytest.mark.parametrize("corruption", ("missing", "duplicate", "foreign", "value", "manual_extra", "unverified", "outside", "duplicate_key"))
def test_bad_role_rows_cannot_borrow_project_or_sibling_seals(tmp_path, monkeypatch, corruption):
    result, dest = _run(tmp_path, monkeypatch, corruption)
    assert result["source_role_coverage_verified"] is True
    assert result["customer_bijection_verified"] is False
    assert result["roles"][0]["customer_bijection_verified"] is True
    assert result["roles"][1]["customer_bijection_verified"] is False
    assert result["roles"][1]["customer_first_failure"] in {
        "role_customer_output_unavailable", "role_customer_output_invalid",
    }
    assert (dest / "ALL_SOURCE_ROLES.sealed.json").is_file()
    assert not (dest / "ALL_SOURCE_ROLES.customer_rows.json").exists()
    assert result["official_four_project_accuracy"] is None
