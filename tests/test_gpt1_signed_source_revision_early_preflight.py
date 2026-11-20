"""A wrong signed producer revision must fail before 18-page PlanReader extraction."""
from __future__ import annotations
import ast
import hashlib
from pathlib import Path
import pytest

from pb_migration_contracts import stable_contract_id
from tools.run_source_closed_project_handoff import (
    _preflight_registered_original_figure_issuers,
    require_source_issuer_revision_contract,
)

SHA = "b" * 64

def _row(source=SHA):
    document_id = "live-source:" + source[:32]
    return (
        document_id, source,
        stable_contract_id("source_revision", {
            "document_id": document_id, "source_sha256": source,
        }, digest_chars=32),
    )

def test_generic_same_document_full_sha_revision_admitted():
    require_source_issuer_revision_contract(
        source_sha256=SHA, issuer_receipts=(_row(),) * 4,
    )

@pytest.mark.parametrize("bad", [
    ("live-source:" + "a" * 32, SHA, _row()[2]),
    (_row()[0], "a" * 64, _row()[2]),
    (_row()[0], SHA, "3laurel_sha_shortened"),
    (_row()[0], SHA, ""),
    (None, SHA, _row()[2]),
])
def test_any_wrong_revision_document_or_sha_abstains_before_decode(bad):
    with pytest.raises(ValueError, match="revision_mismatch_before_decode"):
        require_source_issuer_revision_contract(
            source_sha256=SHA, issuer_receipts=(_row(), bad),
        )

def test_wrong_sha_types_and_empty_issuer_registry_are_rejected():
    with pytest.raises(ValueError, match="digest_required"):
        require_source_issuer_revision_contract(
            source_sha256=True, issuer_receipts=(_row(),),
        )
    with pytest.raises(ValueError, match="issuer_receipts_required"):
        require_source_issuer_revision_contract(
            source_sha256=SHA, issuer_receipts=(),
        )

def test_unrelated_project_does_not_invoke_3laurel_source_issuer():
    _preflight_registered_original_figure_issuers("unrelated-project", SHA)

def test_3laurel_registered_four_source_issuers_match_opening_authority():
    _preflight_registered_original_figure_issuers(
        "au_qld_3laurel",
        "014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e",
    )

def test_original_handoff_checks_revision_before_reading_plan_pages():
    path=Path(__file__).resolve().parents[1]/"tools/run_source_closed_project_handoff.py"
    module=ast.parse(path.read_text())
    funcs=[n for n in module.body if isinstance(n,ast.FunctionDef)
           and n.name=="_generate_project_handoff_locked"]
    assert len(funcs)==1
    calls=[
        (n.func.id, n.lineno) for n in ast.walk(funcs[0])
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
        and n.func.id in {
            "_preflight_registered_original_figure_issuers",
            "_source_page_scopes",
            "collect_live_physical_net_wall_claim",
        }
    ]
    line=dict(calls)
    assert line["_preflight_registered_original_figure_issuers"] < line["_source_page_scopes"] < line["collect_live_physical_net_wall_claim"]
