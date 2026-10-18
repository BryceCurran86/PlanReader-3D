"""Source-figured enclosed room 3D shell from documented floor and height.

The metric footprint already has separately witnessed original figured edges.
A structural floor datum and room clear height are independent source-evidenced
facts. This constructs only CANDIDATE geometry for a VR/3D takeoff editor,
not a new certified room/ceiling height, cost or customer quantity.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from shapely.geometry import Polygon

from pb_gpt1_figured_chain_metric_shadow import FiguredPolygonMetricShadow
from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class OriginalDocumentedRoomZ:
    physical_room_id: str
    lower_finished_floor_z_mm: float
    clear_height_mm: float
    original_floor_datum_figure_id: str
    original_height_figure_id: str
    source_room_elevation_binding_receipts: tuple[str,...]
    source_sha256: str
    revision_id: str


@dataclass(frozen=True)
class FiguredPhysicalRoomShellShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str,...]
    candidate_xyz_vertices_mm: tuple[tuple[float,float,float],...]
    candidate_wall_triangles: tuple[tuple[int,int,int],...]
    candidate_floor_triangles: tuple[tuple[int,int,int],...]
    candidate_ceiling_triangles: tuple[tuple[int,int,int],...]
    candidate_clear_room_volume_m3: float | None
    candidate_wall_surface_m2: float | None
    original_room_height_figure_id: str
    source_side_ids: tuple[str,...]
    diagnostic_only: bool = True


def build_original_figured_room_3d_shell_shadow(
    room: FiguredPolygonMetricShadow,
    elevation: OriginalDocumentedRoomZ,
) -> FiguredPhysicalRoomShellShadow:
    """Simple closed shell; concave wall triangulation without false room split."""
    def block(reason):
        return FiguredPhysicalRoomShellShadow(
            EvidenceResolutionStatus.ABSTAINED,(reason,),(),(),(),(),None,None,
            str(getattr(elevation,"original_height_figure_id","")),(),
        )
    if (
        type(room) is not FiguredPolygonMetricShadow
        or room.status is not EvidenceResolutionStatus.CANDIDATE
        or room.diagnostic_only is not True
        or not room.source_side_ids
        or len(room.metric_vertices_mm)!=len(room.source_side_ids)
        or type(elevation) is not OriginalDocumentedRoomZ
        or elevation.physical_room_id!=room.physical_room_id
        or (elevation.source_sha256,elevation.revision_id)
           != (room.source_sha256,room.revision_id)
        or type(elevation.original_floor_datum_figure_id) is not str
        or not elevation.original_floor_datum_figure_id
        or type(elevation.original_height_figure_id) is not str
        or not elevation.original_height_figure_id
        or elevation.original_height_figure_id==elevation.original_floor_datum_figure_id
        or type(elevation.source_room_elevation_binding_receipts) not in (tuple,list)
        or not elevation.source_room_elevation_binding_receipts
        or any(type(v) is not str or not v for v in
               elevation.source_room_elevation_binding_receipts)
    ):
        return block("original_room_3d_height_and_floor_lineage_unavailable")
    def number(value):
        if type(value) not in (int,float):return None
        try:n=float(value)
        except (ValueError,TypeError,OverflowError):return None
        return n if math.isfinite(n) else None
    lower=number(elevation.lower_finished_floor_z_mm)
    height=number(elevation.clear_height_mm)
    if lower is None or height is None or height<=0:
        return block("original_room_3d_elevation_figures_invalid")
    try:
        polygon=Polygon(room.metric_vertices_mm)
        if not polygon.is_valid or polygon.area<=0:
            return block("original_room_3d_metric_polygon_invalid")
    except (TypeError,ValueError,OverflowError):
        return block("original_room_3d_metric_polygon_invalid")
    n=len(room.metric_vertices_mm)
    verts=tuple((float(x),float(y),lower) for x,y in room.metric_vertices_mm)+tuple(
        (float(x),float(y),lower+height) for x,y in room.metric_vertices_mm
    )
    # Direct wall quad splitting is valid for both convex and concave rooms.
    sides=[]
    for i in range(n):
        j=(i+1)%n
        sides.extend(((i,j,j+n),(i,j+n,i+n)))
    # Arbitrary concave floor polygons require constrained triangulation;
    # never use an invalid fan which crosses outside an L-shaped room.
    from shapely.ops import triangulate
    raw_triangles=[tri for tri in triangulate(polygon) if polygon.covers(tri)]
    if not raw_triangles or not math.isclose(
        math.fsum(t.area for t in raw_triangles),polygon.area,
        rel_tol=1e-9,abs_tol=1e-6
    ):
        return block("original_room_3d_floor_triangulation_incomplete")
    source_vertices={tuple(p):i for i,p in enumerate(room.metric_vertices_mm)}
    floor=[]
    for triangle in raw_triangles:
        coordinates=list(triangle.exterior.coords)[:-1]
        if any(tuple(p) not in source_vertices for p in coordinates):
            return block("original_room_3d_triangulation_created_unowned_vertex")
        floor.append(tuple(source_vertices[tuple(p)] for p in coordinates))
    ceiling=[tuple(i+n for i in reversed(tri)) for tri in floor]
    volume=polygon.area*height/1e9
    side_area=math.fsum(
        math.dist(room.metric_vertices_mm[i],room.metric_vertices_mm[(i+1)%n])
        for i in range(n)
    )*height/1e6
    if not math.isfinite(volume) or not math.isfinite(side_area):
        return block("original_room_3d_metric_result_invalid")
    return FiguredPhysicalRoomShellShadow(
        EvidenceResolutionStatus.CANDIDATE,
        ("original_figured_3d_shell_shadow_only",),
        verts,tuple(sides),tuple(floor),tuple(ceiling),
        volume,side_area,elevation.original_height_figure_id,
        tuple(room.source_side_ids),
    )
