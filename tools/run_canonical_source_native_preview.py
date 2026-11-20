"""Run the ORIGINAL PlanReader UI source-native tracer with exact-source/revision proof.

This is a non-commercial footprint/room preview ONLY. It cannot publish official
frozen120 benchmark accuracy or customer quantities. Never substitute the separate
raster-first/inside-face diagnostic scripts as a full-engine result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from collections.abc import Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXPECTED_PRODUCER = "pb_layered_wall_doorway_room_ring_shadow.build_layered_wall_doorway_room_rings"
NATIVE_STAGE = "attempt_source_native_exterior_wall_trace_first"
RASTER_STAGE = "attempt_raster_source_walls_first"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class WrongTraceRoute(RuntimeError):
    """Never silently turn a diagnostic into a canonical trace receipt."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for piece in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(piece)
    return digest.hexdigest()


def _expected_hash(value: str, length: int, name: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{" + str(length) + r"}", value):
        raise WrongTraceRoute(f"{name}_must_be_full_lowercase_hex_hash")
    return value


def _git_head(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"], cwd=repo_root,
            capture_output=True, text=True, check=True, timeout=10,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise WrongTraceRoute("full_current_repository_checkout_required") from exc
    return _expected_hash(result.stdout.strip(), 40, "checkout_head")


def validate_canonical_preview(
    summary: Mapping[str, object],
    *,
    expected_source_sha256: str,
    expected_page_index: int,
) -> dict[str, object]:
    """Fail closed on any wrong engine, wrong source, fallback or commercial promotion."""
    _expected_hash(expected_source_sha256, 64, "source_sha256")
    if type(expected_page_index) is not int or expected_page_index < 0:
        raise WrongTraceRoute("source_page_index_invalid")
    if not isinstance(summary, Mapping):
        raise WrongTraceRoute("canonical_preview_summary_missing")
    if summary.get("source_sha256") != expected_source_sha256:
        raise WrongTraceRoute("canonical_preview_source_sha_mismatch")
    if type(summary.get("page_index")) is not int or summary["page_index"] != expected_page_index:
        raise WrongTraceRoute("canonical_preview_page_index_mismatch")
    if summary.get("producer") != EXPECTED_PRODUCER:
        raise WrongTraceRoute("wrong_trace_producer_or_diagnostic_only")
    if summary.get("legacy_envelope_used") is not False or summary.get("legacy_fallback_allowed") is not False:
        raise WrongTraceRoute("legacy_trace_fallback_forbidden")
    if summary.get("quantity_authorized") is not False or summary.get("commercial_publishable") is not False:
        raise WrongTraceRoute("preview_must_not_publish_commercial_quantities")
    stages = summary.get("stage_order")
    if not isinstance(stages, (tuple, list)) or not stages:
        raise WrongTraceRoute("canonical_stage_lineage_missing")
    if stages[0] not in (NATIVE_STAGE, RASTER_STAGE):
        raise WrongTraceRoute("canonical_trace_stage_lineage_invalid")
    if "external_wall_trace_status" not in summary or "external_wall_trace_reason" not in summary:
        raise WrongTraceRoute("source_native_outer_wall_authority_result_missing")
    if not isinstance(summary.get("external_wall_native_source_paths"), list):
        raise WrongTraceRoute("native_wall_source_path_lineage_missing")
    if not isinstance(summary.get("external_wall_trace_status"), str) or not isinstance(
        summary.get("external_wall_trace_reason"), str
    ):
        raise WrongTraceRoute("native_wall_result_reason_missing")
    return {
        "route_verified": True,
        "approved_entrypoint": "pb_new_source_trace_preview.source_native_trace_preview",
        "actual_producer": EXPECTED_PRODUCER,
        "source_sha256": expected_source_sha256,
        "page_index": expected_page_index,
        "trace_stage": stages[0],
        "external_wall_trace_status": summary["external_wall_trace_status"],
        "external_wall_trace_reason": summary["external_wall_trace_reason"],
        "evidence_class": "ORIGINAL_SOURCE_NATIVE_PREVIEW_ONLY",
        "official_frozen120_scored": False,
        "measurement_authorized": False,
        "commercial_publishable": False,
    }


def run_preview(
    pdf: Path, *,
    page_index: int,
    expected_source_sha256: str,
    expected_head_sha: str,
    out_dir: Path,
    repo_root: Path = ROOT,
) -> Path:
    """Execute only the UI's real source-native preview at the exact supplied HEAD."""
    source_sha = _expected_hash(expected_source_sha256, 64, "source_sha256")
    required_head = _expected_hash(expected_head_sha, 40, "expected_head")
    if _git_head(repo_root) != required_head:
        raise WrongTraceRoute("wrong_code_revision_stop_before_source_run")
    if not pdf.is_file() or pdf.is_symlink() or pdf.suffix.lower() != ".pdf":
        raise WrongTraceRoute("original_private_pdf_required")
    if _sha256(pdf) != source_sha:
        raise WrongTraceRoute("original_private_pdf_sha_mismatch")
    if type(page_index) is not int or page_index < 0:
        raise WrongTraceRoute("source_page_index_invalid")

    from pb_new_source_trace_preview import source_native_trace_preview

    summary, image_bytes = source_native_trace_preview(pdf, page_index)
    receipt = validate_canonical_preview(
        summary, expected_source_sha256=source_sha, expected_page_index=page_index,
    )
    if not isinstance(image_bytes, bytes) or not image_bytes.startswith(PNG_SIGNATURE):
        raise WrongTraceRoute("original_source_native_preview_png_missing")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "canonical_source_native_preview.png").write_bytes(image_bytes)
    receipt["exact_head_sha"] = required_head
    receipt["full_preview_summary"] = dict(summary)
    (out_dir / "canonical_source_native_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    return out_dir / "canonical_source_native_receipt.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Only the approved ORIGINAL PlanReader source-native preview")
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page-index", type=int, required=True, help="Zero-based original drawing page")
    parser.add_argument("--source-sha256", required=True, help="Exact pinned original private PDF SHA256")
    parser.add_argument("--expected-head-sha", required=True, help="Exact 40-character Git checkout commit")
    parser.add_argument("--out-dir", type=Path, required=True, help="Private results directory")
    parser.add_argument("--purpose", choices=["preview", "official-benchmark"], required=True)
    args = parser.parse_args(argv)
    if args.purpose != "preview":
        parser.error(
            "This is a noncommercial preview, not the frozen120 scorer. "
            "Use the original source-closed project handoff and protected official benchmark."
        )
    try:
        receipt = run_preview(
            args.pdf, page_index=args.page_index,
            expected_source_sha256=args.source_sha256,
            expected_head_sha=args.expected_head_sha, out_dir=args.out_dir,
        )
    except (WrongTraceRoute, OSError, ValueError) as exc:
        print(f"CANONICAL_ROUTE_BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(f"CANONICAL_ORIGINAL_PREVIEW_ONLY: verified receipt at {receipt}")
    print("NOT AN OFFICIAL BENCHMARK SCORE; native candidate does not imply measured footprint.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
