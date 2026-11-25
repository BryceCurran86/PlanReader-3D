"""Manifest-driven external source-PDF bundle and identity-map inventory verifier.

Provides pure, read-only, fail-closed cryptographic inventory and preflight
receipts for external private source PDF directories and independent V2
identity-map directories against any Full Plan V2 suite manifest.

Design invariants:
- Strictly manifest-driven: zero hardcoded project names, filenames, or SHA-256
  digests in executable code.
- Public-safe receipts: serialized outputs never emit host filesystem paths,
  private filenames, or raw object identity bindings—only manifest roles,
  counts, status/reason codes, and cryptographic SHA-256 digests.
- Preflight only: a verified input bundle receipt proves input authenticity
  and map schema integrity; it is never a replay outcome or benchmark score.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

_FROZEN_V2_DIR = (
    Path(__file__).resolve().parent / "benchmarks" / "frozen_holdout" / "full_plan_v2"
)
_FROZEN_V2_ALIAS = "_pb_source_bundle_inventory_frozen_v2"


def _load_frozen_v2_modules() -> tuple[Any, Any]:
    """Load unchanged V2 manifest and reconciliation modules safely.

    Pytest adds ``tests/`` to ``sys.path`` where ``tests/benchmarks`` can shadow
    the repository's top-level ``benchmarks`` package. Loading via a private
    package alias prevents import shadowing in all test and CLI contexts.
    """
    if _FROZEN_V2_ALIAS not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            _FROZEN_V2_ALIAS,
            _FROZEN_V2_DIR / "__init__.py",
            submodule_search_locations=[str(_FROZEN_V2_DIR)],
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("frozen_v2_package_unavailable")
        package = importlib.util.module_from_spec(spec)
        sys.modules[_FROZEN_V2_ALIAS] = package
        spec.loader.exec_module(package)
    manifest_io = importlib.import_module(f"{_FROZEN_V2_ALIAS}.manifest_io")
    reconciliation = importlib.import_module(f"{_FROZEN_V2_ALIAS}.sealed_reconciliation")
    return manifest_io, reconciliation

SCHEMA_VERSION = "1.0.0"
ENV_SOURCE_DIR = "PLANREADER_PRIVATE_SOURCE_ROOT"
ENV_IDENTITY_MAP_DIR = "PLANREADER_PRIVATE_IDENTITY_MAP_ROOT"
_ALLOWED_CONFIG_KEYS = frozenset({"source_dir", "identity_map_dir", "run_root"})
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _digest_payload(payload: Mapping[str, Any]) -> str:
    clean = dict(payload)
    clean.pop("receipt_sha256", None)
    return hashlib.sha256(_canonical_json(clean).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_safe_pdf_name(name: object) -> bool:
    if type(name) is not str:
        return False
    if not name or name in (".", ".."):
        return False
    if "/" in name or "\\" in name or name != Path(name).name:
        return False
    return name.lower().endswith(".pdf")


def _reject_json_constant(token: str) -> Any:
    raise ValueError(f"non_finite_json_constant:{token}")


def _read_strict_json_object(path: Path) -> dict[str, Any]:
    raw_text = path.read_text(encoding="utf-8")
    parsed = json.loads(raw_text, parse_constant=_reject_json_constant)
    if type(parsed) is not dict:
        raise ValueError("json_root_must_be_object")
    return parsed


def _read_pdf_page_count(path: Path) -> int:
    import fitz

    with fitz.open(path) as doc:
        return int(len(doc))


def _check_real_directory(path: Path, label: str) -> Path:
    if not isinstance(path, Path):
        raise TypeError(f"{label} must be a Path")
    if path.is_symlink():
        raise ValueError(f"{label}_symlink_rejected")
    if not path.is_dir():
        raise FileNotFoundError(f"{label}_directory_missing")
    return path


def resolve_bundle_directories(
    *,
    source_dir: Path | str | None = None,
    identity_map_dir: Path | str | None = None,
    config_path: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    default_source_dir: Path | None = None,
) -> tuple[Path, Path]:
    """Resolve external source-PDF and identity-map directories fail-closed.

    Precedence for each directory: explicit argument -> JSON config file ->
    environment variable -> explicit caller default (source_dir only).
    Never scans arbitrary host directories or guesses an identity-map folder.
    """
    env_map = os.environ if env is None else env
    settings: dict[str, str] = {}
    if config_path is not None:
        cfg = Path(config_path).expanduser()
        if cfg.is_symlink() or not cfg.is_file():
            raise ValueError("bundle_config_unavailable_or_symlink")
        parsed = _read_strict_json_object(cfg)
        for key, value in parsed.items():
            if key not in _ALLOWED_CONFIG_KEYS:
                raise ValueError(f"bundle_config_unknown_key:{key}")
            if type(value) is not str or not value.strip():
                raise ValueError(f"bundle_config_invalid_value:{key}")
            settings[key] = value.strip()

    raw_source = (
        str(source_dir).strip()
        if source_dir is not None
        else settings.get("source_dir")
        or str(env_map.get(ENV_SOURCE_DIR, "")).strip()
        or (str(default_source_dir) if default_source_dir is not None else "")
    )
    if not raw_source:
        raise ValueError("source_dir_not_configured")

    raw_maps = (
        str(identity_map_dir).strip()
        if identity_map_dir is not None
        else settings.get("identity_map_dir")
        or str(env_map.get(ENV_IDENTITY_MAP_DIR, "")).strip()
    )
    if not raw_maps:
        raise ValueError("identity_map_dir_not_configured")

    return Path(raw_source).expanduser(), Path(raw_maps).expanduser()


@dataclass(frozen=True)
class SourceDocumentVerification:
    project_id: str
    role: str
    expected_sha256: str
    expected_size_bytes: int
    expected_page_count: int | None
    status: str
    actual_size_bytes: int | None = None
    actual_sha256: str | None = None
    actual_page_count: int | None = None
    matched_layout: str | None = None
    reason_code: str | None = None

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "role": self.role,
            "expected_sha256": self.expected_sha256,
            "expected_size_bytes": self.expected_size_bytes,
            "expected_page_count": self.expected_page_count,
            "status": self.status,
            "actual_size_bytes": self.actual_size_bytes,
            "actual_sha256": self.actual_sha256,
            "actual_page_count": self.actual_page_count,
            "matched_layout": self.matched_layout,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True)
class SourceBundleInventoryReceipt:
    schema_version: str
    status: str
    required_project_count: int
    verified_project_count: int
    required_document_count: int
    verified_document_count: int
    project_statuses: Mapping[str, str]
    documents: tuple[SourceDocumentVerification, ...]
    unexpected_pdf_count: int
    reason_codes: tuple[str, ...]
    receipt_sha256: str

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "required_project_count": self.required_project_count,
            "verified_project_count": self.verified_project_count,
            "required_document_count": self.required_document_count,
            "verified_document_count": self.verified_document_count,
            "project_statuses": dict(sorted(self.project_statuses.items())),
            "documents": [doc.to_safe_dict() for doc in self.documents],
            "unexpected_pdf_count": self.unexpected_pdf_count,
            "reason_codes": list(self.reason_codes),
            "receipt_sha256": self.receipt_sha256,
        }


@dataclass(frozen=True)
class ProjectIdentityMapAudit:
    project_id: str
    status: str
    file_sha256: str | None
    denominator_item_count: int
    binding_count: int
    missing_denominator_item_count: int
    expected_source_hash_count: int
    covered_source_hash_count: int
    shared_ref_tuple_count: int
    shared_ref_atom_count: int
    families: tuple[str, ...]
    reason_codes: tuple[str, ...]

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "status": self.status,
            "file_sha256": self.file_sha256,
            "denominator_item_count": self.denominator_item_count,
            "binding_count": self.binding_count,
            "missing_denominator_item_count": self.missing_denominator_item_count,
            "expected_source_hash_count": self.expected_source_hash_count,
            "covered_source_hash_count": self.covered_source_hash_count,
            "shared_ref_tuple_count": self.shared_ref_tuple_count,
            "shared_ref_atom_count": self.shared_ref_atom_count,
            "families": list(self.families),
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True)
class IdentityMapBundleAuditReceipt:
    schema_version: str
    status: str
    required_project_count: int
    valid_project_count: int
    total_denominator_items: int
    total_bound_items: int
    projects: tuple[ProjectIdentityMapAudit, ...]
    reason_codes: tuple[str, ...]
    receipt_sha256: str

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "required_project_count": self.required_project_count,
            "valid_project_count": self.valid_project_count,
            "total_denominator_items": self.total_denominator_items,
            "total_bound_items": self.total_bound_items,
            "projects": [proj.to_safe_dict() for proj in self.projects],
            "reason_codes": list(self.reason_codes),
            "receipt_sha256": self.receipt_sha256,
        }


@dataclass(frozen=True)
class BenchmarkInputBundlePreflightReceipt:
    schema_version: str
    status: str
    is_score_or_replay_result: bool
    source_inventory: SourceBundleInventoryReceipt
    identity_maps: IdentityMapBundleAuditReceipt
    reason_codes: tuple[str, ...]
    receipt_sha256: str

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "is_score_or_replay_result": self.is_score_or_replay_result,
            "source_inventory": self.source_inventory.to_safe_dict(),
            "identity_maps": self.identity_maps.to_safe_dict(),
            "reason_codes": list(self.reason_codes),
            "receipt_sha256": self.receipt_sha256,
        }


def _verify_single_source_document(
    *,
    project_id: str,
    doc: Any,
    source_dir: Path,
    check_page_count: bool,
) -> SourceDocumentVerification:
    if not _is_safe_pdf_name(doc.name):
        return SourceDocumentVerification(
            project_id=project_id,
            role=doc.role,
            expected_sha256=doc.sha256,
            expected_size_bytes=doc.size_bytes,
            expected_page_count=doc.page_count,
            status="UNSAFE_NAME",
            reason_code="unsafe_manifest_pdf_name",
        )
    if (
        not _SHA256_RE.fullmatch(doc.sha256)
        or doc.size_bytes < 1
        or (doc.page_count is not None and doc.page_count < 1)
    ):
        return SourceDocumentVerification(
            project_id=project_id,
            role=doc.role,
            expected_sha256=doc.sha256,
            expected_size_bytes=doc.size_bytes,
            expected_page_count=doc.page_count,
            status="MALFORMED_MANIFEST",
            reason_code="malformed_manifest_document_declaration",
        )

    flat_path = source_dir / doc.name
    scoped_dir = source_dir / project_id
    scoped_path = scoped_dir / doc.name

    if scoped_dir.is_symlink():
        return SourceDocumentVerification(
            project_id=project_id,
            role=doc.role,
            expected_sha256=doc.sha256,
            expected_size_bytes=doc.size_bytes,
            expected_page_count=doc.page_count,
            status="SYMLINK_REJECTED",
            reason_code="project_scope_directory_symlink_rejected",
        )
    if flat_path.is_symlink() or scoped_path.is_symlink():
        return SourceDocumentVerification(
            project_id=project_id,
            role=doc.role,
            expected_sha256=doc.sha256,
            expected_size_bytes=doc.size_bytes,
            expected_page_count=doc.page_count,
            status="SYMLINK_REJECTED",
            reason_code="source_document_symlink_rejected",
        )

    flat_present = flat_path.is_file()
    scoped_present = scoped_path.is_file()
    if not flat_present and not scoped_present:
        return SourceDocumentVerification(
            project_id=project_id,
            role=doc.role,
            expected_sha256=doc.sha256,
            expected_size_bytes=doc.size_bytes,
            expected_page_count=doc.page_count,
            status="MISSING",
            reason_code="source_document_missing",
        )

    if flat_present and scoped_present:
        flat_size = flat_path.stat().st_size
        scoped_size = scoped_path.stat().st_size
        flat_sha = _sha256_file(flat_path)
        scoped_sha = _sha256_file(scoped_path)
        if flat_size != scoped_size or flat_sha != scoped_sha:
            return SourceDocumentVerification(
                project_id=project_id,
                role=doc.role,
                expected_sha256=doc.sha256,
                expected_size_bytes=doc.size_bytes,
                expected_page_count=doc.page_count,
                status="CONFLICTING_DUPLICATE",
                actual_size_bytes=flat_size,
                actual_sha256=flat_sha,
                matched_layout="both_conflicting",
                reason_code="conflicting_flat_and_project_scoped_source_copies",
            )
        chosen = flat_path
        matched_layout = "both_identical"
        actual_size = flat_size
        actual_sha = flat_sha
    elif flat_present:
        chosen = flat_path
        matched_layout = "flat"
        actual_size = chosen.stat().st_size
        actual_sha = _sha256_file(chosen)
    else:
        chosen = scoped_path
        matched_layout = "project_scoped"
        actual_size = chosen.stat().st_size
        actual_sha = _sha256_file(chosen)

    if actual_size != doc.size_bytes:
        return SourceDocumentVerification(
            project_id=project_id,
            role=doc.role,
            expected_sha256=doc.sha256,
            expected_size_bytes=doc.size_bytes,
            expected_page_count=doc.page_count,
            status="SIZE_MISMATCH",
            actual_size_bytes=actual_size,
            actual_sha256=actual_sha,
            matched_layout=matched_layout,
            reason_code="source_document_size_mismatch",
        )

    if actual_sha != doc.sha256:
        return SourceDocumentVerification(
            project_id=project_id,
            role=doc.role,
            expected_sha256=doc.sha256,
            expected_size_bytes=doc.size_bytes,
            expected_page_count=doc.page_count,
            status="SHA256_MISMATCH",
            actual_size_bytes=actual_size,
            actual_sha256=actual_sha,
            matched_layout=matched_layout,
            reason_code="source_document_sha256_mismatch",
        )

    actual_pages: int | None = None
    if check_page_count and doc.page_count is not None:
        try:
            actual_pages = _read_pdf_page_count(chosen)
        except Exception:
            return SourceDocumentVerification(
                project_id=project_id,
                role=doc.role,
                expected_sha256=doc.sha256,
                expected_size_bytes=doc.size_bytes,
                expected_page_count=doc.page_count,
                status="UNREADABLE",
                actual_size_bytes=actual_size,
                actual_sha256=actual_sha,
                matched_layout=matched_layout,
                reason_code="source_pdf_unreadable",
            )
        if actual_pages != doc.page_count:
            return SourceDocumentVerification(
                project_id=project_id,
                role=doc.role,
                expected_sha256=doc.sha256,
                expected_size_bytes=doc.size_bytes,
                expected_page_count=doc.page_count,
                status="PAGE_COUNT_MISMATCH",
                actual_size_bytes=actual_size,
                actual_sha256=actual_sha,
                actual_page_count=actual_pages,
                matched_layout=matched_layout,
                reason_code="source_pdf_page_count_mismatch",
            )

    return SourceDocumentVerification(
        project_id=project_id,
        role=doc.role,
        expected_sha256=doc.sha256,
        expected_size_bytes=doc.size_bytes,
        expected_page_count=doc.page_count,
        status="VERIFIED",
        actual_size_bytes=actual_size,
        actual_sha256=actual_sha,
        actual_page_count=actual_pages,
        matched_layout=matched_layout,
        reason_code=None,
    )


def _count_unexpected_pdfs(
    manifests: Sequence[Any],
    source_dir: Path,
) -> int:
    expected_root_names: set[str] = set()
    expected_scoped: dict[str, set[str]] = {}
    for manifest in manifests:
        names = {doc.name.casefold() for doc in manifest.source_documents if _is_safe_pdf_name(doc.name)}
        expected_root_names.update(names)
        expected_scoped[manifest.project_id] = names

    unexpected = 0
    for entry in source_dir.iterdir():
        if entry.is_symlink():
            if entry.name.lower().endswith(".pdf"):
                unexpected += 1
            continue
        if entry.is_file() and entry.name.lower().endswith(".pdf"):
            if entry.name.casefold() not in expected_root_names:
                unexpected += 1
        elif entry.is_dir() and entry.name in expected_scoped:
            allowed = expected_scoped[entry.name]
            for sub in entry.iterdir():
                if sub.name.lower().endswith(".pdf"):
                    if sub.is_symlink() or sub.name.casefold() not in allowed:
                        unexpected += 1
    return unexpected


def verify_source_bundle_inventory(
    *,
    suite_root: Path,
    source_dir: Path,
    check_page_count: bool = True,
    strict_no_unexpected_pdfs: bool = False,
) -> SourceBundleInventoryReceipt:
    """Verify an external PDF directory against a Full Plan V2 suite manifest."""
    _check_real_directory(suite_root, "suite_root")
    _check_real_directory(source_dir, "source_dir")
    manifest_io, _ = _load_frozen_v2_modules()
    manifests = manifest_io.load_suite_manifests(suite_root)

    verifications: list[SourceDocumentVerification] = []
    project_statuses: dict[str, str] = {}
    reason_codes: set[str] = set()

    for manifest in manifests:
        seen_names: set[str] = set()
        project_ok = bool(manifest.source_documents)
        if not manifest.source_documents:
            reason_codes.add(f"manifest_has_no_source_documents:{manifest.project_id}")
        for doc in manifest.source_documents:
            key = doc.name.casefold() if isinstance(doc.name, str) else ""
            if key and key in seen_names:
                verif = SourceDocumentVerification(
                    project_id=manifest.project_id,
                    role=doc.role,
                    expected_sha256=doc.sha256,
                    expected_size_bytes=doc.size_bytes,
                    expected_page_count=doc.page_count,
                    status="DUPLICATE_MANIFEST_ENTRY",
                    reason_code="duplicate_manifest_document_name",
                )
            else:
                if key:
                    seen_names.add(key)
                verif = _verify_single_source_document(
                    project_id=manifest.project_id,
                    doc=doc,
                    source_dir=source_dir,
                    check_page_count=check_page_count,
                )
            verifications.append(verif)
            if verif.status != "VERIFIED":
                project_ok = False
                if verif.reason_code:
                    reason_codes.add(verif.reason_code)
        project_statuses[manifest.project_id] = "VERIFIED" if project_ok else "FAILED"

    unexpected_pdf_count = _count_unexpected_pdfs(manifests, source_dir)
    if strict_no_unexpected_pdfs and unexpected_pdf_count > 0:
        reason_codes.add("unexpected_pdf_files_present")

    verified_projects = sum(1 for st in project_statuses.values() if st == "VERIFIED")
    verified_docs = sum(1 for item in verifications if item.status == "VERIFIED")
    all_ok = (
        verified_projects == len(manifests)
        and verified_docs == len(verifications)
        and (not strict_no_unexpected_pdfs or unexpected_pdf_count == 0)
    )
    status = "COMPLETE_VERIFIED" if all_ok else "INCOMPLETE_OR_FAILED"
    ordered_reasons = tuple(sorted(reason_codes))
    doc_tuple = tuple(verifications)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "required_project_count": len(manifests),
        "verified_project_count": verified_projects,
        "required_document_count": len(verifications),
        "verified_document_count": verified_docs,
        "project_statuses": dict(sorted(project_statuses.items())),
        "documents": [doc.to_safe_dict() for doc in doc_tuple],
        "unexpected_pdf_count": unexpected_pdf_count,
        "reason_codes": list(ordered_reasons),
    }
    return SourceBundleInventoryReceipt(
        schema_version=SCHEMA_VERSION,
        status=status,
        required_project_count=len(manifests),
        verified_project_count=verified_projects,
        required_document_count=len(verifications),
        verified_document_count=verified_docs,
        project_statuses=dict(sorted(project_statuses.items())),
        documents=doc_tuple,
        unexpected_pdf_count=unexpected_pdf_count,
        reason_codes=ordered_reasons,
        receipt_sha256=_digest_payload(payload),
    )


def _audit_single_identity_map(
    *,
    manifest: Any,
    identity_map_dir: Path,
    require_all_source_hashes: bool,
    reject_shared_ref_atoms: bool,
    identity_map_loader: Any,
) -> ProjectIdentityMapAudit:
    denom_ids = {
        item.item_id
        for item in manifest.verified_items
        if item.denominator_eligible
    }
    expected_hashes = {doc.sha256 for doc in manifest.source_documents}
    map_path = identity_map_dir / f"{manifest.project_id}.identity_map.json"

    if map_path.is_symlink():
        return ProjectIdentityMapAudit(
            project_id=manifest.project_id,
            status="SYMLINK_REJECTED",
            file_sha256=None,
            denominator_item_count=len(denom_ids),
            binding_count=0,
            missing_denominator_item_count=len(denom_ids),
            expected_source_hash_count=len(expected_hashes),
            covered_source_hash_count=0,
            shared_ref_tuple_count=0,
            shared_ref_atom_count=0,
            families=(),
            reason_codes=("identity_map_symlink_rejected",),
        )
    if not map_path.is_file():
        return ProjectIdentityMapAudit(
            project_id=manifest.project_id,
            status="MISSING",
            file_sha256=None,
            denominator_item_count=len(denom_ids),
            binding_count=0,
            missing_denominator_item_count=len(denom_ids),
            expected_source_hash_count=len(expected_hashes),
            covered_source_hash_count=0,
            shared_ref_tuple_count=0,
            shared_ref_atom_count=0,
            families=(),
            reason_codes=("identity_map_missing",),
        )

    file_sha = _sha256_file(map_path)
    try:
        raw = _read_strict_json_object(map_path)
    except (OSError, UnicodeDecodeError, ValueError):
        return ProjectIdentityMapAudit(
            project_id=manifest.project_id,
            status="INVALID_JSON",
            file_sha256=file_sha,
            denominator_item_count=len(denom_ids),
            binding_count=0,
            missing_denominator_item_count=len(denom_ids),
            expected_source_hash_count=len(expected_hashes),
            covered_source_hash_count=0,
            shared_ref_tuple_count=0,
            shared_ref_atom_count=0,
            families=(),
            reason_codes=("identity_map_invalid_json",),
        )

    try:
        parsed = identity_map_loader(raw)
    except (KeyError, TypeError, ValueError):
        return ProjectIdentityMapAudit(
            project_id=manifest.project_id,
            status="SCHEMA_OR_VALIDATION_ERROR",
            file_sha256=file_sha,
            denominator_item_count=len(denom_ids),
            binding_count=0,
            missing_denominator_item_count=len(denom_ids),
            expected_source_hash_count=len(expected_hashes),
            covered_source_hash_count=0,
            shared_ref_tuple_count=0,
            shared_ref_atom_count=0,
            families=(),
            reason_codes=("identity_map_schema_error",),
        )

    reasons: list[str] = []
    if parsed.project_id != manifest.project_id:
        reasons.append("identity_map_project_id_mismatch")

    supplied_hashes = set(parsed.source_sha256s)
    if not supplied_hashes.issubset(expected_hashes):
        reasons.append("identity_map_unknown_source_sha256")
    covered_hashes = supplied_hashes & expected_hashes
    if require_all_source_hashes and covered_hashes != expected_hashes:
        reasons.append("identity_map_incomplete_source_sha256_coverage")

    unknown_target_count = sum(
        1 for binding in parsed.bindings if binding.benchmark_item_id not in denom_ids
    )
    if unknown_target_count > 0:
        reasons.append("identity_map_unknown_denominator_item")

    ref_tuples = [binding.production_object_identity_refs for binding in parsed.bindings]
    shared_ref_tuple_count = len(ref_tuples) - len(set(ref_tuples))
    all_atoms = [
        atom
        for binding in parsed.bindings
        for atom in binding.production_object_identity_refs
    ]
    shared_ref_atom_count = len(all_atoms) - len(set(all_atoms))
    if reject_shared_ref_atoms and shared_ref_atom_count > 0:
        reasons.append("identity_map_shared_production_ref_atom")

    valid_bound_ids = {
        binding.benchmark_item_id
        for binding in parsed.bindings
        if binding.benchmark_item_id in denom_ids
    }
    families = tuple(
        sorted({binding.production_family for binding in parsed.bindings if binding.production_family})
    )
    status = "VALID" if not reasons else "SCHEMA_OR_VALIDATION_ERROR"
    return ProjectIdentityMapAudit(
        project_id=manifest.project_id,
        status=status,
        file_sha256=file_sha,
        denominator_item_count=len(denom_ids),
        binding_count=len(parsed.bindings),
        missing_denominator_item_count=len(denom_ids) - len(valid_bound_ids),
        expected_source_hash_count=len(expected_hashes),
        covered_source_hash_count=len(covered_hashes),
        shared_ref_tuple_count=shared_ref_tuple_count,
        shared_ref_atom_count=shared_ref_atom_count,
        families=families,
        reason_codes=tuple(sorted(reasons)),
    )


def verify_identity_map_bundle(
    *,
    suite_root: Path,
    identity_map_dir: Path,
    require_all_source_hashes: bool = True,
    reject_shared_ref_atoms: bool = False,
) -> IdentityMapBundleAuditReceipt:
    """Audit all project identity maps in a directory against a V2 suite manifest."""
    _check_real_directory(suite_root, "suite_root")
    _check_real_directory(identity_map_dir, "identity_map_dir")
    manifest_io, reconciliation = _load_frozen_v2_modules()
    manifests = manifest_io.load_suite_manifests(suite_root)

    audits = tuple(
        _audit_single_identity_map(
            manifest=manifest,
            identity_map_dir=identity_map_dir,
            require_all_source_hashes=require_all_source_hashes,
            reject_shared_ref_atoms=reject_shared_ref_atoms,
            identity_map_loader=reconciliation.identity_map_from_dict,
        )
        for manifest in manifests
    )
    valid_projects = sum(1 for audit in audits if audit.status == "VALID")
    total_denom = sum(audit.denominator_item_count for audit in audits)
    total_bound = sum(audit.binding_count for audit in audits if audit.status == "VALID")
    reason_codes = tuple(sorted({code for audit in audits for code in audit.reason_codes}))
    status = "ALL_MAPS_VALID" if valid_projects == len(manifests) else "INCOMPLETE_OR_INVALID"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "required_project_count": len(manifests),
        "valid_project_count": valid_projects,
        "total_denominator_items": total_denom,
        "total_bound_items": total_bound,
        "projects": [audit.to_safe_dict() for audit in audits],
        "reason_codes": list(reason_codes),
    }
    return IdentityMapBundleAuditReceipt(
        schema_version=SCHEMA_VERSION,
        status=status,
        required_project_count=len(manifests),
        valid_project_count=valid_projects,
        total_denominator_items=total_denom,
        total_bound_items=total_bound,
        projects=audits,
        reason_codes=reason_codes,
        receipt_sha256=_digest_payload(payload),
    )


def verify_benchmark_input_bundle(
    *,
    suite_root: Path,
    source_dir: Path,
    identity_map_dir: Path,
    check_page_count: bool = True,
    strict_no_unexpected_pdfs: bool = False,
    require_all_source_hashes: bool = True,
    reject_shared_ref_atoms: bool = False,
) -> BenchmarkInputBundlePreflightReceipt:
    """Run complete read-only preflight over both external PDFs and identity maps."""
    source_receipt = verify_source_bundle_inventory(
        suite_root=suite_root,
        source_dir=source_dir,
        check_page_count=check_page_count,
        strict_no_unexpected_pdfs=strict_no_unexpected_pdfs,
    )
    map_receipt = verify_identity_map_bundle(
        suite_root=suite_root,
        identity_map_dir=identity_map_dir,
        require_all_source_hashes=require_all_source_hashes,
        reject_shared_ref_atoms=reject_shared_ref_atoms,
    )
    reasons = tuple(sorted(set(source_receipt.reason_codes) | set(map_receipt.reason_codes)))
    ready = (
        source_receipt.status == "COMPLETE_VERIFIED"
        and map_receipt.status == "ALL_MAPS_VALID"
    )
    status = "READY" if ready else "BLOCKED"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "is_score_or_replay_result": False,
        "source_inventory": source_receipt.to_safe_dict(),
        "identity_maps": map_receipt.to_safe_dict(),
        "reason_codes": list(reasons),
    }
    return BenchmarkInputBundlePreflightReceipt(
        schema_version=SCHEMA_VERSION,
        status=status,
        is_score_or_replay_result=False,
        source_inventory=source_receipt,
        identity_maps=map_receipt,
        reason_codes=reasons,
        receipt_sha256=_digest_payload(payload),
    )


__all__ = [
    "BenchmarkInputBundlePreflightReceipt",
    "ENV_IDENTITY_MAP_DIR",
    "ENV_SOURCE_DIR",
    "IdentityMapBundleAuditReceipt",
    "ProjectIdentityMapAudit",
    "SCHEMA_VERSION",
    "SourceBundleInventoryReceipt",
    "SourceDocumentVerification",
    "resolve_bundle_directories",
    "verify_benchmark_input_bundle",
    "verify_identity_map_bundle",
    "verify_source_bundle_inventory",
]
