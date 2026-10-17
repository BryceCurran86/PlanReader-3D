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
    FROZEN_ROOT, _json_object, _json_customer_rows, load_suite_manifests,
    _read_json_without_duplicate_keys,
)
from tools.gpt3_signed_v1_replay_drift import inspect_signed_v1_replay

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_LINE = re.compile(r"^([0-9a-f]{64})  ([^\r\n]+)$")
_EXTRA_DERIVED = frozenset({"README.md", "assemble_receipts.py", "RUN_RECEIPT.json"})
_REQUIRED_FILES = frozenset({
    "RUN_RECEIPT.json", "SOURCE_SHA_VERIFICATION.json", "PREFLIGHT_STATUS.json",
})
_SOURCE_SUCCESS = "VERIFIED"
_HISTORICAL_LOT16_ROOT = (
    Path(__file__).resolve().parents[1]
    / "docs/engineering/lot16_original_signed_eight_row_20261015/production"
)


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
    value = _read_json_without_duplicate_keys(_safe_file(root, relative))
    _require(type(value) is list, "derived receipt expected JSON array: " + relative)
    return value


def _sha_index(root: Path, owner: dict) -> tuple[dict[str, str], dict[str, str]]:
    """Independently SHA all 28 derived records AND all SHA256SUMS entries."""
    file_rows = owner.get("files")
    _require(type(file_rows) is list and len(file_rows) == 28,
             "original owner share-safe artifact ledger must contain 28 records")
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
    _require(len(sums) == 31, "original owner SHA256SUMS must contain 31 records")
    # No extra arbitrary artifact may be smuggled into an otherwise hash-valid
    # share-safe owner archive. SHA256SUMS itself is the only unlisted hash file.
    # The original archive has one unindexed repository-only byte policy.
    # Require its exact harmless contents; never interpret other unindexed
    # data files as acceptable to hide source/customer receipts.
    byte_policy = _safe_file(root, ".gitattributes")
    _require(byte_policy.read_bytes() == b"* -text\n",
             "original receipt byte-preservation policy changed")
    expected_tree = set(sums) | {"SHA256SUMS", ".gitattributes"}
    _require(not any(node.is_symlink() for node in root.rglob("*")),
             "untrusted symlink found in derived source receipt package")
    actual_tree = {
        file.relative_to(root).as_posix()
        for file in root.rglob("*") if file.is_file()
    }
    # CPython bytecode is not in the owner's SHA-indexed receipt universe.
    # Never whitelist a .pyc by its filename and size: arbitrary untrusted
    # source bytes could be hidden behind that name. Test runners should use
    # PYTHONDONTWRITEBYTECODE=1 or an import cache outside this archive.
    # Even interpreter-generated caches are unverified and must fail closed.
    _require(actual_tree == expected_tree,
             "unindexed artifact in original share-safe receipt package")
    _require(all(sums[k] == sha for k, sha in indexed.items()),
             "SHA256SUMS and owner receipt disagree")
    return indexed, sums


def _cross_semantic_source_claims(quantities: Any) -> list[dict[str, Any]]:
    """Surface shared physical source with multiple families; never erase rows."""
    claims: dict[tuple[str, str, tuple[str, ...]], list] = {}
    for q in quantities:
        object_refs = tuple(sorted(set(q.object_identity_refs)))
        object_key = (q.source_sha256, q.revision_id, object_refs)
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


def _redacted_execution_receipt_path(value: Any, *, session: str,
                                     subfolder: str, basename: str) -> None:
    """A SHA-pinned owner receipt may not attribute another session's output."""
    _require(type(value) is str and value.startswith("<HOME>\\")
             and "/" not in value, "unredacted or malformed owner run path")
    parts = PureWindowsPath(value).parts
    _require(".." not in parts and tuple(parts[-3:]) == (session, subfolder, basename),
             "owner run receipt points to a different source or session")


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
    # Verify all archival bytes before interpreting producer/source semantics:
    # a changed V1 must fail on SHA mismatch, not an incidental later compare.
    indexed, sums = _sha_index(root, owner)
    _require(owner.get("schema") == "four_job_owner_machine_run_receipt/1",
             "owner run receipt schema mismatch")
    session = owner.get("session")
    _require(type(session) is str and re.fullmatch(r"[0-9]{8}_[0-9]{6}", session)
             is not None, "original owner run session identifier malformed")
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
        _redacted_execution_receipt_path(
            p.get("report"), session=session, subfolder="preflight",
            basename=project + ".json",
        )
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
        _redacted_execution_receipt_path(
            handoff.get("output_folder"), session=session,
            subfolder="project_outputs", basename=project,
        )
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
    historical_lot16_receipt_audit: dict[str, Any] | None = None
    historical_lot16_input_sha256s: dict[str, str] = {}
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
        page_count = summary.get("page_count")
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
        primary_sha = summary.get("source_sha256")
        primary = [doc for doc in manifest.source_documents if doc.sha256 == primary_sha]
        _require(len(primary) == 1, "producer summary lacks original-primary-PDF source SHA")
        _original_windows_reference(
            summary.get("source_path"), project_id=project_id,
            terminal=(primary[0].name,), root_segment="sources",
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
            _require(summary.get("status") == "sealed",
                     "signed V1 run cannot be presented with an unsealed producer status")
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
            if project_id == "au_qld_lot16_power":
                # Compare the actual original owner V1 with the prior immutable
                # archived commercial history using the established reader.
                # This does NOT reissue source scope or allow old customer rows
                # to be projected against a rekeyed fresh V1 fingerprint.
                historical_dir = _HISTORICAL_LOT16_ROOT
                historical_lot16_input_sha256s = {
                    name: _digest(historical_dir / name)
                    for name in ("source_sealed_run.json", "verified_customer_rows.json")
                }
                historical_lot16_receipt_audit = inspect_signed_v1_replay(
                    archived_run=_json_object(historical_dir / "source_sealed_run.json"),
                    candidate_run=payload,
                    archived_customer_rows=_json_customer_rows(
                        historical_dir / "verified_customer_rows.json"
                    ),
                    candidate_customer_rows=None,
                )
                _require(
                    historical_lot16_receipt_audit["historical_quantity_count"] == 8
                    and historical_lot16_receipt_audit["archived_customer_verified"] is True
                    and historical_lot16_receipt_audit["candidate_customer_verified"] is False
                    and historical_lot16_receipt_audit[
                        "safe_to_reuse_archived_customers_with_candidate"
                    ] is False
                    and historical_lot16_receipt_audit["source_issuer_scope_attestation_proven"] is False,
                    "original Lot16 source/customer history is not safely retained",
                )
                _require(all(
                    row["status"] in (
                        "EXACT_HISTORICAL_V1_PRESERVED",
                        "SNAPSHOT_RECEIPT_REKEY_UNATTESTED",
                        "NEW_QUANTITY_REQUIRES_INDEPENDENT_SOURCE_AND_V2_MATCH",
                    ) for row in historical_lot16_receipt_audit["quantity_differences"]
                ), "historical Lot16 original signed physical proposition changed")
            # Do not silently collapse physically overlapping but separately
            # typed quantity families. Surface possible cross-semantic reuse for
            # issuer review without deleting either signed quantity.
            cross_semantic_claims[project_id] = _cross_semantic_source_claims(
                sealed.quantities
            )
            _require(all(q.lineage_ok and not q.abstained and q.value is not None
                         and q.status.strip() for q in sealed.quantities),
                     "signed original quantities cannot contain unverified physical lineage")
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
            _require(set(files) == {family for family, n in family_counts.items() if n > 0},
                     "nonempty original quantity family lacks a source-owned sealed V1 receipt")
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
                _require(family_seal.project_id == project_id
                         and set(family_seal.source_sha256s) == {primary_sha},
                         "family signed run source/project lineage mismatch")
                _require(family_seal.run_id == ids[family],
                         "family signed run id changed")
                _require(
                    {x.quantity_id for x in family_seal.quantities}
                    == {x.quantity_id for x in sealed.quantities if x.family == family},
                    "family signed run identity differs from combined run",
                )
                combined_by_id = {q.quantity_id: q.payload() for q in sealed.quantities}
                _require(all(q.payload() == combined_by_id.get(q.quantity_id)
                             for q in family_seal.quantities),
                         "family signed-run quantity payload differs from combined sealed quantity")
                if len(files) == 1:
                    _require(_digest(_safe_file(root, relative)) == _digest(
                        _safe_file(root, file_path)
                    ), "single-family sealed bytes differ from combined V1")
        else:
            _require(summary.get("status") != "sealed",
                     "unsealed original source attempt cannot advertise sealed producer status")
            _require(summary.get("combined_run_id") is None,
                     "unsealed original source attempt cannot carry a signed V1 run ID")
            _require(count == 0 and not any(family_counts.values()),
                     "unsealed source attempt cannot claim signed quantities")
            _require(not summary.get("family_run_files") and not summary.get("family_run_ids"),
                     "unsealed attempt cannot carry signed family references")
        cross_semantic_claims.setdefault(project_id, [])
        # Source-stage classification is derived from the original producer's
        # own status and NOT from benchmark target expectations. Never label an
        # unevaluated target MISSED based on a source process outcome.
        if state != "COMPLETED":
            observed_gate = "owner_process_stopped:" + state
        elif not is_sealed:
            observed_gate = "source_producer_unsealed:" + str(summary.get("status"))
        elif len(manifest.source_documents) > 1:
            # A checksum preflight for every original document is not proof
            # the *producer* actually processed more than its primary PDF.
            observed_gate = "multidocument_original_source_production_not_complete"
        else:
            observed_gate = "customer_rows_not_verified_for_fresh_source_run"
        # Independent source-stage inventory; no stage is a V2 item result.
        # A configured producer primary input is not full source processing.
        production_completed = state == "COMPLETED" and summary.get("status") not in (
            "source_attempt_recorded_unsealed", "source_complexity_blocked",
        )
        stage_gates = {
            "owner_original_pdf_sha_preflight": "OWNER_REPORTED_VERIFIED",
            "independent_private_pdf_sha_rehash": "NOT_PERFORMED",
            "producer_process_completion": (
                "COMPLETED" if production_completed else "BLOCKED"
            ),
            "all_original_documents_processed": (
                "ONE_SOURCE_ALL_PAGES_EXECUTED_NOT_AUTHENTICATED"
                if production_completed and len(manifest.source_documents) == 1
                else "NOT_PROVEN"
            ),
            "signed_v1_quantity_receipt": (
                "VERIFIED_DERIVED_BYTES" if is_sealed else "NOT_AVAILABLE"
            ),
            "fresh_customer_bijection": "NOT_VERIFIED",
            "physical_identity_map": "NOT_SUPPLIED_IN_OWNER_RECEIPT",
            "frozen_project_manifest": manifest.status,
            "official_v2_project_score": "NOT_EVALUATED",
        }
        all_gates = [observed_gate]
        if len(manifest.source_documents) > 1 and (
            "multidocument_original_source_production_not_complete" not in all_gates
        ):
            all_gates.append("multidocument_original_source_production_not_complete")
        if "customer_rows_not_verified_for_fresh_source_run" not in all_gates:
            all_gates.append("customer_rows_not_verified_for_fresh_source_run")
        all_gates.extend((
            "independent_physical_identity_map_not_supplied",
            "frozen_project_source_manifest_not_verified",
        ) if manifest.status != "VERIFIED" else (
            "independent_physical_identity_map_not_supplied",
        ))
        rows.append({
            "project_id": project_id,
            "authority_stage_statuses": stage_gates,
            "remaining_gates_in_execution_order": all_gates,
            "remaining_gate_count": len(all_gates),
            "frozen_denominator": denominator_by_id[project_id],
            "frozen_manifest_status": manifest.status,
            "process_status": state,
            "producer_status": summary.get("status"),
            "original_source_package_document_count": len(manifest.source_documents),
            "producer_primary_source_document_count": 1,
            "configured_primary_source_document_count": 1,
            "producer_process_completed": production_completed,
            "fresh_customer_bijection_verified": False,
            "four_job_official_target_item_results_available": False,
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
    _require(_REQUIRED_FILES.issubset(sums), "required owner receipt source files absent")
    _require(all(path in sums for path in (
        "RUN_RECEIPT.json", "SOURCE_SHA_VERIFICATION.json", "PREFLIGHT_STATUS.json"
    )), "archive source receipts missing")
    frozen_source_inputs = {
        str(path.relative_to(FROZEN_ROOT)): _digest(path)
        for path in (
            FROZEN_ROOT / "manifest.json",
            FROZEN_ROOT / "evaluator.py",
            FROZEN_ROOT / "sealed_reconciliation.py",
            *(
                FROZEN_ROOT / "projects" / project / name
                for project in sorted(frozen_by_id)
                for name in ("source_manifest.json", "reference_takeoff.json")
            ),
        )
    }
    _require(len(historical_lot16_input_sha256s) == 2,
             "original historical Lot16 signed source/customer package unavailable")
    fingerprint = sha256(json.dumps({
        "owner_producer_commit": head,
        "historical_lot16_signed_inputs": historical_lot16_input_sha256s,
        "frozen_input_sha256s": frozen_source_inputs,
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
        "historical_lot16_v1_and_customer_file_sha256s": historical_lot16_input_sha256s,
        "frozen_source_evaluator_file_sha256s": frozen_source_inputs,
        "frozen_denominator": 120,
        "official_four_project_coverage_accuracy": None,
        "official_four_project_precision_adjusted_accuracy": None,
        "cross_semantic_signed_object_claims_for_review": cross_semantic_claims,
        "historical_lot16_v1_source_customer_retention": historical_lot16_receipt_audit,
        "official_publication_status": "UNPUBLISHED",
        "projects": rows,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--receipt-root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    if (
        args.output.resolve().is_relative_to(args.receipt_root.resolve())
        or args.output.resolve().is_relative_to(FROZEN_ROOT.resolve())
        or args.output.resolve().is_relative_to(_HISTORICAL_LOT16_ROOT.resolve())
    ):
        raise ValueError("derived receipt diagnostic cannot overwrite evidence")
    if args.output.is_symlink():
        raise ValueError("derived receipt diagnostic cannot follow output symlinks")
    if args.output.exists():
        try:
            previous = _json_object(args.output)
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValueError("derived receipt diagnostic cannot replace unrelated evidence") from exc
        if previous.get("schema_version") != "gpt3-derived-owner-receipt-audit-v1":
            raise ValueError("derived receipt diagnostic cannot replace unrelated evidence")
    result = verify_owner_four_job_receipts(args.receipt_root)
    _write_readiness_report(
        args.output, json.dumps(result, indent=2, sort_keys=True) + "\n",
        protected_roots=(args.receipt_root, FROZEN_ROOT, _HISTORICAL_LOT16_ROOT),
    )
    print(json.dumps({
        "official_publication_status": result["official_publication_status"],
        "original_document_count": result["original_document_count"],
        "verified_derived_artifacts": result["independently_verified_share_safe_derived_file_count"],
    }, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
