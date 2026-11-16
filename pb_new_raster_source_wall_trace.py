"""Raster pixel segment tracing for original PDF pages with tiled image walls.

Uses source PDF *image pixels*, not the old auto-envelope / bounding-hull
detector. Output is diagnostic noncommercial AXIAL segment candidates only.
No room rings, source physical exterior, line closure or dimension scaling.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Any


@dataclass(frozen=True)
class RasterSourceSegmentTrace:
    status: str
    reason: str
    source_page_index: int
    rendered_scale_px_per_pdf_pt: float
    candidate_axis_segments_pdf_pts: tuple[tuple[float,float,float,float], ...] = ()
    source_raster_xrefs: tuple[int, ...] = ()
    exterior_wall_authenticated: bool = False
    physical_wall_authenticated: bool = False
    commercial_publishable: bool = False

    def to_dict(self):
        return dict(
            status=self.status,reason=self.reason,page_index=self.source_page_index,
            candidate_axis_segments_pdf_pts=[list(s) for s in self.candidate_axis_segments_pdf_pts],
            source_raster_image_xrefs=list(self.source_raster_xrefs),
            source_pixel_scale=self.rendered_scale_px_per_pdf_pt,
            exterior_wall_authenticated=False,
            physical_wall_authenticated=False,
            commercial_publishable=False,
        )


def trace_source_raster_wall_lines(
    page: Any, *,
    source_page_index: int,
    source_raster_xrefs: tuple[int, ...],
    max_long_axis_px: int = 2600,
    max_segments: int = 2500,
) -> RasterSourceSegmentTrace:
    """Source-backed raster straight-line candidates, with no hull fallback.

    Does not yet distinguish dimensions from structural wall lines. The
    output deliberately lacks a perimeter polygon or room metric quantities.
    """
    from io import BytesIO
    from PIL import Image
    try:
        import cv2
        import numpy as np
    except ImportError:
        return RasterSourceSegmentTrace(
            "ABSTAINED","native_raster_line_backend_unavailable",
            source_page_index,0.,source_raster_xrefs=source_raster_xrefs,
        )
    rect=page.rect
    zoom=min(2.4,max_long_axis_px/max(rect.width,rect.height))
    if zoom < .25 or not math.isfinite(zoom):
        return RasterSourceSegmentTrace(
            "ABSTAINED","source_raster_invalid_render_scale",
            source_page_index,0.,source_raster_xrefs=source_raster_xrefs,
        )
    # Importantly scan the *image XObjects*, not page.get_pixmap(): the
    # latter composites unrelated native vector DIMENSION lines onto the
    # architectural raster and would silently re-admit those as walls.
    # All candidate pixels must come from actual source image bytes/xrefs.
    width=max(1,round(rect.width*zoom))
    height=max(1,round(rect.height*zoom))
    scale_x=width/max(rect.width,.01)
    scale_y=height/max(rect.height,.01)
    stitched=Image.new("RGB",(width,height),(255,255,255))
    source=page.parent
    source_info=page.get_image_info(xrefs=True)
    inserted=0
    used_tile_xrefs=set()
    for info in source_info:
        xref=info.get("xref")
        if type(xref) is not int or xref<=0 or xref not in source_raster_xrefs:
            continue
        bbox=info.get("bbox")
        matrix=info.get("transform")
        if not bbox or len(bbox)!=4 or not matrix or len(matrix)!=6:
            continue
        a,b,c,d,e,f=(float(v) for v in matrix)
        x0,y0,x1,y1=(float(v) for v in bbox)
        if (x1-x0)*(y1-y0)<.04*rect.get_area():
            # Logo and decorative images are not the architectural raster.
            # In Lot16 the title-block logo is reflected and unrelated to
            # the ten unrotated raster wall tiles. Exclude before checking
            # supported architectural image orientation.
            continue
        # The current renderer supports axis-aligned non-reflected source
        # tiles. For rotation/reflection of a substantial architectural tile,
        # fail closed (never use the old raster envelope).
        if abs(b)>1e-4 or abs(c)>1e-4 or a<=0 or d<=0:
            return RasterSourceSegmentTrace(
                "ABSTAINED","source_raster_transform_not_implemented",
                source_page_index,zoom,source_raster_xrefs=source_raster_xrefs,
            )
        try:
            raw=source.extract_image(xref)["image"]
            with Image.open(BytesIO(raw)) as decoded:
                tile=decoded.convert("RGB")
        except (KeyError,ValueError,OSError,TypeError):
            return RasterSourceSegmentTrace(
                "ABSTAINED","source_raster_image_decode_failed",
                source_page_index,zoom,source_raster_xrefs=source_raster_xrefs,
            )
        px0=round((x0-rect.x0)*scale_x)
        py0=round((y0-rect.y0)*scale_y)
        px1=round((x1-rect.x0)*scale_x)
        py1=round((y1-rect.y0)*scale_y)
        target_w=max(1,px1-px0)
        target_h=max(1,py1-py0)
        tile=tile.resize((target_w,target_h),Image.Resampling.BILINEAR)
        stitched.paste(tile,(px0,py0))
        inserted+=1
        used_tile_xrefs.add(xref)
    if inserted<4:
        return RasterSourceSegmentTrace(
            "ABSTAINED","source_raster_tiled_images_incomplete",
            source_page_index,zoom,source_raster_xrefs=source_raster_xrefs,
        )
    rgb=np.asarray(stitched)
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    ink=np.where(gray<=125,255,0).astype("uint8")
    min_pixels=max(20,round(18.*min(scale_x,scale_y)))
    kernel=max(8,round(7.*min(scale_x,scale_y)))
    candidates=[]
    for is_horizontal in (True,False):
        shape=(kernel,1) if is_horizontal else (1,kernel)
        structure=cv2.getStructuringElement(cv2.MORPH_RECT,shape)
        filtered=cv2.morphologyEx(ink,cv2.MORPH_OPEN,structure)
        lines=cv2.HoughLinesP(
            filtered,rho=1,theta=math.pi/180,threshold=28,
            minLineLength=min_pixels,
            maxLineGap=max(1,round(.7*min(scale_x,scale_y))),
        )
        if lines is None:
            continue
        for entry in lines.reshape(-1,4):
            ax,ay,bx,by=(int(q) for q in entry)
            if is_horizontal:
                if abs(ay-by)>2 or abs(ax-bx)<min_pixels:
                    continue
                y=(ay+by)/2
                x0,x1=sorted((ax,bx))
                coords=(x0/scale_x+rect.x0,y/scale_y+rect.y0,x1/scale_x+rect.x0,y/scale_y+rect.y0)
            else:
                if abs(ax-bx)>2 or abs(ay-by)<min_pixels:
                    continue
                x=(ax+bx)/2
                y0,y1=sorted((ay,by))
                coords=(x/scale_x+rect.x0,y0/scale_y+rect.y0,x/scale_x+rect.x0,y1/scale_y+rect.y0)
            if all(math.isfinite(v) for v in coords):
                candidates.append(tuple(round(float(v),3) for v in coords))
            if len(candidates)>max_segments*2:
                return RasterSourceSegmentTrace(
                    "ABSTAINED","source_raster_line_candidates_exceed_cap",
                    source_page_index,zoom,source_raster_xrefs=source_raster_xrefs,
                )
    # Scan deterministic source pixels; duplicate Hough responses on nearby
    # ink may remain distinct CANDIDATES, never independent wall counts.
    unique=tuple(sorted(set(candidates)))
    if len(unique)>max_segments:
        return RasterSourceSegmentTrace(
            "ABSTAINED","source_raster_line_candidates_exceed_cap",
            source_page_index,zoom,source_raster_xrefs=source_raster_xrefs,
        )
    return RasterSourceSegmentTrace(
        "CANDIDATE" if unique else "ABSTAINED",
        "raster_source_line_candidates_not_wall_or_exterior"
        if unique else "source_raster_no_axial_wall_ink_detected",
        source_page_index,zoom,unique,tuple(sorted(used_tile_xrefs)),
    )
