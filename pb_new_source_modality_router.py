"""Identify original PDF source modality before ANY structural wall tracing.

A tiled-JPEG architectural page cannot be reduced to its unrelated vector
dimension lines. This source-only router never calls the old raster envelope.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Any

from shapely.geometry import box
from shapely.ops import unary_union


@dataclass(frozen=True)
class SourcePageModality:
    route: str
    reason: str
    raster_coverage_fraction: float
    raster_image_instances: int
    raster_unique_xrefs: tuple[int, ...]
    original_vector_path_count: int
    commercial_publishable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return dict(
            route=self.route,reason=self.reason,
            raster_coverage_fraction=round(self.raster_coverage_fraction,5),
            raster_image_instances=self.raster_image_instances,
            raster_unique_xrefs=list(self.raster_unique_xrefs),
            original_vector_path_count=self.original_vector_path_count,
            old_envelope_fallback=False,
            commercial_publishable=False,
        )


def classify_source_page_modality(
    page: Any, *, vector_path_count: int | None = None,
) -> SourcePageModality:
    if vector_path_count is None:
        vector_path_count=len(page.get_drawings())
    original_rect=page.rect
    page_area=original_rect.get_area()
    if not math.isfinite(page_area) or page_area<=0:
        raise ValueError("page_raster_modality_invalid_dimensions")
    info=page.get_image_info(xrefs=True)
    polygons=[]
    xrefs=set()
    for entry in info:
        bbox=entry.get("bbox")
        if not bbox or len(bbox)!=4:
            continue
        try:
            x0,y0,x1,y1=map(float,bbox)
        except (TypeError,ValueError):
            continue
        if not all(math.isfinite(q) for q in (x0,y0,x1,y1)):
            continue
        x0=max(original_rect.x0,x0)
        y0=max(original_rect.y0,y0)
        x1=min(original_rect.x1,x1)
        y1=min(original_rect.y1,y1)
        if x0>=x1 or y0>=y1:
            continue
        # Ignore tiny logos/stamps; image coverage proves the source modality
        # only when the actual architectural sheet is image-backed.
        if (x1-x0)*(y1-y0) < .015*page_area:
            continue
        polygons.append(box(x0,y0,x1,y1))
        if isinstance(entry.get("xref"),int) and entry["xref"]>0:
            xrefs.add(int(entry["xref"]))
    union=unary_union(polygons) if polygons else None
    fraction=min(1.,float(union.area/page_area)) if union else 0.
    # Two gates: high raster COVERAGE and multiple substantial image tiles.
    # A photo/logo plus CAD geometry cannot hijack the source-native route.
    raster=fraction>=.74 and len(polygons)>=4
    return SourcePageModality(
        route="tiled_raster_underlay" if raster else "native_vector",
        reason=(
            "source_architectural_geometry_dominantly_tiled_image"
            if raster else "source_native_vector_geometry_preferred"
        ),
        raster_coverage_fraction=fraction,
        raster_image_instances=len(polygons),
        raster_unique_xrefs=tuple(sorted(xrefs)),
        original_vector_path_count=vector_path_count,
    )
