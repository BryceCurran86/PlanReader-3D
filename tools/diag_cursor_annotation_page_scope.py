"""Measure page-wide wall and room faces after annotation-cycle withholding.

Page-wide scope is the live composition path. Viewport scope was measured
separately. This does not publish quantities.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from pb_live_physical_net_wall_integration import (
    LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_room_face_authority import (
    SourceRoomFaceSelector,
    build_source_room_face_authority,
)
from pb_source_room_label_authority import _point_in_polygon
from pb_source_visibility_authority import SourceVisibilityProducer

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
    import pb_physical_wall_candidate_authority as wall_mod
    real = wall_mod._without_proven_annotation_cycles

    def _counted(segments, **kwargs):
        after = real(segments, **kwargs)
        before_ids = [str(segment.get("id") or "") for segment in segments]
        after_ids = {str(segment.get("id") or "") for segment in after}
        dropped = [sid for sid in before_ids if sid not in after_ids]
        print(
            "WITHHELD", len(dropped),
            "input", len(before_ids),
            "d26362", "d26362i0" in dropped,
            "ids", dropped[:8],
            flush=True,
        )
        return after

    wall_mod._without_proven_annotation_cycles = _counted
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
        source_locator="memory://annotation-page-scope.pdf",
        page_ids=("7", "11"),
    )
    print("INGEST_OK", published.revision.revision_id, flush=True)
    producer = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source, page_ids=("7", "11"),
    )
    wall_auth = producer.authority()
    room_auth = build_source_room_face_authority(wall_auth)
    for walls in producer._scopes.values():
        selector = PhysicalWallCandidateSelector(
            document_id=walls.document_id,
            revision_id=walls.revision_id,
            source_sha256=walls.source_sha256,
            snapshot_id=walls.snapshot_id,
            page_id=walls.page_id,
            decision_scope_id=walls.decision_scope_id,
        )
        rooms = room_auth.resolve_scope(SourceRoomFaceSelector(
            **{key: getattr(selector, key) for key in SCOPE_KEYS}
        ))
        print(
            "SCOPE", walls.page_id, walls.decision_scope_id,
            "wall_status", walls.status,
            "walls", len(walls.records),
            "reasons", walls.reason_codes,
            "faces", len(rooms.records),
            "abstained", len(rooms.abstained_faces),
            "room_status", rooms.status,
            flush=True,
        )
        if walls.page_id != "7":
            continue
        faces = list(rooms.records) + list(rooms.abstained_faces)
        for name, x, y, expected_area, expected_verts in PROBES:
            hits = [face for face in faces if _point_in_polygon((x, y), face.polygon_pdf_pts)]
            if not hits:
                print("PROBE", name, "NO_FACE", flush=True)
                continue
            for face in hits:
                print(
                    "PROBE", name,
                    "area", f"{float(face.area_page_pts2):.3f}",
                    "delta", f"{float(face.area_page_pts2) - expected_area:.3f}",
                    "verts", len(face.polygon_pdf_pts),
                    "expected_verts", expected_verts,
                    "valid", _ring_valid(face.polygon_pdf_pts),
                    "published", face in rooms.records,
                    flush=True,
                )


if __name__ == "__main__":
    main()
