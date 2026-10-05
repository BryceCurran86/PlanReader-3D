"""Reconcile sealed production identities into Full Plan V2 evaluator rows.

This module is deliberately benchmark-side. Production exports canonical/source
identities only; a frozen V2 identity binding maps those exact identities to a
verified benchmark item after production execution is sealed.

Labels, descriptions, room names, numeric similarity and expected quantities are
never matching inputs.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

if __package__:
    from .evaluator import (
        ProducedTakeoffItemV2,
        ProjectBenchmarkManifestV2,
        VerifiedTakeoffItemV2,
    )
else:
    _evaluator_path = Path(__file__).with_name("evaluator.py")
    _evaluator_spec = importlib.util.spec_from_file_location(
        "full_plan_takeoff_v2_evaluator",
        _evaluator_path,
    )
    assert _evaluator_spec is not None and _evaluator_spec.loader is not None
    _evaluator_module = sys.modules.get(_evaluator_spec.name)
    if _evaluator_module is None:
        _evaluator_module = importlib.util.module_from_spec(_evaluator_spec)
        sys.modules[_evaluator_spec.name] = _evaluator_module
        _evaluator_spec.loader.exec_module(_evaluator_module)
    ProducedTakeoffItemV2 = _evaluator_module.ProducedTakeoffItemV2
    ProjectBenchmarkManifestV2 = _evaluator_module.ProjectBenchmarkManifestV2
    VerifiedTakeoffItemV2 = _evaluator_module.VerifiedTakeoffItemV2


SEALED_SOURCE_RUN_SCHEMA_VERSION = "1.0.0"
V2_IDENTITY_MAP_SCHEMA_VERSION = "1.0.0"


def _required(value: object, name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{name} must be non-empty")
    return clean


def _tuple(values: Sequence[object], name: str) -> tuple[str, ...]:
    clean = tuple(sorted({_required(value, name) for value in values}))
    return clean


def _unit_dimension(value: object) -> str | None:
    unit = _required(value, "unit").strip().lower()
    if unit in {"m2", "m²", "sqm"}:
        return "area"
    if unit in {"ea", "each", "nr", "no", "no.", "number"}:
        return "count"
    return None


def _reconciled_unit(production_unit: object, benchmark_unit: object) -> str:
    """Return benchmark notation only for exact physical unit equivalence.

    This performs no numeric conversion. It exists solely because production
    and the independently frozen reference may use different notation for the
    same physical dimension, for example ea versus nr.
    """
    production = _required(production_unit, "production unit").strip().lower()
    benchmark = _required(benchmark_unit, "benchmark unit").strip().lower()
    if production == benchmark:
        return benchmark

    production_dimension = _unit_dimension(production)
    benchmark_dimension = _unit_dimension(benchmark)
    if (
        production_dimension is not None
        and production_dimension == benchmark_dimension
    ):
        return benchmark
    raise ValueError(
        f"bound production unit {production!r} is not equivalent to "
        f"benchmark unit {benchmark!r}"
    )

def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _verify_fingerprint(payload: Mapping[str, Any], name: str) -> None:
    claimed = _required(payload.get("fingerprint"), f"{name}.fingerprint")
    clean = dict(payload)
    clean.pop("fingerprint", None)
    actual = hashlib.sha256(_canonical_json(clean).encode("utf-8")).hexdigest()
    if claimed != actual:
        raise ValueError(f"{name} fingerprint mismatch")


@dataclass(frozen=True)
class V2ProductionIdentityBinding:
    benchmark_item_id: str
    production_object_identity_refs: tuple[str, ...]
    production_family: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "benchmark_item_id",
            _required(self.benchmark_item_id, "benchmark_item_id"),
        )
        refs = _tuple(
            self.production_object_identity_refs,
            "production_object_identity_refs",
        )
        if not refs:
            raise ValueError("production_object_identity_refs must be non-empty")
        object.__setattr__(self, "production_object_identity_refs", refs)
        if self.production_family is not None:
            object.__setattr__(
                self,
                "production_family",
                _required(self.production_family, "production_family"),
            )


@dataclass(frozen=True)
class V2ProductionIdentityMap:
    project_id: str
    source_sha256s: tuple[str, ...]
    bindings: tuple[V2ProductionIdentityBinding, ...]
    schema_version: str = V2_IDENTITY_MAP_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "project_id", _required(self.project_id, "project_id"))
        hashes = _tuple(self.source_sha256s, "source_sha256s")
        if not hashes:
            raise ValueError("source_sha256s must be non-empty")
        object.__setattr__(self, "source_sha256s", hashes)
        item_ids = [binding.benchmark_item_id for binding in self.bindings]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("benchmark_item_id bindings must be unique")
        keys = [
            (
                binding.production_family,
                binding.production_object_identity_refs,
            )
            for binding in self.bindings
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("production identity bindings must be unique")


def identity_map_from_dict(raw: Mapping[str, Any]) -> V2ProductionIdentityMap:
    if str(raw.get("schema_version")) != V2_IDENTITY_MAP_SCHEMA_VERSION:
        raise ValueError("unsupported V2 identity-map schema_version")
    bindings = tuple(
        V2ProductionIdentityBinding(
            benchmark_item_id=value["benchmark_item_id"],
            production_object_identity_refs=tuple(
                value.get("production_object_identity_refs") or ()
            ),
            production_family=value.get("production_family"),
        )
        for value in raw.get("bindings", ())
    )
    return V2ProductionIdentityMap(
        project_id=raw["project_id"],
        source_sha256s=tuple(raw.get("source_sha256s") or ()),
        bindings=bindings,
    )


def _verified_items_by_id(
    manifest: ProjectBenchmarkManifestV2,
) -> dict[str, VerifiedTakeoffItemV2]:
    return {
        item.item_id: item
        for item in manifest.verified_items
        if item.denominator_eligible
    }


def _validate_identity_map(
    manifest: ProjectBenchmarkManifestV2,
    identity_map: V2ProductionIdentityMap,
) -> dict[str, VerifiedTakeoffItemV2]:
    if identity_map.project_id != manifest.project_id:
        raise ValueError("identity-map project_id does not match manifest")
    expected_hashes = {doc.sha256 for doc in manifest.source_documents}
    supplied_hashes = set(identity_map.source_sha256s)
    if not supplied_hashes.issubset(expected_hashes):
        raise ValueError("identity-map source hashes are not from the V2 source package")
    items = _verified_items_by_id(manifest)
    for binding in identity_map.bindings:
        if binding.benchmark_item_id not in items:
            raise ValueError(
                f"identity binding references unknown denominator item "
                f"{binding.benchmark_item_id}"
            )
    return items


def _validate_sealed_run(
    manifest: ProjectBenchmarkManifestV2,
    sealed_run: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    if str(sealed_run.get("schema_version")) != SEALED_SOURCE_RUN_SCHEMA_VERSION:
        raise ValueError("unsupported sealed source-run schema_version")
    if (
        _required(sealed_run.get("project_id"), "sealed_run.project_id")
        != manifest.project_id
    ):
        raise ValueError("sealed-run project_id does not match manifest")
    _verify_fingerprint(sealed_run, "sealed_run")
    expected_hashes = {doc.sha256 for doc in manifest.source_documents}
    run_hashes = {
        _required(value, "sealed_run.source_sha256s")
        for value in sealed_run.get("source_sha256s", ())
    }
    if not run_hashes or not run_hashes.issubset(expected_hashes):
        raise ValueError("sealed-run source hashes are not from the V2 source package")

    quantities = tuple(sealed_run.get("quantities") or ())
    quantity_ids: list[str] = []
    for index, row in enumerate(quantities):
        if not isinstance(row, Mapping):
            raise TypeError("sealed-run quantities must contain objects")
        _verify_fingerprint(row, f"sealed_run.quantities[{index}]")
        quantity_ids.append(_required(row.get("quantity_id"), "quantity_id"))
    if len(quantity_ids) != len(set(quantity_ids)):
        raise ValueError("sealed-run quantity ids must be unique")
    return quantities


def _binding_matches(
    binding: V2ProductionIdentityBinding,
    row: Mapping[str, Any],
) -> bool:
    refs = _tuple(
        tuple(row.get("object_identity_refs") or ()),
        "object_identity_refs",
    )
    if refs != binding.production_object_identity_refs:
        return False
    if (
        binding.production_family is not None
        and _required(row.get("family"), "family") != binding.production_family
    ):
        return False
    return True


def reconcile_sealed_run_v2(
    manifest: ProjectBenchmarkManifestV2,
    sealed_run: Mapping[str, Any],
    identity_map: V2ProductionIdentityMap,
) -> tuple[ProducedTakeoffItemV2, ...]:
    """Convert sealed production output into exact-identity V2 evaluator rows."""
    items = _validate_identity_map(manifest, identity_map)
    rows = _validate_sealed_run(manifest, sealed_run)
    produced: list[ProducedTakeoffItemV2] = []
    matched_quantity_by_item_id: dict[str, str] = {}

    for row in rows:
        matches = tuple(
            binding
            for binding in identity_map.bindings
            if _binding_matches(binding, row)
        )
        if len(matches) > 1:
            raise ValueError(
                f"production quantity {row['quantity_id']} matches multiple V2 bindings"
            )

        abstained = bool(row.get("abstained", False))
        lineage_ok = bool(row.get("lineage_ok", False))
        value = None if row.get("value") is None else float(row["value"])
        production_unit = _required(row.get("unit"), "unit")

        if len(matches) == 1:
            binding = matches[0]
            prior_quantity_id = matched_quantity_by_item_id.get(
                binding.benchmark_item_id
            )
            if prior_quantity_id is not None:
                raise ValueError(
                    "multiple sealed quantities map to one V2 binding "
                    f"{binding.benchmark_item_id}: "
                    f"{prior_quantity_id} and {row['quantity_id']}"
                )
            matched_quantity_by_item_id[binding.benchmark_item_id] = _required(
                row.get("quantity_id"),
                "quantity_id",
            )
            item = items[binding.benchmark_item_id]
            reconciled_unit = _reconciled_unit(
                production_unit,
                item.unit,
            )
            produced.append(
                ProducedTakeoffItemV2(
                    quantity_id=_required(row.get("quantity_id"), "quantity_id"),
                    trade_category=item.trade_category,
                    value=value,
                    unit=reconciled_unit,
                    object_refs=item.expected_object_refs,
                    lineage_ok=lineage_ok,
                    abstained=abstained,
                )
            )
            continue

        raw_refs = tuple(row.get("object_identity_refs") or ())
        unmapped_refs = tuple(
            f"production-unmapped:{identity_ref}"
            for identity_ref in raw_refs
            if str(identity_ref).strip()
        ) or (f"production-unmapped:{row['quantity_id']}",)
        produced.append(
            ProducedTakeoffItemV2(
                quantity_id=_required(row.get("quantity_id"), "quantity_id"),
                trade_category=(
                    f"production-unmapped:{_required(row.get('family'), 'family')}"
                ),
                value=value,
                unit=production_unit,
                object_refs=unmapped_refs,
                lineage_ok=lineage_ok,
                abstained=abstained,
            )
        )

    return tuple(produced)


__all__ = [
    "SEALED_SOURCE_RUN_SCHEMA_VERSION",
    "V2_IDENTITY_MAP_SCHEMA_VERSION",
    "V2ProductionIdentityBinding",
    "V2ProductionIdentityMap",
    "identity_map_from_dict",
    "reconcile_sealed_run_v2",
]
