"""Read-only crash-persistent source-stage timing for existing source handoffs.

No source filtering, geometry, measurement, area, material, quantity or seal
authorization is implemented here. The tool runs the unchanged production
entrypoint, wrapping named stage callables only to record start/end/error.
Use an ORIGINAL SHA-verified PDF and a fresh output directory.

Example:
PYTHONPATH=. python -u tools/diag_source_closed_stage_journal.py \
  --pdf documents/sources/Arch_Combined_Maryborough_Service_Station.pdf \
  --expected-sha256 b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007 \
  --project-id diagnostic-source-maryborough --family-group surfaces \
  --output-dir artifacts/new-source-run --journal artifacts/new-source-stage.jsonl
The external Actions shell may bound this invocation with `timeout`; the
journal is synchronously persisted before each producer stage begins.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import re
try:
    import resource
except ImportError:  # Windows diagnostic import is never a source failure.
    resource = None
from time import monotonic_ns, time_ns
from typing import Any, Iterable, Iterator

import pb_live_physical_net_wall_integration as integration
import pb_physical_wall_candidate_authority as wall_candidates
from pb_semantic_opening_enumeration_authority import SemanticOpeningEnumerationProducer
from pb_physical_opening_authority import PhysicalOpeningAuthority
from tools.run_source_closed_project_handoff import generate_project_handoff


# High-level original source authority calls. Never patch validators, source
# authentication, candidate selection, physical identity or scoring.
_STAGE_NAMES = (
    "compose_live_wall_opening_authority",
    "compose_live_canonical_walls",
    "compose_live_canonical_rooms",
    "compose_live_canonical_spaces",
    "compose_live_canonical_floor_surfaces",
    "enrich_live_canonical_floor_metric_areas",
    "compose_live_physical_opening_voids",
    "publish_live_opening_area_quantities",
    "publish_live_authenticated_opening_count_quantities",
    "compose_live_gross_wall_geometry",
    "compose_live_whole_wall_roles",
    "compose_live_external_physical_net_wall_publication",
)
_MODULE_STAGES = (
    (wall_candidates, "_build_scope_result", "physical_wall_candidate_page_build"),
    # Read-only original W4 page-local cost decomposition. The producer's
    # own _build_scope_result still selects original page and source receipts;
    # these are imported internal callables, not replacement algorithms.
    (wall_candidates, "_source_page_segments", "physical_wall_source_page_segments"),
    (wall_candidates, "_producer_owned_points_per_mm", "physical_wall_source_scale"),
    (wall_candidates, "_assemble_scope_result", "physical_wall_scope_assembly"),
    (wall_candidates, "_filter_repeated_non_physical_drafting_primitives", "physical_wall_motif_filter"),
    (wall_candidates, "_proven_filled_wall_strips", "physical_wall_source_filled_strips"),
    (wall_candidates, "build_wall_graph_for_viewport", "physical_wall_W2_graph"),
    (wall_candidates, "classify_junctions", "physical_wall_W3_junctions"),
    (wall_candidates, "assemble_wall_topology", "physical_wall_W4_assembly"),
    (wall_candidates, "collect_physical_wall_identities", "physical_wall_identity_collection"),
    (wall_candidates, "_source_snap_collapsed_fragment_inventory", "physical_wall_collapsed_source_inventory"),
    (wall_candidates, "resolve_physical_wall_equivalence", "physical_wall_equivalence"),
    (wall_candidates, "_producer_opening_relation_overrides", "physical_wall_opening_relations"),
    (wall_candidates, "_producer_proven_page_opening_records", "physical_wall_full_original_opening_proof"),
)
_METHOD_STAGES = (
    (integration.SourceVisibilityProducer, "augment_with_raster_opening_primitives"),
    (integration.SourceVisibilityProducer, "augment_with_raster_visible_segments"),
    (SemanticOpeningEnumerationProducer, "publish_page_scope"),
    (PhysicalOpeningAuthority, "_visible_all_structural_candidates"),
    (integration.SourceVisibilityProducer, "ingest_native_pdf_bytes"),
    (integration.CrossViewFloorFinishProducer, "publish"),
    (integration.CrossViewCeilingFinishProducer, "publish"),
    (integration.SameViewRoomAreaProducer, "publish"),
    (integration.CrossViewRoomAreaProducer, "publish"),
)


def _peak_rss_kb() -> int:
    """Non-authoritative Linux Actions process peak-memory observation."""
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) if resource is not None else 0


class StageJournal:
    def __init__(self, output: Path) -> None:
        self._stream = output.open("x", encoding="utf-8")
        self._next_call = 0

    def emit(self, *, stage: str, event: str, call_id: int,
             elapsed_ms: float | None = None, error_type: str | None = None,
             source_page_id: str | None = None,
             observation_calls: int | None = None,
             cumulative_ms: float | None = None) -> None:
        payload: dict[str, Any] = {
            "diagnostic_only": True,
            "stage": stage,
            "event": event,
            "call_id": call_id,
            "wallclock_unix_ns": time_ns(),
            "monotonic_ns": monotonic_ns(),
            "peak_rss_kb": _peak_rss_kb(),
        }
        if elapsed_ms is not None:
            payload["elapsed_ms"] = round(elapsed_ms, 3)
        if error_type is not None:
            payload["error_type"] = error_type
        if source_page_id is not None:
            payload["source_page_id"] = source_page_id
        if observation_calls is not None:
            payload["observation_calls"] = observation_calls
        if cumulative_ms is not None:
            payload["cumulative_ms"] = round(cumulative_ms, 3)
        self._stream.write(json.dumps(payload, sort_keys=True) + "\n")
        self._stream.flush()
        os.fsync(self._stream.fileno())

    def next_id(self) -> int:
        self._next_call += 1
        return self._next_call

    def close(self) -> None:
        self._stream.close()


@contextmanager
def journal_source_stages(journal: StageJournal) -> Iterator[None]:
    """Wrap calls, never their results, inputs, errors or original authority."""
    originals: list[tuple[Any, str, Any]] = []
    targets: Iterable[tuple[Any, str, str]] = (
        *((integration, name, name) for name in _STAGE_NAMES),
        *((owner, name, label) for owner, name, label in _MODULE_STAGES),
        *((cls, name, f"{cls.__name__}.{name}") for cls, name in _METHOD_STAGES),
    )
    try:
        for owner, name, label in targets:
            original = getattr(owner, name)
            if not callable(original):
                raise TypeError(f"stage is not callable: {label}")

            def wrapper_factory(fn, stage):
                @wraps(fn)
                def wrapper(*args, **kwargs):
                    call_id = journal.next_id()
                    started = monotonic_ns()
                    # Emit only a producer-supplied exact source-page address.
                    # No injected page scope, inferred viewport or benchmark ID.
                    source_page_id = kwargs.get("page_id")
                    if (type(source_page_id) is not str
                            or re.fullmatch(r"[0-9]{1,5}", source_page_id) is None):
                        source_page_id = None
                    journal.emit(stage=stage, event="entered", call_id=call_id,
                                 source_page_id=source_page_id)
                    try:
                        result = fn(*args, **kwargs)
                    except BaseException as exc:
                        journal.emit(
                            stage=stage, event="failed", call_id=call_id,
                            elapsed_ms=(monotonic_ns() - started) / 1_000_000,
                            error_type=type(exc).__name__,
                            source_page_id=source_page_id,
                        )
                        raise
                    journal.emit(
                        stage=stage, event="completed", call_id=call_id,
                        elapsed_ms=(monotonic_ns() - started) / 1_000_000,
                        source_page_id=source_page_id,
                    )
                    return result
                return wrapper

            setattr(owner, name, wrapper_factory(original, label))
            originals.append((owner, name, original))

        # Report bounded progress during the original semantic opening scan.
        # Classification is called per source observation and a per-call fsync
        # would itself distort performance; emit only one sample per 256 calls.
        # This wrapper neither selects nor skips an observation, and never
        # changes the original authority's result, selector or exception.
        classifier = PhysicalOpeningAuthority.classify_disposition
        classifier_calls = 0
        classifier_elapsed_ns = 0

        @wraps(classifier)
        def sampled_classification(*args, **kwargs):
            nonlocal classifier_calls, classifier_elapsed_ns
            started = monotonic_ns()
            try:
                result = classifier(*args, **kwargs)
            except BaseException as exc:
                classifier_elapsed_ns += monotonic_ns() - started
                journal.emit(
                    stage="PhysicalOpeningAuthority.classify_disposition",
                    event="failed", call_id=journal.next_id(),
                    elapsed_ms=(monotonic_ns() - started) / 1_000_000,
                    observation_calls=classifier_calls,
                    cumulative_ms=classifier_elapsed_ns / 1_000_000,
                    error_type=type(exc).__name__,
                )
                raise
            classifier_elapsed_ns += monotonic_ns() - started
            classifier_calls += 1
            if classifier_calls % 256 == 0:
                journal.emit(
                    stage="PhysicalOpeningAuthority.classify_disposition",
                    event="sample", call_id=journal.next_id(),
                    observation_calls=classifier_calls,
                    cumulative_ms=classifier_elapsed_ns / 1_000_000,
                )
            return result

        PhysicalOpeningAuthority.classify_disposition = sampled_classification
        originals.append((PhysicalOpeningAuthority, "classify_disposition", classifier))

        # The W4 original-page proof replays EVERY source observation. A sample
        # after every 512 existence proofs measures true cost without O(n)
        # fsync overhead and without removing or reordering a source selector.
        # The measured count is diagnostic only, never opening completeness.
        original_prove = PhysicalOpeningAuthority.prove_existence
        proof_calls = 0
        proof_elapsed_ns = 0

        @wraps(original_prove)
        def sampled_original_existence(*args, **kwargs):
            nonlocal proof_calls, proof_elapsed_ns
            started = monotonic_ns()
            try:
                result = original_prove(*args, **kwargs)
            except BaseException as exc:
                proof_elapsed_ns += monotonic_ns() - started
                journal.emit(
                    stage="PhysicalOpeningAuthority.prove_existence",
                    event="failed", call_id=journal.next_id(),
                    elapsed_ms=(monotonic_ns() - started) / 1_000_000,
                    observation_calls=proof_calls,
                    cumulative_ms=proof_elapsed_ns / 1_000_000,
                    error_type=type(exc).__name__,
                )
                raise
            proof_elapsed_ns += monotonic_ns() - started
            proof_calls += 1
            if proof_calls % 512 == 0:
                journal.emit(
                    stage="PhysicalOpeningAuthority.prove_existence",
                    event="sample", call_id=journal.next_id(),
                    observation_calls=proof_calls,
                    cumulative_ms=proof_elapsed_ns / 1_000_000,
                )
            return result

        PhysicalOpeningAuthority.prove_existence = sampled_original_existence
        originals.append((PhysicalOpeningAuthority, "prove_existence", original_prove))
        yield
    finally:
        for owner, name, original in reversed(originals):
            setattr(owner, name, original)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--workspace-id", type=int, default=1)
    parser.add_argument("--family-group", choices=("all", "core", "surfaces"), default="surfaces")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    args = parser.parse_args()

    if not args.pdf.is_file():
        parser.error(f"source PDF unavailable: {args.pdf}")
    if not re.fullmatch(r"[a-fA-F0-9]{64}", args.expected_sha256):
        parser.error("expected source SHA-256 must be exactly 64 hex digits")
    source_sha = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    if source_sha != args.expected_sha256.lower():
        raise ValueError("original source SHA does not match expected evidence")
    if args.journal.exists() or args.journal.is_symlink():
        raise FileExistsError(f"refuse to overwrite stage journal: {args.journal}")
    args.journal.parent.mkdir(parents=True, exist_ok=True)
    with StageJournalContext(args.journal) as journal:
        journal.emit(stage="source_input", event="sha_verified", call_id=0)
        with journal_source_stages(journal):
            summary = generate_project_handoff(
                pdf_path=args.pdf,
                project_id=args.project_id,
                workspace_id=args.workspace_id,
                output_dir=args.output_dir,
                family_group=args.family_group,
            )
    if (summary.get("source_sha256") != source_sha
            or hashlib.sha256(args.pdf.read_bytes()).hexdigest() != source_sha):
        raise RuntimeError("original source identity changed during diagnostic run")
    print(json.dumps({
        "original_pdf_sha256": source_sha,
        "journal": str(args.journal),
        "diagnostic_only": True,
        "production_status": summary.get("status"),
        "benchmark_score_granted": False,
        "sealed_run_file": summary.get("combined_run_file"),
    }, sort_keys=True), flush=True)
    return 0 if summary.get("status") == "sealed" else 1


@contextmanager
def StageJournalContext(path: Path) -> Iterator[StageJournal]:
    journal = StageJournal(path)
    try:
        yield journal
    finally:
        journal.close()


if __name__ == "__main__":
    raise SystemExit(main())
