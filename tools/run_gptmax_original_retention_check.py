"""Execute an existing original-source producer and audit exact retention.

Validation only: no benchmark truth, object mapping, quantity manufacture or
archived-row import into a producer. A matching file alone is not execution.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from tools.run_gpt3_lot16_original_sealed_score_input import _publish_new

PRODUCERS = {
    "lot16":"tools.run_gpt3_lot16_original_sealed_score_input",
    "maryborough":"tools.run_gpt3_maryborough_original_floor_score_input",
}
SIGNED_FILES = ("source_sealed_run.json", "verified_customer_rows.json")


def _git(repo, *args):
    return subprocess.check_output(["git","-C",str(repo),*args],text=True).strip()


def compare_retained_source_files(produced, archived):
    """Byte evidence only. This function does not claim source execution."""
    result = []
    for name in SIGNED_FILES:
        actual, original = Path(produced)/name, Path(archived)/name
        if not actual.is_file() or not original.is_file():
            raise ValueError("signed retention file unavailable: " + name)
        a, b = actual.read_bytes(), original.read_bytes()
        result.append({"file":name, "produced_sha256":hashlib.sha256(a).hexdigest(),
                       "archived_sha256":hashlib.sha256(b).hexdigest(), "byte_identical":a == b})
    return result


def _environment(project):
    packages = ("PyMuPDF","numpy","opencv-python-headless","shapely","Pillow")
    versions = {name:importlib.metadata.version(name) for name in packages}
    result = {"python":sys.version.split()[0], "packages":versions}
    if project == "maryborough":
        # Room-label proof uses the listed OCR bridge as well as the OS binary.
        # Missing OCR must fail preflight, not masquerade as a zero-floor replay.
        import pytesseract
        if shutil.which(pytesseract.pytesseract.tesseract_cmd) is None:
            raise ValueError("required original-source OCR binary unavailable")
        result["packages"]["pytesseract"] = importlib.metadata.version("pytesseract")
        result["tesseract"] = str(pytesseract.get_tesseract_version())
    return result


def run_retention_check(*, project, pdf, expected_source_sha256, archived, output, expected_head):
    repo = Path(__file__).resolve().parents[1]
    pdf, archived, output = Path(pdf), Path(archived), Path(output)
    if project not in PRODUCERS:
        raise ValueError("an existing original-source producer is required")
    head = _git(repo,"rev-parse","HEAD")
    if head != expected_head or _git(repo,"status","--porcelain","--untracked-files=all"):
        raise ValueError("source replay requires the exact clean committed producer head")
    if (not pdf.is_file() or hashlib.sha256(pdf.read_bytes()).hexdigest() != expected_source_sha256):
        raise ValueError("original source SHA mismatch")
    if output.exists() or output.is_symlink():
        raise FileExistsError("source retention output must be new")
    if output.resolve().is_relative_to(archived.resolve()):
        raise ValueError("source retention cannot write into archived evidence")
    if any(not (archived/name).is_file() for name in SIGNED_FILES):
        raise ValueError("archived signed source/customer pair unavailable")
    environment = _environment(project)
    archive_hashes = {name:hashlib.sha256((archived/name).read_bytes()).hexdigest() for name in SIGNED_FILES}
    tree = _git(repo,"rev-parse","HEAD^{tree}")
    output.mkdir(parents=True)
    production = output/"production"
    command = [sys.executable,"-u","-m",PRODUCERS[project],"--pdf",str(pdf.resolve()),
               "--output-dir",str(production.resolve())]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    with (output/"producer.log").open("w",encoding="utf-8") as stream:
        completed = subprocess.run(command,cwd=repo,env=env,stdout=stream,stderr=subprocess.STDOUT,check=False)
    unchanged = head == _git(repo,"rev-parse","HEAD") and not _git(repo,"status","--porcelain","--untracked-files=all")
    comparison_error = None
    try:
        files = compare_retained_source_files(production,archived) if completed.returncode == 0 else []
    except ValueError as exc:
        files, comparison_error = [], str(exc)
    source_unchanged = hashlib.sha256(pdf.read_bytes()).hexdigest() == expected_source_sha256
    archive_unchanged = all(hashlib.sha256((archived/name).read_bytes()).hexdigest() == sha
                            for name,sha in archive_hashes.items())
    receipt = {"producer_head_sha":head, "producer_tree_sha":tree,
        "source_sha256":expected_source_sha256, "project":project, "environment":environment,
        "source_replay_completed":completed.returncode == 0, "producer_returncode":completed.returncode,
        "source_bytes_unchanged":source_unchanged, "comparison_error":comparison_error,
        "producer_head_unchanged":unchanged, "archived_source_receipts_unchanged":archive_unchanged,
        "files":files, "retention_verified":completed.returncode == 0 and unchanged
            and source_unchanged and archive_unchanged and len(files) == len(SIGNED_FILES)
            and all(r["byte_identical"] for r in files),
        "benchmark_score_granted":False, "commercial_promotion_granted":False}
    _publish_new(output/"retention_receipt.json",receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project",required=True,choices=tuple(PRODUCERS))
    parser.add_argument("--pdf",required=True,type=Path)
    parser.add_argument("--expected-source-sha256",required=True)
    parser.add_argument("--archived",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--expected-head",required=True)
    result = run_retention_check(**vars(parser.parse_args()))
    print(json.dumps(result,sort_keys=True))
    return 0 if result["retention_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
