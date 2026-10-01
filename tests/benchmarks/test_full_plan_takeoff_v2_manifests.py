from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "frozen_holdout" / "full_plan_v2"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_suite_is_exactly_four_new_australian_projects():
    suite = _json(ROOT / "manifest.json")
    assert suite["required_project_count"] == 4
    assert len(suite["projects"]) == 4
    assert suite["historical_canonical_five_headline"] is False
    assert suite["projects"] == [
        "au_qld_lot16_power",
        "au_qld_3laurel",
        "au_qld_maryborough_service_station",
        "au_qld_q5446_armstrong32_harlequin",
    ]


def test_all_four_configured_projects_are_source_complete_but_not_falsely_verified():
    suite = _json(ROOT / "manifest.json")
    manifests = [
        _json(ROOT / "projects" / project_id / "source_manifest.json")
        for project_id in suite["projects"]
    ]
    assert len(manifests) == 4
    assert all(m["source_package_complete"] for m in manifests)
    assert all(m["status"] == "INCOMPLETE" for m in manifests)
    assert all("reference_takeoff_not_supplied" in m["reason_codes"] for m in manifests)


def test_source_hashes_are_frozen_to_uploaded_files():
    expected = {
        "au_qld_3laurel": "014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e",
        "au_qld_maryborough_service_station": "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007",
        "au_qld_lot16_power": "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844",
        "au_qld_q5446_armstrong32_harlequin": "5f29aa0122d72e2cc8886b3f19239ff32865c8d705eee99f785c389ca27fb7f0",
    }
    for project_id, sha in expected.items():
        manifest = _json(ROOT / "projects" / project_id / "source_manifest.json")
        assert manifest["source_documents"][0]["sha256"] == sha


def test_baseline_cli_runs_directly_from_repo_checkout():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "run_baseline.py")],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["publication_status"] == "UNPUBLISHED"
    assert payload["configured_projects"] == 4
