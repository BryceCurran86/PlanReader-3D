"""Read-only, unsigned integrity review of an archived GPT3 sealed-customer package.

This module may inspect a benchmark-side mapping only AFTER the production V1
run was sealed. It never generates a quantity, authenticates a new producer
scope, publishes customer output, or issues a benchmark score. No production
module should import it.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

from pb_customer_output_verification import verify_sealed_customer_output
from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from scripts.report_full_plan_v2_readiness import _parse_evidence_json

FILES = (
    "production/source_sealed_run.json",
    "production/verified_customer_rows.json",
    "identity_map_with_1215.json",
    "exact_project_report.json",
    "producer_head_sha.txt",
)
_MANIFEST = re.compile(r"([0-9a-f]{64}) \*([^\r\n]+)\Z")
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class EvidencePackageError(ValueError):
    """Archived evidence is unsafe, altered, inconsistent, or unverified."""


def _check(ok: bool, message: str) -> None:
    if not ok:
        raise EvidencePackageError(message)


def _source_bytes(root: Path, name: str) -> bytes:
    logical = PurePosixPath(name)
    _check(
        logical.as_posix() == name and not logical.is_absolute()
        and ".." not in logical.parts and "\\" not in name,
        "noncanonical archived source path",
    )
    path = root.joinpath(*logical.parts)
    _check(
        all(not parent.is_symlink() for parent in (root, *list(path.parents)[:-1]))
        and not path.is_symlink() and path.is_file(),
        "symlink, nonfile, or unavailable archived evidence",
    )
    return path.read_bytes()


def _object(data: bytes, description: str) -> dict[str, Any]:
    try:
        parsed = _parse_evidence_json(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise EvidencePackageError(description + " is not strict JSON") from exc
    _check(type(parsed) is dict, description + " must be a JSON object")
    return parsed


def _array(data: bytes, description: str) -> list[dict[str, Any]]:
    try:
        parsed = _parse_evidence_json(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise EvidencePackageError(description + " is not strict JSON") from exc
    _check(
        type(parsed) is list and all(type(row) is dict for row in parsed),
        description + " must be a JSON array of objects",
    )
    return parsed


def _unique(values: list[Any], message: str) -> None:
    _check(
        all(type(value) is str and bool(value) and value == value.strip()
            for value in values) and len(values) == len(set(values)),
        message,
    )


def _physical_key(family: Any, identities: Any) -> tuple[str, tuple[str, ...]]:
    _check(type(family) is str and bool(family), "missing production family")
    _check(
        type(identities) in (list, tuple) and bool(identities)
        and all(type(value) is str and bool(value) and value == value.strip()
                for value in identities)
        and len(set(identities)) == len(identities),
        "missing, duplicated, or malformed physical source identities",
    )
    return family, tuple(sorted(identities))


def verify_archived_package(directory: Path | str) -> dict[str, Any]:
    """Check fixed, immutable inputs and return an expressly UNSIGNED review."""
    root = Path(directory)
    _check(
        not root.is_symlink() and root.is_dir(),
        "archived evidence directory must be a real directory",
    )
    manifest_data = _source_bytes(root, "SHA256SUMS")
    try:
        lines = manifest_data.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise EvidencePackageError("non-ASCII digest manifest") from exc
    expected: dict[str, str] = {}
    for line in lines:
        match = _MANIFEST.fullmatch(line)
        _check(match is not None, "malformed digest manifest")
        digest, name = match.groups()
        _check(name in FILES and name not in expected, "unknown or duplicate archived file")
        expected[name] = digest
    _check(set(expected) == set(FILES), "missing archived evidence digest")
    contents: dict[str, bytes] = {}
    for name in FILES:
        data = _source_bytes(root, name)
        _check(sha256(data).hexdigest() == expected[name], "archived evidence SHA mismatch: " + name)
        contents[name] = data

    sealed_payload = _object(contents[FILES[0]], "source sealed run")
    customers = _array(contents[FILES[1]], "customer evidence")
    mapping = _object(contents[FILES[2]], "post-seal identity map")
    report = _object(contents[FILES[3]], "post-seal exact project report")

    try:
        sealed = sealed_source_closed_run_from_dict(sealed_payload)
        verified = verify_sealed_customer_output(sealed, customers)
    except (ValueError, TypeError, RuntimeError, KeyError, AttributeError) as exc:
        raise EvidencePackageError("invalid original source seal or customer projection") from exc

    _check(sealed_payload.get("schema_version") == "1.0.0", "V1 archived fingerprint schema changed")
    quantity_by_id = {q.quantity_id: q for q in sealed.quantities}
    _check(
        len(quantity_by_id) == len(sealed.quantities) == len(customers) > 0
        and verified.valid_quantity_count == len(sealed.quantities)
        and len(verified.verified_quantity_ids) == len(sealed.quantities)
        and all(q.lineage_ok and not q.abstained for q in sealed.quantities),
        "signed source/customer quantity identity mismatch",
    )
    _unique([row.get("quantity_id") for row in customers], "reused customer quantity identity")
    _check(
        set(row["quantity_id"] for row in customers) == set(quantity_by_id),
        "missing or foreign customer quantity",
    )
    _check(
        all(row.get("inclusion_status") == "PROVISIONAL"
            and row.get("quantity_status") == "To review" for row in customers),
        "archived review-only customer row was commercially promoted",
    )

    source_keys = [
        _physical_key(q.family, q.object_identity_refs)
        for q in sealed.quantities
    ]
    _check(len(set(source_keys)) == len(source_keys), "reused signed physical source")
    _check(
        type(mapping.get("bindings")) is list and mapping.get("project_id") == sealed.project_id
        and mapping.get("source_sha256s") == list(sealed.source_sha256s),
        "identity-map project or source-root conflict",
    )
    bindings = mapping["bindings"]
    _check(
        all(type(row) is dict for row in bindings),
        "malformed benchmark-side identity binding",
    )
    _unique([row.get("benchmark_item_id") for row in bindings], "reused benchmark-side target")
    map_keys = [
        _physical_key(row.get("production_family"), row.get("production_object_identity_refs"))
        for row in bindings
    ]
    _check(
        len(map_keys) == len(set(map_keys)) and set(map_keys) == set(source_keys),
        "benchmark-side identity map not bijective with original physical source",
    )

    _check(
        report.get("project_id") == sealed.project_id
        and report.get("sealed_run_fingerprint") == sealed.fingerprint
        and report.get("sealed_run_id") == sealed.run_id
        and report.get("source_sha256s") == list(sealed.source_sha256s)
        and report.get("source_sha_verified") is True
        and report.get("reconciliation_complete") is True,
        "post-seal project, signature or source report conflict",
    )
    produced = report.get("produced_items")
    _check(type(produced) is list and all(type(row) is dict for row in produced),
           "malformed post-seal produced-item report")
    _unique([row.get("quantity_id") for row in produced], "reused post-seal quantity identity")
    _check(
        len(produced) == len(sealed.quantities)
        and {row["quantity_id"] for row in produced} == set(quantity_by_id),
        "post-seal quantity ID set mismatch",
    )
    for row in produced:
        q = quantity_by_id[row["quantity_id"]]
        _check(
            row.get("unit") == q.unit and type(row.get("value")) in (int, float)
            and row["value"] == q.value and row.get("lineage_ok") is True
            and row.get("abstained") is False,
            "post-seal quantity or lineage disagreement",
        )
    fields = (
        "denominator", "matched_within_tolerance", "matched_outside_tolerance",
        "missed", "partial", "unresolved", "abstained_outputs",
        "lineage_conflicts", "unsupported_extra",
    )
    _check(
        all(type(report.get(field)) is int and report[field] >= 0 for field in fields),
        "invalid post-seal reconciliation count",
    )
    accounted = sum(report[field] for field in (
        "matched_within_tolerance", "matched_outside_tolerance",
        "missed", "partial", "unresolved",
    ))
    _check(
        report["denominator"] > 0 and accounted == report["denominator"]
        and report["lineage_conflicts"] == 0 and report["unsupported_extra"] == 0
        and report["abstained_outputs"] == 0,
        "post-seal reconciliation is incomplete or conflicted",
    )
    head = contents["producer_head_sha.txt"].decode("ascii").strip()
    _check(bool(_HEX40.fullmatch(head)), "invalid original producer commit identity")
    _check(bool(_HEX64.fullmatch(sealed.fingerprint)), "invalid original sealed run fingerprint")
    return {
        "status": "UNSIGNED_REVIEW_ONLY",
        "customer_commercial_approval_granted": False,
        "signed_v2_scope_granted": False,
        "full_suite_score_granted": False,
        "project_id": sealed.project_id,
        "original_producer_head": head,
        "source_sha256s": list(sealed.source_sha256s),
        "sealed_run_fingerprint": sealed.fingerprint,
        "signed_quantity_count": len(sealed.quantities),
        "verified_customer_row_count": verified.valid_quantity_count,
        "unique_postseal_identity_bindings": len(map_keys),
        "reported_project_denominator": report["denominator"],
        "reported_project_matched_within_tolerance": report["matched_within_tolerance"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify_archived_package(args.fixture_dir), sort_keys=True))


if __name__ == "__main__":
    main()
