"""Owner-only, role-complete source-closed project handoff.

Unlike four_job_windows_launcher (primary architectural PDF only), this opt-in
runner independently produces every frozen original SOURCE DOCUMENT role. It
never invents a multi-PDF source SHA or blesses a missing producer. It uses the
existing sealed-run verifier and composer only when *every* original document
produced an actual canonical seal; absent/empty secondary documents remain
unsealed negative evidence, not a source-complete or scored result.

The one owner-approved exception is opt-in: a supporting document whose
generic producer completed every page with exactly ``no_sealable_quantities``,
and whose native decode coverage was independently re-verified, closes with an
explicit source-owned ABSTAIN receipt. That receipt carries no value, no
physical identity and no customer row; it is never a quantity seal, and it can
only accompany at least one other role that sealed a genuine quantity.

No PDF is uploaded or copied; all output stays under an owner-chosen private
destination, and no evaluator/benchmark mapping is invoked.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any

import fitz

from pb_combine_source_closed_runs import (
    combine_sealed_run_files, load_verified_sealed_run,
)
from pb_customer_output_verification import verify_sealed_customer_output
from pb_migration_contracts import QuantityEvidence, stable_contract_id
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_source_closed_run_export import SealedSourceClosedRun, seal_source_closed_run
from tools.four_job_windows_launcher import PROJECTS, run_logged
from tools.q5446_source_role_customer_runtime import source_owned_role_module
from tools.report_gpt3_four_project_evidence import FROZEN_ROOT, _json_object, _json_customer_rows

_SHA = re.compile(r"^[0-9a-f]{64}$")
GENERIC_ROLE_PRODUCER = "tools.run_source_closed_project_handoff"
SOURCE_ROLE_ABSTENTION_FAMILY = "source_role_abstention"
SOURCE_ROLE_ABSTENTION_FILE = "source_role_abstention.sealed.json"
_ABSTENTION_AUTHORITY = "tools.gpt3_owner_all_source_role_handoff.source_role_abstention"
_ABSTENTION_WORKSPACE_ID = 1
# The generic producer records every one of these for family group "all".
_ALL_GROUP_FAMILY_COUNTS = (
    "floor_area", "floor_finish_area", "opening_area", "opening_width",
    "opening_height", "opening_count", "ceiling_area",
)


def _sha256(path: Path) -> str:
    h = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _source(root: Path, project_id: str, name: str) -> Path:
    if (
        type(name) is not str or name != Path(name).name
        or name in (".", "..") or "/" in name or "\\" in name
        or not name.lower().endswith(".pdf")
    ):
        raise ValueError("source manifest includes an unsafe PDF name")
    choices = (root / name, root / project_id / name)
    found = [p for p in choices if p.is_file() and not p.is_symlink()]
    if any(p.is_symlink() for p in choices):
        raise ValueError("source document symlink cannot be authenticated")
    if len(found) == 2:
        if _sha256(found[0]) != _sha256(found[1]):
            raise ValueError("conflicting flat and project-scope source copies")
        return found[0]
    if len(found) != 1:
        raise FileNotFoundError("original source document role is absent")
    return found[0]


def original_roster(project_id: str, root: Path) -> list[dict[str, Any]]:
    if project_id not in PROJECTS or root.is_symlink() or not root.is_dir():
        raise ValueError("invalid original source project or directory")
    manifest_path = FROZEN_ROOT / "projects" / project_id / "source_manifest.json"
    manifest = _json_object(manifest_path)
    if manifest.get("project_id") != project_id:
        raise ValueError("frozen project identifier mismatch")
    documents = manifest.get("source_documents")
    if type(documents) is not list or not documents:
        raise ValueError("frozen source document role universe missing")
    seen: set[str] = set()
    roster = []
    for row in documents:
        if type(row) is not dict:
            raise ValueError("invalid frozen source role declaration")
        name, role = row.get("name"), row.get("role")
        digest, count, size = row.get("sha256"), row.get("page_count"), row.get("size_bytes")
        if (
            type(name) is not str or name.casefold() in seen
            or type(role) is not str or not role.strip()
            or type(digest) is not str or not _SHA.fullmatch(digest)
            or type(count) is not int or count < 1
            or type(size) is not int or size < 1
        ):
            raise ValueError("malformed original source role declaration")
        seen.add(name.casefold())
        path = _source(root, project_id, name)
        if path.stat().st_size != size or _sha256(path) != digest:
            raise ValueError("frozen original PDF byte authentication rejected source")
        with fitz.open(path) as pdf:
            if len(pdf) != count:
                raise ValueError("original PDF page count differs from frozen source")
        roster.append({
            "role": role, "sha256": digest, "page_count": count,
            "path": path,
        })
    return roster


def _write_summary(path: Path, report: dict) -> None:
    # Report is share-safe: no PDF bytes, local filenames, home paths, customer
    # notes or material is allowed. Only project ID, SHA, roles and status.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_exclusive(path: Path, content: str) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError("sealed cross-role output already exists")
    stage: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", dir=path.parent, prefix=".source-roles-", suffix=".tmp",
            encoding="utf-8", delete=False,
        ) as handle:
            stage = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(stage, path)
    finally:
        if stage is not None:
            stage.unlink(missing_ok=True)


def _verified_role_customer_rows(role_dir: Path, summary: dict, signed) -> tuple[dict, ...]:
    """Only the complete role artifact may match this role's actual source seal.

    Family-only files are intentionally excluded: globbing all verified files
    duplicates their rows once a whole-project file exists, or borrows a full
    source seal for an independently verified subset.
    """
    if summary.get("customer_rows_verified") is not True:
        raise ValueError("complete role customer output unavailable")
    name = summary.get("customer_rows_file")
    if type(name) is not str:
        raise ValueError("complete role customer artifact unavailable")
    path = Path(name)
    if (path.name != "verified_customer_rows.json"
            or path.resolve().parent != role_dir.resolve()
            or path.is_symlink() or not path.is_file()):
        raise ValueError("untrusted complete role customer artifact path")
    rows = _json_customer_rows(path)
    verified = verify_sealed_customer_output(signed, rows)
    expected = {q.quantity_id for q in signed.quantities if not q.abstained}
    if (len(rows) != len(expected)
            or verified.customer_row_count != len(expected)
            or set(verified.verified_quantity_ids) != expected):
        raise ValueError("complete role customer quantity bijection unavailable")
    return tuple(rows)


def _complete_native_coverage(native_input: Any, *, sha256: str, page_count: int) -> tuple[str, str, str]:
    if type(native_input) is not dict:
        raise ValueError("source role abstention requires a verified native decode receipt")
    coverage = native_input.get("coverage")
    fingerprint = native_input.get("fingerprint")
    if (
        native_input.get("source_sha256") != sha256
        or type(coverage) is not dict
        or coverage.get("state") != "complete"
        or coverage.get("total_pages") != page_count
        or coverage.get("decoded_pages") != list(range(1, page_count + 1))
        or coverage.get("failed_pages") != []
        or type(fingerprint) is not str or not _SHA.fullmatch(fingerprint)
    ):
        raise ValueError("source role abstention requires complete native decode coverage")
    document_id, revision_id = coverage.get("document_id"), coverage.get("revision_id")
    if any(type(value) is not str or not value or value != value.strip()
           for value in (document_id, revision_id)):
        raise ValueError("source role abstention requires the decoded source revision")
    return document_id, revision_id, fingerprint


def build_source_role_abstention_run(
    *, project_id: str, sha256: str, page_count: int, native_input: dict,
) -> SealedSourceClosedRun:
    """The deterministic ABSTAIN receipt for one fully decoded no-quantity role."""
    document_id, revision_id, fingerprint = _complete_native_coverage(
        native_input, sha256=sha256, page_count=page_count,
    )
    coverage_id = stable_contract_id(
        "native_source_input_coverage",
        {"source_sha256": sha256, "fingerprint": fingerprint},
        digest_chars=32,
    )
    identity = {
        "project_id": project_id, "source_sha256": sha256,
        "document_id": document_id, "revision_id": revision_id,
        "native_source_input_coverage_id": coverage_id,
        "producer_status": "no_sealable_quantities",
    }
    quantity = QuantityEvidence(
        quantity_id=stable_contract_id(SOURCE_ROLE_ABSTENTION_FAMILY, identity, digest_chars=32),
        family=SOURCE_ROLE_ABSTENTION_FAMILY,
        semantic_key="source_document_quantity_scope",
        value=None,
        unit="document",
        evidence_ids=(coverage_id,),
        authority=_ABSTENTION_AUTHORITY,
        status="abstained",
        confidence=0.0,
        abstained=True,
        blocking_reasons=("source_role_no_sealable_quantity",),
        reason_codes=(
            "native_source_input_coverage_complete",
            "source_role_producer_no_sealable_quantities",
        ),
        metadata={
            "project_id": project_id, "document_id": document_id,
            "source_sha256": sha256, "revision_id": revision_id,
        },
    )
    trace = CommercialTakeoffSourceTrace(
        workspace_id=_ABSTENTION_WORKSPACE_ID, project_id=project_id,
        document_id=document_id, source_sha256=sha256,
        source_page=f"1-{page_count}", viewport_id="source_document",
        revision_id=revision_id, current_revision_id=revision_id,
        evidence_ids=(coverage_id,),
    )
    run = seal_source_closed_run(
        (quantity,), project_id=project_id,
        traces_by_quantity_id={quantity.quantity_id: trace},
    )
    row = run.quantities[0]
    if (len(run.quantities) != 1 or not row.abstained or row.value is not None
            or not row.lineage_ok or row.object_identity_refs
            or tuple(run.source_sha256s) != (sha256,)):
        raise ValueError("source role abstention receipt failed its own lineage seal")
    return run


def _generic_producer_abstained_on_every_page(summary: dict, *, project_id: str, role: dict) -> bool:
    """Exactly a complete, successful, empty generic run; never a blocked or partial one."""
    pages = list(range(1, role["page_count"] + 1))
    counts = summary.get("family_counts")
    return (
        summary.get("status") == "no_sealable_quantities"
        and summary.get("project_id") == project_id
        and summary.get("source_sha256") == role["sha256"]
        and summary.get("page_count") == role["page_count"]
        and summary.get("family_group") == "all"
        and summary.get("complete_project_handoff") is True
        and summary.get("source_positive_partial_page") is None
        and summary.get("execution_pages") == pages
        and summary.get("semantic_execution_pages") == pages
        and summary.get("combined_run_file") is None
        and summary.get("combined_quantity_count") == 0
        and summary.get("family_run_files") == {}
        and summary.get("family_run_ids") == {}
        and summary.get("customer_rows_verified") is False
        and summary.get("verified_customer_row_count") == 0
        and summary.get("floor_finish_customer_rows_verified") is False
        and summary.get("ceiling_customer_rows_verified") is False
        and type(counts) is dict
        and set(_ALL_GROUP_FAMILY_COUNTS) <= set(counts)
        and all(type(value) is int and value == 0 for value in counts.values())
    )


def _issue_source_role_abstention(
    role_dir: Path, *, project_id: str, role: dict, native_input: dict,
) -> Path:
    run = build_source_role_abstention_run(
        project_id=project_id, sha256=role["sha256"],
        page_count=role["page_count"], native_input=native_input,
    )
    path = role_dir / SOURCE_ROLE_ABSTENTION_FILE
    _write_exclusive(path, run.to_json())
    signed = load_verified_sealed_run(path)
    verified = verify_sealed_customer_output(signed, [])
    if (signed.to_dict() != run.to_dict()
            or signed.project_id != project_id
            or tuple(signed.source_sha256s) != (role["sha256"],)
            or [(q.family, q.abstained, q.value, q.object_identity_refs) for q in signed.quantities]
            != [(SOURCE_ROLE_ABSTENTION_FAMILY, True, None, ())]
            or verified.customer_row_count != 0
            or tuple(verified.verified_quantity_ids)):
        raise ValueError("source role abstention receipt did not round-trip")
    return path


def produce_all_source_roles(
    *, project_id: str, source_dir: Path, output_dir: Path,
    family_group: str = "all", timeout_min: int = 180,
    max_private_gb: float = 10, min_free_commit_gb: float = 3,
    record_native_source_input_coverage: bool = False,
    source_native_finish_text_shadow: bool = False,
    source_glyph_ledger_text_trust: bool = False,
    source_role_abstention_receipts: bool = False,
) -> dict[str, Any]:
    requested_controls = {
        "source_native_finish_text_shadow": source_native_finish_text_shadow,
        "source_glyph_ledger_text_trust": source_glyph_ledger_text_trust,
    }
    if any(type(value) is not bool for value in requested_controls.values()):
        raise ValueError("source text controls must be explicit booleans")
    if type(record_native_source_input_coverage) is not bool:
        raise ValueError("native source input coverage audit must be an explicit boolean")
    if type(source_role_abstention_receipts) is not bool:
        raise ValueError("source role abstention receipts must be an explicit boolean")
    if family_group not in ("all", "core", "surfaces", "floor_area"):
        raise ValueError("invalid canonical source producer family")
    if source_role_abstention_receipts and (
        not record_native_source_input_coverage or family_group != "all"
    ):
        raise ValueError(
            "source role abstention receipts require native source input coverage and family group all"
        )
    if (
        type(timeout_min) is not int or timeout_min < 1
        or not 0 < max_private_gb < 100000
        or not 0 <= min_free_commit_gb < 100000
    ):
        raise ValueError("unsafe source role resource limits")
    # Validate all original bytes before creating any source producer output.
    roster = original_roster(project_id, source_dir)
    dest = output_dir.resolve()
    inputs = (source_dir.resolve(), FROZEN_ROOT.resolve())
    if (
        output_dir.exists() or output_dir.is_symlink()
        or any(dest == root or dest.is_relative_to(root) for root in inputs)
    ):
        raise ValueError("owner source role output must be a new private location")
    output_dir.mkdir(parents=True, exist_ok=False)
    report: dict[str, Any] = {
        "schema_version": "gpt3-owner-original-role-attempt-v1",
        "project_id": project_id,
        "expected_source_document_roles": len(roster),
        "source_sha_verified": True,
        "roles": [],
        "source_role_coverage_verified": False,
        "customer_bijection_verified": False,
        "benchmark_score_granted": False,
        "official_four_project_accuracy": None,
        "status": "INCOMPLETE",
    }
    if any(requested_controls.values()):
        # These are requested execution settings, never source proof or
        # permission to seal a physical quantity. Keep legacy reports intact.
        report["requested_source_controls"] = requested_controls
        _write_summary(output_dir / "SOURCE_ROLE_STATUS.json", report)
    if record_native_source_input_coverage and project_id == "au_qld_q5446_armstrong32_harlequin":
        # Original material-support evidence may corroborate a finish *scope*.
        # It grants no quantity, customer seal, signed role or V2 credit.
        # Never expose proprietary source text or physical geometry in status.
        from pb_gptmax_q5446_finish_support_shadow import inspect_q5446_finish_support
        report["q5446_finish_support_shadow"] = inspect_q5446_finish_support(roster).public_summary()
    if record_native_source_input_coverage:
        from tools.gpt3_native_source_execution_coverage import (
            build_native_source_execution_coverage,
            verify_native_source_execution_coverage,
        )
        from tools.gpt3_original_source_preflight import _stable_original_digest
        # Input coverage is separate from quantity-seal coverage. Persist an
        # unverified attempt before decoding; failures cannot leave a success.
        report["native_source_input_coverage_verified"] = False
        _write_summary(output_dir / "SOURCE_ROLE_STATUS.json", report)
    if source_role_abstention_receipts:
        report["source_role_abstention_receipts"] = True
        report["source_role_abstention_count"] = 0
    sealed: list[Path] = []
    abstentions: list[Path] = []
    genuine_quantity_roles = 0
    customer_rows: list[dict] = []
    for index, role in enumerate(roster):
        role_dir = output_dir / ("source_role_%02d" % (index + 1))
        role_dir.mkdir(parents=True)
        native_input = None
        if record_native_source_input_coverage:
            native_digest, native_source_identity = _stable_original_digest(role["path"])
            if native_digest != role["sha256"]:
                raise ValueError("native source input changed before role production")
            native_input = build_native_source_execution_coverage(
                pdf_path=role["path"], expected_sha256=role["sha256"],
                expected_page_count=role["page_count"],
            )
        # The immutable roster already proved this PDF hash and page count.
        # Select the one source-specific original issuer by source ownership,
        # not by project name, filename, expected item or frozen quantity.
        producer_module = source_owned_role_module(
            role["sha256"], family_group=family_group,
        )
        command = [
            sys.executable, "-m", producer_module,
            "--pdf", str(role["path"]), "--project-id", project_id,
            "--family-group", family_group, "--output-dir", str(role_dir),
        ]
        forwarded_controls = None
        if any(requested_controls.values()):
            if producer_module == "tools.run_source_closed_project_handoff":
                for name, enabled in requested_controls.items():
                    if enabled:
                        command.append("--" + name.replace("_", "-"))
                forwarded_controls = {
                    "status": "FORWARDED",
                    "forwarded": dict(requested_controls),
                }
            elif producer_module == "tools.q5446_source_role_customer_runtime":
                # This registered SHA-owned issuer authenticates its own
                # original-source evidence. Generic parser flags do not
                # replace that proof and are not accepted by its parser.
                forwarded_controls = {
                    "status": "NOT_APPLICABLE_SOURCE_OWNED_ISSUER",
                    "forwarded": {name: False for name in requested_controls},
                }
            else:
                raise ValueError("source controls unsupported by registered role producer")
        rc, status, usage = run_logged(
            command, Path(__file__).resolve().parents[1],
            output_dir / ("source_role_%02d.log" % (index + 1)),
            timeout_s=timeout_min * 60, track_memory=True,
            max_private_mb=int(max_private_gb * 1024),
            min_free_commit_mb=int(min_free_commit_gb * 1024),
        )
        if record_native_source_input_coverage:
            # Reconstruct coverage after the real child. Never attach a
            # borrowed, modified or stale pre-process input receipt.
            native_input = verify_native_source_execution_coverage(
                native_input, pdf_path=role["path"],
                expected_sha256=role["sha256"], expected_page_count=role["page_count"],
            )
            final_digest, final_identity = _stable_original_digest(role["path"])
            if final_digest != role["sha256"] or final_identity != native_source_identity:
                raise ValueError("native source input changed during role production")
        measured = usage if type(usage) is dict else {}
        safe_usage = {}
        for key in ("peak_working_set_kb", "peak_private_kb", "min_system_free_commit_kb"):
            value = measured.get(key)
            safe_usage[key] = value if type(value) is int and value >= 0 else None
        row = {
            "role": role["role"], "sha256": role["sha256"],
            "process_status": status, "process_exit_code": rc,
            "sealed": False,
            "first_failure": None,
            "customer_bijection_verified": False,
            "customer_first_failure": None,
            "resource_usage": safe_usage,
        }
        if forwarded_controls is not None:
            row["source_controls"] = forwarded_controls
        if record_native_source_input_coverage:
            row["native_source_input_coverage"] = native_input
            row["native_source_input_coverage_verified"] = True
        if rc == 0 and status == "COMPLETED":
            summary_file = role_dir / "production_summary.json"
            if summary_file.is_file():
                summary = _json_object(summary_file)
                # Counts/status only. Do not copy private source text, paths,
                # error messages, room names, geometry or quantity values.
                statuses = {"sealed", "no_sealable_quantities", "source_complexity_blocked",
                            "production_failed", "source_envelope_conflict",
                            "family_quantity_identity_conflict", "sealed_project_combination_failed"}
                row["production_status"] = (
                    summary.get("status") if summary.get("status") in statuses else "OTHER"
                )
                counts = summary.get("family_counts", {})
                row["family_counts"] = {
                    name: counts[name] for name in (
                        "floor_area", "floor_finish_area", "opening_area", "opening_count",
                        "opening_width", "opening_height", "ceiling_area", "wall_net_area",
                    ) if type(counts) is dict and type(counts.get(name)) is int and counts[name] >= 0
                }
                customer_gates = {
                    "NO_SEALED_PROJECT", "FULL_PROJECT_FAMILY_SCOPE",
                    "FLOOR_AREA_CUSTOMER_PROJECTION", "OPENING_CUSTOMER_PROJECTION",
                    "FLOOR_FINISH_CUSTOMER_UNVERIFIED", "CEILING_CUSTOMER_UNVERIFIED",
                    "EXACT_SEALED_PROJECT_CUSTOMER_BIJECTION", "PROJECT_VERIFIED",
                }
                gate = summary.get("full_project_customer_first_gate")
                row["full_project_customer_first_gate"] = (
                    gate if type(gate) is str and gate in customer_gates else "UNAVAILABLE"
                )
                file = summary.get("combined_run_file")
                if summary.get("status") == "sealed" and type(file) is str:
                    sealed_file = Path(file)
                    if (
                        sealed_file.resolve().parent == role_dir.resolve()
                        and sealed_file.is_file() and not sealed_file.is_symlink()
                    ):
                        try:
                            signed = load_verified_sealed_run(sealed_file)
                        except (OSError, TypeError, ValueError, RuntimeError):
                            row["first_failure"] = "original_role_signed_receipt_invalid"
                        else:
                            if (
                                signed.project_id == project_id
                                and set(signed.source_sha256s) == {role["sha256"]}
                            ):
                                sealed.append(sealed_file)
                                row["sealed"] = True
                                if source_role_abstention_receipts and any(
                                    not quantity.abstained for quantity in signed.quantities
                                ):
                                    genuine_quantity_roles += 1
                                if summary.get("customer_rows_verified") is True:
                                    try:
                                        batch = _verified_role_customer_rows(role_dir, summary, signed)
                                    except (OSError, TypeError, ValueError, RuntimeError):
                                        row["customer_first_failure"] = "role_customer_output_invalid"
                                    else:
                                        customer_rows.extend(batch)
                                        row["customer_bijection_verified"] = True
                                else:
                                    row["customer_first_failure"] = "role_customer_output_unavailable"
                            else:
                                row["first_failure"] = "original_role_seal_source_envelope_conflict"
                    else:
                        row["first_failure"] = "role_seal_output_path_untrusted"
                else:
                    row["first_failure"] = "role_producer_no_sealable_result"
                    if (
                        source_role_abstention_receipts
                        and producer_module == GENERIC_ROLE_PRODUCER
                        and _generic_producer_abstained_on_every_page(
                            summary, project_id=project_id, role=role,
                        )
                    ):
                        try:
                            receipt = _issue_source_role_abstention(
                                role_dir, project_id=project_id, role=role,
                                native_input=native_input,
                            )
                        except (OSError, TypeError, ValueError, RuntimeError):
                            row["first_failure"] = "source_role_abstention_receipt_invalid"
                        else:
                            # Never a seal: one value-free row, no customer row.
                            abstentions.append(receipt)
                            row["first_failure"] = None
                            row["source_role_abstained"] = True
                            row["customer_bijection_verified"] = True
                            report["source_role_abstention_count"] = len(abstentions)
            else:
                row["first_failure"] = "role_producer_summary_missing"
        else:
            row["first_failure"] = "role_producer_did_not_complete"
        report["roles"].append(row)
        _write_summary(output_dir / "SOURCE_ROLE_STATUS.json", report)
        # Only original roles that produce a genuine, individually authentic
        # run are allowed in the cross-document signer. Missing roles veto
        # aggregate publication: do not stuff their SHA into an envelope.
    if record_native_source_input_coverage:
        report["native_source_input_coverage_verified"] = (
            len(report["roles"]) == len(roster)
            and all(row.get("native_source_input_coverage_verified") is True
                    for row in report["roles"])
        )
    # An abstention receipt closes only a supporting role; a project of
    # receipts alone has no genuine quantity and stays incomplete.
    abstention_closure = (
        bool(abstentions) and genuine_quantity_roles > 0
        and len(sealed) + len(abstentions) == len(roster)
    )
    if abstentions and not abstention_closure and len(sealed) + len(abstentions) == len(roster):
        report["source_role_abstention_first_failure"] = "no_role_sealed_a_genuine_quantity"
    if len(sealed) == len(roster) or abstention_closure:
        combined = combine_sealed_run_files([*sealed, *abstentions], project_id=project_id)
        expected = {x["sha256"] for x in roster}
        if set(combined.source_sha256s) != expected:
            raise ValueError("combined original-role SHA universe mismatch")
        _write_exclusive(output_dir / "ALL_SOURCE_ROLES.sealed.json", combined.to_json())
        report["source_role_coverage_verified"] = True
        report["status"] = (
            "ALL_ROLES_CLOSED_WITH_SOURCE_ABSTENTION_CUSTOMER_AND_V2_PENDING"
            if abstentions else "ALL_ROLES_SEALED_CUSTOMER_AND_V2_PENDING"
        )
        if all(row["customer_bijection_verified"] for row in report["roles"]):
            # Recheck the union against the actual cross-document composer;
            # individual role success alone is insufficient project proof.
            verified = verify_sealed_customer_output(combined, customer_rows)
            expected = {q.quantity_id for q in combined.quantities if not q.abstained}
            if (len(customer_rows) != len(expected)
                    or verified.customer_row_count != len(expected)
                    or set(verified.verified_quantity_ids) != expected):
                raise ValueError("combined role customer quantity bijection unavailable")
            _write_exclusive(
                output_dir / "ALL_SOURCE_ROLES.customer_rows.json",
                json.dumps(customer_rows, sort_keys=True, allow_nan=False) + "\n",
            )
            report["customer_bijection_verified"] = True
            report["status"] = (
                "ALL_ROLES_CLOSED_WITH_SOURCE_ABSTENTION_CUSTOMER_VERIFIED_V2_PENDING"
                if abstentions else "ALL_ROLES_SEALED_CUSTOMER_VERIFIED_V2_PENDING"
            )
    else:
        report["status"] = "SOURCE_ROLES_INCOMPLETE"
    _write_summary(output_dir / "SOURCE_ROLE_STATUS.json", report)
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-id", required=True, choices=PROJECTS)
    p.add_argument("--source-dir", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--family-group", choices=("all", "core", "surfaces", "floor_area"), default="all")
    p.add_argument("--timeout-min", type=int, default=180)
    p.add_argument("--max-private-gb", type=float, default=10)
    p.add_argument("--min-free-commit-gb", type=float, default=3)
    p.add_argument(
        "--record-native-source-input-coverage", action="store_true",
        help="Opt in to native original-page input audit; does not complete quantity seals or permit scoring",
    )
    p.add_argument(
        "--source-native-finish-text-shadow", action="store_true",
        help="Forward existing native source text proof to generic roles; grants no quantity authority",
    )
    p.add_argument(
        "--source-glyph-ledger-text-trust", action="store_true",
        help="Forward existing glyph-ledger trust to generic roles; source-owned issuers retain their own proof",
    )
    p.add_argument(
        "--source-role-abstention-receipts", action="store_true",
        help=("Close a fully decoded generic role that sealed nothing with a value-free ABSTAIN "
              "receipt; requires native coverage and a genuinely sealed sibling role"),
    )
    args = p.parse_args(argv)
    report = produce_all_source_roles(
        project_id=args.project_id, source_dir=args.source_dir,
        output_dir=args.output_dir, family_group=args.family_group,
        timeout_min=args.timeout_min, max_private_gb=args.max_private_gb,
        min_free_commit_gb=args.min_free_commit_gb,
        **({"record_native_source_input_coverage": True}
           if args.record_native_source_input_coverage else {}),
        **({"source_native_finish_text_shadow": True}
           if args.source_native_finish_text_shadow else {}),
        **({"source_glyph_ledger_text_trust": True}
           if args.source_glyph_ledger_text_trust else {}),
        **({"source_role_abstention_receipts": True}
           if args.source_role_abstention_receipts else {}),
    )
    console = {
        "status": report["status"],
        "project_id": report["project_id"],
        "sealed_roles": sum(row["sealed"] for row in report["roles"]),
        "required_roles": report["expected_source_document_roles"],
        "official_four_project_accuracy": None,
    }
    if args.record_native_source_input_coverage:
        console["native_source_input_coverage_verified"] = report["native_source_input_coverage_verified"]
    if args.source_role_abstention_receipts:
        console["source_role_abstentions"] = report["source_role_abstention_count"]
    print(json.dumps(console, sort_keys=True))
    return 0 if report["source_role_coverage_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
