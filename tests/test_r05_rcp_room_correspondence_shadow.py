"""Focused tests for AG-R05 / A12 generic cross-block RCP bubble-to-room correspondence."""
from __future__ import annotations

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_rcp_room_correspondence_shadow import (
    CEILING_PROFILE_BULKHEAD,
    CEILING_PROFILE_FLAT,
    CEILING_PROFILE_RAKED,
    CEILING_PROFILE_STEPPED,
    RcpCeilingBubbleWitness,
    RcpRoomAnchorWitness,
    link_rcp_bubbles_to_rooms_shadow,
)

SHA = "a" * 64


def _room(rid: str, key: str, block: int, center, bbox=None, *, vp="vp_rcp", rev="rev1"):
    return RcpRoomAnchorWitness(
        room_anchor_id=rid,
        document_id="doc1",
        revision_id=rev,
        source_sha256=SHA,
        page_id="10",
        viewport_id=vp,
        block_no=block,
        room_key=key,
        label_center_pt=center,
        region_bbox_pt=bbox,
    )


def _bubble(
    bid: str,
    block: int,
    center,
    mat="CL1",
    h=2700.0,
    hmax=None,
    profile=CEILING_PROFILE_FLAT,
    subzone="",
    *,
    vp="vp_rcp",
    rev="rev1",
):
    return RcpCeilingBubbleWitness(
        bubble_id=bid,
        document_id="doc1",
        revision_id=rev,
        source_sha256=SHA,
        page_id="10",
        viewport_id=vp,
        block_no=block,
        center_pt=center,
        material_code=mat,
        height_mm=h,
        height_max_mm=hmax,
        profile=profile,
        subzone_label=subzone,
    )


def test_cross_block_containment_links_distinct_blocks_and_never_copies_floor_to_empty_room() -> None:
    rooms = (
        _room("r1", "ROOM_A", block=1, center=(50, 50), bbox=(0, 0, 100, 100)),
        _room("r2", "ROOM_B", block=2, center=(250, 50), bbox=(200, 0, 300, 100)),
    )
    bubbles = (_bubble("b1", block=99, center=(60, 60), mat="CL1", h=2700.0),)
    res = link_rcp_bubbles_to_rooms_shadow(bubbles=bubbles, room_anchors=rooms)
    assert res.shadow_only is True
    assert res.commercial_authority_granted is False
    assert len(res.links) == 1
    assert res.links[0].status is EvidenceResolutionStatus.CORROBORATED
    assert res.links[0].cross_block is True
    assert res.links[0].match_mode == "containment"
    assert res.links[0].room_anchor_id == "r1"
    # ROOM_B has no RCP bubble -> abstains cleanly (no floor-copy ceiling)
    assert res.abstained_room_anchor_ids == ("r2",)
    assert "rcp_ceiling_bubble_unavailable_no_floor_copy" in res.reason_codes


def test_stepped_raked_bulkhead_subzones_preserved_while_same_subzone_conflict_vetoes() -> None:
    rooms = (_room("r1", "HALL", block=1, center=(50, 50), bbox=(0, 0, 200, 200)),)
    bubbles = (
        _bubble("b_flat", block=10, center=(40, 40), mat="CL1", h=2700.0, profile=CEILING_PROFILE_FLAT),
        _bubble("b_bulk", block=11, center=(120, 40), mat="CL2", h=2400.0, profile=CEILING_PROFILE_BULKHEAD),
        _bubble("b_rake", block=12, center=(120, 120), mat="CL3", h=2700.0, hmax=3600.0, profile=CEILING_PROFILE_RAKED),
        _bubble("b_step", block=13, center=(40, 120), mat="CL4", h=3000.0, profile=CEILING_PROFILE_STEPPED),
    )
    res = link_rcp_bubbles_to_rooms_shadow(bubbles=bubbles, room_anchors=rooms)
    assert len(res.links) == 4
    assert all(l.status is EvidenceResolutionStatus.CORROBORATED for l in res.links)
    assert res.conflict_room_anchor_ids == ()

    # Now add a conflicting flat height in the exact same subzone -> CONFLICT
    conflict_bubbles = bubbles + (
        _bubble("b_flat_bad", block=14, center=(45, 45), mat="CL1", h=3100.0, profile=CEILING_PROFILE_FLAT),
    )
    res_bad = link_rcp_bubbles_to_rooms_shadow(bubbles=conflict_bubbles, room_anchors=rooms)
    assert "r1" in res_bad.conflict_room_anchor_ids
    assert any(l.status is EvidenceResolutionStatus.CONFLICT for l in res_bad.links)


def test_ambiguous_competing_room_labels_and_cross_scope_bubbles_abstain() -> None:
    rooms = (
        _room("r1", "A", block=1, center=(100, 100)),
        _room("r2", "B", block=2, center=(140, 100)),
    )
    # Bubble right at midpoint (120, 100): equidistant -> ambiguity veto!
    b_mid = _bubble("b_mid", block=5, center=(120, 100))
    # Cross-viewport & cross-revision bubbles -> rejected!
    b_vp = _bubble("b_vp", block=6, center=(100, 100), vp="other_vp")
    b_rev = _bubble("b_rev", block=7, center=(100, 100), rev="other_rev")

    res = link_rcp_bubbles_to_rooms_shadow(bubbles=(b_mid, b_vp, b_rev), room_anchors=rooms)
    assert res.links == ()
    assert set(res.unmatched_bubble_ids) == {"b_mid", "b_vp", "b_rev"}
    assert "rcp_bubble_ambiguous_competing_room_labels" in res.reason_codes
    assert "rcp_bubble_no_same_scope_room_anchor" in res.reason_codes
