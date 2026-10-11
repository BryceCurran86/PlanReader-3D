"""Unpublished Full Plan V2 readiness diagnostics; never an accuracy score.

This read-only utility inspects frozen manifests and optional real production
files. It deliberately does not import, alter, or invoke the benchmark evaluator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from collections import Counter
from pathlib import Path

DEFAULT_ROOT = Path("benchmarks/frozen_holdout/full_plan_v2")


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict:
    """Reject duplicated object keys before one may shadow source identity."""
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite_json_constant(token: str) -> None:
    """NaN and Infinity are not JSON numbers or admissible source evidence."""
    raise ValueError(f"non-finite JSON number: {token}")


def _finite_json_float(token: str) -> float:
    """Reject finite-looking JSON numeric literals that overflow to infinity."""
    value = float(token)
    if not math.isfinite(value):
        raise ValueError("non-finite JSON floating-point value")
    return value


def _finite_json_int(token: str) -> int:
    """Keep oversized JSON integers from overflowing numeric parity checks."""
    value = int(token)
    try:
        finite_as_float = math.isfinite(value)
    except OverflowError:
        finite_as_float = False
    if not finite_as_float:
        raise ValueError("out-of-range JSON integer magnitude")
    return value


def _parse_evidence_json(payload: str) -> object:
    # Python JSON parser recursion handling varies across supported runtimes.
    # Guard genuine JSON object/array nesting before parsing, ignoring bracket
    # characters inside properly quoted/escaped strings. This is only a
    # complexity safeguard, not source/evaluator schema inference.
    depth = 0
    in_string = False
    escaped = False
    for character in payload:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
        elif character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > 512:
                raise ValueError("JSON nesting exceeds safe parser depth")
        elif character in "]}":
            depth -= 1
    # Preserve the native parser's validation of mismatched braces, malformed
    # escapes and all strict producer-key and number checks.
    try:
        return json.loads(
            payload,
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_nonfinite_json_constant,
            parse_float=_finite_json_float,
            parse_int=_finite_json_int,
        )
    except RecursionError as exc:
        raise ValueError("JSON nesting exceeds safe parser depth") from exc


def _object(path: Path) -> dict:
    # A signed or frozen source envelope must never silently accept a second
    # conflicting JSON key; last-write-wins could replace source identity.
    value = _parse_evidence_json(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _source_sha_proof(manifest: dict, source_root: Path | None, project_id: str) -> tuple[bool, list[str]]:
    """Hash real source files against the frozen name, size, and SHA-256."""
    documents = manifest.get("source_documents")
    if not isinstance(documents, list) or not documents:
        return False, ["source_manifest_documents_missing"]
    if source_root is None:
        return False, ["source_files_not_supplied"]
    reasons: list[str] = []
    for document in documents:
        if not isinstance(document, dict):
            raise ValueError("source manifest document must be an object")
        name, expected_sha, expected_size = document.get("name"), document.get("sha256"), document.get("size_bytes")
        if not isinstance(name, str) or not name or Path(name).name != name:
            raise ValueError("source document name must be a plain filename")
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            raise ValueError("source manifest sha256 invalid")
        source = source_root / project_id / name
        try:
            exists = source.is_file()
        except OSError:
            # Path.is_file() can itself raise if a file vanishes while
            # filesystem metadata is being queried (Python 3.13 included).
            reasons.append(f"source_file_unreadable:{name}")
            continue
        if not exists:
            reasons.append(f"source_file_missing:{name}")
            continue
        # A concurrently replaced or unreadable source PDF must fail this
        # project's SHA authority, not terminate the four-project diagnostic.
        # Keep streaming original bytes; never infer a source SHA from names.
        try:
            if source.stat().st_size != expected_size:
                reasons.append(f"source_file_size_mismatch:{name}")
                continue
            digest = hashlib.sha256()
            with source.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError:
            reasons.append(f"source_file_unreadable:{name}")
            continue
        if digest.hexdigest() != expected_sha.lower():
            reasons.append(f"source_file_sha_mismatch:{name}")
    return not reasons, reasons


def _sealed_run_proof(
    sealed_root: Path | None, project_id: str, expected_shas: set[str],
    *, seal_fingerprint_sink: list[str] | None = None,
) -> tuple[bool, int | None, list[str]]:
    """Verify complete production seal fingerprints, lineage and source envelope."""
    if sealed_root is None:
        return False, None, ["sealed_run_not_supplied"]
    path = sealed_root / project_id / "sealed_run.json"
    if not path.is_file():
        return False, None, ["sealed_run_missing"]
    from pb_source_closed_run_export import (SourceClosedRunExportError, sealed_source_closed_run_from_dict)

    try:
        sealed = sealed_source_closed_run_from_dict(_object(path))
    except (SourceClosedRunExportError, TypeError, ValueError, KeyError, UnicodeError, OSError):
        return False, None, ["sealed_run_integrity_invalid"]
    if sealed.project_id != project_id:
        return False, len(sealed.quantities), ["sealed_run_project_mismatch"]
    reasons: list[str] = []
    if set(sealed.source_sha256s) != expected_shas:
        reasons.append("sealed_run_source_envelope_mismatch")
    if not sealed.quantities:
        reasons.append("sealed_run_empty")
    if any(not row.lineage_ok for row in sealed.quantities):
        reasons.append("sealed_run_lineage_conflict")
    if any(not row.object_identity_refs and not row.abstained for row in sealed.quantities):
        reasons.append("sealed_run_missing_physical_identity")
    # Snapshot the cryptographically verified production run that this proof
    # actually accepted; a later valid but DIFFERENT seal may not inherit it.
    if not reasons and seal_fingerprint_sink is not None:
        seal_fingerprint_sink.append(sealed.fingerprint)
    return not reasons, len(sealed.quantities), reasons


def _safe_finite_quantity_number(value: object) -> bool:
    """Avoid int-to-float overflow in parity for already-decoded quantities."""
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def produced_sealed_parity_blockers(produced: list[dict], sealed_quantities: tuple) -> list[str]:
    """Prove quantity projection from authenticated production IDs, never V2 truth.

    Firm sealed quantities must be represented exactly once; an ABSTAIN may be
    omitted but must remain ABSTAIN if supplied. Trade category is separately
    authenticated upstream and is not inferred from benchmark descriptions.
    """
    blockers: list[str] = []
    by_id: dict[str, dict] = {}
    for item in produced:
        quantity_id = item.get("quantity_id")
        if not isinstance(quantity_id, str) or not quantity_id.strip():
            blockers.append("produced_quantity_id_missing")
            continue
        if quantity_id in by_id:
            blockers.append(f"duplicate_produced_quantity_id:{quantity_id}")
        by_id[quantity_id] = item
    sealed_by_id = {row.quantity_id: row for row in sealed_quantities}
    if len(sealed_by_id) != len(sealed_quantities):
        blockers.append("duplicate_sealed_quantity_ids")
    for quantity_id, row in sealed_by_id.items():
        item = by_id.get(quantity_id)
        if item is None:
            if not row.abstained:
                blockers.append(f"firm_sealed_quantity_not_projected:{quantity_id}")
            continue
        if type(item.get("abstained")) is not bool or item["abstained"] != row.abstained:
            blockers.append(f"projection_abstention_mismatch:{quantity_id}")
        if type(item.get("lineage_ok")) is not bool or item["lineage_ok"] != row.lineage_ok:
            blockers.append(f"projection_lineage_mismatch:{quantity_id}")
        if not isinstance(item.get("unit"), str) or item["unit"].strip().lower() != row.unit.strip().lower():
            blockers.append(f"projection_unit_mismatch:{quantity_id}")
        value = item.get("value")
        if row.abstained:
            if value is not None:
                blockers.append(f"abstained_projection_has_value:{quantity_id}")
        elif (
            type(value) not in (int, float)
            or not _safe_finite_quantity_number(value)
            or row.value is None
            or value != row.value
        ):
            blockers.append(f"projection_value_mismatch:{quantity_id}")
        refs = item.get("object_refs")
        if (
            not isinstance(refs, list)
            or any(not isinstance(ref, str) or not ref.strip() for ref in refs)
            or len(set(refs)) != len(refs)
            or set(refs) != set(row.object_identity_refs)
        ):
            blockers.append(f"projection_object_identity_mismatch:{quantity_id}")
        # New source exporter records additional original signed V1 fields.
        # These are optional for legacy diagnostic inputs, but an explicit
        # field is never allowed to drift under the same quantity_id.
        for produced_field, sealed_field in (
            ("project_id", "project_id"),
            ("family", "family"),
            ("status", "status"),
            ("authority", "authority"),
            ("source_page", "source_page"),
            ("viewport_id", "viewport_id"),
            ("semantic_key", "semantic_key"),
            ("source_document_id", "document_id"),
            ("source_sha256", "source_sha256"),
            ("revision_id", "revision_id"),
            ("sealed_quantity_fingerprint", "fingerprint"),
        ):
            if produced_field in item:
                source_value = getattr(row, sealed_field, None)
                if (
                    type(item[produced_field]) is not str
                    or not item[produced_field]
                    or item[produced_field] != source_value
                ):
                    blockers.append(
                        f"projection_{produced_field}_mismatch:{quantity_id}"
                    )
        if "confidence" in item:
            original_confidence = getattr(row, "confidence", None)
            candidate_confidence = item["confidence"]
            if (
                not _safe_finite_quantity_number(candidate_confidence)
                or original_confidence is None
                or candidate_confidence != original_confidence
            ):
                blockers.append(f"projection_confidence_mismatch:{quantity_id}")
        # Source-sealed quantities are not proof that customer output exists.
        # The new exporter records false until the existing signed-customer
        # bijection has been independently executed. A true flag is only a
        # reported receipt, not estimator approval or trade authentication.
        if (
            "customer_output_parity_verified" in item
            and item["customer_output_parity_verified"] is not True
        ):
            blockers.append(
                f"projection_customer_output_parity_unverified:{quantity_id}"
            )
        # A signed-customer claim consists of a flag *and* its scoped proof
        # status. The exporter writes these together. An independently
        # authentic-looking flag paired with an unchecked or forged status
        # must never become the readiness receipt for this quantity.
        if "customer_output_parity_status" in item:
            status = item["customer_output_parity_status"]
            verified_flag = item.get("customer_output_parity_verified")
            if (
                (status == "SIGNED_CUSTOMER_BIJECTION_VERIFIED" and verified_flag is not True)
                or (status == "NOT_CHECKED_SOURCE_SEAL_ONLY" and verified_flag is not False)
                or status not in (
                    "SIGNED_CUSTOMER_BIJECTION_VERIFIED", "NOT_CHECKED_SOURCE_SEAL_ONLY"
                )
            ):
                blockers.append(
                    f"projection_customer_output_status_inconsistent:{quantity_id}"
                )
        category = item.get("trade_category")
        if not isinstance(category, str) or not category.strip():
            blockers.append(f"projection_trade_category_missing:{quantity_id}")
    for quantity_id in set(by_id) - set(sealed_by_id):
        blockers.append(f"unsealed_produced_quantity:{quantity_id}")
    return sorted(set(blockers))


def _sealed_projection_proof(
    sealed_root: Path | None, project_id: str, produced: list[dict],
    sealed_run_verified: bool, *,
    expected_seal_fingerprint: str | None = None,
    downstream_reason_sink: list[str] | None = None,
) -> tuple[bool, list[str]]:
    if not sealed_run_verified or sealed_root is None:
        return False, ["produced_sealed_parity_not_proven"]
    from pb_source_closed_run_export import sealed_source_closed_run_from_dict

    # A parallel production seal writer can replace/remove this file after
    # _sealed_run_proof succeeded. The second independent read must fail closed
    # for this project, not abort the four-project readiness diagnostic.
    from pb_source_closed_run_export import SourceClosedRunExportError
    try:
        sealed = sealed_source_closed_run_from_dict(
            _object(sealed_root / project_id / "sealed_run.json")
        )
    except (SourceClosedRunExportError, TypeError, ValueError, KeyError,
            UnicodeError, OSError):
        return False, ["sealed_run_changed_during_parity"]
    if sealed.project_id != project_id:
        return False, ["sealed_run_changed_during_parity"]
    # Reverify the *same* signed run as the first seal-integrity stage. Hash
    # equality of actual production seal payloads is stronger than project ID,
    # source envelope or mere equality of projected quantity IDs.
    if (expected_seal_fingerprint is not None
            and sealed.fingerprint != expected_seal_fingerprint):
        return False, ["sealed_run_changed_during_parity"]
    blockers = produced_sealed_parity_blockers(produced, sealed.quantities)
    # Quantity projection is a separate authority gate from commercial trade
    # classification and customer publication. The exporter deliberately
    # leaves trade unavailable and marks customer parity unchecked until
    # their *independent* original-source/customer-row evidence arrives.
    # Do not relabel those expected downstream blockers as signed quantity
    # identity failures or hide the first actual failed authority stage.
    downstream_prefixes = (
        "projection_trade_category_missing:",
        "projection_customer_output_parity_unverified:",
    )
    if downstream_reason_sink is not None:
        downstream_reason_sink.extend(
            reason for reason in blockers if reason.startswith(downstream_prefixes)
        )
    signed_quantity_blockers = [
        reason for reason in blockers
        if not reason.startswith(downstream_prefixes)
    ]
    return not signed_quantity_blockers, signed_quantity_blockers


def _customer_output_bijection_proof(
    sealed_root: Path | None, customer_root: Path | None,
    project_id: str, sealed_run_verified: bool, *,
    expected_seal_fingerprint: str | None = None,
) -> tuple[bool, list[str]]:
    """Authenticate real customer rows against the *same* signed production run.

    A produced-items JSON claim of customer parity is never enough. This gate
    reopens customer bytes and the independently verified V1 seal, and runs
    the existing source-to-customer bijection verifier. It is diagnostic only.
    """
    if customer_root is None:
        return False, ["customer_rows_not_supplied"]
    if not sealed_run_verified or sealed_root is None or not expected_seal_fingerprint:
        return False, ["customer_sealed_run_not_verified"]
    customer_path = customer_root / project_id / "customer_rows.json"
    if not customer_path.is_file():
        return False, ["customer_rows_missing"]
    from pb_customer_output_verification import (
        CustomerOutputVerificationError, verify_sealed_customer_output,
    )
    from pb_source_closed_run_export import (
        SourceClosedRunExportError, sealed_source_closed_run_from_dict,
    )
    from tools.export_gpt3_produced_items import _verify_embedded_customer_notes

    sealed_path = sealed_root / project_id / "sealed_run.json"
    try:
        before = customer_path.read_bytes()
        customer_rows = _parse_evidence_json(before.decode("utf-8"))
        if not isinstance(customer_rows, list) or any(
            not isinstance(row, dict) for row in customer_rows
        ):
            return False, ["customer_rows_invalid_shape"]
        _verify_embedded_customer_notes(customer_rows)
        sealed = sealed_source_closed_run_from_dict(_object(sealed_path))
        if sealed.project_id != project_id or sealed.fingerprint != expected_seal_fingerprint:
            return False, ["customer_sealed_run_changed"]
        # The verifier proves the complete bijection or raises a specific
        # CustomerOutputVerificationError. Its return value is a summary
        # receipt, not an object with a `.complete` attribute.
        verify_sealed_customer_output(sealed, customer_rows)
        # Do not let a concurrent writer change either signed input after
        # this proof while still reporting that its earlier bytes passed.
        if customer_path.read_bytes() != before:
            return False, ["customer_rows_changed_during_readiness"]
        reopened = sealed_source_closed_run_from_dict(_object(sealed_path))
        if reopened.fingerprint != expected_seal_fingerprint:
            return False, ["customer_sealed_run_changed"]
    except (SourceClosedRunExportError, CustomerOutputVerificationError,
            TypeError, ValueError, KeyError, UnicodeError, OSError, OverflowError):
        return False, ["customer_bijection_integrity_invalid"]
    return True, []


def _first_failing_authority_stage(
    *, source_verified: bool, source_reasons: list[str],
    manifest_status: str, manifest_reasons: list[str],
    sealed_verified: bool, seal_reasons: list[str],
    produced_present: bool, produced_valid: bool, produced_count: int | None,
    produced_reasons: list[str],
    parity_verified: bool, parity_reasons: list[str],
    customer_verified: bool = True, customer_reasons: list[str] | None = None,
) -> tuple[str, str]:
    """Return a grounded earliest authority failure, never a benchmark match.

    Stage order is source bytes -> physical universe -> sealed production ->
    produced identity -> parity -> independent commercial trade authority.
    No stage consults gold descriptions, matches or evaluator quantities.
    """
    if not source_verified:
        return "ORIGINAL_SOURCE_SHA_AUTHORITY", (
            sorted(source_reasons)[0] if source_reasons else "source_sha_unverified"
        )
    if manifest_status != "VERIFIED":
        return "SOURCE_UNIVERSE_CLOSURE", (
            manifest_reasons[0] if manifest_reasons else "frozen_manifest_not_verified"
        )
    if not sealed_verified:
        return "SEALED_PRODUCTION_AUTHORITY", (
            sorted(seal_reasons)[0] if seal_reasons else "sealed_run_unverified"
        )
    if not produced_present:
        return "PRODUCED_ITEMS", "production_items_missing"
    if not produced_valid:
        return "PRODUCED_ITEMS", (
            sorted(produced_reasons)[0] if produced_reasons
            else "produced_items_invalid_json_or_shape"
        )
    if not produced_count:
        return "PRODUCED_ITEMS", "empty_produced_items_unverified"
    if not parity_verified:
        return "SIGNED_QUANTITY_PARITY", (
            sorted(parity_reasons)[0] if parity_reasons else "produced_sealed_parity_not_proven"
        )
    if not customer_verified:
        return "CUSTOMER_OUTPUT_BIJECTION", (
            sorted(customer_reasons or ())[0] if customer_reasons
            else "customer_output_bijection_not_verified"
        )
    return "COMMERCIAL_TRADE_AUTHORITY", "commercial_trade_authority_not_independently_verified"


def diagnostic_report(
    root: Path, produced_root: Path, source_root: Path | None = None,
    sealed_root: Path | None = None, customer_root: Path | None = None,
) -> dict:
    suite = _object(root / "manifest.json")
    project_ids = suite["projects"]
    required_count = suite["required_project_count"]
    if (
        not isinstance(project_ids, list)
        or not isinstance(required_count, int)
        or len(project_ids) != required_count
        or len(set(project_ids)) != required_count
    ):
        raise ValueError("invalid frozen suite project list")
    projects = []
    for project_id in project_ids:
        if not isinstance(project_id, str) or not project_id:
            raise ValueError("invalid frozen project id")
        manifest = _object(root / "projects" / project_id / "source_manifest.json")
        if manifest.get("project_id") != project_id:
            raise ValueError(f"frozen project identity mismatch: {project_id}")
        path = produced_root / project_id / "produced_items.json"
        exists = path.is_file()
        invalid_produced_shape = False
        produced_initial_sha: str | None = None
        if exists:
            try:
                # Bind the actual bytes parsed for parity, not a later read.
                produced_bytes = path.read_bytes()
                produced_initial_sha = hashlib.sha256(produced_bytes).hexdigest()
                produced = _parse_evidence_json(produced_bytes.decode("utf-8"))
            except (ValueError, UnicodeError, OSError):
                produced = []
                invalid_produced_shape = True
            if not isinstance(produced, list) or any(not isinstance(x, dict) for x in produced):
                produced = []
                invalid_produced_shape = True
            # Keep examining the other projects; an unreadable produced file
            # must be an explicit source-readiness blocker, never a score or
            # a fatal exception that conceals unrelated project failures.
            # A malformed production row is a readiness blocker, not a
            # reason to crash before the remaining four-project diagnostic.
            # Reject absent, blank and non-string IDs without manufacturing
            # a replacement identity such as the literal string "None".
            ids = [
                item["quantity_id"] for item in produced
                if isinstance(item.get("quantity_id"), str)
                and item["quantity_id"].strip()
            ]
            invalid_produced_id_count = len(produced) - len(ids)
        else:
            produced, ids = [], []
            invalid_produced_id_count = 0
        duplicate_ids = sorted(k for k, count in Counter(ids).items() if count > 1)
        eligible = manifest.get("verified_takeoff_items", [])
        denominator = sum(item.get("denominator_eligible", True) is True for item in eligible)
        blockers = list(manifest.get("reason_codes") or ())
        source_verified, source_reasons = _source_sha_proof(manifest, source_root, project_id)
        blockers.extend(source_reasons)
        expected_shas = {doc["sha256"] for doc in manifest.get("source_documents", ())}
        seal_fingerprints: list[str] = []
        seal_verified, sealed_count, seal_reasons = _sealed_run_proof(
            sealed_root, project_id, expected_shas,
            seal_fingerprint_sink=seal_fingerprints,
        )
        blockers.extend(seal_reasons)
        downstream_parity_reasons: list[str] = []
        parity_verified, parity_reasons = (
            _sealed_projection_proof(
                sealed_root, project_id, produced, seal_verified,
                expected_seal_fingerprint=(
                    seal_fingerprints[0] if seal_fingerprints else None
                ),
                downstream_reason_sink=downstream_parity_reasons,
            )
            if exists and not invalid_produced_shape and (
                not seal_verified or len(seal_fingerprints) == 1
            )
            else (False, ["produced_sealed_parity_not_proven"])
        )
        blockers.extend(parity_reasons)
        # Retain precise per-quantity downstream facts in the report while
        # keeping them outside the signed *quantity* identity/metric verdict.
        blockers.extend(downstream_parity_reasons)
        customer_verified, customer_reasons = _customer_output_bijection_proof(
            sealed_root, customer_root, project_id, seal_verified,
            expected_seal_fingerprint=(
                seal_fingerprints[0] if len(seal_fingerprints) == 1 else None
            ),
        )
        blockers.extend(customer_reasons)
        # The first original-PDF hash is not durable source proof if a long
        # seal/parity pass rotates the on-disk source package. Rehash just
        # before the final readiness result, without consulting gold values.
        if source_verified:
            source_still_verified, final_source_reasons = _source_sha_proof(
                manifest, source_root, project_id
            )
            if not source_still_verified:
                source_verified = False
                source_reasons.extend(final_source_reasons)
                source_reasons.append("source_changed_during_readiness")
                blockers.extend(final_source_reasons)
                blockers.append("source_changed_during_readiness")
        if exists and produced_initial_sha is not None:
            # A concurrent producer may replace a valid produced file after
            # first parsing but before parity/report publication. Never use
            # the stale in-memory rows as proof of the on-disk artifact.
            try:
                current_produced_sha = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                current_produced_sha = None
            if current_produced_sha != produced_initial_sha:
                parity_verified = False
                invalid_produced_shape = True
                parity_reasons.append("produced_items_changed_during_readiness")
                blockers.append("produced_items_changed_during_readiness")
        if exists:
            blockers.append("commercial_trade_authority_not_independently_verified")
        if manifest.get("status") != "VERIFIED":
            blockers.insert(0, "frozen_manifest_not_verified")
        if not exists:
            blockers.append("production_items_missing")
        if invalid_produced_id_count:
            blockers.append("produced_quantity_id_missing_or_invalid")
        if duplicate_ids:
            blockers.append("duplicate_produced_quantity_ids")
        if any(item.get("lineage_ok") is not True for item in produced):
            blockers.append("production_lineage_conflict_or_unverified")
        if invalid_produced_shape:
            blockers.append("produced_items_invalid_json_or_shape")
        elif not produced and exists:
            blockers.append("empty_produced_items_unverified")
        first_stage, first_reason = _first_failing_authority_stage(
            source_verified=source_verified,
            source_reasons=source_reasons,
            manifest_status=manifest.get("status"),
            manifest_reasons=list(manifest.get("reason_codes") or ()),
            sealed_verified=seal_verified,
            seal_reasons=seal_reasons,
            produced_present=exists,
            produced_valid=not invalid_produced_shape and invalid_produced_id_count == 0 and not duplicate_ids,
            produced_count=len(produced) if exists and not invalid_produced_shape else None,
            produced_reasons=(
                (["produced_items_changed_during_readiness"] if "produced_items_changed_during_readiness" in blockers else [])
                + (["produced_items_invalid_json_or_shape"] if invalid_produced_shape else [])
                + (["produced_quantity_id_missing_or_invalid"] if invalid_produced_id_count else [])
                + (["duplicate_produced_quantity_ids"] if duplicate_ids else [])
            ),
            parity_verified=parity_verified,
            parity_reasons=parity_reasons,
            customer_verified=customer_verified,
            customer_reasons=customer_reasons,
        )
        projects.append({
            "project_id": project_id,
            "manifest_status": manifest.get("status"),
            "denominator": denominator,
            "produced_file_present": exists,
            "produced_count": len(produced) if exists and not invalid_produced_shape else None,
            "lineage_conflict_count": sum(item.get("lineage_ok") is not True for item in produced) if exists and not invalid_produced_shape else None,
            "abstention_count": sum(item.get("abstained") is True for item in produced) if exists and not invalid_produced_shape else None,
            "duplicate_quantity_ids": duplicate_ids,
            "source_sha_verified": source_verified,
            "sealed_run_verified": seal_verified,
            "sealed_quantity_count": sealed_count,
            "produced_sealed_parity_verified": parity_verified,
            "customer_output_bijection_verified": customer_verified,
            "customer_output_bijection_reason_codes": customer_reasons,
            "commercial_trade_authority_verified": False,
            "reconciliation_complete": False,
            "first_failing_authority_stage": first_stage,
            "first_failing_authority_reason": first_reason,
            # No frozen evaluator has run on a source-complete universe.
            # Unknown classification counts must not silently become zero.
            "reconciliation_evaluation_status": "NOT_EVALUATED",
            "matched_within_tolerance": None,
            "matched_outside_tolerance": None,
            "missed": None,
            "partial": None,
            "unresolved": None,
            "unsupported_extra": None,
            "blockers": sorted(set(blockers)),
            "coverage_accuracy": None,
            "precision_adjusted_accuracy": None,
        })
    return {
        "report_type": "FULL_PLAN_V2_READINESS_DIAGNOSTIC",
        "publication_status": "UNPUBLISHED",
        "score_claim": False,
        "required_project_count": required_count,
        "projects": projects,
    }


def _write_readiness_report(
    output: Path, encoded: str, *, protected_roots: tuple[Path | None, ...],
) -> None:
    """Publish diagnostics atomically without mutating any evidence directory.

    Frozen manifests, source PDFs, signed runs, produced rows and customer rows
    remain immutable inputs to this read-only report, including symlink aliases.
    """
    destination = output.resolve()
    for original_root in protected_roots:
        if original_root is None:
            continue
        protected = original_root.resolve()
        if destination == protected or destination.is_relative_to(protected):
            raise ValueError("readiness output may not overwrite evidence or frozen benchmark inputs")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output.parent,
            prefix=f".{output.name}.", suffix=".tmp", delete=False,
        ) as writer:
            temporary_path = Path(writer.name)
            writer.write(encoded)
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(temporary_path, output)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--produced-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--sealed-root", type=Path)
    parser.add_argument("--customer-root", type=Path,
                        help="Per-project customer_rows.json files to independently verify")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = diagnostic_report(
        args.benchmark_root, args.produced_root, args.source_root,
        args.sealed_root, args.customer_root,
    )
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        _write_readiness_report(
            args.output, encoded,
            protected_roots=(
                args.benchmark_root, args.produced_root, args.source_root,
                args.sealed_root, args.customer_root,
            ),
        )
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
