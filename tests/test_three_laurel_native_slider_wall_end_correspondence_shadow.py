"""Original dark wall ends stay physical; CS/robe leaf stays an opening."""

from __future__ import annotations

import fitz
from pb_next_wall_ring_preview import (
    KIND_CAVITY_SLIDER,
    KIND_SLIDING_LEAF,
    KIND_STROKE,
    LayeredDoorwayClosure,
)
from pb_three_laurel_native_slider_wall_end_correspondence_shadow import (
    corroborate_native_wall_ends_at_existing_slider as match,
)

SHA = "b" * 64


def _native(
    bounds, *, layer="Enclosure_WallInternal", fill=(0.0, 0.0, 0.0), scope="", type="f"
):
    r = {"rect": fitz.Rect(*bounds), "layer": layer, "type": type, "fill": fill}
    if scope:
        r["source_viewport_id"] = scope
    return r


def _slider(
    kind=KIND_CAVITY_SLIDER,
    *,
    axis="v",
    refs=("w342",),
    paths=(),
    band=(100.0, 102.5),
    gap=(130.0, 160.0),
):
    return LayeredDoorwayClosure(
        closure_id="source-owned-CS",
        kind=kind,
        horizontal=axis == "h",
        band=band,
        gap_interval=gap,
        native_path_indices=paths,
        wall_path_indices=(),
        native_word_refs=refs,
    )


def _vertical():
    return (
        _native((100, 90, 102.5, 130)),
        _native((100, 160, 102.5, 210)),
        _native((99.8, 130, 102.7, 131.2), fill=(1.0, 1.0, 1.0)),
    )


def test_existing_source_wall_hosts_physically_flank_cavity_opening():
    rec = match(_slider(), _vertical(), source_sha256=SHA, page_index=2)
    assert rec is not None
    assert rec.wall_host_path_ids == (0, 1)
    assert rec.wall_source_layer == "Enclosure_WallInternal"
    assert rec.wall_role == "source_painted_wall_ends"
    assert rec.sliding_role == "pocket_and_aperture_not_opaque_wall"
    assert rec.to_dict()["measurement_authorized"] is False
    assert rec.to_dict()["physical_room_authenticated"] is False


def test_robe_sliding_frame_opposite_dark_wall_ends():
    d = (
        _native((70, 100, 100, 102.5)),
        _native((140, 100, 167, 102.5)),
        _native((100, 99.8, 101.2, 102.7), fill=(1.0, 1.0, 1.0)),
    )
    c = _slider(
        KIND_SLIDING_LEAF,
        axis="h",
        band=(100, 102.5),
        gap=(100, 140),
        refs=(),
        paths=(3, 4, 5, 6),
    )
    r = match(c, d, source_sha256=SHA, page_index=2)
    assert r is not None
    assert r.wall_host_path_ids == (0, 1)
    assert r.kind == KIND_SLIDING_LEAF


def test_no_authentication_without_two_black_structural_wall_owners():
    d = _vertical()
    assert match(_slider(), d[:1], source_sha256=SHA, page_index=2) is None
    assert match(_slider(), d[1:], source_sha256=SHA, page_index=2) is None
    assert (
        match(
            _slider(),
            (_native((100, 90, 102.5, 130), layer="Finish_Floor"), d[1]),
            source_sha256=SHA,
            page_index=2,
        )
        is None
    )
    assert (
        match(
            _slider(),
            (_native((100, 90, 102.5, 130), fill=(1.0, 1.0, 1.0)), d[1]),
            source_sha256=SHA,
            page_index=2,
        )
        is None
    )
    assert (
        match(
            _slider(),
            (_native((100, 90, 102.5, 130), layer="Annotation_General"), d[1]),
            source_sha256=SHA,
            page_index=2,
        )
        is None
    )


def test_mixed_viewport_and_competing_wall_owners_fail_closed():
    d = (
        _native((100, 90, 102.5, 130), scope="ground"),
        _native((100, 160, 102.5, 210), scope="upper"),
    )
    assert match(_slider(), d, source_sha256=SHA, page_index=2) is None
    d = _vertical() + (_native((100, 90, 102.5, 130)),)
    assert match(_slider(), d, source_sha256=SHA, page_index=2) is None


def test_no_full_solid_wall_through_clear_slider_opening():
    d = _vertical() + (_native((100, 120, 102.5, 172)),)
    assert match(_slider(), d, source_sha256=SHA, page_index=2) is None


def test_missing_printed_cs_or_framed_leaf_refs_is_not_native_opening():
    d = _vertical()
    assert match(_slider(refs=()), d, source_sha256=SHA, page_index=2) is None
    assert (
        match(
            _slider(KIND_SLIDING_LEAF, refs=(), paths=(3,)),
            d,
            source_sha256=SHA,
            page_index=2,
        )
        is None
    )
    assert match(_slider(kind=KIND_STROKE), d, source_sha256=SHA, page_index=2) is None


def test_nearby_off_band_or_wrong_endpoint_does_not_become_host():
    d = (_native((94, 90, 96.5, 130)), _native((100, 160, 102.5, 210)))
    assert match(_slider(), d, source_sha256=SHA, page_index=2) is None
    d = (_native((100, 90, 102.5, 129)), _native((100, 161, 102.5, 210)))
    assert match(_slider(), d, source_sha256=SHA, page_index=2) is None


def test_invalid_fingerprint_or_page_abstains():
    d = _vertical()
    assert match(_slider(), d, source_sha256="bad", page_index=2) is None
    assert match(_slider(), d, source_sha256=SHA, page_index=-1) is None


def test_no_new_billing_even_with_separately_colored_user_markup():
    d = _vertical() + (
        _native(
            (100, 132, 102.5, 159), layer="Annotation_Colour", fill=(1.0, 0.0, 0.5)
        ),
    )
    r = match(_slider(), d, source_sha256=SHA, page_index=2)
    assert r is not None
    assert r.measurement_authorized is False
    assert r.physical_room_authenticated is False
