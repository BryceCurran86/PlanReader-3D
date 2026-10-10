"""Fail-closed runtime source-PDF availability check; no benchmark truth access.

The frozen source_manifest.json is an immutable expected source inventory,
NOT evidence that the source files were actually loaded. This tool consults
only source_documents (never verified_takeoff_items or reference_takeoff).
It does not mint source ownership, RCP viewports, area, quantities or scores.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import fitz


def _unique_manifest_keys(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate source manifest key: {key}")
        result[key] = value
    return result


def _reject_nonfinite_json(token: str) -> None:
    raise ValueError(f"nonfinite source manifest value: {token}")


def check_source_pdf_package(manifest_path: Path, source_root: Path) -> dict:
    manifest = json.loads(
        Path(manifest_path).read_text(encoding="utf-8"),
        object_pairs_hook=_unique_manifest_keys,
        parse_constant=_reject_nonfinite_json,
    )
    if not isinstance(manifest, dict):
        raise ValueError("source manifest must be an object")
    documents = manifest.get("source_documents")
    if not isinstance(documents, list) or not documents:
        raise ValueError("missing source document inventory")
    root = Path(source_root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("source root directory unavailable or symlinked")
    seen = set()
    rows = []
    for document in documents:
        if not isinstance(document, dict):
            raise ValueError("malformed source document")
        name = document.get("name")
        sha = document.get("sha256")
        size = document.get("size_bytes")
        count = document.get("page_count")
        role = document.get("role")
        if (
            not isinstance(name, str) or not name or name in (".", "..")
            or name != Path(name).name or "/" in name or "\\" in name
            or name.casefold() in seen
            or not name.lower().endswith(".pdf")
            or not isinstance(role, str) or not role.strip()
            or not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{64}", sha) is None
            or type(size) is not int or size <= 0
            or type(count) is not int or count <= 0
        ):
            raise ValueError("invalid, unsafe or duplicate original source manifest entry")
        seen.add(name.casefold())
        path = root / name
        row = {
            "name": name,
            "role": role,
            "expected_sha256": sha,
            "expected_size_bytes": size,
            "expected_page_count": count,
            "status": "MISSING",
        }
        if path.is_symlink():
            row["status"] = "SOURCE_SYMLINK_UNTRUSTED"
        elif path.is_file():
            try:
                payload = path.read_bytes()
            except OSError:
                row["status"] = "SOURCE_UNREADABLE"
            else:
                actual_hash = hashlib.sha256(payload).hexdigest()
                row["actual_sha256"] = actual_hash
                row["actual_size_bytes"] = len(payload)
                if len(payload) != size:
                    row["status"] = "SIZE_MISMATCH"
                elif actual_hash != sha:
                    row["status"] = "SHA_MISMATCH"
                else:
                    try:
                        with fitz.open(stream=payload, filetype="pdf") as pdf:
                            pages = len(pdf)
                        row["actual_page_count"] = pages
                        row["status"] = (
                            "VERIFIED" if pages == count else "PAGE_COUNT_MISMATCH"
                        )
                    except (ValueError, RuntimeError, fitz.FileDataError):
                        row["status"] = "UNREADABLE_OR_MALFORMED_PDF"
        rows.append(row)
    complete = all(row["status"] == "VERIFIED" for row in rows)
    return {
        "project_id": str(manifest.get("project_id") or ""),
        "manifest_declares_source_package_complete": (
            manifest.get("source_package_complete") is True
        ),
        "actual_source_package_runtime_complete": complete,
        "verified_source_document_count": sum(
            row["status"] == "VERIFIED" for row in rows
        ),
        "expected_source_document_count": len(rows),
        "source_documents": rows,
        "rcp_or_metric_or_finish_authority_granted": False,
        "commercial_quantity_publication_granted": False,
        "benchmark_score_granted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = check_source_pdf_package(args.manifest, args.source_root)
    data = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(data, encoding="utf-8")
    print(data)
    if not result["actual_source_package_runtime_complete"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
