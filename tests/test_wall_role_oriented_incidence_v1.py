from __future__ import annotations

from pathlib import Path

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_role_authority import (
    WallRoleClassification,
    WallRoleProducer,
    WallRoleSelector,
)


def _write_partitioned_rectangle(path: Path, *, dividers: tuple[float, ...]) -> None:
    doc = fitz.open()
    page = doc.new_page(width=320, height=220)
    segments = [
        ((40.0, 40.0), (280.0, 40.0)),
        ((280.0, 40.0), (280.0, 180.0)),
        ((280.0, 180.0), (40.0, 180.0)),
        ((40.0, 180.0), (40.0, 40.0)),
    ]
    segments.extend(((x, 40.0), (x, 180.0)) for x in dividers)
    for first, second in segments:
        page.draw_line(
            fitz.Point(*first),
            fitz.Point(*second),
            color=(0, 0, 0),
            width=1,
        )
    doc.save(path)
    doc.close()


def _resolved_roles(path: Path):
    payload = path.read_bytes()
    source = SourceVisibilityProducer(
        producer_method="oriented-wall-role-test",
        producer_version="1.0",
    )
    pub = source.ingest_native_pdf_bytes(
        document_id=f"test:{path.name}",
        source_bytes=payload,
        source_locator=str(path),
    )
    walls = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source,
        page_ids=("1",),
    ).authority()
    selector = PhysicalWallCandidateSelector(
        document_id=pub.revision.document_id,
        revision_id=pub.revision.revision_id,
        source_sha256=pub.revision.source_sha256,
        snapshot_id=pub.snapshot.snapshot_id,
        page_id="1",
        decision_scope_id="wall-source:page-1",
    )
    scope = walls.resolve_scope(selector)
    assert scope.status is EvidenceResolutionStatus.CORROBORATED
    assert scope.scope_complete is True

    roles = WallRoleProducer.from_source_topology(
        physical_wall_candidate_authority=walls,
    )

    rows = []
    for record in scope.records:
        result = roles.publish(
            WallRoleSelector(
                document_id=scope.document_id,
                revision_id=scope.revision_id,
                source_sha256=scope.source_sha256,
                snapshot_id=scope.snapshot_id,
                page_id=scope.page_id,
                decision_scope_id=scope.decision_scope_id,
                physical_wall_id=record.wall_candidate_id,
            )
        )
        points = tuple(
            (round(float(x), 6), round(float(y), 6))
            for x, y in record.wall_candidate.centerline_pts
        )
        rows.append(
            {
                "wall": record.wall_candidate_id,
                "points": points,
                "role_status": result.status,
                "role": None if result.record is None else result.record.role,
                "reasons": result.reason_codes,
            }
        )
    return rows


def _horizontal_covering(rows, y: float):
    matches = []
    for row in rows:
        pts = row["points"]
        if len(pts) < 2:
            continue
        ys = {p[1] for p in pts}
        xs = [p[0] for p in pts]
        if len(ys) == 1 and abs(next(iter(ys)) - y) <= 1e-6:
            if min(xs) <= 40.0 + 1e-6 and max(xs) >= 280.0 - 1e-6:
                matches.append(row)
    assert len(matches) == 1, matches
    return matches[0]


def _vertical_covering(rows, x: float):
    matches = []
    for row in rows:
        pts = row["points"]
        if len(pts) < 2:
            continue
        xs = {p[0] for p in pts}
        ys = [p[1] for p in pts]
        if len(xs) == 1 and abs(next(iter(xs)) - x) <= 1e-6:
            if min(ys) <= 40.0 + 1e-6 and max(ys) >= 180.0 - 1e-6:
                matches.append(row)
    assert len(matches) == 1, matches
    return matches[0]


def _assert_role(row, role: WallRoleClassification) -> None:
    assert row["role_status"] is EvidenceResolutionStatus.CORROBORATED, row
    assert row["role"] is role, row


def test_r01_two_room_long_exterior_walls_keep_one_sided_external_role(
    tmp_path: Path,
) -> None:
    path = tmp_path / "r01-two-room.pdf"
    _write_partitioned_rectangle(path, dividers=(160.0,))
    rows = _resolved_roles(path)

    # Long top/bottom walls pass a T-junction and touch two bounded rooms on
    # the SAME physical side. They are still envelope walls, not partitions.
    _assert_role(_horizontal_covering(rows, 40.0), WallRoleClassification.EXTERNAL)
    _assert_role(_horizontal_covering(rows, 180.0), WallRoleClassification.EXTERNAL)
    _assert_role(_vertical_covering(rows, 40.0), WallRoleClassification.EXTERNAL)
    _assert_role(_vertical_covering(rows, 280.0), WallRoleClassification.EXTERNAL)

    # The divider has one bounded room on each oriented side.
    _assert_role(_vertical_covering(rows, 160.0), WallRoleClassification.INTERNAL)


def test_r02_three_same_side_rooms_do_not_turn_long_envelope_wall_internal(
    tmp_path: Path,
) -> None:
    path = tmp_path / "r02-three-room.pdf"
    _write_partitioned_rectangle(path, dividers=(120.0, 200.0))
    rows = _resolved_roles(path)

    _assert_role(_horizontal_covering(rows, 40.0), WallRoleClassification.EXTERNAL)
    _assert_role(_horizontal_covering(rows, 180.0), WallRoleClassification.EXTERNAL)
    _assert_role(_vertical_covering(rows, 40.0), WallRoleClassification.EXTERNAL)
    _assert_role(_vertical_covering(rows, 280.0), WallRoleClassification.EXTERNAL)

    _assert_role(_vertical_covering(rows, 120.0), WallRoleClassification.INTERNAL)
    _assert_role(_vertical_covering(rows, 200.0), WallRoleClassification.INTERNAL)



def _write_mixed_role_wall(path: Path) -> None:
    """L-shaped two-space plan with one wall changing role along its run.

    Target x=160 wall:
      y=40..110   one bounded side  -> envelope/external interval
      y=110..180  two bounded sides -> internal interval
    """
    doc = fitz.open()
    page = doc.new_page(width=320, height=220)
    segments = [
        ((40.0, 40.0), (160.0, 40.0)),
        ((160.0, 40.0), (160.0, 180.0)),  # target continuous wall
        ((40.0, 180.0), (280.0, 180.0)),
        ((40.0, 40.0), (40.0, 180.0)),
        ((160.0, 110.0), (280.0, 110.0)),
        ((280.0, 110.0), (280.0, 180.0)),
    ]
    for first, second in segments:
        page.draw_line(
            fitz.Point(*first),
            fitz.Point(*second),
            color=(0, 0, 0),
            width=1,
        )
    doc.save(path)
    doc.close()


def test_r12_mixed_interval_roles_do_not_collapse_to_any_external_or_internal(
    tmp_path: Path,
) -> None:
    path = tmp_path / "r12-mixed-role.pdf"
    _write_mixed_role_wall(path)
    rows = _resolved_roles(path)

    target = _vertical_covering(rows, 160.0)
    assert target["role_status"] is EvidenceResolutionStatus.ABSTAINED, target
    assert target["role"] is None, target
    assert "wall_role_mixed_interval_profile" in target["reasons"], target
