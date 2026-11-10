"""No public pull-request workflow may require the private 3Laurel original without a guard (owner priority 2026-11-10).

A workflow is an OFFENDER when it can run on ``pull_request``, has a job that names the 3Laurel original, and that job is neither
restricted to ``workflow_dispatch`` nor under the public ``skip_missing_in_public_ci`` policy: on a public PR the original is
absent, so the job can only fail (or, worse, pass without it). Jobs listed in ``KNOWN_UNMIGRATED`` belong to the canonical
private-source bridge (MAX) and are tolerated until it retires them (the list is empty now); a NEW offender, or a migrated one left in the list, fails.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ORIGINAL_MARK = "3LAUREL - Construction Plan Set"
POLICY = "PLANREADER_PRIVATE_ORIGINAL_POLICY"
PUBLIC_POLICY = "skip_missing_in_public_ci"
WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"

# (workflow file stem, job id): migrate each to workflow_dispatch-only or to the public skip policy, then delete its entry.
# Empty since the canonical bridge change retired both previously listed jobs (real-source-stages, original-3laurel-customer-shadow).
KNOWN_UNMIGRATED: set[tuple[str, str]] = set()


def _events(document) -> set[str]:
    on = document.get(True, document.get("on"))
    if isinstance(on, dict):
        return set(on)
    if isinstance(on, list):
        return set(on)
    return {on} if on else set()


def _job_has_policy(job: dict) -> bool:
    if (job.get("env") or {}).get(POLICY) == PUBLIC_POLICY:
        return True
    return any((step.get("env") or {}).get(POLICY) == PUBLIC_POLICY for step in job.get("steps", []) if isinstance(step, dict))


def offenders() -> set[tuple[str, str]]:
    found = set()
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        if ORIGINAL_MARK not in text:
            continue
        document = yaml.safe_load(text)
        if not ({"pull_request", "pull_request_target"} & _events(document)):
            continue
        for job_id, job in (document.get("jobs") or {}).items():
            if ORIGINAL_MARK not in yaml.safe_dump(job):
                continue
            guarded = "workflow_dispatch" in str(job.get("if", ""))
            if not guarded and not _job_has_policy(job):
                found.add((path.stem, job_id))
    return found


def test_every_pull_request_job_that_names_the_3laurel_original_is_guarded_or_a_known_unmigrated_job():
    current = offenders()
    new = current - KNOWN_UNMIGRATED
    assert not new, f"unguarded public PR job(s) naming the private 3Laurel original: {sorted(new)}"


def test_a_migrated_job_is_removed_from_the_known_list():
    stale = KNOWN_UNMIGRATED - offenders()
    assert not stale, f"already guarded, remove from KNOWN_UNMIGRATED: {sorted(stale)}"


def test_the_two_claude_measurement_workflows_are_dispatch_only():
    for stem in ("diag-claude-handoff-profile-stack", "diag-claude-lineage-attach-original-source"):
        document = yaml.safe_load((WORKFLOWS / f"{stem}.yml").read_text(encoding="utf-8"))
        assert _events(document) == {"workflow_dispatch"}, stem
        assert all("workflow_dispatch" in str(job.get("if", "")) or str(job.get("if", "")) == "always()" for job in document["jobs"].values()), stem


@pytest.mark.parametrize("stem", ["gpt1-3laurel-original-floor-area", "gpt1-3laurel-source-positive-opening"])
def test_the_provisioned_3laurel_workflows_fail_rather_than_skip_when_the_original_is_missing(stem):
    document = yaml.safe_load((WORKFLOWS / f"{stem}.yml").read_text(encoding="utf-8"))
    (job,) = document["jobs"].values()
    provisioning = [s for s in job["steps"] if "provision-original-sources" in str(s.get("uses", ""))]
    assert provisioning and all(str(s["with"]["allow-missing"]).lower() == "false" for s in provisioning)    # absent original: the job fails
    assert "workflow_dispatch" in str(job.get("if", "")) and "refs/heads/main" in str(job.get("if", ""))     # and never on a PR
    assert POLICY not in yaml.safe_dump(job)                                                                   # the public skip policy is never set here
