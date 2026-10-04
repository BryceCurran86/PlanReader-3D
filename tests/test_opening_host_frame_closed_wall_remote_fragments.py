"""A whole-wall host frame ignores unrelated aligned walls only when the wall is provably closed.

``OpeningHostFrameProducer`` must prove the extent of a whole wall before it publishes a
frame, so an aligned candidate outside the component must be excluded by positive proof.
A wall whose faces end in L corners at both ends cannot continue along its line, so a
fragment of another wall that lies beyond a closed end, and that the equivalence gate
itself excludes as non-competing, cannot be part of it. Open ends, fragments inside the
extent, admitted pairs and recorded SAME/AMBIGUOUS relations all stay fail-closed.

Synthetic geometry only; nothing here reads a project, file name, page number or quantity.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import SimpleNamespace

import fitz
import pytest

import pb_opening_host_frame_authority as frame_authority
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_room_topology_contracts import JunctionType

CORROBORATED = EvidenceResolutionStatus.CORROBORATED
ABSTAINED = EvidenceResolutionStatus.ABSTAINED

PAGE = 700.0


def hseg(y, x0, x1):
    return ((x0, y), (x1, y))


def vseg(x, y0, y1):
    return ((x, y0), (x, y1))


def building(*, window=(190.0, 230.0), east_closed=True, west_closed=True):
    """Outer rectangle 40..280 x 40..200 (wall 10 thick) with one north window gap.

    East and west end walls are optional, so a wall can be left open at either end.
    """
    x0, y0, x1, y1, t = 40.0, 40.0, 280.0, 200.0, 10.0
    wa, wb = window
    lines = [
        hseg(y0, x0, wa),
        hseg(y0, wb, x1),
        hseg(y0 + t, x0 + t, wa),
        hseg(y0 + t, wb, x1 - t),
        vseg(wa, y0, y0 + t),
        vseg(wb, y0, y0 + t),
        hseg(y1, x0, x1),
        hseg(y1 - t, x0 + t, x1 - t),
    ]
    if west_closed:
        lines += [vseg(x0, y0, y1), vseg(x0 + t, y0 + t, y1 - t)]
    if east_closed:
        lines += [vseg(x1, y0, y1), vseg(x1 - t, y0 + t, y1 - t)]
    return lines


# a second, unrelated wing whose north faces are collinear with the building's faces
REMOTE_FACES = [hseg(40.0, 400.0, 560.0), hseg(50.0, 410.0, 550.0)]
REMOTE_SINGLE_LINE = [hseg(50.0, 410.0, 550.0)]


def pdf_bytes(lines, *, size=PAGE):
    doc = fitz.open()
    try:
        page = doc.new_page(width=size, height=size)
        shape = page.new_shape()
        for start, end in lines:
            shape.draw_line(fitz.Point(*start), fitz.Point(*end))
        shape.finish(width=1.0)
        shape.commit()
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


@dataclass
class Outcome:
    status: EvidenceResolutionStatus
    frames: list
    traces: list
    bindings: list

    @property
    def frame(self):
        assert len(self.frames) == 1
        return self.frames[0]

    @property
    def reasons(self):
        """Publish-time reason codes (the sealed authority only returns sealed records)."""
        assert len(self.traces) == 1
        return tuple(self.traces[0].reason_codes)


def compose(lines, *, name, size=PAGE) -> Outcome:
    source = SourceVisibilityProducer(producer_method="closed-wall-frame-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id=f"closed-wall-{name}",
        source_bytes=pdf_bytes(lines, size=size),
        source_locator=f"memory://closed-wall-{name}.pdf",
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    frames = []
    for trace in composition.host_frames:
        selector = composition.host_frame_selectors[trace.opening_identity_id]
        frames.append(composition.opening_host_frame_authority.resolve(selector))
    return Outcome(
        composition.status, frames, list(composition.host_frames), list(composition.opening_bindings)
    )


def transformed(lines, *, dx=0.0, dy=0.0, scale=1.0, quarter_turns=0, reverse=False):
    centre = PAGE / 2.0

    def move(point):
        x, y = point
        for _ in range(quarter_turns % 4):
            x, y = centre - (y - centre), centre + (x - centre)
        return (x * scale + dx, y * scale + dy)

    moved = [(move(a), move(b)) for a, b in lines]
    if reverse:
        moved = [(b, a) for a, b in reversed(moved)]
    return moved


# ---------------------------------------------------------------------------
# End to end through the live chain
# ---------------------------------------------------------------------------


def test_the_solo_closed_building_publishes_a_whole_wall_frame():
    outcome = compose(building(), name="solo")
    assert outcome.frame.status is CORROBORATED
    assert len(outcome.frame.evidence.whole_wall_candidate_ids) == 4


@pytest.mark.parametrize("remote", [REMOTE_FACES, REMOTE_SINGLE_LINE], ids=["pair", "single"])
def test_unrelated_remote_collinear_walls_do_not_veto_a_closed_wall(remote):
    solo = compose(building(), name="solo-ref").frame.evidence
    with_remote = compose(building() + remote, name="with-remote")
    assert with_remote.frame.status is CORROBORATED
    evidence = with_remote.frame.evidence
    # unrelated content changes nothing about the proven wall (frame ids embed the
    # producer snapshot, so identity is compared through its members and geometry)
    assert evidence.whole_wall_candidate_ids == solo.whole_wall_candidate_ids
    assert evidence.origin_pt == solo.origin_pt
    assert evidence.whole_wall_length_pt == pytest.approx(solo.whole_wall_length_pt)
    assert (evidence.u0_pt, evidence.u1_pt) == pytest.approx((solo.u0_pt, solo.u1_pt))


def test_a_wall_left_open_at_both_ends_still_blocks_on_a_remote_fragment():
    lines = building(east_closed=False, west_closed=False) + REMOTE_FACES
    outcome = compose(lines, name="open-both")
    assert outcome.frame.status is ABSTAINED
    assert frame_authority.OPENING_HOST_FRAME_WHOLE_WALL_UNPROVEN in outcome.reasons


def test_a_wall_closed_at_only_one_end_still_blocks_on_a_fragment_beyond_the_open_end():
    lines = building(east_closed=False, west_closed=True) + REMOTE_FACES
    outcome = compose(lines, name="open-east")
    assert outcome.frame.status is ABSTAINED
    assert frame_authority.OPENING_HOST_FRAME_WHOLE_WALL_UNPROVEN in outcome.reasons


def test_an_open_wall_without_any_remote_fragment_is_unchanged():
    alone = compose(building(east_closed=False, west_closed=False), name="open-alone")
    assert alone.frame.status is CORROBORATED


def test_an_aligned_fragment_with_a_recorded_ambiguous_relation_still_blocks():
    """Overlapping independent fragments next to the window stay uncertain candidates."""
    lines = building()
    lines = [seg for seg in lines if seg != hseg(50.0, 50.0, 190.0)]
    lines += [hseg(50.0, 50.0, 150.0), hseg(50.0, 147.0, 190.0)]  # overlap by 3 pt
    outcome = compose(lines, name="overlap")
    assert all(frame.status is ABSTAINED for frame in outcome.frames)


# ---------------------------------------------------------------------------
# Metamorphic and replay properties
# ---------------------------------------------------------------------------


def test_translation_keeps_the_frame_and_its_geometry():
    base = compose(building() + REMOTE_FACES, name="base").frame.evidence
    moved = compose(transformed(building() + REMOTE_FACES, dx=60.0, dy=35.0), name="moved")
    assert moved.frame.status is CORROBORATED
    evidence = moved.frame.evidence
    assert len(evidence.whole_wall_candidate_ids) == len(base.whole_wall_candidate_ids)
    assert evidence.whole_wall_length_pt == pytest.approx(base.whole_wall_length_pt)
    assert evidence.wall_thickness_pt == pytest.approx(base.wall_thickness_pt)
    assert (evidence.u0_pt, evidence.u1_pt) == pytest.approx((base.u0_pt, base.u1_pt))


@pytest.mark.parametrize("quarter_turns", [1, 2, 3])
def test_quarter_turns_keep_the_frame_and_its_geometry(quarter_turns):
    base = compose(building() + REMOTE_FACES, name="base-rot").frame.evidence
    turned = compose(
        transformed(building() + REMOTE_FACES, quarter_turns=quarter_turns), name=f"rot{quarter_turns}"
    )
    assert turned.frame.status is CORROBORATED
    evidence = turned.frame.evidence
    assert len(evidence.whole_wall_candidate_ids) == len(base.whole_wall_candidate_ids)
    assert evidence.whole_wall_length_pt == pytest.approx(base.whole_wall_length_pt)
    assert evidence.wall_thickness_pt == pytest.approx(base.wall_thickness_pt)
    assert (evidence.u1_pt - evidence.u0_pt) == pytest.approx(base.u1_pt - base.u0_pt)


def test_uniform_scale_scales_the_frame_geometry():
    base = compose(building() + REMOTE_FACES, name="base-scale").frame.evidence
    scaled = compose(transformed(building() + REMOTE_FACES, scale=0.5), name="half")
    assert scaled.frame.status is CORROBORATED
    evidence = scaled.frame.evidence
    assert evidence.whole_wall_length_pt == pytest.approx(base.whole_wall_length_pt * 0.5)
    assert evidence.wall_thickness_pt == pytest.approx(base.wall_thickness_pt * 0.5)


def test_input_order_and_primitive_direction_do_not_change_the_frame():
    base = compose(building() + REMOTE_FACES, name="base-order").frame.evidence
    reordered = compose(transformed(building() + REMOTE_FACES, reverse=True), name="reversed")
    assert reordered.frame.status is CORROBORATED
    evidence = reordered.frame.evidence
    assert len(evidence.whole_wall_candidate_ids) == len(base.whole_wall_candidate_ids)
    assert evidence.whole_wall_length_pt == pytest.approx(base.whole_wall_length_pt)


def test_a_larger_page_with_extra_unrelated_walls_changes_nothing():
    base = compose(building() + REMOTE_FACES, name="base-viewport").frame.evidence
    bigger = compose(
        building() + REMOTE_FACES + [hseg(300.0, 420.0, 600.0), vseg(420.0, 300.0, 380.0)],
        name="bigger",
        size=900.0,
    )
    assert bigger.frame.status is CORROBORATED
    assert bigger.frame.evidence.whole_wall_candidate_ids == base.whole_wall_candidate_ids
    assert bigger.frame.evidence.whole_wall_length_pt == pytest.approx(base.whole_wall_length_pt)


def test_replay_is_deterministic():
    first = compose(building() + REMOTE_FACES, name="replay-a").frame.evidence
    second = compose(building() + REMOTE_FACES, name="replay-b").frame.evidence
    assert first.whole_wall_candidate_ids == second.whole_wall_candidate_ids
    assert first.whole_wall_candidate_ids == tuple(sorted(first.whole_wall_candidate_ids))
    assert (first.origin_pt, first.u0_pt, first.u1_pt) == (second.origin_pt, second.u0_pt, second.u1_pt)


# ---------------------------------------------------------------------------
# Unit tests of the proof helpers
# ---------------------------------------------------------------------------


def _wall(points, ends):
    return SimpleNamespace(
        centerline_pts=tuple(points), junction_types=tuple(ends), is_curved=False
    )


def _record(points, ends):
    return SimpleNamespace(wall_candidate=_wall(points, ends))


AXIS = (1.0, 0.0)


def test_only_an_l_corner_closes_the_end_that_lies_at_the_target():
    corner = _record([(0.0, 0.0), (10.0, 0.0)], [JunctionType.ENDPOINT, JunctionType.L_CORNER])
    assert frame_authority._end_is_corner(corner, AXIS, 10.0) is True
    assert frame_authority._end_is_corner(corner, AXIS, 0.0) is False  # the free end
    for kind in (JunctionType.T_JUNCTION, JunctionType.X_CROSSING, JunctionType.AMBIGUOUS,
                 JunctionType.NEAR_JUNCTION_REVIEW, JunctionType.ENDPOINT):
        other = _record([(0.0, 0.0), (10.0, 0.0)], [JunctionType.ENDPOINT, kind])
        assert frame_authority._end_is_corner(other, AXIS, 10.0) is False
    assert frame_authority._end_is_corner(corner, AXIS, 5.0) is False  # not an end at all


def test_a_face_end_is_closed_only_when_every_member_reaching_it_is_a_corner():
    corner = _record([(0.0, 0.0), (10.0, 0.0)], [JunctionType.L_CORNER, JunctionType.L_CORNER])
    open_end = _record([(0.0, 0.0), (10.0, 0.0)], [JunctionType.L_CORNER, JunctionType.ENDPOINT])
    other_face = _record([(0.0, 6.0), (10.0, 6.0)], [JunctionType.L_CORNER, JunctionType.L_CORNER])
    records = {"a": corner, "b": other_face}
    closures = frame_authority.OpeningHostFrameProducer._face_closures(
        records, ("a", "b"), AXIS, (0.0, 1.0), (0.0, 6.0), 0.5
    )
    assert closures == ((0.0, 10.0, True, True), (0.0, 10.0, True, True))

    mixed = {"a": corner, "dup": open_end, "b": other_face}
    closures = frame_authority.OpeningHostFrameProducer._face_closures(
        mixed, ("a", "dup", "b"), AXIS, (0.0, 1.0), (0.0, 6.0), 0.5
    )
    assert closures[0][2] is True and closures[0][3] is False  # a duplicate open end spoils the max end


def test_a_face_without_members_or_projection_gives_no_closure():
    records = {"a": _record([(0.0, 0.0), (10.0, 0.0)], [JunctionType.L_CORNER, JunctionType.L_CORNER])}
    assert frame_authority.OpeningHostFrameProducer._face_closures(
        records, ("a",), AXIS, (0.0, 1.0), (0.0, 50.0), 0.5
    ) is None
    degenerate = {"a": _record([(0.0, 0.0), (0.0, 0.0)], [JunctionType.L_CORNER, JunctionType.L_CORNER])}
    assert frame_authority.OpeningHostFrameProducer._face_closures(
        degenerate, ("a",), AXIS, (0.0, 1.0), (0.0,), 0.5
    ) is None


def test_non_competing_needs_an_explicit_gate_exclusion_and_usable_identities():
    from pb_physical_wall_identity import PhysicalWallIdentity
    from pb_migration_contracts import EvidenceResolutionStatus as Status

    def identity(wall_id, path, primitive):
        return PhysicalWallIdentity(
            wall_candidate_id=wall_id,
            viewport_id="v",
            candidate_identity_id=f"id-{wall_id}",
            path_fingerprint=tuple(path),
            source_primitive_ids=(primitive,),
            edge_ids=(f"e-{wall_id}",),
            status=Status.CORROBORATED,
        )

    def record(wall_id, path, primitive):
        return SimpleNamespace(physical_identity=identity(wall_id, path, primitive))

    equivalence = SimpleNamespace(candidate_pair_audit=SimpleNamespace(verified_points_per_mm=None))
    near = record("a", [(0.0, 0.0), (100.0, 0.0)], "p1")
    touching = record("b", [(100.0, 0.0), (200.0, 0.0)], "p2")
    remote = record("c", [(500.0, 0.0), (600.0, 0.0)], "p3")
    assert frame_authority._positively_non_competing(near, remote, equivalence) is True
    assert frame_authority._positively_non_competing(near, touching, equivalence) is False  # contact admits it
    unusable = SimpleNamespace(
        physical_identity=PhysicalWallIdentity(
            wall_candidate_id="u", viewport_id="v", candidate_identity_id=None,
            path_fingerprint=None, source_primitive_ids=(), edge_ids=(),
            status=Status.ABSTAINED, blocking_reasons=("x",),
        )
    )
    assert frame_authority._positively_non_competing(near, unusable, equivalence) is False


def test_the_proof_adds_no_scale_angle_or_gap_threshold():
    source = open(frame_authority.__file__, encoding="utf-8").read()
    added = source.split("def _positively_non_competing", 1)[1].split("def _band_node", 1)[0]
    assert "math.radians" not in added and "tolerance" not in added.lower().replace("tolerance_pt", "")
    assert math.isfinite(frame_authority._COORD_TOL)
