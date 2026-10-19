"""Exact source-flank bands from typed 300-DPI raster face/end lineages."""
from dataclasses import replace
import math

import pytest

from pb_gpt2_raster_opening_parent_source_shadow import (
    AuthenticatedRasterOpeningParentLine, RasterOpeningParentSourceHandoff,
)
from pb_gpt2_raster_source_flank_band_shadow import (
    reconstruct_raster_source_flank_bands_shadow,
)


def _row(role, name, geometry):
    return AuthenticatedRasterOpeningParentLine(
        parent_observation_id=name,
        visible_observation_id="visible-" + name,
        observation_kind=role,
        original_source_primitive_ref="visible:raster_opening_primitive:source:" + name,
        page_id="3",
        geometry_pdf_points=geometry,
    )


def _handoff(rows, *, status="SOURCE_ONLY_CANDIDATE", missing=()):
    return RasterOpeningParentSourceHandoff(
        status=status,
        source_sha256="e" * 64,
        requested_parent_ids=tuple(sorted(
            {r.parent_observation_id for r in rows} | set(missing)
        )),
        lines=tuple(rows), unresolved_parent_ids=tuple(missing),
        reason_codes=("original_raster_opening_source_lines_authenticated_not_w4",),
    )


def _solid_left():
    return (
        _row("raster_wall_band_face", "left-face-1", (-20., 0., 0., 0.)),
        _row("raster_wall_band_face", "left-face-2", (-20., 2.4, 0., 2.4)),
        _row("raster_wall_band_end", "left-end", (0., 0., 0., 2.4)),
    )


def _solid_right():
    return (
        _row("raster_wall_band_face", "right-face-1", (30., 0., 50., 0.)),
        _row("raster_wall_band_face", "right-face-2", (30., 2.4, 50., 2.4)),
        _row("raster_wall_band_end", "right-end", (30., 0., 30., 2.4)),
    )


def test_two_solid_flanks_source_owned_but_never_physical_wall():
    result = reconstruct_raster_source_flank_bands_shadow(
        _handoff((*_solid_left(), *_solid_right()))
    )
    assert result.status == "SOURCE_BAND_GEOMETRY_CANDIDATE"
    assert len(result.candidates) == 2
    assert result.unresolved_source_parent_ids == ()
    assert [v.end_parent_id for v in result.candidates] == ["left-end", "right-end"]
    assert result.candidates[0].near_center_pdf_pt == (0., 1.2)
    assert result.candidates[0].far_center_pdf_pt == (-20., 1.2)
    assert not result.physical_wall_granted and not result.opening_host_granted
    assert not result.opening_count_granted and not result.firm_quantity_granted
    assert all(not v.structural_wall_granted and not v.host_binding_granted
               for v in result.candidates)


def test_reversed_paths_and_order_never_change_source_band():
    rows = _solid_left()
    original = reconstruct_raster_source_flank_bands_shadow(_handoff(rows))
    flipped = tuple(replace(r, geometry_pdf_points=(
        r.geometry_pdf_points[2], r.geometry_pdf_points[3],
        r.geometry_pdf_points[0], r.geometry_pdf_points[1],
    )) for r in reversed(rows))
    changed = reconstruct_raster_source_flank_bands_shadow(_handoff(flipped))
    assert changed == original


def test_source_face_split_reconstructs_identical_centerline_geometry():
    left = _solid_left()
    split = (
        replace(left[0], geometry_pdf_points=(0., 0., -10., 0.)),
        replace(left[1], geometry_pdf_points=(0., 2.4, -10., 2.4)),
        _row("raster_wall_band_face", "left-face-1b", (-10., 0., -20., 0.)),
        _row("raster_wall_band_face", "left-face-2b", (-10., 2.4, -20., 2.4)),
        left[2],
    )
    a = reconstruct_raster_source_flank_bands_shadow(_handoff(left))
    b = reconstruct_raster_source_flank_bands_shadow(_handoff(split))
    assert len(a.candidates) == len(b.candidates) == 1
    assert a.candidates[0].near_center_pdf_pt == b.candidates[0].near_center_pdf_pt
    assert a.candidates[0].far_center_pdf_pt == b.candidates[0].far_center_pdf_pt
    assert len(b.candidates[0].original_source_visible_ids) == 5
    assert len(b.candidates[0].face_parent_chains[0]) == 2


@pytest.mark.parametrize("angle,scale,shift", [
    (0, 1, (210, -40)), (math.pi / 2, 1, (7, -5)),
    (math.pi / 4, 2, (8, 11)), (math.pi, 0.5, (-6, 9)),
])
def test_source_geometry_rigid_or_scale_transforms_recover(angle, scale, shift):
    def transform(a, b):
        return (shift[0] + scale*(a*math.cos(angle)-b*math.sin(angle)),
                shift[1] + scale*(a*math.sin(angle)+b*math.cos(angle)))
    rows = []
    for row in _solid_left():
        x0,y0,x1,y1 = row.geometry_pdf_points
        a,b = transform(x0,y0),transform(x1,y1)
        rows.append(replace(row, geometry_pdf_points=(*a,*b)))
    result = reconstruct_raster_source_flank_bands_shadow(_handoff(rows))
    assert result.status == "SOURCE_BAND_GEOMETRY_CANDIDATE"
    assert len(result.candidates) == 1
    n = result.candidates[0].near_center_pdf_pt
    f = result.candidates[0].far_center_pdf_pt
    assert math.dist(n, transform(0,1.2)) < 1e-7
    assert math.dist(f, transform(-20,1.2)) < 1e-7


@pytest.mark.parametrize("tamper", [
    "no-end", "one-face", "face-role", "nonperpendicular", "unequal-face-length",
    "gap-in-source-chain", "same-side-faces",
])
def test_source_likeness_does_not_grant_unverified_closed_flank(tamper):
    a,b,c = _solid_left()
    rows = (a,b,c)
    if tamper == "no-end":
        rows = (a,b)
    elif tamper == "one-face":
        rows = (a,c)
    elif tamper == "face-role":
        rows = (a,replace(b, observation_kind="raster_line_run"),c)
    elif tamper == "nonperpendicular":
        rows = (a,b,replace(c, geometry_pdf_points=(0.,0.,2.,2.4)))
    elif tamper == "unequal-face-length":
        rows = (a,replace(b, geometry_pdf_points=(-19.,2.4,0.,2.4)),c)
    elif tamper == "gap-in-source-chain":
        rows = (
            replace(a, geometry_pdf_points=(0.,0.,-10.,0.)),
            b, c,
            _row("raster_wall_band_face","invisible-face-gap",(-10.5,0.,-20.,0.)),
        )
    elif tamper == "same-side-faces":
        rows = (a,replace(b, geometry_pdf_points=(-20.,0.,0.,0.)),c)
    result = reconstruct_raster_source_flank_bands_shadow(_handoff(rows))
    assert not result.candidates
    assert not result.opening_host_granted and not result.firm_quantity_granted


def test_competing_original_face_at_one_end_abstains():
    a,b,c = _solid_left()
    competitor = _row("raster_wall_band_face","second-colliding-end-face",
                       (-22.,0.,0.,0.))
    result = reconstruct_raster_source_flank_bands_shadow(
        _handoff((a,b,c,competitor))
    )
    assert result.candidates == ()


def test_incomplete_parent_source_inventory_never_produces_band_geometry():
    report = reconstruct_raster_source_flank_bands_shadow(
        _handoff(_solid_left(), status="PARTIAL_ABSTAIN", missing=("missing",))
    )
    assert report.status == "ABSTAIN"
    assert not report.candidates


def test_identical_physical_source_id_claims_are_not_two_faces():
    a,b,c = _solid_left()
    output = reconstruct_raster_source_flank_bands_shadow(
        _handoff((a,b,c,replace(a, visible_observation_id="foreign"))))
    assert output.status == "ABSTAIN"
    assert not output.candidates


def test_source_owned_non_wall_primitives_remain_unassigned():
    other = _row("raster_line_run","other-ink", (100.,100.,110.,100.))
    result = reconstruct_raster_source_flank_bands_shadow(
        _handoff((*_solid_left(),other))
    )
    assert len(result.candidates) == 1
    assert result.unresolved_source_parent_ids == ("other-ink",)
    assert not result.physical_wall_granted
