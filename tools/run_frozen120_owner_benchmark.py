"""Run the four frozen projects or verify and re-score saved results."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
from time import perf_counter

from tools.gpt3_safe_original_report_output import preflight_new_diagnostic
from tools.report_gpt3_four_project_evidence import FROZEN_ROOT, main as report_evidence


def _score_run(source_dir: Path, identity_map_dir: Path, evidence_dir: Path, output_dir: Path) -> int:
    return report_evidence([
        "--source-dir", str(source_dir), "--sealed-dir", str(evidence_dir / "sealed"),
        "--identity-map-dir", str(identity_map_dir), "--customer-dir", str(evidence_dir / "customer"),
        "--output", str(output_dir / "frozen120_score.json"),
    ])


def run_benchmark(
    *, source_dir: Path, identity_map_dir: Path, output_dir: Path, timeout_min: int,
    saved_run_dir: Path | None = None,
) -> int:
    """Run serially or re-score existing handoffs through the same verifier."""
    source_dir = source_dir.resolve()
    identity_map_dir = identity_map_dir.resolve()
    preflight_new_diagnostic(
        output_dir, protected_roots=(source_dir, identity_map_dir, FROZEN_ROOT, saved_run_dir),
    )
    if saved_run_dir is not None:
        saved_run_dir = saved_run_dir.resolve()
        if not (saved_run_dir / "sealed").is_dir() or not (saved_run_dir / "customer").is_dir():
            raise ValueError("saved run directory must contain sealed and customer directories")
        return _score_run(source_dir, identity_map_dir, saved_run_dir, output_dir)

    from tools.gpt3_owner_all_source_role_handoff import (
        PROJECTS, original_roster, produce_all_source_roles,
    )

    rosters = [original_roster(project, source_dir) for project in PROJECTS]
    if sum(map(len, rosters)) != 10:
        raise ValueError("expected ten authentic frozen benchmark sources")
    output_dir.mkdir(parents=True, exist_ok=False)
    output_dir = output_dir.resolve()
    sealed_dir = output_dir / "sealed"
    customer_dir = output_dir / "customer"
    sealed_dir.mkdir()
    customer_dir.mkdir()

    total_started = perf_counter()
    outcomes = []
    for project in PROJECTS:
        started = perf_counter()
        role_dir = output_dir / "production" / project
        print(f"Starting original-source replay for {project}", flush=True)
        try:
            status = produce_all_source_roles(
                project_id=project, source_dir=source_dir, output_dir=role_dir,
                timeout_min=timeout_min, record_native_source_input_coverage=True,
                source_native_finish_text_shadow=True, source_role_abstention_receipts=True,
            )
            outcome = {"project_id": project, "status": status["status"]}
            if (
                status.get("native_source_input_coverage_verified") is True
                and status.get("source_role_coverage_verified") is True
                and status.get("customer_bijection_verified") is True
            ):
                shutil.copyfile(role_dir / "ALL_SOURCE_ROLES.sealed.json", sealed_dir / f"{project}.json")
                shutil.copyfile(
                    role_dir / "ALL_SOURCE_ROLES.customer_rows.json",
                    customer_dir / f"{project}.customer_rows.json",
                )
        except (OSError, TypeError, ValueError, RuntimeError) as exc:
            outcome = {"project_id": project, "status": "ROLE_REPLAY_FAILED",
                       "failure_type": type(exc).__name__}
        outcome["elapsed_seconds"] = round(perf_counter() - started, 3)
        outcomes.append(outcome)
        print(json.dumps(outcome, sort_keys=True), flush=True)
        status_path = output_dir / "attempt_status.json"
        staged = status_path.with_suffix(".tmp")
        staged.write_text(
            json.dumps({"projects": outcomes, "elapsed_seconds": round(perf_counter() - total_started, 3)},
                       indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        staged.replace(status_path)

    return _score_run(source_dir, identity_map_dir, output_dir, output_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--identity-map-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout-min", type=int, default=180,
                        help="Maximum extraction time per source document")
    parser.add_argument("--saved-run-dir", type=Path,
                        help="Verify and re-score an existing sealed/customer run without extracting PDFs")
    args = parser.parse_args(argv)
    if args.timeout_min < 1:
        parser.error("--timeout-min must be positive")
    return run_benchmark(
        source_dir=args.source_dir, identity_map_dir=args.identity_map_dir,
        output_dir=args.output_dir, timeout_min=args.timeout_min,
        saved_run_dir=args.saved_run_dir,
    )


if __name__ == "__main__":
    raise SystemExit(main())
