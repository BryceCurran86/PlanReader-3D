"""Context-bound metric wall-dimension binding authority.

This module bridges trusted wall-length and wall-height QuantityEvidence into one
immutable, deterministic wall-dimension proposition.  It deliberately does not
construct source-space geometry and never reconstructs dimensions from scalar
area.  Downstream gross/net wall geometry code must still prove its own geometric
frame before using these metric dimensions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Mapping

from pb_geometry_takeoff_model import AuthorityStatus
from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence, stable_contract_id
from pb_migration_provider_envelope import ProviderContext
from pb_wall_gross_area_quantity import (
    build_gross_wall_area_quantity,
    quantity_evidence_fingerprint,
)


WALL_METRIC_DIMENSION_BINDING_SCHEMA_VERSION = "1.0.0"
WALL_METRIC_DIMENSION_BINDING_RESOLVED = "wall_metric_dimension_binding_resolved"
WALL_METRIC_DIMENSION_BINDING_CONTEXT_MISMATCH = "wall_metric_dimension_binding_context_mismatch"
WALL_METRIC_DIMENSION_BINDING_UPSTREAM_BLOCKED = "wall_metric_dimension_binding_upstream_blocked"
WALL_METRIC_DIMENSION_BINDING_RECORD_UNAVAILABLE = "wall_metric_dimension_binding_record_unavailable"

_RECORD_SEAL = object()


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


def _metadata(quantity: QuantityEvidence) -> Mapping[str, object]:
    return quantity.metadata if isinstance(quantity.metadata, Mapping) else {}


@dataclass(frozen=True)
class WallMetricDimensionBindingSelector:
    """Exact wall/context requested by a downstream geometry producer."""

    document_id: str
    source_sha256: str
    revision_id: str
    evidence_snapshot_id: str
    viewport_id: str
    page_no: int
    physical_wall_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "source_sha256",
            "revision_id",
            "evidence_snapshot_id",
            "viewport_id",
            "physical_wall_id",
        ):
            _required(getattr(self, name), name)
        if isinstance(self.page_no, bool) or int(self.page_no) <= 0:
            raise ValueError("page_no must be a positive integer")
        object.__setattr__(self, "page_no", int(self.page_no))


@dataclass(frozen=True)
class WallMetricDimensionBindingRecord:
    """Producer-created metric proposition for one exact physical wall."""

    record_id: str
    document_id: str
    source_sha256: str
    revision_id: str
    evidence_snapshot_id: str
    canonical_graph_snapshot_id: str | None
    viewport_id: str
    page_no: int
    physical_wall_id: str
    length_m: float
    height_m: float
    gross_area_m2: float
    wall_length_quantity_id: str
    wall_height_quantity_id: str
    gross_area_quantity_id: str
    wall_length_fingerprint: str
    wall_height_fingerprint: str
    context_fingerprint: str
    schema_version: str = WALL_METRIC_DIMENSION_BINDING_SCHEMA_VERSION
    _seal: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("WallMetricDimensionBindingRecord is producer-owned")
        for name in (
            "record_id",
            "document_id",
            "source_sha256",
            "revision_id",
            "evidence_snapshot_id",
            "viewport_id",
            "physical_wall_id",
            "wall_length_quantity_id",
            "wall_height_quantity_id",
            "gross_area_quantity_id",
            "wall_length_fingerprint",
            "wall_height_fingerprint",
            "context_fingerprint",
        ):
            _required(getattr(self, name), name)
        for name in ("length_m", "height_m", "gross_area_m2"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
            object.__setattr__(self, name, value)
        if isinstance(self.page_no, bool) or int(self.page_no) <= 0:
            raise ValueError("page_no must be a positive integer")
        object.__setattr__(self, "page_no", int(self.page_no))


@dataclass(frozen=True)
class WallMetricDimensionBindingResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: WallMetricDimensionBindingRecord | None = None
    schema_version: str = WALL_METRIC_DIMENSION_BINDING_SCHEMA_VERSION


def _blocked(reason: str, *upstream: str) -> WallMetricDimensionBindingResult:
    return WallMetricDimensionBindingResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=tuple(dict.fromkeys([reason, *(str(item) for item in upstream if str(item))])),
        record=None,
    )


def _selector_matches_context(
    selector: WallMetricDimensionBindingSelector,
    context: ProviderContext,
) -> bool:
    if selector.document_id != context.document_id:
        return False
    if selector.source_sha256 != context.source_sha256:
        return False
    if selector.revision_id != context.current_revision_id:
        return False
    if selector.evidence_snapshot_id != context.evidence_snapshot_id:
        return False
    if selector.viewport_id not in context.trusted_viewport_ids():
        return False
    expected_page = context.page_for_viewport(selector.viewport_id)
    if expected_page is not None and expected_page != selector.page_no:
        return False
    return True


def bind_wall_metric_dimensions(
    *,
    selector: WallMetricDimensionBindingSelector,
    context: ProviderContext,
    wall_length: QuantityEvidence,
    wall_height: QuantityEvidence,
) -> WallMetricDimensionBindingResult:
    """Bind current FIRM wall dimensions without inventing wall geometry.

    The existing gross-wall quantity builder remains the canonical validator for
    measurement authority, same-wall identity, source/revision/viewport lineage,
    snapshot freshness, units, and positive finite values.  This function adds an
    exact selector boundary and seals the validated dimensions for downstream
    geometry consumers.
    """
    if type(selector) is not WallMetricDimensionBindingSelector:
        raise TypeError("selector must be WallMetricDimensionBindingSelector")
    if type(context) is not ProviderContext:
        raise TypeError("context must be ProviderContext")
    if type(wall_length) is not QuantityEvidence or type(wall_height) is not QuantityEvidence:
        raise TypeError("wall_length and wall_height must be QuantityEvidence")

    if not _selector_matches_context(selector, context):
        return _blocked(WALL_METRIC_DIMENSION_BINDING_CONTEXT_MISMATCH)

    length_meta = _metadata(wall_length)
    height_meta = _metadata(wall_height)
    if length_meta.get("viewport_id") != selector.viewport_id:
        return _blocked(WALL_METRIC_DIMENSION_BINDING_CONTEXT_MISMATCH, "wall_length_viewport_mismatch")
    if height_meta.get("viewport_id") != selector.viewport_id:
        return _blocked(WALL_METRIC_DIMENSION_BINDING_CONTEXT_MISMATCH, "wall_height_viewport_mismatch")
    if length_meta.get("page_no") != selector.page_no:
        return _blocked(WALL_METRIC_DIMENSION_BINDING_CONTEXT_MISMATCH, "wall_length_page_mismatch")
    if height_meta.get("page_no") != selector.page_no:
        return _blocked(WALL_METRIC_DIMENSION_BINDING_CONTEXT_MISMATCH, "wall_height_page_mismatch")

    gross = build_gross_wall_area_quantity(
        wall_id=selector.physical_wall_id,
        wall_length=wall_length,
        wall_height=wall_height,
        context=context,
    )
    if (
        gross.abstained
        or gross.status != AuthorityStatus.FIRM.value
        or gross.value is None
    ):
        upstream = gross.blocking_reasons or gross.reason_codes or (WALL_METRIC_DIMENSION_BINDING_RECORD_UNAVAILABLE,)
        return _blocked(WALL_METRIC_DIMENSION_BINDING_UPSTREAM_BLOCKED, *upstream)

    if wall_length.value is None or wall_height.value is None:
        return _blocked(WALL_METRIC_DIMENSION_BINDING_RECORD_UNAVAILABLE)

    length_m = float(wall_length.value)
    height_m = float(wall_height.value)
    gross_area_m2 = float(gross.value)
    length_fp = quantity_evidence_fingerprint(wall_length)
    height_fp = quantity_evidence_fingerprint(wall_height)
    context_fp = context.fingerprint()

    payload = {
        "schema_version": WALL_METRIC_DIMENSION_BINDING_SCHEMA_VERSION,
        "document_id": selector.document_id,
        "source_sha256": selector.source_sha256,
        "revision_id": selector.revision_id,
        "evidence_snapshot_id": selector.evidence_snapshot_id,
        "canonical_graph_snapshot_id": context.canonical_graph_snapshot_id,
        "viewport_id": selector.viewport_id,
        "page_no": selector.page_no,
        "physical_wall_id": selector.physical_wall_id,
        "length_m": length_m,
        "height_m": height_m,
        "gross_area_m2": gross_area_m2,
        "wall_length_quantity_id": wall_length.quantity_id,
        "wall_height_quantity_id": wall_height.quantity_id,
        "gross_area_quantity_id": gross.quantity_id,
        "wall_length_fingerprint": length_fp,
        "wall_height_fingerprint": height_fp,
        "context_fingerprint": context_fp,
    }
    record = WallMetricDimensionBindingRecord(
        record_id=stable_contract_id("wall_metric_binding", payload),
        document_id=selector.document_id,
        source_sha256=selector.source_sha256,
        revision_id=selector.revision_id,
        evidence_snapshot_id=selector.evidence_snapshot_id,
        canonical_graph_snapshot_id=context.canonical_graph_snapshot_id,
        viewport_id=selector.viewport_id,
        page_no=selector.page_no,
        physical_wall_id=selector.physical_wall_id,
        length_m=length_m,
        height_m=height_m,
        gross_area_m2=gross_area_m2,
        wall_length_quantity_id=wall_length.quantity_id,
        wall_height_quantity_id=wall_height.quantity_id,
        gross_area_quantity_id=gross.quantity_id,
        wall_length_fingerprint=length_fp,
        wall_height_fingerprint=height_fp,
        context_fingerprint=context_fp,
        _seal=_RECORD_SEAL,
    )
    return WallMetricDimensionBindingResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(WALL_METRIC_DIMENSION_BINDING_RESOLVED,),
        record=record,
    )
