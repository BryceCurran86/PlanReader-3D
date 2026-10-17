"""Insert the ``provision-original-sources`` step into every workflow job that reads the original source PDFs.

Dry run by default; ``--apply`` rewrites the files. Line endings and every other byte of each workflow are preserved: the
only change is one inserted step after the job's first ``actions/checkout`` step. Each rewrite is re-parsed and compared
with the original structure before it is written, and a second run changes nothing.

A job needs the originals when its text names ``documents/sources`` / ``benchmarks/sources``, or when it is listed in
``WHOLE_SUITE`` (jobs that run the full ``tests/`` tree, whose tests read the originals without the workflow saying so).
The step provisions exactly the manifest names the job mentions; a job that mentions the directory but no file name, and
the whole-suite jobs, get every document.

Usage:
    python scripts/apply_provision_original_sources.py [--root .] [--action-ref main] [--only GLOB ...] [--apply]
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import yaml

ACTION_REPO = "BryceCurran86/PlanReader-3D"
ACTION_PATH = ".github/actions/provision-original-sources"
MANIFEST_GLOB = "benchmarks/frozen_holdout/full_plan_v2/projects/*/source_manifest.json"
MARKER = "provision-original-sources"
SOURCE_DIR_TOKENS = ("documents/sources", "benchmarks/sources")
# A job that runs the whole tests/ tree: its tests read the originals without the workflow saying so.
WHOLE_SUITE = re.compile(r"pytest[^\n#]*\stests/?(?=\s|$|[\"'])")


def manifest_names(root: Path) -> List[str]:
    names: List[str] = []
    for path in sorted(root.glob(MANIFEST_GLOB)):
        for doc in json.loads(path.read_text(encoding="utf-8")).get("source_documents", []):
            if doc.get("name") not in names:
                names.append(doc["name"])
    if not names:
        raise SystemExit(f"no source manifests under {root}")
    return names


def reads_originals(job_text: str) -> bool:
    """True when the job names the source directories or runs the whole test tree."""
    return bool(WHOLE_SUITE.search(job_text)) or any(token in job_text for token in SOURCE_DIR_TOKENS)


# (workflow file, job id) -> reason. These jobs are never given the originals.
EXCLUDED_JOBS = {
    ("package-full-plan-v2-verified-checkout.yml", "snapshot-public-repository-only"):
        "obsolete: it archives the tracked checkout and asserts that an original PDF is inside it, which is exactly what the "
        "originals-out-of-git policy forbids; provisioning would change nothing (git archive skips untracked files) and "
        "the assertion can only pass if a PDF is tracked again",
}
# An artifact path that could sweep documents/sources into a downloadable artifact (artifacts of a public repository are
# readable by anyone). Paths under artifacts/ or the runner temp directory are the repository convention and are fine.
_BROAD_ARTIFACT_PATHS = {".", "./", "*", "**", "**/*", "documents", "documents/", "${{ github.workspace }}"}


def unsafe_artifact_paths(steps: Sequence[object]) -> List[str]:
    """Upload-artifact paths in a job's steps that could include documents/sources."""
    bad: List[str] = []
    for step in steps:
        if not isinstance(step, dict) or "actions/upload-artifact" not in str(step.get("uses", "")):
            continue
        raw = (step.get("with") or {}).get("path", "")
        for line in str(raw).splitlines():
            entry = line.strip().strip("'\"")
            if not entry:
                continue
            if (entry in _BROAD_ARTIFACT_PATHS or entry.startswith("documents/") or entry.startswith("./documents")
                    or "documents/sources" in entry or "benchmarks/sources" in entry):
                bad.append(entry)
    return bad


def _job_spans(lines: Sequence[str]) -> Dict[str, Tuple[int, int]]:
    """Line span [start, end) of each job under the top-level ``jobs:`` key (2-space job indent)."""
    start = next((i for i, line in enumerate(lines) if line.rstrip() == "jobs:"), None)
    if start is None:
        return {}
    heads: List[Tuple[str, int]] = []
    end_of_jobs = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line.strip() == "" or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0:
            end_of_jobs = i
            break
        match = re.match(r"^  ([A-Za-z0-9_-]+):\s*(#.*)?$", line.rstrip())
        if indent == 2 and match:
            heads.append((match.group(1), i))
    spans: Dict[str, Tuple[int, int]] = {}
    for n, (name, first) in enumerate(heads):
        last = heads[n + 1][1] if n + 1 < len(heads) else end_of_jobs
        spans[name] = (first, last)
    return spans


def _checkout_step_end(lines: Sequence[str], first: int, last: int) -> Optional[Tuple[int, str]]:
    """(index after the first checkout step, indent of its ``- `` marker) inside lines[first:last]."""
    for i in range(first, last):
        if re.search(r"uses:\s*actions/checkout@", lines[i]):
            # find the dash line that opens this step (the line itself or one above it)
            j = i
            while j >= first and not re.match(r"^\s*- ", lines[j]):
                j -= 1
            if j < first:
                return None
            indent = len(lines[j]) - len(lines[j].lstrip(" "))
            k = i + 1
            while k < last:
                line = lines[k]
                if line.strip() == "":
                    k += 1
                    continue
                cur = len(line) - len(line.lstrip(" "))
                if cur <= indent:
                    break
                k += 1
            # do not swallow trailing blank/comment lines that belong to the next step
            while k > i + 1 and (lines[k - 1].strip() == "" or lines[k - 1].lstrip().startswith("#")):
                k -= 1
            return k, " " * indent
    return None


def step_text(indent: str, names: Sequence[str], action_ref: str) -> List[str]:
    use = f"./{ACTION_PATH}" if action_ref == "local" else f"{ACTION_REPO}/{ACTION_PATH}@{action_ref}"
    out = [
        f"{indent}- name: Provision original sources",
        f"{indent}  uses: {use}",
        f"{indent}  with:",
        f"{indent}    token: ${{{{ secrets.ORIGINAL_SOURCES_TOKEN }}}}",
        f"{indent}    repository: ${{{{ vars.ORIGINAL_SOURCES_REPOSITORY }}}}",
        f"{indent}    ref: ${{{{ vars.ORIGINAL_SOURCES_REF }}}}",
    ]
    if names:
        out.append(f"{indent}    names: |")
        out.extend(f"{indent}      {n}" for n in names)
    return out


def plan_file(path: Path, all_names: Sequence[str], action_ref: str) -> Optional[Tuple[str, List[str], List[str]]]:
    """Return (new text, changed job ids, skipped job ids) or None when nothing needs to change."""
    raw = path.read_bytes().decode("utf-8")
    eol = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.split(eol)
    spans = _job_spans(lines)
    if not spans:
        return None
    inserts: List[Tuple[int, List[str]]] = []
    changed: List[str] = []
    skipped: List[str] = []
    parsed_jobs = (yaml.safe_load(raw) or {}).get("jobs") or {}
    for job, (first, last) in spans.items():
        text = eol.join(lines[first:last])
        if MARKER in text:
            continue
        whole = bool(WHOLE_SUITE.search(text))
        if not reads_originals(text):
            continue
        if (path.name, job) in EXCLUDED_JOBS or unsafe_artifact_paths((parsed_jobs.get(job) or {}).get("steps") or []):
            skipped.append(job)
            continue
        located = _checkout_step_end(lines, first, last)
        if located is None:
            skipped.append(job)
            continue
        end, indent = located
        names = [] if whole else [n for n in all_names if n in text]
        inserts.append((end, step_text(indent, names, action_ref)))
        changed.append(job)
    if not inserts:
        return (raw, [], skipped) if skipped else None
    for end, block in sorted(inserts, key=lambda t: t[0], reverse=True):
        lines[end:end] = block
    new = eol.join(lines)
    _assert_only_steps_added(raw, new, changed)
    return new, changed, skipped


def _assert_only_steps_added(old: str, new: str, changed_jobs: Sequence[str]) -> None:
    before, after = yaml.safe_load(old), yaml.safe_load(new)
    for job in changed_jobs:
        old_steps = before["jobs"][job]["steps"]
        new_steps = after["jobs"][job]["steps"]
        added = [s for s in new_steps if isinstance(s, dict) and MARKER in str(s.get("uses", ""))]
        if len(added) != 1 or len(new_steps) != len(old_steps) + 1:
            raise SystemExit(f"{job}: expected exactly one inserted step")
        remaining = [s for s in new_steps if s is not added[0]]
        if remaining != old_steps:
            raise SystemExit(f"{job}: existing steps changed")
        after["jobs"][job]["steps"] = old_steps
    if after != before:
        raise SystemExit("workflow changed outside the inserted steps")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=".")
    parser.add_argument("--action-ref", default="main", help="branch/tag/commit of the action repository, or 'local'")
    parser.add_argument("--only", action="append", default=[], metavar="GLOB",
                        help="only workflow files whose name matches this glob (repeatable), to roll out in batches")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root)
    names = manifest_names(root)
    files = sorted((root / ".github" / "workflows").glob("*.y*ml"))
    if args.only:
        files = [f for f in files if any(fnmatch.fnmatch(f.name, pattern) for pattern in args.only)]
    touched = jobs = 0
    skipped_all: List[str] = []
    for path in files:
        result = plan_file(path, names, args.action_ref)
        if result is None:
            continue
        new, changed, skipped = result
        skipped_all.extend(f"{path.name}:{j}" for j in skipped)
        if not changed:
            continue
        touched += 1
        jobs += len(changed)
        if args.apply:
            path.write_bytes(new.encode("utf-8"))
        else:
            print(f"would change {path.name}: {', '.join(changed)}")
    verb = "changed" if args.apply else "would change"
    print(f"{verb} {touched} workflow file(s), {jobs} job(s)")
    if skipped_all:
        print("jobs that need the originals but were left alone (no actions/checkout step, excluded, or an artifact path "
              "that could publish them):", ", ".join(skipped_all))
    return 0


if __name__ == "__main__":
    sys.exit(main())
