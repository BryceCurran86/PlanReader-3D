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


def test_all_owned_parent_sources_survive_without_first_source_selection():
    records, lines = _fixture()
    # One physical W4 candidate retains two authentic matching source lines.
    # The previous implementation silently reported only whichever came first.
    records[0].physical_identity.source_primitive_ids = (
        "raw:left", "raw:left_other"
    )
    lines["raw:left_other"] = (20.0, 54.0, 100.0, 54.0)
    first = _ledger(records, lines)
    left = next(row for row in first["flanks"] if row["role"] == "left")
    assert left["disposition"].endswith("unique_local_w4_end_reach_observed")
    observed = left["local_end_reach_candidates"][0]
    assert observed["matched_source_primitive_id"] is None
    assert observed["matched_source_primitive_ids"] == [
        "raw:left", "raw:left_other"
    ]
    assert [x["local_chain_reaches_flank_end"]
            for x in observed["source_parent_end_reach"]] == [True, True]
    assert not first["host_granted"]

    records[0].physical_identity.source_primitive_ids = (
        "raw:left_other", "raw:left"
    )
    second = _ledger(tuple(reversed(records)), dict(reversed(tuple(lines.items()))))
    assert first == second


def test_conflicting_local_parent_span_end_reach_abstains_not_first_or_nearest():
    records, lines = _fixture()
    records[0].physical_identity.source_primitive_ids = (
        "raw:leftshort", "raw:left"
    )
    # The W4 chain approaches the sealed end to within original snap allowance
    # but source parent 99..100 has NO overlap with actual W4 chain ending 98.
    # The longer 20..100 primitive DOES overlap and is a positive candidate.
    # Both parents terminate at the source's original flank end.
    records[0].wall_candidate.centerline_pts = (
        (20.0, 53.0), (98.0, 53.0)
    )
    lines["raw:leftshort"] = (99.0, 53.0, 100.0, 53.0)
    first = _ledger(records, lines)
    left = next(row for row in first["flanks"] if row["role"] == "left")
    assert left["disposition"] == (
        "raster_source_band_left_source_parent_end_reach_conflict_abstained"
    )
    assert left["local_end_reach_candidates"] == []
    assert left["remote_ancestry_only_candidates"] == []
    assert left["source_member_count"] == 1
    assert len(left["conflicting_source_parent_candidates"]) == 1
    conflicted = left["conflicting_source_parent_candidates"][0]
    assert conflicted["wall_candidate_id"] == "left"
    assert conflicted["local_chain_reaches_flank_end"] is None
    assert [(x["source_primitive_id"], x["local_chain_reaches_flank_end"])
            for x in conflicted["source_parent_end_reach"]] == [
                ("raw:left", True),
                ("raw:leftshort", False),
            ]
    assert not first["host_granted"]
    assert not first["metric_quantity_granted"]
    assert not first["customer_publication_granted"]

    # Source parent and wall candidate permutation cannot elect the first one.
    records[0].physical_identity.source_primitive_ids = (
        "raw:left", "raw:leftshort"
    )
    reordered_lines = dict(reversed(list(lines.items())))
    assert _ledger(tuple(reversed(records)), reordered_lines) == first


def test_duplicate_source_parent_id_rejected_not_normalized_to_one_w4_owner():
    records, lines = _fixture()
    records[0].physical_identity.source_primitive_ids = (
        "raw:left", "raw:left"
    )
    with pytest.raises(ValueError, match="duplicate W4 source primitive"):
        _ledger(records, lines)
