"""Duplicate public CI must preserve indexed receipts and declare source omissions."""
from copy import deepcopy
from pathlib import Path
import os
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = (
    "test-gptmax-raster-connected-frame-source.yml",
    "test-gptmax-raster-aperture-identity.yml",
    "test-gptmax-opening-wall-face-preservation.yml",
    "test-gptmax-native-description-source.yml",
    "test-gptmax-raster-measurement-source.yml",
    "test-gptmax-source-band-host-current.yml",
)
POLICY = "PLANREADER_PRIVATE_ORIGINAL_POLICY"


def _contract(document):
    jobs = document["jobs"]
    public = jobs["full-regressions"]
    assert public["env"][POLICY] == "skip_missing_in_public_ci"
    assert "PYTHONPYCACHEPREFIX" not in public["env"]
    assert all("${{ runner." not in str(value) for value in public["env"].values())
    # The runner context exists only after job dispatch, at step scope.
    cache_steps = [step for step in public["steps"] if step.get("name") in
                   ("Integrity and provider isolation", "Full regression suite")]
    assert len(cache_steps) == 2
    assert all(step.get("env", {}).get("PYTHONPYCACHEPREFIX") ==
               "${{ runner.temp }}/planreader-pycache" for step in cache_steps)
    assert public["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert public["strategy"]["matrix"]["python-version"] == ["3.13", "3.14"]
    scripts = [step.get("run", "") for step in public["steps"]]
    assert "PYTHONPATH=. python -m pytest -q tests/" in scripts
    assert any("python -m compileall -q ." in script for script in scripts)
    assert any("check_full_plan_v2_integrity.py" in script for script in scripts)
    assert any("check_provider_gold_isolation.py" in script for script in scripts)
    # An unavailable-source policy is only for public regressions. Original
    # source jobs must still actually run and fail when originals are missing.
    assert POLICY not in document.get("env", {})
    assert "source-proof" in jobs
    assert any("tools/diag_" in step.get("run", "")
               for step in jobs["source-proof"]["steps"])
    for name, job in jobs.items():
        if name == "full-regressions":
            continue
        assert POLICY not in job.get("env", {})
        for step in job.get("steps", ()):
            assert POLICY not in step.get("env", {})


@pytest.mark.parametrize("workflow", WORKFLOWS)
def test_public_regressions_match_required_ci_without_skipping_source_jobs(workflow):
    document = yaml.safe_load((ROOT / ".github/workflows" / workflow).read_text())
    _contract(document)


def test_every_duplicate_full_regression_job_is_discovered_without_a_stale_allowlist():
    discovered=set()
    for path in sorted((ROOT / '.github/workflows').glob('*.y*ml')):
        document=yaml.safe_load(path.read_text())
        if isinstance(document,dict) and 'full-regressions' in (document.get('jobs') or {}):
            discovered.add(path.name)
            _contract(document)
    assert discovered == set(WORKFLOWS)


def test_actual_compileall_keeps_indexed_source_tree_unchanged(tmp_path):
    document=yaml.safe_load((ROOT / '.github/workflows' / WORKFLOWS[-1]).read_text())
    public=document['jobs']['full-regressions']
    step=next(s for s in public['steps'] if s.get('name')=='Integrity and provider isolation')
    protected=tmp_path/'indexed-receipt-package'
    protected.mkdir()
    source=protected/'receipt_verifier.py'
    source.write_text('RECEIPT = 7\n',encoding='utf-8')
    before={p.relative_to(protected):p.read_bytes() for p in protected.rglob('*') if p.is_file()}
    external_cache=tmp_path/'runner-cache'
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':public['env']['PYTHONDONTWRITEBYTECODE'],
         'PYTHONPYCACHEPREFIX':step['env']['PYTHONPYCACHEPREFIX'].replace(
             '${{ runner.temp }}',str(external_cache))}
    subprocess.run([sys.executable,'-m','compileall','-q','.'],cwd=protected,
                   env=env,check=True,capture_output=True,text=True)
    after={p.relative_to(protected):p.read_bytes() for p in protected.rglob('*') if p.is_file()}
    assert after == before
    assert list(external_cache.rglob('receipt_verifier.*.pyc'))


@pytest.mark.parametrize("damage", ("local_cache", "bytecode", "source_policy", "narrow_tests", "job_runner_context", "missing_test_cache"))
def test_regression_contract_rejects_archive_pollution_and_false_source_pass(damage):
    document = yaml.safe_load((ROOT / ".github/workflows" / WORKFLOWS[0]).read_text())
    damaged = deepcopy(document)
    public = damaged["jobs"]["full-regressions"]
    if damage == "local_cache":
        next(s for s in public["steps"] if s.get("name") == "Integrity and provider isolation")["env"]["PYTHONPYCACHEPREFIX"] = "docs/engineering/cache"
    elif damage == "bytecode":
        public["env"].pop("PYTHONDONTWRITEBYTECODE")
    elif damage == "source_policy":
        damaged["jobs"]["source-proof"].setdefault("env", {})[POLICY] = "skip_missing_in_public_ci"
    elif damage == "job_runner_context":
        public["env"]["PYTHONPYCACHEPREFIX"] = "${{ runner.temp }}/planreader-pycache"
    elif damage == "missing_test_cache":
        next(s for s in public["steps"] if s.get("name") == "Full regression suite")["env"].pop("PYTHONPYCACHEPREFIX")
    else:
        for step in public["steps"]:
            if "pytest" in step.get("run", ""):
                step["run"] = "python -m pytest -q tests/test_one.py"
    with pytest.raises((AssertionError, KeyError)):
        _contract(damaged)
