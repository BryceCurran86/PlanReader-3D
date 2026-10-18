"""Documented source construction layer volumes from already-measured zones.

This supports slabs, screeds and insulation without adopting a typical
thickness, cost, waste factor or material density. CANDIDATE only.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from pb_gpt1_figured_chain_metric_shadow import FiguredPolygonMetricShadow
from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class OriginalMaterialLayer:
    source_layer_id: str
    physical_surface_id: str
    source_material_code: str
    source_definition_receipt_id: str
    thickness_mm: float
    thickness_figured_receipt_ids: tuple[str, ...]
    source_sha256: str
    revision_id: str
    page_id: str


@dataclass(frozen=True)
class FiguredSourceLayerVolumeShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    candidate_volume_by_layer_m3: tuple[tuple[str,float], ...]
    candidate_total_volume_m3: float | None
    original_layer_receipt_ids: tuple[str, ...]
    diagnostic_only: bool = True


def measure_source_figured_layer_volumes_shadow(
    surface: FiguredPolygonMetricShadow,
    physical_surface_id: str,
    layers: tuple[OriginalMaterialLayer, ...],
) -> FiguredSourceLayerVolumeShadow:
    """Area * original figured thickness, never inferred nominal dimensions."""
    def block(reason):
        return FiguredSourceLayerVolumeShadow(
            EvidenceResolutionStatus.ABSTAINED,(reason,),(),None,()
        )
    if (
        type(surface) is not FiguredPolygonMetricShadow
        or surface.status is not EvidenceResolutionStatus.CANDIDATE
        or type(surface.candidate_area_m2) is not float
        or not math.isfinite(surface.candidate_area_m2)
        or surface.candidate_area_m2 <= 0
        or type(physical_surface_id) is not str or not physical_surface_id
        or type(layers) not in (tuple,list) or not layers
    ):
        return block("original_figured_layer_surface_unavailable")
    layer_ids,thickness_ids,results=set(),set(),[]
    for layer in layers:
        if (
            type(layer) is not OriginalMaterialLayer
            or type(layer.source_layer_id) is not str or not layer.source_layer_id
            or layer.source_layer_id in layer_ids
            or layer.physical_surface_id != physical_surface_id
            or type(layer.source_material_code) is not str or not layer.source_material_code
            or type(layer.source_definition_receipt_id) is not str
            or not layer.source_definition_receipt_id
            or (layer.source_sha256, layer.revision_id, layer.page_id)
            != (surface.source_sha256, surface.revision_id, surface.page_id)
            or type(layer.thickness_mm) not in (int,float)
            or type(layer.thickness_figured_receipt_ids) not in (tuple,list)
            or not layer.thickness_figured_receipt_ids
            or any(type(v) is not str or not v or v != v.strip()
                   for v in layer.thickness_figured_receipt_ids)
            or thickness_ids.intersection(layer.thickness_figured_receipt_ids)
        ):
            return block("original_figured_layer_source_conflict")
        try:
            thickness=float(layer.thickness_mm)
        except (TypeError, ValueError, OverflowError):
            return block("original_figured_layer_thickness_invalid")
        if not math.isfinite(thickness) or thickness<=0:
            return block("original_figured_layer_thickness_invalid")
        layer_ids.add(layer.source_layer_id)
        thickness_ids.update(layer.thickness_figured_receipt_ids)
        volume=surface.candidate_area_m2*thickness/1000.0
        if not math.isfinite(volume) or volume <= 0:
            return block("original_figured_layer_volume_unrepresentable")
        results.append((layer.source_layer_id,volume))
    return FiguredSourceLayerVolumeShadow(
        EvidenceResolutionStatus.CANDIDATE,
        ("original_figured_material_layer_volume_shadow_only",),
        tuple(sorted(results)),math.fsum(v for _,v in results),
        tuple(sorted(thickness_ids)),
    )
