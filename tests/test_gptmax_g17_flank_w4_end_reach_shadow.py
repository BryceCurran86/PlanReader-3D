"""G17 flank → local W4 end-reach shadow ledger never publishes a host."""
from __future__ import annotations

from copy import deepcopy

import pytest

import pb_opening_host_binding_authority as host
from pb_g17_flank_w4_end_reach_shadow import build_g17_flank_w4_end_reach_ledger
from test_raster_opening_source_band_host import _fixture, _support
from test_raster_opening_split_centerline_host import OPENING, _record


def _ledger(records=None, lines=None, support=None, opening=OPENING):
    if records is None or lines is None:
        records, lines = _fixture()
    return build_g17_flank_w4_end_reach_ledger(
        _support() if support is None else support,
        records,
        opening,
        lines,
    )


def test_unique_local_end_reach_is_observed_but_never_grants_host():
    records, lines = _fixture()
    before = deepcopy((records, lines))
    report = _ledger(records, lines)
    assert report["shadow_only"] is True
    assert report["host_granted"] is False
    assert report["frame_granted"] is False
    assert report["metric_quantity_granted"] is False
    assert report["benchmark_score_granted"] is False
    by_role = {row["role"]: row for row in report["flanks"]}
    assert by_role["left"]["disposition"] == (
        "raster_source_band_left_unique_local_w4_end_reach_observed"
    )
    assert by_role["right"]["disposition"] == (
        "raster_source_band_right_unique_local_w4_end_reach_observed"
    )
    assert by_role["left"]["local_end_reach_candidates"][0]["wall_candidate_id"] == "left"
    assert by_role["left"]["host_granted"] is False
    assert (records, lines) == before


def test_missing_source_ancestry_reports_source_primitive_unmapped():
    records, lines = _fixture()
    records[0].physical_identity.source_primitive_ids = ("unrelated",)
    report = _ledger(records, lines)
    left = next(row for row in report["flanks"] if row["role"] == "left")
    assert left["disposition"] == "raster_source_band_left_source_primitive_unmapped"
    assert left["source_member_count"] == 0
    assert left["local_end_reach_candidates"] == []
    assert report["host_granted"] is False


def test_remote_shared_primitive_reports_local_wall_owner_unmapped():
    records, lines = _fixture()
    # Truncate the left centerline so ancestry exists but the chain never
    # reaches the sealed left flank end at axis=100.
    records[0].wall_candidate.centerline_pts = ((20.0, 53.0), (40.0, 53.0))
    report = _ledger(records, lines)
    left = next(row for row in report["flanks"] if row["role"] == "left")
    assert left["disposition"] == "raster_source_band_left_local_wall_owner_unmapped"
    assert left["source_member_count"] == 1
    assert left["local_end_reach_candidates"] == []
    assert left["remote_ancestry_only_candidates"][0]["wall_candidate_id"] == "left"
    assert report["host_granted"] is False


def test_competing_local_owners_are_retained_without_nearest_election():
    records, lines = _fixture()
    extra = _record("other", start=20.0, end=100.0, offset=-1.0, source_ids=("raw:other",))
    lines["raw:other"] = (20.0, 54.0, 100.0, 54.0)
    report = _ledger((*records, extra), lines)
    left = next(row for row in report["flanks"] if row["role"] == "left")
    assert left["disposition"] == (
        "raster_source_band_left_multiple_local_w4_end_reach_retained"
    )
    ids = [row["wall_candidate_id"] for row in left["local_end_reach_candidates"]]
    assert ids == ["left", "other"]
    assert report["host_granted"] is False


def test_closed_face_end_failure_abstains_without_inventing_flanks():
    support = list(_support())
    support.pop(2)  # drop left end
    report = _ledger(support=support)
    assert report["host_granted"] is False
    assert report["flanks"] == ()
    assert "exact_original_g17_face_end_closure_unavailable" in report["reason_codes"]


@pytest.mark.parametrize(
    "scale,rotation,dx,dy",
    [(1.0, 0, 333.0, -120.0), (1.0, 1, 0.0, 0.0), (2.0, 1, -100.0, 200.0), (0.5, 0, 5.0, 8.0)],
)
def test_metamorphic_transform_preserves_unique_local_observation(scale, rotation, dx, dy):
    records, lines = _fixture()
    support = _support()

    def point(p):
        x, y = p
        if rotation:
            x, y = -y, x
        return (x * scale + dx, y * scale + dy)

    def line(values):
        return (*point(values[:2]), *point(values[2:]))

    for record in records:
        start, end = record.wall_candidate.centerline_pts
        midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        record.wall_candidate.centerline_pts = tuple(
            point(p) for p in (start, midpoint, end)
        )
    for item in support:
        item.geometry = line(item.geometry)
    lines = {k: line(v) for k, v in lines.items()}
    opening = host._OpeningGeometry(
        origin=point(OPENING.origin),
        axis=(0.0, 1.0) if rotation else (1.0, 0.0),
        normal=(-1.0, 0.0) if rotation else (0.0, 1.0),
        length=OPENING.length * scale,
        thickness=OPENING.thickness * scale,
    )
    report = _ledger(records, lines, support, opening)
    by_role = {row["role"]: row for row in report["flanks"]}
    assert by_role["left"]["disposition"].endswith("unique_local_w4_end_reach_observed")
    assert by_role["right"]["disposition"].endswith("unique_local_w4_end_reach_observed")
    assert report["host_granted"] is False


def test_input_order_invariance_for_records_and_support():
    records, lines = _fixture()
    first = _ledger(records, lines)
    second = _ledger(tuple(reversed(records)), dict(reversed(tuple(lines.items()))),
                     tuple(reversed(_support())))
    assert first == second
    assert first["host_granted"] is False


def test_furniture_lookalike_outside_band_does_not_become_a_member():
    records, lines = _fixture()
    lookalike = _record("furniture", start=20.0, end=100.0, offset=20.0, source_ids=("raw:furniture",))
    lines["raw:furniture"] = (20.0, 75.0, 100.0, 75.0)
    report = _ledger((*records, lookalike), lines)
    left = next(row for row in report["flanks"] if row["role"] == "left")
    assert all(
        row["wall_candidate_id"] != "furniture"
        for row in left["local_end_reach_candidates"] + left["remote_ancestry_only_candidates"]
    )
    assert report["host_granted"] is False
