"""Report only (#4764 7211359981, geometry task C23): enclosures strictly inside a room face.

Architecture note. Observed: the source room-face authority withholds a connected component with a single bounded face (an
isolated box), and does not subtract it from the face around it, so a column, shaft or island inside a room leaves that
room's page-space polygon unreduced. Proposed: list, per room face, the strictly enclosed loops of wall linework (and any
inner room faces) with their area, and the net area. Nothing here classifies an enclosure (column, shaft, island or
furniture is unknown), changes a face, a wall or a quantity, or grants authority; nothing on a live path imports it. Must not
influence implementation: any benchmark area or count.
"""
from __future__ import annotations

from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union

ENCLOSED_LOOP = "enclosed_wall_loop"
NESTED_FACE = "nested_room_face"


def _polygon(points) -> Polygon | None:
    if len(points) < 3:
        return None
    polygon = Polygon([(float(x), float(y)) for x, y in points])
    return polygon if polygon.is_valid and polygon.area > 0 else None


def _loops(records, used_wall_ids: set[str]) -> list[tuple[Polygon, tuple[str, ...]]]:
    """Outer outlines enclosed by the wall linework that bounds no room face."""
    lines = {}
    for record in records:
        wall = record.wall_candidate
        points = [(float(x), float(y)) for x, y in wall.centerline_pts]
        if record.wall_candidate_id not in used_wall_ids and len(points) >= 2:
            lines[record.wall_candidate_id] = LineString(points)
    if not lines:
        return []
    noded = unary_union(sorted(lines.values(), key=lambda line: tuple(line.coords)))
    enclosed = unary_union(list(polygonize(noded)))
    parts = [] if enclosed.is_empty else getattr(enclosed, "geoms", [enclosed])
    return [(part, tuple(sorted(wall_id for wall_id, line in lines.items() if part.exterior.intersection(line).length > 0)))
            for part in parts]  # the union of all bounded faces: nested loops are already filled


def room_face_hole_report(wall_scope, room_result) -> dict:
    """Per room face (published or withheld): strictly enclosed loops/inner faces and the net page-space area."""
    faces = [("published", face) for face in room_result.records] + [("withheld", face) for face in room_result.abstained_faces]
    shapes = {face.face_id: _polygon(face.polygon_pdf_pts) for _status, face in faces}
    used = {wall_id for _status, face in faces for wall_id in face.bounding_wall_ids}
    loops = _loops(wall_scope.records, used)
    rows = []
    for status, face in sorted(faces, key=lambda item: item[1].face_id):
        shape = shapes[face.face_id]
        if shape is None:
            rows.append({"face_id": face.face_id, "status": status, "gross_area_pt2": None, "holes": [], "net_area_pt2": None})
            continue
        holes = [(ENCLOSED_LOOP, outline, owners) for outline, owners in loops if shape.contains_properly(outline)]
        holes += [(NESTED_FACE, other_shape, tuple(sorted(other.bounding_wall_ids)))
                  for _s, other in faces
                  if other.face_id != face.face_id and (other_shape := shapes[other.face_id]) is not None
                  and shape.contains_properly(other_shape)]
        union = unary_union([outline for _kind, outline, _owners in holes]) if holes else None
        rows.append({
            "face_id": face.face_id,
            "status": status,
            "gross_area_pt2": shape.area,
            "holes": sorted(({"kind": kind, "area_pt2": outline.area, "wall_ids": list(owners)}
                             for kind, outline, owners in holes), key=lambda row: (row["kind"], row["wall_ids"])),
            "net_area_pt2": shape.area - (union.area if union is not None else 0.0),
        })
    return {"page_id": wall_scope.page_id, "faces": rows,
            "faces_with_holes": sum(bool(row["holes"]) for row in rows)}
