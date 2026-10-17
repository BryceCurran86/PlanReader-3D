"""Two independently signed projects: source-byte-verifiable development audit.

Does not modify the frozen V2 evaluator, discover identity bindings, infer any
quantity or publish the four-project suite. Every project must supply original
PDF bytes, a cryptographically intact source seal, its complete commercial
customer projection, an independent identity map and the frozen exact report.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence

from pb_customer_output_verification import verify_sealed_customer_output
from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from tools.gpt3_signed_v2_family_trade_integrity import (
    require_signed_v2_family_trade_integrity,
)
from tools.report_gpt3_four_project_evidence import _json_customer_rows, _json_object
from tools.run_gpt3_original_byte_gated_exact_project import (
    FROZEN_ROOT, _sha256, _unchanged_frozen_exact_report,
)

_ENTRY_KEYS = frozenset({
    "manifest", "original_files", "sealed", "customer", "identity_map",
    "exact_report",
})
_COUNT_FIELDS = (
    "denominator", "matched_within_tolerance", "matched_outside_tolerance",
    "missed", "partial", "unresolved", "unsupported_extra",
    "abstained_outputs", "lineage_conflicts",
)


def _original_source_subset_gate(
    manifest: Mapping[str, Any], originals: Sequence[Path],
) -> tuple[list[str], bool]:
    """Rehash every *used* original PDF; never require unrelated source PDFs.

    A source-firm architectural opening may be independently measured without
    ingesting an unrelated structural drawing. The frozen manifest's complete
    document list is left intact. Missing documents prevent a claim of a
    complete project source execution, but do not turn a real sealed item into
    a fabricated zero.
    """
    declared = manifest.get("source_documents")
    if type(declared) is not list or not declared:
        raise ValueError("frozen source document universe is unavailable")
    names: dict[str, tuple[str, int]] = {}
    for doc in declared:
        if type(doc) is not dict:
            raise ValueError("malformed frozen source document declaration")
        name, digest, size = (doc.get("name"), doc.get("sha256"), doc.get("size_bytes"))
        if (
            type(name) is not str or not name or Path(name).name != name
            or name in names or type(digest) is not str or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
            or type(size) is not int or size <= 0
        ):
            raise ValueError("invalid immutable frozen source document declaration")
        names[name] = (digest, size)
    if not originals or len({path.name for path in originals}) != len(originals):
        raise ValueError("original PDF source path universe missing or duplicated")
    supplied: list[str] = []
    for original in originals:
        declared_source = names.get(original.name)
        if declared_source is None or not original.is_file():
            raise ValueError("original PDF source is not an independently frozen document")
        digest, size = declared_source
        if original.stat().st_size != size or _sha256(original) != digest:
            raise ValueError("original PDF source SHA/size mismatch")
        supplied.append(digest)
    return sorted(supplied), set(path.name for path in originals) == set(names)


def _json_wire_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Compare exact frozen scorer values as persisted JSON, not Python tuples.

    dataclasses.asdict retains object_refs tuples, while the signed persisted
    report encodes them as JSON arrays. This only converts serialization types;
    it must never drop, round, reorder or remap an actual produced quantity.
    """
    encoded = json.dumps(report, sort_keys=True, allow_nan=False)
    decoded = json.loads(encoded)
    if type(decoded) is not dict:
        raise ValueError("original frozen scorer report must be a JSON object")
    return decoded


def _checked_one(raw: Mapping[str, Any]) -> dict[str, Any]:
    if type(raw) is not dict or set(raw) != _ENTRY_KEYS:
        raise ValueError("selected project entry must name all six original evidence fields")
    paths = {}
    for field in _ENTRY_KEYS - {"original_files"}:
        value = raw[field]
        if type(value) is not str or not value or value != value.strip():
            raise ValueError("project evidence paths must be exact nonempty strings")
        paths[field] = Path(value)
    original_values = raw["original_files"]
    if (
        type(original_values) is not list or not original_values
        or any(type(value) is not str or not value or value != value.strip()
               for value in original_values)
    ):
        raise ValueError("original source path universe must be an exact nonempty list")
    originals = [Path(value) for value in original_values]
    all_inputs = [*paths.values(), *originals]
    # Every original PDF, signed V1, independent map, customer output and
    # exact frozen report is a distinct evidence role. An aliased file path
    # can collapse before/after SHA tracking into one dictionary key.
    if len({path.resolve() for path in all_inputs}) != len(all_inputs):
        raise ValueError("selected original source and signed evidence roles alias one file")
    raw_manifest = _json_object(paths["manifest"])
    project_id = raw_manifest.get("project_id")
    if type(project_id) is not str or not project_id or project_id != project_id.strip():
        raise ValueError("frozen project identity is invalid")
    canonical_manifest = (
        FROZEN_ROOT / "projects" / project_id / "source_manifest.json"
    ).resolve()
    if paths["manifest"].resolve() != canonical_manifest:
        raise ValueError("cannot substitute a noncanonical frozen V2 manifest")

    source_hashes, whole_source_universe_verified = _original_source_subset_gate(
        raw_manifest, originals
    )
    expected_source_hashes = set(source_hashes)

    # Hash the original *file bytes* before processing; any in-place rewrite
    # during scoring invalidates the entire selected comparison.
    input_files = (
        [paths[name] for name in ("manifest", "sealed", "customer", "identity_map", "exact_report")]
        + originals
    )
    digests = {path.resolve(): _sha256(path) for path in input_files}
    sealed = sealed_source_closed_run_from_dict(_json_object(paths["sealed"]))
    rows = _json_customer_rows(paths["customer"])
    verified = verify_sealed_customer_output(sealed, rows)
    mapping = _json_object(paths["identity_map"])
    if (
        sealed.project_id != project_id
        or set(sealed.source_sha256s) != expected_source_hashes
        or type(mapping.get("source_sha256s")) is not list
        or len(mapping["source_sha256s"]) != len(expected_source_hashes)
        or len(set(mapping["source_sha256s"])) != len(mapping["source_sha256s"])
        or set(mapping["source_sha256s"]) != expected_source_hashes
        or mapping.get("project_id") != project_id
        or verified.project_id != project_id
        or verified.customer_row_count != len(rows)
        or len(rows) != verified.valid_quantity_count
    ):
        raise ValueError("original signed/customer/map source envelope or bijection mismatch")

    require_signed_v2_family_trade_integrity(
        verified_items=raw_manifest.get("verified_takeoff_items") or (),
        sealed_quantities=sealed.quantities,
        identity_bindings=mapping.get("bindings") or (),
    )
    recomputed = _unchanged_frozen_exact_report(
        paths["manifest"], paths["sealed"], paths["identity_map"],
    )
    stored = _json_object(paths["exact_report"])
    # The unchanged frozen reporter returns dataclass asdict() rows with tuple
    # object_refs. The persisted JSON report necessarily serialises those as
    # arrays (lists). Compare *wire-equivalent* data, not Python tuple vs list;
    # do not change the evaluator, identity map, quantities or numeric values.
    recomputed_on_disk = _json_wire_report(recomputed)
    if stored != recomputed_on_disk:
        # Diagnostic keys only: never log source quantities or substitute a
        # persisted result for the independent unchanged frozen evaluator.
        differing = sorted(
            key for key in (set(stored) | set(recomputed_on_disk))
            if key not in stored or key not in recomputed_on_disk
            or stored[key] != recomputed_on_disk[key]
        )
        raise ValueError(
            "persisted frozen exact-project result differs from unchanged scorer; "
            f"top-level differing fields: {differing}"
        )
    if (
        recomputed.get("project_id") != project_id
        or recomputed.get("source_sha_verified") is not True
        or recomputed.get("reconciliation_complete") is not True
        or recomputed.get("sealed_run_id") != sealed.run_id
        or recomputed.get("sealed_run_fingerprint") != sealed.fingerprint
        or any(type(recomputed.get(field)) is not int or recomputed[field] < 0
               for field in _COUNT_FIELDS)
    ):
        raise ValueError("exact-project source/scoring receipt incomplete")

    source_hashes_after, whole_after = _original_source_subset_gate(
        raw_manifest, originals
    )
    if (
        source_hashes_after != source_hashes
        or whole_after != whole_source_universe_verified
        or any(_sha256(path) != digest for path, digest in digests.items())
    ):
        raise ValueError("original source or signed evidence bytes changed during reconciliation")

    return {
        "project_id": project_id,
        "original_source_sha_verified": True,
        "source_sha256s": source_hashes,
        "original_source_document_universe_complete": whole_source_universe_verified,
        "sealed_run_id": sealed.run_id,
        "sealed_run_fingerprint": sealed.fingerprint,
        "customer_quantity_ids": list(verified.verified_quantity_ids),
        "customer_bijection_verified": True,
        "reconciliation_complete": True,
        **{field: recomputed[field] for field in _COUNT_FIELDS},
        "coverage_accuracy": recomputed["coverage_accuracy"],
        "precision_adjusted_accuracy": recomputed["precision_adjusted_accuracy"],
        "produced_items": recomputed["produced_items"],
    }


def build_selected_two_project_development_evidence(
    entries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Require precisely two actual source executions; never publish full V2."""
    if type(entries) not in (list, tuple) or len(entries) != 2:
        raise ValueError("selected development audit requires exactly two source-executed projects")
    projects = sorted((_checked_one(entry) for entry in entries),
                      key=lambda report: report["project_id"])
    project_ids = [r["project_id"] for r in projects]
    if len(set(project_ids)) != 2:
        raise ValueError("two selected projects cannot reuse one source identity")

    seen_quantities: set[str] = set()
    for project in projects:
        ids = project["customer_quantity_ids"]
        if any(qid in seen_quantities for qid in ids):
            raise ValueError("source quantity identity reused across independent projects")
        seen_quantities.update(ids)
    sums = {field: sum(p[field] for p in projects) for field in _COUNT_FIELDS}
    denom = sums["denominator"]
    if denom <= 0:
        raise ValueError("selected frozen development denominator must be positive")

    return {
        "publication_status": "SELECTED_PROJECT_DEVELOPMENT_ONLY",
        "selected_project_count": len(projects),
        "selected_denominator": denom,
        "selected_coverage_accuracy": sums["matched_within_tolerance"] / denom,
        "selected_precision_adjusted_accuracy": None,
        **{key: value for key, value in sums.items() if key != "denominator"},
        "projects": projects,
        "official_four_project_suite_result": None,
        "official_four_project_accuracy": None,
        "full_four_project_publication_allowed": False,
        "no_source_quantity_or_benchmark_binding_created": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entry", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    entries = [_json_object(path) for path in args.entry]
    report = build_selected_two_project_development_evidence(entries)
    output = args.output
    if output.is_symlink() or output.exists() or any(
        output.resolve() == Path(value).resolve()
        for entry in entries for key, value in entry.items()
        if key != "original_files"
    ):
        raise FileExistsError("source development report must be a new file")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=output.parent, prefix=".selected-v2.",
            suffix=".tmp", delete=False,
        ) as stream:
            temp = Path(stream.name)
            stream.write(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp, output)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    print(json.dumps({
        "publication_status": report["publication_status"],
        "selected_denominator": report["selected_denominator"],
        "matched_within_tolerance": report["matched_within_tolerance"],
        "selected_coverage_accuracy": report["selected_coverage_accuracy"],
        "official_four_project_accuracy": None,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
