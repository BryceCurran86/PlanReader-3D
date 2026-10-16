"""Compare page-7 source room faces after proven annotation-cycle withholding.

Reads the original Maryborough PDF and the live viewport producer. Prints the
published face that contains each known label center. Does not publish quantities.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from pb_drawing_evidence_binding import DrawingViewType
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_room_face_authority import (
    SourceRoomFaceSelector,
    build_source_room_face_authority,
)
from pb_source_room_label_authority import _point_in_polygon
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_live_physical_net_wall_integration import (
    LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
)

PDF = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
EXPECTED_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
PROBES = (
    ("FOOD PREP", 332.7274932861328, 692.8547668457031, 8026.758, 18),
    ("OFFICE", 242.01063537597656, 1489.5415649414062, 1145.145, 4),
    ("COLD ROOM", 421.0467224121094, 976.0536193847656, 67798.244, 105),
    ("FREEZER", 481.04486083984375, 1216.2904052734375, 19303.547, 70),
)
SCOPE_KEYS = (
    "document_id", "revision_id", "source_sha256", "snapshot_id",
    "page_id", "decision_scope_id",
)


def _ring_valid(points) -> bool:
    try:
        from shapely.geometry import Polygon
    except ImportError:
        return True
    ring = [(float(p[0]), float(p[1])) for p in points]
    if len(ring) >= 2 and ring[0] == ring[-1]:
        ring = ring[:-1]
    if len(ring) < 3:
        return False
    return bool(Polygon(ring).is_valid)


def main() -> None:
    # Live withhold is unwired. This tool reports current production faces only.
    pdf_bytes = PDF.read_bytes()
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    if digest != EXPECTED_SHA:
        raise SystemExit("sha mismatch")
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{digest[:32]}",
        source_bytes=pdf_bytes,
        source_locator="memory://annotation-room-preservation.pdf",
        page_ids=("7",),
    )
    print("INGEST_OK", published.revision.revision_id, flush=True)
    producer = PhysicalWallCandidateProducer.from_authenticated_viewports(
        source, page_ids=("7",),
    )
    wall_auth = producer.authority()
    room_auth = build_source_room_face_authority(wall_auth)
    snapshot = source.published_snapshot_for_revision(published.revision.revision_id)
    selectors = wall_auth.selectors_for_authenticated_viewports(
        document_id=snapshot.revision.document_id,
        revision_id=snapshot.revision.revision_id,
        source_sha256=digest,
        snapshot_id=snapshot.snapshot.snapshot_id,
        page_id="7",
        view_type=DrawingViewType.FLOOR_PLAN.value,
    )
    print("FLOOR_PLAN_SCOPES", len(selectors), flush=True)
    for wall_selector in selectors:
        walls = wall_auth.resolve_scope(wall_selector)
        rooms = room_auth.resolve_scope(SourceRoomFaceSelector(
            **{key: getattr(wall_selector, key) for key in SCOPE_KEYS}
        ))
        print(
            "SCOPE", wall_selector.decision_scope_id,
            "walls", len(getattr(walls, "records", ())),
            "wall_status", walls.status,
            "faces", len(rooms.records),
            "abstained", len(rooms.abstained_faces),
            "room_status", rooms.status,
            flush=True,
        )
        faces = list(rooms.records) + list(rooms.abstained_faces)
        for name, x, y, expected_area, expected_verts in PROBES:
            hits = [
                face for face in faces
                if _point_in_polygon((x, y), face.polygon_pdf_pts)
            ]
            if not hits:
                print("PROBE", name, "NO_FACE", flush=True)
                continue
            for face in hits:
                area = float(face.area_page_pts2)
                verts = len(face.polygon_pdf_pts)
                valid = _ring_valid(face.polygon_pdf_pts)
                area_delta = area - expected_area
                print(
                    "PROBE", name,
                    "face", face.face_id,
                    "area", f"{area:.3f}",
                    "delta", f"{area_delta:.3f}",
                    "verts", verts,
                    "expected_verts", expected_verts,
                    "valid", valid,
                    "published", face in rooms.records,
                    flush=True,
                )


if __name__ == "__main__":
    main()
