"""Read-only take-off coverage registry v1.

This module implements the architecture approved in PR #1141 at
8a21547cf2b4b5b8a607e546f8eadf43e12a4b99.

It is shadow-only.  It never establishes physical existence, mutates producer
records, promotes commercial authority, reads benchmark gold, or guesses links.
Admission comes only from producer-owned universe snapshots bound by the run
manifest.  All object/quantity joins are exact identity joins.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass, replace
import math
import re
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence

from pb_editable_3d_correction_model import EditableGeometryObject
from pb_migration_contracts import QuantityEvidence
from pb_takeoff_output_authority import TakeoffOutputRow


COVERAGE_ACCOUNTED = "ACCOUNTED"
COVERAGE_PARTIAL = "PARTIAL"
COVERAGE_UNACCOUNTED = "UNACCOUNTED"
COVERAGE_ABSTAINED = "ABSTAINED"
COVERAGE_STATES = (
    COVERAGE_ACCOUNTED,
    COVERAGE_PARTIAL,
    COVERAGE_UNACCOUNTED,
    COVERAGE_ABSTAINED,
)

ENUMERATION_COMPLETE = "COMPLETE"
ENUMERATION_INCOMPLETE = "INCOMPLETE"
ENUMERATION_UNAVAILABLE = "UNAVAILABLE"
ENUMERATION_NOT_ENUMERATED = "NOT_ENUMERATED"
ENUMERATION_STATUSES = (
    ENUMERATION_COMPLETE,
    ENUMERATION_INCOMPLETE,
    ENUMERATION_UNAVAILABLE,
    ENUMERATION_NOT_ENUMERATED,
)

CENSUS_LINKED = "LINKED_QUANTITY"
CENSUS_DANGLING = "DANGLING_QUANTITY"
CENSUS_ORPHAN_UNBOUND = "ORPHAN_UNBOUND_QUANTITY"
CENSUS_CONFLICTING_LINEAGE = "CONFLICTING_LINEAGE_QUANTITY"
QUANTITY_CENSUS_STATES = (
    CENSUS_LINKED,
    CENSUS_DANGLING,
    CENSUS_ORPHAN_UNBOUND,
    CENSUS_CONFLICTING_LINEAGE,
)

COVERAGE_BASIS_EXPLICIT_DEPENDENCIES_ONLY = "EXPLICIT_DEPENDENCIES_ONLY"
EXPECTED_FAMILY_COMPLETENESS_UNKNOWN = "UNKNOWN"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_STALE_ROW_REASON = "stale_after_geometry_correction"


class CoverageRegistryContractError(ValueError):
    """Fail-closed contract error for a registry run."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        self.reason_code = str(reason_code or "").strip() or "coverage_registry_contract_error"
        self.detail = str(detail or "").strip()
        message = self.reason_code if not self.detail else f"{self.reason_code}: {self.detail}"
        super().__init__(message)


def _required(value: Any, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be a non-empty string")
    return clean


def _sha256(value: Any, field_name: str = "source_sha256") -> str:
    clean = str(value or "").strip().lower()
    if not _SHA256_RE.fullmatch(clean):
        raise ValueError(f"{field_name} must be a 64-character lowercase SHA-256 digest")
    return clean


def _string_tuple(values: Sequence[Any], field_name: str) -> tuple[str, ...]:
    clean = tuple(str(v or "").strip() for v in values)
    if any(not value for value in clean):
        raise ValueError(f"{field_name} values must be non-empty strings")
    if len(set(clean)) != len(clean):
        raise ValueError(f"{field_name} values must be unique")
    return tuple(sorted(clean))


def _reason_tuple(values: Sequence[Any]) -> tuple[str, ...]:
    return _string_tuple(values, "reason_codes") if values else ()


def _expected_keys(values: Sequence[Sequence[Any]], field_name: str) -> tuple[tuple[str, str], ...]:
    out: list[tuple[str, str]] = []
    for raw in values:
        if len(raw) != 2:
            raise ValueError(f"{field_name} entries must contain exactly two values")
        out.append((_required(raw[0], f"{field_name}.left"), _required(raw[1], f"{field_name}.right")))
    if len(set(out)) != len(out):
        raise ValueError(f"{field_name} entries must be unique")
    return tuple(sorted(out))


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))})
    if isinstance(value, tuple):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, set):
        return tuple(sorted((_freeze(v) for v in value), key=str))
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    return value


def _to_mapping(value: Any) -> Mapping[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return value
    if is_dataclass(value):
        return {field.name: getattr(value, field.name) for field in fields(value)}
    data = getattr(value, "__dict__", None)
    return data if isinstance(data, Mapping) else {}


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _optional_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    clean = str(value).strip()
    return clean or None


def _source_pages(metadata: Mapping[str, Any]) -> tuple[int, ...]:
    raw = metadata.get("source_pages")
    if raw is None:
        raw = () if metadata.get("source_page") is None else (metadata.get("source_page"),)
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raw = (raw,)
    pages: set[int] = set()
    for value in raw:
        if isinstance(value, bool):
            continue
        try:
            page = int(value)
        except (TypeError, ValueError, OverflowError):
            continue
        if page >= 0:
            pages.add(page)
    return tuple(sorted(pages))


def _metadata_strings(metadata: Mapping[str, Any], *names: str) -> tuple[str, ...]:
    out: set[str] = set()
    for name in names:
        raw = metadata.get(name)
        if raw is None:
            continue
        if isinstance(raw, (str, bytes)):
            raw = (raw,)
        elif not isinstance(raw, Sequence):
            raw = (raw,)
        for value in raw:
            clean = _optional_string(value)
            if clean:
                out.add(clean)
    return tuple(sorted(out))


@dataclass(frozen=True)
class CoverageRegistryRunManifestV1:
    source_document_id: str
    revision_id: str
    source_sha256: str
    registry_run_id: str
    snapshot_id: str
    expected_object_universe_keys: tuple[tuple[str, str], ...]
    expected_quantity_evidence_universe_keys: tuple[tuple[str, str], ...]
    expected_takeoff_row_universe_keys: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_document_id", _required(self.source_document_id, "source_document_id"))
        object.__setattr__(self, "revision_id", _required(self.revision_id, "revision_id"))
        object.__setattr__(self, "source_sha256", _sha256(self.source_sha256))
        object.__setattr__(self, "registry_run_id", _required(self.registry_run_id, "registry_run_id"))
        object.__setattr__(self, "snapshot_id", _required(self.snapshot_id, "snapshot_id"))
        object.__setattr__(
            self,
            "expected_object_universe_keys",
            _expected_keys(self.expected_object_universe_keys, "expected_object_universe_keys"),
        )
        object.__setattr__(
            self,
            "expected_quantity_evidence_universe_keys",
            _expected_keys(
                self.expected_quantity_evidence_universe_keys,
                "expected_quantity_evidence_universe_keys",
            ),
        )
        object.__setattr__(
            self,
            "expected_takeoff_row_universe_keys",
            _expected_keys(self.expected_takeoff_row_universe_keys, "expected_takeoff_row_universe_keys"),
        )

    def to_dict(self) -> dict[str, Any]:
        return _thaw(_to_mapping(self))


@dataclass(frozen=True)
class ProducerObjectUniverseSnapshotV1:
    producer: str
    owning_authority: str
    category: str
    source_document_id: str
    revision_id: str
    source_sha256: str
    registry_run_id: str
    snapshot_id: str
    admitted_object_ids: tuple[str, ...]
    enumeration_status: str
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "producer", _required(self.producer, "producer"))
        object.__setattr__(self, "owning_authority", _required(self.owning_authority, "owning_authority"))
        object.__setattr__(self, "category", _required(self.category, "category"))
        _normalize_snapshot_common(self)
        object.__setattr__(self, "admitted_object_ids", _string_tuple(self.admitted_object_ids, "admitted_object_ids"))
        _validate_enumeration_payload(self.enumeration_status, self.reason_codes, self.admitted_object_ids)

    def to_dict(self) -> dict[str, Any]:
        return _thaw(_to_mapping(self))


@dataclass(frozen=True)
class QuantityEvidenceUniverseSnapshotV1:
    producer: str
    source: str
    source_document_id: str
    revision_id: str
    source_sha256: str
    registry_run_id: str
    snapshot_id: str
    quantity_ids: tuple[str, ...]
    enumeration_status: str
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "producer", _required(self.producer, "producer"))
        object.__setattr__(self, "source", _required(self.source, "source"))
        _normalize_snapshot_common(self)
        object.__setattr__(self, "quantity_ids", _string_tuple(self.quantity_ids, "quantity_ids"))
        _validate_enumeration_payload(self.enumeration_status, self.reason_codes, self.quantity_ids)

    def to_dict(self) -> dict[str, Any]:
        return _thaw(_to_mapping(self))


@dataclass(frozen=True)
class TakeoffOutputRowUniverseSnapshotV1:
    source: str
    collection: str
    source_document_id: str
    revision_id: str
    source_sha256: str
    registry_run_id: str
    snapshot_id: str
    quantity_ids: tuple[str, ...]
    enumeration_status: str
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", _required(self.source, "source"))
        object.__setattr__(self, "collection", _required(self.collection, "collection"))
        _normalize_snapshot_common(self)
        object.__setattr__(self, "quantity_ids", _string_tuple(self.quantity_ids, "quantity_ids"))
        _validate_enumeration_payload(self.enumeration_status, self.reason_codes, self.quantity_ids)

    def to_dict(self) -> dict[str, Any]:
        return _thaw(_to_mapping(self))


def _normalize_snapshot_common(snapshot: Any) -> None:
    object.__setattr__(
        snapshot,
        "source_document_id",
        _required(snapshot.source_document_id, "source_document_id"),
    )
    object.__setattr__(snapshot, "revision_id", _required(snapshot.revision_id, "revision_id"))
    object.__setattr__(snapshot, "source_sha256", _sha256(snapshot.source_sha256))
    object.__setattr__(snapshot, "registry_run_id", _required(snapshot.registry_run_id, "registry_run_id"))
    object.__setattr__(snapshot, "snapshot_id", _required(snapshot.snapshot_id, "snapshot_id"))
    status = _required(snapshot.enumeration_status, "enumeration_status").upper()
    if status not in ENUMERATION_STATUSES:
        raise ValueError(f"unknown enumeration_status: {status}")
    object.__setattr__(snapshot, "enumeration_status", status)
    reasons = _reason_tuple(snapshot.reason_codes)
    object.__setattr__(snapshot, "reason_codes", reasons)


def _validate_enumeration_payload(
    status: str,
    reason_codes: Sequence[str],
    ids: Sequence[str],
) -> None:
    if status != ENUMERATION_COMPLETE and not reason_codes:
        raise ValueError(f"{status} enumeration requires at least one reason_code")
    if status in {ENUMERATION_UNAVAILABLE, ENUMERATION_NOT_ENUMERATED} and ids:
        raise ValueError(f"{status} enumeration cannot carry enumerated ids")


@dataclass(frozen=True)
class CoverageObjectRecordV1:
    object_id: str
    object_type: str
    producer: str
    owning_authority: str
    source_document_id: str
    revision_id: str
    source_sha256: str
    source_pages: tuple[int, ...]
    evidence_ids: tuple[str, ...]
    geometry_ids: tuple[str, ...]
    parent_host_ids: tuple[str, ...]
    quantity_ids: tuple[str, ...]
    takeoff_row_ids: tuple[str, ...]
    coverage_state: str
    reason_codes: tuple[str, ...]
    quantity_contribution: Mapping[str, Optional[float]]
    unit: Mapping[str, str]
    provenance: Mapping[str, Any]
    coverage_basis: str = COVERAGE_BASIS_EXPLICIT_DEPENDENCIES_ONLY
    expected_family_completeness: str = EXPECTED_FAMILY_COMPLETENESS_UNKNOWN

    def __post_init__(self) -> None:
        object.__setattr__(self, "object_id", _required(self.object_id, "object_id"))
        object.__setattr__(self, "object_type", _required(self.object_type, "object_type"))
        object.__setattr__(self, "producer", _required(self.producer, "producer"))
        object.__setattr__(self, "owning_authority", _required(self.owning_authority, "owning_authority"))
        object.__setattr__(self, "source_document_id", _required(self.source_document_id, "source_document_id"))
        object.__setattr__(self, "revision_id", _required(self.revision_id, "revision_id"))
        object.__setattr__(self, "source_sha256", _sha256(self.source_sha256))
        pages = tuple(sorted({int(page) for page in self.source_pages}))
        if any(page < 0 for page in pages):
            raise ValueError("source_pages must be non-negative")
        object.__setattr__(self, "source_pages", pages)
        for name in ("evidence_ids", "geometry_ids", "parent_host_ids", "quantity_ids", "takeoff_row_ids"):
            object.__setattr__(self, name, _string_tuple(getattr(self, name), name))
        state = _required(self.coverage_state, "coverage_state").upper()
        if state not in COVERAGE_STATES:
            raise ValueError(f"unknown coverage_state: {state}")
        object.__setattr__(self, "coverage_state", state)
        object.__setattr__(self, "reason_codes", _reason_tuple(self.reason_codes))
        if self.coverage_basis != COVERAGE_BASIS_EXPLICIT_DEPENDENCIES_ONLY:
            raise ValueError("coverage_basis is frozen to EXPLICIT_DEPENDENCIES_ONLY")
        if self.expected_family_completeness != EXPECTED_FAMILY_COMPLETENESS_UNKNOWN:
            raise ValueError("expected_family_completeness is frozen to UNKNOWN")
        contributions: dict[str, Optional[float]] = {}
        for quantity_id, value in self.quantity_contribution.items():
            qid = _required(quantity_id, "quantity_contribution key")
            if qid not in self.quantity_ids:
                raise ValueError("quantity_contribution keys must be present in quantity_ids")
            if value is None:
                contributions[qid] = None
                continue
            numeric = float(value)
            if not math.isfinite(numeric) or numeric < 0.0:
                raise ValueError("quantity_contribution values must be finite and non-negative")
            contributions[qid] = numeric
        units: dict[str, str] = {}
        for quantity_id, unit in self.unit.items():
            qid = _required(quantity_id, "unit key")
            if qid not in self.quantity_ids:
                raise ValueError("unit keys must be present in quantity_ids")
            units[qid] = _required(unit, "unit")
        object.__setattr__(self, "quantity_contribution", _freeze(contributions))
        object.__setattr__(self, "unit", _freeze(units))
        object.__setattr__(self, "provenance", _freeze(dict(self.provenance)))

    def to_dict(self) -> dict[str, Any]:
        return _thaw(_to_mapping(self))


@dataclass(frozen=True)
class CoverageRegistrySummaryV1:
    manifest: CoverageRegistryRunManifestV1
    object_universe_snapshots: tuple[ProducerObjectUniverseSnapshotV1, ...]
    quantity_evidence_universe_snapshots: tuple[QuantityEvidenceUniverseSnapshotV1, ...]
    takeoff_output_row_universe_snapshots: tuple[TakeoffOutputRowUniverseSnapshotV1, ...]
    object_records: tuple[CoverageObjectRecordV1, ...]
    object_counts_by_coverage_state: Mapping[str, int]
    object_ids_by_coverage_state: Mapping[str, tuple[str, ...]]
    quantity_counts_by_census_state: Mapping[str, int]
    quantity_ids_by_census_state: Mapping[str, tuple[str, ...]]
    object_universe_complete: bool
    quantity_evidence_universe_complete: bool
    takeoff_output_row_universe_complete: bool
    quantity_census_conclusive: bool
    reason_codes: tuple[str, ...] = ()
    coverage_basis: str = COVERAGE_BASIS_EXPLICIT_DEPENDENCIES_ONLY
    expected_family_completeness: str = EXPECTED_FAMILY_COMPLETENESS_UNKNOWN

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, CoverageRegistryRunManifestV1):
            raise TypeError("manifest must be CoverageRegistryRunManifestV1")
        if self.coverage_basis != COVERAGE_BASIS_EXPLICIT_DEPENDENCIES_ONLY:
            raise ValueError("coverage_basis is frozen to EXPLICIT_DEPENDENCIES_ONLY")
        if self.expected_family_completeness != EXPECTED_FAMILY_COMPLETENESS_UNKNOWN:
            raise ValueError("expected_family_completeness is frozen to UNKNOWN")
        object.__setattr__(self, "reason_codes", _reason_tuple(self.reason_codes))
        object.__setattr__(self, "object_counts_by_coverage_state", _freeze(dict(self.object_counts_by_coverage_state)))
        object.__setattr__(self, "object_ids_by_coverage_state", _freeze(dict(self.object_ids_by_coverage_state)))
        object.__setattr__(self, "quantity_counts_by_census_state", _freeze(dict(self.quantity_counts_by_census_state)))
        object.__setattr__(self, "quantity_ids_by_census_state", _freeze(dict(self.quantity_ids_by_census_state)))

    def to_dict(self) -> dict[str, Any]:
        return _thaw(_to_mapping(self))


def _manifest_lineage(manifest: CoverageRegistryRunManifestV1) -> tuple[str, str, str, str, str]:
    return (
        manifest.source_document_id,
        manifest.revision_id,
        manifest.source_sha256,
        manifest.registry_run_id,
        manifest.snapshot_id,
    )


def _snapshot_lineage(snapshot: Any) -> tuple[str, str, str, str, str]:
    return (
        snapshot.source_document_id,
        snapshot.revision_id,
        snapshot.source_sha256,
        snapshot.registry_run_id,
        snapshot.snapshot_id,
    )


def _require_manifest_lineage(manifest: CoverageRegistryRunManifestV1, snapshot: Any, kind: str) -> None:
    if _snapshot_lineage(snapshot) != _manifest_lineage(manifest):
        raise CoverageRegistryContractError(
            "coverage_registry_run_lineage_conflict",
            f"{kind} lineage does not match manifest",
        )


def _resolve_object_snapshots(
    manifest: CoverageRegistryRunManifestV1,
    supplied: Sequence[ProducerObjectUniverseSnapshotV1],
) -> tuple[ProducerObjectUniverseSnapshotV1, ...]:
    expected = set(manifest.expected_object_universe_keys)
    indexed: dict[tuple[str, str], ProducerObjectUniverseSnapshotV1] = {}
    for snapshot in tuple(supplied):
        if not isinstance(snapshot, ProducerObjectUniverseSnapshotV1):
            raise TypeError("object_universe_snapshots must contain ProducerObjectUniverseSnapshotV1")
        _require_manifest_lineage(manifest, snapshot, "object universe")
        key = (snapshot.producer, snapshot.category)
        if key not in expected:
            raise CoverageRegistryContractError("unexpected_universe_key", f"object universe {key!r}")
        if key in indexed:
            raise CoverageRegistryContractError("duplicate_universe_enumeration", f"object universe {key!r}")
        indexed[key] = snapshot
    resolved: list[ProducerObjectUniverseSnapshotV1] = []
    for producer, category in manifest.expected_object_universe_keys:
        snapshot = indexed.get((producer, category))
        if snapshot is None:
            snapshot = ProducerObjectUniverseSnapshotV1(
                producer=producer,
                owning_authority="registry_missing_enumeration",
                category=category,
                source_document_id=manifest.source_document_id,
                revision_id=manifest.revision_id,
                source_sha256=manifest.source_sha256,
                registry_run_id=manifest.registry_run_id,
                snapshot_id=manifest.snapshot_id,
                admitted_object_ids=(),
                enumeration_status=ENUMERATION_NOT_ENUMERATED,
                reason_codes=("expected_object_universe_snapshot_missing",),
            )
        resolved.append(snapshot)
    return tuple(resolved)


def _resolve_quantity_evidence_snapshots(
    manifest: CoverageRegistryRunManifestV1,
    supplied: Sequence[QuantityEvidenceUniverseSnapshotV1],
) -> tuple[QuantityEvidenceUniverseSnapshotV1, ...]:
    expected = set(manifest.expected_quantity_evidence_universe_keys)
    indexed: dict[tuple[str, str], QuantityEvidenceUniverseSnapshotV1] = {}
    for snapshot in tuple(supplied):
        if not isinstance(snapshot, QuantityEvidenceUniverseSnapshotV1):
            raise TypeError("quantity_evidence_universe_snapshots must contain QuantityEvidenceUniverseSnapshotV1")
        _require_manifest_lineage(manifest, snapshot, "QuantityEvidence universe")
        key = (snapshot.producer, snapshot.source)
        if key not in expected:
            raise CoverageRegistryContractError("unexpected_universe_key", f"QuantityEvidence universe {key!r}")
        if key in indexed:
            raise CoverageRegistryContractError("duplicate_universe_enumeration", f"QuantityEvidence universe {key!r}")
        indexed[key] = snapshot
    resolved: list[QuantityEvidenceUniverseSnapshotV1] = []
    for producer, source in manifest.expected_quantity_evidence_universe_keys:
        snapshot = indexed.get((producer, source))
        if snapshot is None:
            snapshot = QuantityEvidenceUniverseSnapshotV1(
                producer=producer,
                source=source,
                source_document_id=manifest.source_document_id,
                revision_id=manifest.revision_id,
                source_sha256=manifest.source_sha256,
                registry_run_id=manifest.registry_run_id,
                snapshot_id=manifest.snapshot_id,
                quantity_ids=(),
                enumeration_status=ENUMERATION_NOT_ENUMERATED,
                reason_codes=("expected_quantity_evidence_universe_snapshot_missing",),
            )
        resolved.append(snapshot)
    return tuple(resolved)


def _resolve_takeoff_row_snapshots(
    manifest: CoverageRegistryRunManifestV1,
    supplied: Sequence[TakeoffOutputRowUniverseSnapshotV1],
) -> tuple[TakeoffOutputRowUniverseSnapshotV1, ...]:
    expected = set(manifest.expected_takeoff_row_universe_keys)
    indexed: dict[tuple[str, str], TakeoffOutputRowUniverseSnapshotV1] = {}
    for snapshot in tuple(supplied):
        if not isinstance(snapshot, TakeoffOutputRowUniverseSnapshotV1):
            raise TypeError("takeoff_output_row_universe_snapshots must contain TakeoffOutputRowUniverseSnapshotV1")
        _require_manifest_lineage(manifest, snapshot, "TakeoffOutputRow universe")
        key = (snapshot.source, snapshot.collection)
        if key not in expected:
            raise CoverageRegistryContractError("unexpected_universe_key", f"TakeoffOutputRow universe {key!r}")
        if key in indexed:
            raise CoverageRegistryContractError("duplicate_universe_enumeration", f"TakeoffOutputRow universe {key!r}")
        indexed[key] = snapshot
    resolved: list[TakeoffOutputRowUniverseSnapshotV1] = []
    for source, collection in manifest.expected_takeoff_row_universe_keys:
        snapshot = indexed.get((source, collection))
        if snapshot is None:
            snapshot = TakeoffOutputRowUniverseSnapshotV1(
                source=source,
                collection=collection,
                source_document_id=manifest.source_document_id,
                revision_id=manifest.revision_id,
                source_sha256=manifest.source_sha256,
                registry_run_id=manifest.registry_run_id,
                snapshot_id=manifest.snapshot_id,
                quantity_ids=(),
                enumeration_status=ENUMERATION_NOT_ENUMERATED,
                reason_codes=("expected_takeoff_row_universe_snapshot_missing",),
            )
        resolved.append(snapshot)
    return tuple(resolved)


def _normalize_universe_data(
    supplied: Optional[Mapping[tuple[str, str], Sequence[Any]]],
    expected_keys: Sequence[tuple[str, str]],
    label: str,
) -> dict[tuple[str, str], tuple[Any, ...]]:
    if supplied is None:
        return {}
    expected = set(expected_keys)
    out: dict[tuple[str, str], tuple[Any, ...]] = {}
    for raw_key, records in supplied.items():
        if len(raw_key) != 2:
            raise CoverageRegistryContractError("unexpected_universe_key", f"{label} key {raw_key!r}")
        key = (_required(raw_key[0], f"{label}.key.left"), _required(raw_key[1], f"{label}.key.right"))
        if key not in expected:
            raise CoverageRegistryContractError("unexpected_universe_key", f"{label} {key!r}")
        if key in out:
            raise CoverageRegistryContractError("duplicate_universe_payload", f"{label} {key!r}")
        out[key] = tuple(records)
    return out


def _records_for_snapshot(
    snapshot: Any,
    records: Sequence[Any],
    record_type: type,
    id_field: str,
    label: str,
) -> tuple[tuple[Any, ...], tuple[str, ...], tuple[str, ...]]:
    if snapshot.enumeration_status == ENUMERATION_NOT_ENUMERATED:
        reasons = ("records_present_without_enumeration_snapshot",) if records else ()
        return (), (), reasons
    if snapshot.enumeration_status == ENUMERATION_UNAVAILABLE:
        if records:
            raise CoverageRegistryContractError(
                "unavailable_universe_has_records",
                f"{label} {records!r}",
            )
        return (), (), ()
    declared = set(snapshot.quantity_ids)
    actual: list[Any] = []
    actual_ids: list[str] = []
    for record in tuple(records):
        if not isinstance(record, record_type):
            raise TypeError(f"{label} records must be {record_type.__name__}")
        quantity_id = _required(_field(record, id_field), id_field)
        if quantity_id not in declared:
            raise CoverageRegistryContractError(
                "record_not_in_enumeration_snapshot",
                f"{label} quantity_id={quantity_id}",
            )
        actual.append(record)
        actual_ids.append(quantity_id)
    missing = tuple(sorted(declared - set(actual_ids)))
    return tuple(actual), missing, ()


def _qe_lineage_conflicts(
    quantity: QuantityEvidence,
    manifest: CoverageRegistryRunManifestV1,
) -> tuple[str, ...]:
    metadata = quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
    expected = {
        "document_id": manifest.source_document_id,
        "source_document_id": manifest.source_document_id,
        "revision_id": manifest.revision_id,
        "source_sha256": manifest.source_sha256,
        "registry_run_id": manifest.registry_run_id,
        "snapshot_id": manifest.snapshot_id,
    }
    reasons: list[str] = []
    for key, authoritative in expected.items():
        if key not in metadata or metadata.get(key) is None:
            continue
        if str(metadata.get(key)).strip() != authoritative:
            reasons.append(f"quantity_{key}_lineage_conflict")
    return tuple(sorted(set(reasons)))


def _index_editable_objects(
    editable_objects: Sequence[EditableGeometryObject],
) -> dict[str, EditableGeometryObject]:
    indexed: dict[str, EditableGeometryObject] = {}
    for obj in tuple(editable_objects):
        if not isinstance(obj, EditableGeometryObject):
            raise TypeError("editable_objects must contain EditableGeometryObject")
        object_id = _required(obj.object_id, "EditableGeometryObject.object_id")
        if object_id in indexed:
            raise CoverageRegistryContractError("duplicate_editable_object_id", object_id)
        indexed[object_id] = obj
    return indexed


def _object_metadata(
    raw: Any,
    snapshot: ProducerObjectUniverseSnapshotV1,
) -> dict[str, Any]:
    metadata = dict(_to_mapping(raw))
    if bool(metadata.get("no_instance_creation", False)):
        raise CoverageRegistryContractError(
            "evidence_only_object_cannot_be_admitted",
            f"{snapshot.producer}/{snapshot.category}",
        )
    for key, expected in (
        ("source_document_id", snapshot.source_document_id),
        ("revision_id", snapshot.revision_id),
        ("source_sha256", snapshot.source_sha256),
        ("registry_run_id", snapshot.registry_run_id),
        ("snapshot_id", snapshot.snapshot_id),
    ):
        value = metadata.get(key)
        if value is not None and str(value).strip() != expected:
            raise CoverageRegistryContractError(
                "admitted_object_metadata_lineage_conflict",
                f"{key}={value!r}",
            )
    return metadata


def _editable_join(
    metadata: Mapping[str, Any],
    editable: Optional[EditableGeometryObject],
) -> tuple[bool, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    if editable is None:
        return True, (), (), ()
    reasons: list[str] = []
    expected_source_file_id = _optional_string(metadata.get("source_file_id"))
    if expected_source_file_id and editable.source_file_id and editable.source_file_id != expected_source_file_id:
        reasons.append("editable_source_lineage_conflict")
    expected_revision_hash = _optional_string(metadata.get("revision_hash"))
    if expected_revision_hash and editable.revision_hash and editable.revision_hash != expected_revision_hash:
        reasons.append("editable_revision_lineage_conflict")
    expected_original_geometry = _optional_string(metadata.get("original_geometry_ref"))
    if (
        expected_original_geometry
        and editable.original_geometry_ref
        and editable.original_geometry_ref != expected_original_geometry
    ):
        reasons.append("editable_geometry_lineage_conflict")
    if reasons:
        return False, (), (), tuple(sorted(set(reasons)))
    geometry_ids = tuple(
        sorted(
            {
                value
                for value in (
                    _optional_string(editable.original_geometry_ref),
                    _optional_string(editable.geometry_ref),
                )
                if value
            }
        )
    )
    dependent_ids = _string_tuple(editable.dependent_quantity_ids, "dependent_quantity_ids")
    return True, geometry_ids, dependent_ids, ()


def _row_lineage_reasons(
    row: TakeoffOutputRow,
    linked_object_ids: Sequence[str],
    object_geometry_ids: Mapping[str, tuple[str, ...]],
    editable_by_id: Mapping[str, EditableGeometryObject],
) -> tuple[str, ...]:
    reasons: list[str] = []
    allowed_geometry_refs: set[str] = set(linked_object_ids)
    for object_id in linked_object_ids:
        allowed_geometry_refs.update(object_geometry_ids.get(object_id, ()))
    if linked_object_ids and row.geometry_ref is not None:
        geometry_ref = str(row.geometry_ref).strip()
        if geometry_ref and geometry_ref not in allowed_geometry_refs:
            reasons.append("takeoff_row_geometry_lineage_conflict")
    for object_id in linked_object_ids:
        editable = editable_by_id.get(object_id)
        if editable is None or not editable.revision_hash or not row.revision_hash:
            continue
        if editable.revision_hash != row.revision_hash:
            reasons.append("takeoff_row_revision_stale")
    if any(_STALE_ROW_REASON in str(reason) or "stale" in str(reason).lower() for reason in row.blocking_reasons):
        reasons.append("takeoff_row_revision_stale")
    return tuple(sorted(set(reasons)))


def _coverage_state(
    explicit_quantity_ids: Sequence[str],
    abstained_quantity_ids: set[str],
    defective_quantity_ids: set[str],
) -> str:
    # Frozen precedence from approved architecture:
    # 1) no explicit relation -> UNACCOUNTED
    # 2) abstention-only -> ABSTAINED
    # 3) any non-abstained explicit relationship with downstream defect, or a
    #    mix of resolved/non-abstained and abstained dependencies -> PARTIAL
    # 4) one-or-more explicit dependencies, all clean -> ACCOUNTED
    explicit = tuple(explicit_quantity_ids)
    if not explicit:
        return COVERAGE_UNACCOUNTED
    if set(explicit) == abstained_quantity_ids:
        return COVERAGE_ABSTAINED
    if defective_quantity_ids:
        return COVERAGE_PARTIAL
    return COVERAGE_ACCOUNTED


def build_coverage_registry_v1(
    *,
    manifest: CoverageRegistryRunManifestV1,
    object_universe_snapshots: Sequence[ProducerObjectUniverseSnapshotV1] = (),
    quantity_evidence_universe_snapshots: Sequence[QuantityEvidenceUniverseSnapshotV1] = (),
    takeoff_output_row_universe_snapshots: Sequence[TakeoffOutputRowUniverseSnapshotV1] = (),
    quantity_evidence_by_universe: Optional[
        Mapping[tuple[str, str], Sequence[QuantityEvidence]]
    ] = None,
    takeoff_rows_by_universe: Optional[
        Mapping[tuple[str, str], Sequence[TakeoffOutputRow]]
    ] = None,
    editable_objects: Sequence[EditableGeometryObject] = (),
    object_metadata_by_id: Optional[Mapping[str, Any]] = None,
) -> CoverageRegistrySummaryV1:
    """Build one fail-closed, read-only coverage registry run.

    The manifest and producer snapshots establish *which* physical object IDs are
    admitted. object_metadata_by_id may enrich those already-admitted IDs but can
    never add an object to the universe.
    """
    if not isinstance(manifest, CoverageRegistryRunManifestV1):
        raise TypeError("manifest must be CoverageRegistryRunManifestV1")

    object_snapshots = _resolve_object_snapshots(manifest, object_universe_snapshots)
    qe_snapshots = _resolve_quantity_evidence_snapshots(
        manifest, quantity_evidence_universe_snapshots
    )
    row_snapshots = _resolve_takeoff_row_snapshots(
        manifest, takeoff_output_row_universe_snapshots
    )

    qe_payloads = _normalize_universe_data(
        quantity_evidence_by_universe,
        manifest.expected_quantity_evidence_universe_keys,
        "QuantityEvidence universe",
    )
    row_payloads = _normalize_universe_data(
        takeoff_rows_by_universe,
        manifest.expected_takeoff_row_universe_keys,
        "TakeoffOutputRow universe",
    )
    editable_by_id = _index_editable_objects(editable_objects)
    supplied_metadata = dict(object_metadata_by_id or {})

    admitted_by_id: dict[str, ProducerObjectUniverseSnapshotV1] = {}
    metadata_by_id: dict[str, dict[str, Any]] = {}
    geometry_by_id: dict[str, tuple[str, ...]] = {}
    editable_dependency_ids: dict[str, tuple[str, ...]] = {}
    object_join_reasons: dict[str, tuple[str, ...]] = {}

    for snapshot in object_snapshots:
        for object_id in snapshot.admitted_object_ids:
            if object_id in admitted_by_id:
                raise CoverageRegistryContractError(
                    "duplicate_admitted_object_id",
                    object_id,
                )
            admitted_by_id[object_id] = snapshot
            metadata = _object_metadata(supplied_metadata.get(object_id), snapshot)
            metadata_by_id[object_id] = metadata
            explicit_geometry = set(
                _metadata_strings(
                    metadata,
                    "geometry_ids",
                    "geometry_ref",
                    "original_geometry_ref",
                    "source_primitive_ids",
                )
            )
            valid_editable, editable_geometry, dependent_ids, join_reasons = _editable_join(
                metadata,
                editable_by_id.get(object_id),
            )
            if valid_editable:
                explicit_geometry.update(editable_geometry)
                editable_dependency_ids[object_id] = dependent_ids
            else:
                editable_dependency_ids[object_id] = ()
            geometry_by_id[object_id] = tuple(sorted(explicit_geometry))
            object_join_reasons[object_id] = join_reasons

    qe_records_by_id: dict[str, list[QuantityEvidence]] = {}
    row_records_by_id: dict[str, list[TakeoffOutputRow]] = {}
    qe_declared_keys: dict[str, list[tuple[str, str]]] = {}
    row_declared_keys: dict[str, list[tuple[str, str]]] = {}
    missing_qe_record_ids: set[str] = set()
    missing_row_record_ids: set[str] = set()
    summary_reasons: set[str] = set()

    for snapshot in qe_snapshots:
        key = (snapshot.producer, snapshot.source)
        records, missing, extra_reasons = _records_for_snapshot(
            snapshot,
            qe_payloads.get(key, ()),
            QuantityEvidence,
            "quantity_id",
            "QuantityEvidence",
        )
        summary_reasons.update(extra_reasons)
        missing_qe_record_ids.update(missing)
        for quantity_id in snapshot.quantity_ids:
            qe_declared_keys.setdefault(quantity_id, []).append(key)
        for record in records:
            qe_records_by_id.setdefault(record.quantity_id, []).append(record)

    for snapshot in row_snapshots:
        key = (snapshot.source, snapshot.collection)
        records, missing, extra_reasons = _records_for_snapshot(
            snapshot,
            row_payloads.get(key, ()),
            TakeoffOutputRow,
            "quantity_id",
            "TakeoffOutputRow",
        )
        summary_reasons.update(extra_reasons)
        missing_row_record_ids.update(missing)
        for quantity_id in snapshot.quantity_ids:
            row_declared_keys.setdefault(quantity_id, []).append(key)
        for record in records:
            row_records_by_id.setdefault(record.quantity_id, []).append(record)

    duplicate_qe_ids = {
        quantity_id
        for quantity_id, records in qe_records_by_id.items()
        if len(records) != 1 or len(qe_declared_keys.get(quantity_id, ())) != 1
    }
    duplicate_row_ids = {
        quantity_id
        for quantity_id, records in row_records_by_id.items()
        if len(records) != 1 or len(row_declared_keys.get(quantity_id, ())) != 1
    }
    duplicate_qe_ids.update(
        quantity_id for quantity_id, keys in qe_declared_keys.items() if len(keys) != 1
    )
    duplicate_row_ids.update(
        quantity_id for quantity_id, keys in row_declared_keys.items() if len(keys) != 1
    )

    qe_lineage_reasons: dict[str, tuple[str, ...]] = {}
    qe_links_by_object: dict[str, set[str]] = {
        object_id: set() for object_id in admitted_by_id
    }
    qe_unadmitted_targets: dict[str, set[str]] = {}
    for quantity_id, records in qe_records_by_id.items():
        reasons: set[str] = set()
        for quantity in records:
            reasons.update(_qe_lineage_conflicts(quantity, manifest))
            for object_id in quantity.input_entity_ids:
                if object_id in admitted_by_id:
                    qe_links_by_object[object_id].add(quantity_id)
                else:
                    qe_unadmitted_targets.setdefault(quantity_id, set()).add(object_id)
        qe_lineage_reasons[quantity_id] = tuple(sorted(reasons))

    editable_links_by_quantity: dict[str, set[str]] = {}
    for object_id, quantity_ids in editable_dependency_ids.items():
        for quantity_id in quantity_ids:
            editable_links_by_quantity.setdefault(quantity_id, set()).add(object_id)

    exact_links_by_quantity: dict[str, set[str]] = {}
    for object_id, quantity_ids in qe_links_by_object.items():
        for quantity_id in quantity_ids:
            exact_links_by_quantity.setdefault(quantity_id, set()).add(object_id)
    for quantity_id, object_ids in editable_links_by_quantity.items():
        exact_links_by_quantity.setdefault(quantity_id, set()).update(object_ids)

    row_lineage_reasons: dict[str, tuple[str, ...]] = {}
    for quantity_id, rows in row_records_by_id.items():
        linked_object_ids = tuple(sorted(exact_links_by_quantity.get(quantity_id, ())))
        reasons: set[str] = set()
        for row in rows:
            reasons.update(
                _row_lineage_reasons(
                    row,
                    linked_object_ids,
                    geometry_by_id,
                    editable_by_id,
                )
            )
        row_lineage_reasons[quantity_id] = tuple(sorted(reasons))

    object_records: list[CoverageObjectRecordV1] = []
    for object_id in sorted(admitted_by_id):
        snapshot = admitted_by_id[object_id]
        metadata = metadata_by_id[object_id]
        explicit_quantity_ids = tuple(
            sorted(
                set(qe_links_by_object.get(object_id, ()))
                | set(editable_dependency_ids.get(object_id, ()))
            )
        )
        record_reasons: set[str] = set(object_join_reasons.get(object_id, ()))
        abstained_quantity_ids: set[str] = set()
        defective_quantity_ids: set[str] = set()
        row_ids: set[str] = set()
        contributions: dict[str, Optional[float]] = {}
        units: dict[str, str] = {}

        if not explicit_quantity_ids:
            record_reasons.add("no_explicit_object_quantity_relationship")

        for quantity_id in explicit_quantity_ids:
            dependency_reasons: set[str] = set()
            quantities = qe_records_by_id.get(quantity_id, [])
            rows = row_records_by_id.get(quantity_id, [])

            if quantity_id in duplicate_qe_ids:
                dependency_reasons.add("duplicate_or_conflicting_quantity_evidence_id")
            if quantity_id in duplicate_row_ids:
                dependency_reasons.add("duplicate_or_conflicting_takeoff_row_quantity_id")
            if quantity_id in missing_qe_record_ids:
                dependency_reasons.add("quantity_evidence_record_missing")
            dependency_reasons.update(qe_lineage_reasons.get(quantity_id, ()))
            dependency_reasons.update(row_lineage_reasons.get(quantity_id, ()))
            if qe_unadmitted_targets.get(quantity_id):
                dependency_reasons.add("quantity_input_entity_not_admitted")

            quantity = quantities[0] if len(quantities) == 1 else None
            row = rows[0] if len(rows) == 1 else None
            if quantity is not None and quantity.input_entity_ids:
                if (
                    object_id not in quantity.input_entity_ids
                    and quantity_id in editable_dependency_ids.get(object_id, ())
                ):
                    dependency_reasons.add("quantity_evidence_object_link_conflict")

            if quantity is not None and quantity.abstained:
                abstained_quantity_ids.add(quantity_id)
                dependency_reasons.add("quantity_abstained")

            if row is not None:
                row_ids.add(quantity_id)
            elif quantity is None or not quantity.abstained:
                dependency_reasons.add("takeoff_row_missing")
            if quantity_id in missing_row_record_ids and not (
                quantity is not None and quantity.abstained
            ):
                dependency_reasons.add("takeoff_row_record_missing")

            if dependency_reasons:
                defective_quantity_ids.add(quantity_id)
                record_reasons.update(
                    f"{reason}:{quantity_id}" for reason in dependency_reasons
                )

            if quantity is not None:
                units[quantity_id] = quantity.unit
                if quantity.abstained:
                    contributions[quantity_id] = None
                elif not quantity.input_entity_ids or quantity.input_entity_ids == (object_id,):
                    contributions[quantity_id] = quantity.value
                else:
                    contributions[quantity_id] = None
            elif row is not None:
                units[quantity_id] = row.unit
                contributions[quantity_id] = row.value

        coverage_state = _coverage_state(
            explicit_quantity_ids,
            abstained_quantity_ids,
            defective_quantity_ids,
        )

        source_pages = set(_source_pages(metadata))
        editable = editable_by_id.get(object_id)
        if editable is not None and editable.source_page is not None:
            try:
                source_pages.add(int(editable.source_page))
            except (TypeError, ValueError, OverflowError):
                pass
        evidence_ids = set(
            _metadata_strings(
                metadata,
                "evidence_ids",
                "source_evidence_ids",
                "supporting_evidence_ids",
            )
        )
        parent_host_ids = set(
            _metadata_strings(
                metadata,
                "parent_host_ids",
                "parent_id",
                "host_id",
                "host_wall_id",
                "bound_wall_id",
            )
        )
        provenance = dict(metadata.get("provenance") or {})
        provenance.update(
            {
                "producer_snapshot_id": snapshot.snapshot_id,
                "registry_run_id": snapshot.registry_run_id,
                "enumeration_status": snapshot.enumeration_status,
            }
        )
        object_type = _optional_string(metadata.get("object_type")) or snapshot.category

        object_records.append(
            CoverageObjectRecordV1(
                object_id=object_id,
                object_type=object_type,
                producer=snapshot.producer,
                owning_authority=snapshot.owning_authority,
                source_document_id=snapshot.source_document_id,
                revision_id=snapshot.revision_id,
                source_sha256=snapshot.source_sha256,
                source_pages=tuple(sorted(source_pages)),
                evidence_ids=tuple(sorted(evidence_ids)),
                geometry_ids=geometry_by_id.get(object_id, ()),
                parent_host_ids=tuple(sorted(parent_host_ids)),
                quantity_ids=explicit_quantity_ids,
                takeoff_row_ids=tuple(sorted(row_ids)),
                coverage_state=coverage_state,
                reason_codes=tuple(sorted(record_reasons)),
                quantity_contribution=contributions,
                unit=units,
                provenance=provenance,
            )
        )

    all_quantity_ids: set[str] = set(qe_declared_keys) | set(row_declared_keys)
    all_quantity_ids.update(qe_records_by_id)
    all_quantity_ids.update(row_records_by_id)
    all_quantity_ids.update(editable_links_by_quantity)

    census: dict[str, list[str]] = {state: [] for state in QUANTITY_CENSUS_STATES}
    for quantity_id in sorted(all_quantity_ids):
        conflicting = (
            quantity_id in duplicate_qe_ids
            or quantity_id in duplicate_row_ids
            or bool(qe_lineage_reasons.get(quantity_id))
            or bool(row_lineage_reasons.get(quantity_id))
        )
        if conflicting:
            census[CENSUS_CONFLICTING_LINEAGE].append(quantity_id)
            continue

        linked_object_ids = set(exact_links_by_quantity.get(quantity_id, ()))
        unadmitted_targets = qe_unadmitted_targets.get(quantity_id, set())
        quantities = qe_records_by_id.get(quantity_id, [])
        rows = row_records_by_id.get(quantity_id, [])
        quantity = quantities[0] if len(quantities) == 1 else None

        if unadmitted_targets:
            census[CENSUS_DANGLING].append(quantity_id)
            continue
        if not linked_object_ids:
            if quantity_id in missing_qe_record_ids or quantity_id in missing_row_record_ids:
                census[CENSUS_DANGLING].append(quantity_id)
            else:
                census[CENSUS_ORPHAN_UNBOUND].append(quantity_id)
            continue

        if quantity_id in missing_qe_record_ids:
            census[CENSUS_DANGLING].append(quantity_id)
            continue
        if quantity_id in missing_row_record_ids:
            if quantity is None or not quantity.abstained:
                census[CENSUS_DANGLING].append(quantity_id)
                continue
        if not rows and (quantity is None or not quantity.abstained):
            census[CENSUS_DANGLING].append(quantity_id)
            continue

        census[CENSUS_LINKED].append(quantity_id)

    object_ids_by_state = {
        state: tuple(
            record.object_id for record in object_records if record.coverage_state == state
        )
        for state in COVERAGE_STATES
    }
    quantity_ids_by_state = {
        state: tuple(census[state]) for state in QUANTITY_CENSUS_STATES
    }

    object_complete = all(
        snapshot.enumeration_status == ENUMERATION_COMPLETE for snapshot in object_snapshots
    )
    qe_complete = all(
        snapshot.enumeration_status == ENUMERATION_COMPLETE for snapshot in qe_snapshots
    )
    row_complete = all(
        snapshot.enumeration_status == ENUMERATION_COMPLETE for snapshot in row_snapshots
    )
    if not object_complete:
        summary_reasons.add("object_universe_not_complete")
    if not qe_complete:
        summary_reasons.add("quantity_evidence_universe_not_complete")
    if not row_complete:
        summary_reasons.add("takeoff_output_row_universe_not_complete")
    if not (qe_complete and row_complete):
        summary_reasons.add("quantity_census_not_conclusive")

    return CoverageRegistrySummaryV1(
        manifest=manifest,
        object_universe_snapshots=object_snapshots,
        quantity_evidence_universe_snapshots=qe_snapshots,
        takeoff_output_row_universe_snapshots=row_snapshots,
        object_records=tuple(object_records),
        object_counts_by_coverage_state={
            state: len(object_ids_by_state[state]) for state in COVERAGE_STATES
        },
        object_ids_by_coverage_state=object_ids_by_state,
        quantity_counts_by_census_state={
            state: len(quantity_ids_by_state[state]) for state in QUANTITY_CENSUS_STATES
        },
        quantity_ids_by_census_state=quantity_ids_by_state,
        object_universe_complete=object_complete,
        quantity_evidence_universe_complete=qe_complete,
        takeoff_output_row_universe_complete=row_complete,
        quantity_census_conclusive=qe_complete and row_complete,
        reason_codes=tuple(sorted(summary_reasons)),
    )


__all__ = [
    "COVERAGE_ACCOUNTED",
    "COVERAGE_PARTIAL",
    "COVERAGE_UNACCOUNTED",
    "COVERAGE_ABSTAINED",
    "CENSUS_LINKED",
    "CENSUS_DANGLING",
    "CENSUS_ORPHAN_UNBOUND",
    "CENSUS_CONFLICTING_LINEAGE",
    "ENUMERATION_COMPLETE",
    "ENUMERATION_INCOMPLETE",
    "ENUMERATION_UNAVAILABLE",
    "ENUMERATION_NOT_ENUMERATED",
    "COVERAGE_BASIS_EXPLICIT_DEPENDENCIES_ONLY",
    "EXPECTED_FAMILY_COMPLETENESS_UNKNOWN",
    "CoverageRegistryContractError",
    "CoverageRegistryRunManifestV1",
    "ProducerObjectUniverseSnapshotV1",
    "QuantityEvidenceUniverseSnapshotV1",
    "TakeoffOutputRowUniverseSnapshotV1",
    "CoverageObjectRecordV1",
    "CoverageRegistrySummaryV1",
    "build_coverage_registry_v1",
]