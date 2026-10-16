"""Read-only original four-job owner RECEIPT verification, not a PDF hash reread.

The archived package contains share-safe derived artifacts, not the owner's
original PDFs. This verifier checks those committed bytes, their internal
source-manifest claims and stage-by-stage producer receipts. It cannot publish
or estimate frozen V2 accuracy, reissue source authority, or approve customers.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from typing import Any

from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from scripts.report_full_plan_v2_readiness import _write_readiness_report
from tools.report_gpt3_four_project_evidence import (
    FROZEN_ROOT, _json_object, load_suite_manifests, _read_json_without_duplicate_keys,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_LINE = re.compile(r"^([0-9a-f]{64})  ([^\r\n]+)$")
_EXTRA_DERIVED = frozenset({"README.md", "assemble_receipts.py", "RUN_RECEIPT.json"})
_REQUIRED_FILES = frozenset({
    "RUN_RECEIPT.json", "SOURCE_SHA_VERIFICATION.json", "PREFLIGHT_STATUS.json",
})
_SOURCE_SUCCESS = "VERIFIED"


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def _safe_file(root: Path, relative: str) -> Path:
    """No absolute, parent, escape, symlink, or alternate-separator aliases."""
    _require(type(relative) is str and bool(relative) and "\\" not in relative,
             "invalid receipt path")
    name = PurePosixPath(relative)
    _require(
        not name.is_absolute() and str(name) == relative
        and bool(name.parts) and all(part not in (".", "..") for part in name.parts)
        and ":" not in name.parts[0], "unsafe receipt path",
    )
    candidate = root
    for part in name.parts:
        candidate = candidate / part
        _require(not candidate.is_symlink(), "symlink in derived source receipt path")
    _require(candidate.resolve().is_relative_to(root.resolve()),
             "derived artifact escapes the receipt directory")
    _require(candidate.is_file(), "missing derived artifact: " + relative)
    return candidate


def _digest(path: Path) -> str:
    h = sha256()
    with path.open("rb") as reader:
        for block in iter(lambda: reader.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _object(root: Path, relative: str) -> dict[str, Any]:
    return _json_object(_safe_file(root, relative))


def _list(root: Path, relative: str) -> list:
    value = _read_json_without_duplicate_keys(
        _safe_file(root, relative).read_text(encoding="utf-8")
    )
    _require(type(value) is list, "derived receipt expected JSON array: " + relative)
    return value


def _sha_index(root: Path, owner: dict) -> tuple[dict[str, str], dict[str, str]]:
    """Independently SHA all 28 derived records AND all SHA256SUMS entries."""
    file_rows = owner.get("files")
    _require(type(file_rows) is list and bool(file_rows), "owner file ledger unavailable")
    indexed: dict[str, str] = {}
    for row in file_rows:
        _require(type(row) is dict, "invalid owner file ledger row")
        path = row.get("file")
        _require(type(path) is str and path not in indexed,
                 "duplicate or nonstring owner artifact path")
        expected = row.get("share_safe_sha256")
        _require(type(expected) is str and _SHA256.fullmatch(expected) is not None,
                 "malformed owner artifact SHA")
        private_sha = row.get("private_original_sha256")
        _require(type(private_sha) is str and _SHA256.fullmatch(private_sha) is not None,
                 "malformed original machine artifact SHA")
        _require(type(row.get("bytes")) is int and row["bytes"] >= 0,
                 "invalid original machine artifact size")
        actual_path = _safe_file(root, path)
        actual_sha = _digest(actual_path)
        _require(actual_sha == expected, "derived artifact digest mismatch: " + path)
        if private_sha == expected:
            _require(actual_path.stat().st_size == row["bytes"],
                     "unredacted derived artifact byte-size mismatch: " + path)
        indexed[path] = actual_sha
    lines = _safe_file(root, "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    sums: dict[str, str] = {}
    for line in lines:
        parsed = _LINE.fullmatch(line)
        _require(parsed is not None, "malformed SHA256SUMS line")
        digest, path = parsed.groups()
        _require(path not in sums, "duplicate SHA256SUMS entry")
        sums[path] = digest
        _require(_digest(_safe_file(root, path)) == digest,
                 "SHA256SUMS actual byte digest mismatch: " + path)
    _require(set(sums) == set(indexed) | _EXTRA_DERIVED,
             "SHA256SUMS universe differs from archived derived receipt")
    # No extra arbitrary artifact may be smuggled into an otherwise hash-valid
    # share-safe owner archive. SHA256SUMS itself is the only unlisted hash file.
    expected_tree = set(sums) | {"SHA256SUMS"}
    actual_tree = {
        file.relative_to(root).as_posix()
        for file in root.rglob("*") if file.is_file()
    }
    _require(actual_tree == expected_tree,
             "unindexed artifact in original share-safe receipt package")
    _require(all(sums[k] == sha for k, sha in indexed.items()),
             "SHA256SUMS and owner receipt disagree")
    return indexed, sums


def _cross_semantic_source_claims(quantities: Any) -> list[dict[str, Any]]:
    """Surface shared physical source with multiple families; never erase rows."""
    claims: dict[tuple[str, str, tuple[str, ...]], list] = {}
    for q in quantities:
        object_key = (
            q.source_sha256, q.revision_id, tuple(q.object_identity_refs),
        )
        claims.setdefault(object_key, []).append(q)
    return [
        {
            "source_sha256": key[0],
            "revision_id": key[1],
            "canonical_object_refs": list(key[2]),
            "signed_quantity_ids": sorted(q.quantity_id for q in values),
            "quantity_families": sorted({q.family for q in values}),
            "source_review_required": True,
        }
        for key, values in sorted(claims.items())
        if key[2] and len({q.family for q in values}) > 1
    ]


def _exact_execution_pages(value: Any, page_count: int, field: str) -> None:
    """A claimed all-page execution is not proved by an untyped/subset range."""
    _require(type(value) is list and all(type(v) is int for v in value),
             field + " must be canonical page-number array")
    _require(value == list(range(1, page_count + 1)),
             field + " does not span the original document exactly")


def _source_pages_subset(value: Any, page_count: int, field: str) -> None:
    _require(type(value) is list and all(type(v) is int for v in value),
             field + " must contain integer source pages")
    _require(len(set(value)) == len(value) and all(1 <= v <= page_count for v in value),
             field + " contains duplicate or out-of-source page")


def _original_windows_reference(
    value: Any,
    *,
    project_id: str,
    terminal: tuple[str, ...],
    root_segment: str,
) -> None:
    """A redacted Windows reference cannot point into a competing project."""
    _require(type(value) is str and value.startswith("<HOME>\\"),
             "producer original Windows reference missing redacted owner root")
    _require("/" not in value and ".." not in PureWindowsPath(value).parts,
             "malformed private source reference")
    parts = PureWindowsPath(value).parts
    expected_suffix = (root_segment, project_id, *terminal)
    _require(tuple(parts[-len(expected_suffix):]) == expected_suffix,
             "original source reference points to different project or artifact")


def _source_owned_reason_array(value: Any, name: str) -> None:
    _require(
        type(value) is list and all(
            type(v) is str and bool(v) and v == v.strip() for v in value
        ),
        name + " contains noncanonical source reason",
    )
    _require(len(set(value)) == len(value), name + " duplicates source reasons")


def verify_owner_four_job_receipts(root: Path) -> dict[str, Any]:
    """Reconcile share-safe owner-derived receipts without opening original PDFs."""
    root = root.resolve()
    _require(root.is_dir(), "original owner receipt directory unavailable")
    manifests = load_suite_manifests(FROZEN_ROOT)
    _require(len(manifests) == 4, "frozen four-project suite changed")
    frozen_by_id = {m.project_id: m for m in manifests}
    _require(len(frozen_by_id) == 4, "duplicate frozen project")
    denominator_by_id = {
        m.project_id: sum(item.denominator_eligible for item in m.verified_items)
        for m in manifests
    }
    _require(sum(denominator_by_id.values()) == 120, "frozen V2 denominator drift")
    original_docs = {
        (m.project_id, doc.name): doc for m in manifests for doc in m.source_documents
    }
    _require(len(original_docs) == 10, "frozen ten-document source universe drift")
    owner = _object(root, "RUN_RECEIPT.json")
    _require(owner.get("schema") == "four_job_owner_machine_run_receipt/1",
             "owner run receipt schema mismatch")
    head = owner.get("repo_head")
    _require(type(head) is str and _COMMIT.fullmatch(head) is not None,
             "owner original producer commit not pinned")
    _require(owner.get("requested_ref") == head, "owner execution ref differs from checkout")
    _require(owner.get("source_pdf_count") == 10,
             "owner source package not a ten-original-document universe")
    _require(owner.get("source_preflight") == "VERIFIED",
             "owner source package preflight not verified")
    _require(owner.get("full_suite_publication_status") == "UNPUBLISHED"
             and owner.get("official_four_project_coverage_accuracy") is None,
             "partial original owner receipts cannot publish a four-project score")

    source_receipt = _object(root, "SOURCE_SHA_VERIFICATION.json")
    _require(
        source_receipt.get("benchmark_id") == "full_plan_takeoff_reconciliation_v2"
        and source_receipt.get("expected_document_count") == 10
        and source_receipt.get("verified_document_count") == 10
        and source_receipt.get("score_granted") is False,
        "source receipt counts or benchmark publication mismatch",
    )
    original_rows = source_receipt.get("rows")
    _require(type(original_rows) is list and len(original_rows) == 10,
             "source SHA receipt did not enumerate all ten originals")
    seen_docs = set()
    for row in original_rows:
        _require(type(row) is dict, "malformed original document verification record")
        key = (row.get("project_id"), row.get("file_name"))
        _require(key in original_docs and key not in seen_docs,
                 "foreign or duplicate original source document in owner receipt")
        seen_docs.add(key)
        _require(row.get("status") == _SOURCE_SUCCESS,
                 "original source verification record is not VERIFIED")
    _require(seen_docs == set(original_docs), "incomplete original owner source universe")

    preflights = _list(root, "PREFLIGHT_STATUS.json")
    _require(len(preflights) == 4, "four original project preflights required")
    statuses: dict[str, dict] = {}
    for p in preflights:
        _require(type(p) is dict and type(p.get("project_id")) is str,
                 "invalid original preflight status")
        project = p["project_id"]
        _require(project in frozen_by_id and project not in statuses,
                 "foreign or duplicated project preflight")
        _require(p.get("status") == "COMPLETED" and p.get("exit_code") == 0,
                 "original project preflight failed")
        statuses[project] = p
    _require(set(statuses) == set(frozen_by_id), "original project preflight missing")

    handoffs = owner.get("project_handoffs")
    _require(type(handoffs) is list and len(handoffs) == 4,
             "four owner process handoff receipts required")
    process: dict[str, dict] = {}
    for handoff in handoffs:
        _require(type(handoff) is dict and type(handoff.get("project_id")) is str,
                 "invalid owner process receipt")
        project = handoff["project_id"]
        _require(project in frozen_by_id and project not in process,
                 "foreign or duplicated owner production attempt")
        _require(handoff.get("single_document_handoff_only") is True,
                 "owner diagnostic cannot imply full multidocument source closure")
        state = handoff.get("status")
        _require(type(state) is str and state in (
            "COMPLETED", "TIMEOUT", "MEMORY_LIMIT", "SYSTEM_MEMORY_GUARD",
            "ERROR", "FAILED",
        ), "unknown original handoff disposition")
        if state == "COMPLETED":
            _require(handoff.get("exit_code") == 0,
                     "completed source handoff has failing exit code")
        else:
            _require(handoff.get("exit_code") != 0,
                     "stopped source handoff falsely claims successful exit")
        process[project] = handoff
    _require(set(process) == set(frozen_by_id), "missing owner production status")

    rows: list[dict[str, Any]] = []
    cross_semantic_claims: dict[str, list[dict[str, Any]]] = {}
    verified_manifest_docs = 0
    for project_id, manifest in frozen_by_id.items():
        pre = _object(root, project_id + "/source_package_preflight.json")
        _require(pre.get("project_id") == project_id, "project preflight identity mismatch")
        documents = pre.get("source_documents")
        _require(type(documents) is list
                 and len(documents) == len(manifest.source_documents),
                 "original per-project source document count mismatch")
        _require(
            pre.get("expected_source_document_count") == len(documents)
            and pre.get("verified_source_document_count") == len(documents)
            and pre.get("actual_source_package_runtime_complete") is True,
            "source package runtime/preflight receipt incomplete",
        )
        _require(pre.get("benchmark_score_granted") is False
                 and pre.get("commercial_quantity_publication_granted") is False
                 and pre.get("rcp_or_metric_or_finish_authority_granted") is False,
                 "preflight illegitimately grants quantity or benchmark authority")
        _require(pre.get("manifest_declares_source_package_complete")
                 is manifest.source_package_complete,
                 "source package manifest completeness flag changed")
        by_name = {doc.name: doc for doc in manifest.source_documents}
        seen = set()
        for doc in documents:
            _require(type(doc) is dict, "malformed source preflight document")
            name = doc.get("name")
            _require(type(name) is str and name in by_name and name not in seen,
                     "duplicate/foreign per-project source preflight document")
            seen.add(name)
            expected = by_name[name]
            for key, value in (
                ("role", expected.role),
                ("expected_sha256", expected.sha256),
                ("actual_sha256", expected.sha256),
                ("expected_size_bytes", expected.size_bytes),
                ("actual_size_bytes", expected.size_bytes),
                ("expected_page_count", expected.page_count),
                ("actual_page_count", expected.page_count),
                ("status", _SOURCE_SUCCESS),
            ):
                _require(doc.get(key) == value,
                         "manifest/source preflight mismatch: " + key)
            verified_manifest_docs += 1
        _require(seen == set(by_name), "original manifest source page universe incomplete")

        summary = _object(root, project_id + "/outputs/production_summary.json")
        _require(summary.get("project_id") == project_id,
                 "producer summary project identity mismatch")
        _require(summary.get("schema_version") == "1.0.0"
                 and summary.get("benchmark_score_granted") is False
                 and summary.get("frozen_v2_reconciliation_complete") is False,
                 "producer summary falsely asserts benchmark reconciliation")
        _require(summary.get("customer_rows_file") is None
                 and summary.get("customer_rows_verified") is False
                 and summary.get("verified_customer_row_count") == 0,
                 "diagnostic has unsupported customer verification claim")
        family_counts = summary.get("family_counts")
        _require(type(family_counts) is dict and all(
            type(v) is int and v >= 0 for v in family_counts.values()
        ), "invalid production quantity family counts")
        # A completed process can still contain source-only candidates; the
        # producer's own page-scope receipts must agree before any sealing.
        page_count = primary_pages = summary.get("page_count")
        _require(type(page_count) is int and page_count > 0,
                 "invalid original producer source page count")
        _exact_execution_pages(summary.get("execution_pages"), page_count,
                               "production execution_pages")
        _exact_execution_pages(summary.get("semantic_execution_pages"), page_count,
                               "production semantic_execution_pages")
        for page_field in (
            "topology_pages", "room_area_support_pages", "canonical_wall_source_pages"
        ):
            _source_pages_subset(summary.get(page_field), page_count, page_field)
        candidate_page = summary.get("source_positive_partial_page")
        _require(candidate_page is None or (
            type(candidate_page) is int and 1 <= candidate_page <= page_count
        ), "partial source page lies outside authenticated document")
        _require(type(summary.get("canonical_counts")) is dict
                 and all(type(v) is int and v >= 0
                         for v in summary["canonical_counts"].values()),
                 "canonical diagnostic counts have invalid or negative value")
        _require(type(summary.get("unresolved_wall_candidate_count")) is int
                 and summary["unresolved_wall_candidate_count"] >= 0,
                 "invalid unresolved structural wall candidate count")
        _require(summary.get("claim_status") in (None, "abstained"),
                 "owner diagnostic cannot declare source-only firm claim")
        _require(summary.get("canonical_wall_status") in (
            None, "candidate", "abstained", "conflict",
        ), "owner diagnostic cannot promote candidate wall existence")
        for name in ("claim_reason_codes", "canonical_wall_reason_codes"):
            _source_owned_reason_array(summary.get(name), name)
        _require(type(summary.get("topology_mode")) is str
                 and summary["topology_mode"] in (
                     "source_classified_scope", "live_authority_all_pages_fallback",
                 ), "unrecognized source topology scope")
        _original_windows_reference(
            summary.get("source_path"), project_id=project_id,
            terminal=(next(d.name for d in manifest.source_documents
                           if d.sha256 == summary["source_sha256"]),),
            root_segment="sources",
        )
        source_attempt = _object(
            root, project_id + "/outputs/source_attempt_preflight.json"
        )
        _require(source_attempt.get("project_id") == project_id
                 and source_attempt.get("source_sha256_at_start")
                 == summary.get("source_sha256"),
                 "initial original source-at-start ownership mismatch")
        _require(source_attempt.get("source_page_count") == page_count,
                 "source-at-start page count drift")
        _exact_execution_pages(
            source_attempt.get("execution_page_numbers"), page_count,
            "source-at-start original execution pages",
        )
        _require(source_attempt.get("family_group") == "all"
                 and source_attempt.get("topology_mode") == summary["topology_mode"],
                 "original source-at-start producer scope changed")
        _require(source_attempt.get("status") == "SOURCE_INPUT_RECORDED_UNSEALED"
                 and source_attempt.get("sealed_run_file") is None
                 and source_attempt.get("complete_source_coverage_proven") is False
                 and source_attempt.get("benchmark_score_granted") is False,
                 "original source-at-start preflight falsely grants sealed/score status")
        primary_sha = summary.get("source_sha256")
        primary = [doc for doc in manifest.source_documents if doc.sha256 == primary_sha]
        _require(len(primary) == 1, "producer summary lacks original-primary-PDF source SHA")
        _require(summary.get("page_count") == primary[0].page_count,
                 "producer summary source page count changed")
        _require(summary.get("family_group") == "all",
                 "owner handoff not original all-family execution")
        state = process[project_id]["status"]
        combined = summary.get("combined_run_file")
        count = summary.get("combined_quantity_count", 0)
        _require(type(count) is int and count >= 0,
                 "invalid combined sealed quantity count")
        _require(not (combined is not None and state != "COMPLETED"),
                 "noncompleted source process cannot claim a sealed run")
        _require(not (summary.get("status") == "source_attempt_recorded_unsealed"
                      and state == "COMPLETED"),
                 "unsealed interrupted source attempt cannot claim completed process")
        _require(not (state != "COMPLETED" and summary.get("status") != "source_attempt_recorded_unsealed"),
                 "interrupted production must have an unsealed attempt record")
        _require(not (summary.get("complete_project_handoff") is False and combined is not None),
                 "incomplete producer cannot claim complete signed output")
        is_sealed = combined is not None
        if is_sealed:
            _require(type(combined) is str and combined
                     and summary.get("combined_run_id"),
                     "sealed project missing run identity")
            _original_windows_reference(
                combined, project_id=project_id, terminal=(project_id + ".json",),
                root_segment="project_outputs",
            )
            file_path = project_id + "/outputs/" + project_id + ".json"
            payload = _object(root, file_path)
            sealed = sealed_source_closed_run_from_dict(payload)
            _require(sealed.project_id == project_id
                     and set(sealed.source_sha256s) == {primary_sha}
                     and sealed.run_id == summary["combined_run_id"],
                     "sealed project original source identity or run ID mismatch")
            # Do not silently collapse physically overlapping but separately
            # typed quantity families. Surface possible cross-semantic reuse for
            # issuer review without deleting either signed quantity.
            cross_semantic_claims[project_id] = _cross_semantic_source_claims(
                sealed.quantities
            )
            _require(len(sealed.quantities) == count
                     and sum(family_counts.values()) == count,
                     "producer family quantity counts disagree with sealed run")
            for family, number in family_counts.items():
                actual_count = sum(x.family == family for x in sealed.quantities)
                _require(actual_count == number, "signed family count mismatch")
            files = summary.get("family_run_files")
            ids = summary.get("family_run_ids")
            _require(type(files) is dict and type(ids) is dict
                     and set(files) == set(ids),
                     "family signed-run proof universe incomplete")
            for family in files:
                _require(type(family) is str and family in family_counts
                         and family_counts[family] > 0,
                         "signed family reference is not a nonempty quantity family")
                _original_windows_reference(
                    files[family], project_id=project_id,
                    terminal=("family_runs", family + ".sealed.json"),
                    root_segment="project_outputs",
                )
                relative = project_id + "/outputs/family_runs/" + family + ".sealed.json"
                family_payload = _object(root, relative)
                family_seal = sealed_source_closed_run_from_dict(family_payload)
                _require(family_seal.run_id == ids[family],
                         "family signed run id changed")
                _require(
                    {x.quantity_id for x in family_seal.quantities}
                    == {x.quantity_id for x in sealed.quantities if x.family == family},
                    "family signed run identity differs from combined run",
                )
                if len(files) == 1:
                    _require(_digest(_safe_file(root, relative)) == _digest(
                        _safe_file(root, file_path)
                    ), "single-family sealed bytes differ from combined V1")
        else:
            _require(count == 0 and not any(family_counts.values()),
                     "unsealed source attempt cannot claim signed quantities")
            _require(not summary.get("family_run_files") and not summary.get("family_run_ids"),
                     "unsealed attempt cannot carry signed family references")
        # Source-stage classification is derived from the original producer's
        # own status and NOT from benchmark target expectations. Never label an
        # unevaluated target MISSED based on a source process outcome.
        if state != "COMPLETED":
            observed_gate = "owner_process_stopped:" + state
        elif not is_sealed:
            observed_gate = "source_producer_unsealed:" + str(summary.get("status"))
        else:
            observed_gate = "customer_rows_not_verified_for_fresh_source_run"
        rows.append({
            "project_id": project_id,
            "frozen_denominator": denominator_by_id[project_id],
            "frozen_manifest_status": manifest.status,
            "process_status": state,
            "producer_status": summary.get("status"),
            "earliest_verified_project_execution_gate": observed_gate,
            "derived_sealed_quantity_count": count,
            "signed_run_verified_against_derived_bytes": is_sealed,
            "verified_customer_rows_in_run": 0,
            "original_source_pdf_bytes_rehashed_here": False,
            "reason_codes": (
                ["original_owner_run_partial_or_source_blocked", "customer_projection_not_verified"]
                if not is_sealed else
                ["single_primary_document_diagnostic_only", "customer_projection_not_verified"]
            ),
            "official_project_score": None,
        })
    _require(verified_manifest_docs == 10, "all ten per-project manifest receipts not proven")
    # A public/share-safe diagnostic kit must not accidentally include original
    # confidential source files, even outside its SHA-indexed derived list.
    _require(not any(p.is_file() and p.suffix.lower() == ".pdf"
                     for p in root.rglob("*")),
             "private original PDF appeared in derived share-safe receipt package")
    indexed, sums = _sha_index(root, owner)
    _require(_REQUIRED_FILES.issubset(sums), "required owner receipt source files absent")
    _require(all(path in sums for path in (
        "RUN_RECEIPT.json", "SOURCE_SHA_VERIFICATION.json", "PREFLIGHT_STATUS.json"
    )), "archive source receipts missing")
    fingerprint = sha256(json.dumps({
        "owner_producer_commit": head,
        "derived_artifact_sha256s": indexed,
        "source_manifest_sha256s": {
            m.project_id: sorted(d.sha256 for d in m.source_documents)
            for m in manifests
        },
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "schema_version": "gpt3-derived-owner-receipt-audit-v1",
        "original_owner_producer_commit": head,
        "original_document_count": 10,
        "verified_derived_manifest_document_records": verified_manifest_docs,
        "owner_reported_original_pdf_sha_verification": True,
        "independently_rehashed_original_private_pdf_bytes": False,
        "independently_verified_share_safe_derived_file_count": len(indexed),
        "independently_verified_sha256sums_entries": len(sums),
        "reconciled_derived_artifact_fingerprint": fingerprint,
        "frozen_denominator": 120,
        "official_four_project_coverage_accuracy": None,
        "official_four_project_precision_adjusted_accuracy": None,
        "cross_semantic_signed_object_claims_for_review": cross_semantic_claims,
        "official_publication_status": "UNPUBLISHED",
        "projects": rows,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--receipt-root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    if args.output.resolve().is_relative_to(args.receipt_root.resolve()) or (
        args.output.resolve().is_relative_to(FROZEN_ROOT.resolve())
    ):
        raise ValueError("derived receipt diagnostic cannot overwrite evidence")
    result = verify_owner_four_job_receipts(args.receipt_root)
    _write_readiness_report(
        args.output, json.dumps(result, indent=2, sort_keys=True) + "\n",
        protected_roots=(args.receipt_root, FROZEN_ROOT),
    )
    print(json.dumps({
        "official_publication_status": result["official_publication_status"],
        "original_document_count": result["original_document_count"],
        "verified_derived_artifacts": result["independently_verified_share_safe_derived_file_count"],
    }, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
