"""Shadow: recover unmatched external swing/stacker/window instances.

Cursor-05 (#4537). Inventories source-hosted exterior openings with genuine
outside-wall hosts, opening kind, nominal printed dimensions and frame path
IDs. Does not recount already verified instances. Never issues FIRM areas.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pb_source_sliding_door_footprint_continuity import (
    detect_exterior_sliding_door_footprint_bridges,
)
from pb_source_swing_door_footprint_continuity import (
    detect_exterior_swing_door_footprint_bridges,
)
from pb_source_window_footprint_continuity import (
    detect_exterior_window_footprint_bridges,
)


@dataclass(frozen=True)
class ExternalOpeningInstanceReceipt:
    kind: str
    host_path_ids: tuple[int, ...]
    frame_path_ids: tuple[int, ...]
    bounds_pdf_pts: tuple[float, float, float, float]
    page_index: int
    label_text: str = ""
    already_verified: bool = False
    physical_opening_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "host_path_ids": list(self.host_path_ids),
            "frame_path_ids": list(self.frame_path_ids),
            "bounds_pdf_pts": list(self.bounds_pdf_pts),
            "page_index": self.page_index,
            "label_text": self.label_text,
            "already_verified": self.already_verified,
            "physical_opening_authenticated": False,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }


@dataclass(frozen=True)
class ExternalOpeningInstanceCensus:
    unmatched_swing: tuple[ExternalOpeningInstanceReceipt, ...]
    unmatched_stacker_or_slider: tuple[ExternalOpeningInstanceReceipt, ...]
    unmatched_window: tuple[ExternalOpeningInstanceReceipt, ...]
    skipped_verified_count: int
    status: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "unmatched_swing_count": len(self.unmatched_swing),
            "unmatched_stacker_or_slider_count": len(self.unmatched_stacker_or_slider),
            "unmatched_window_count": len(self.unmatched_window),
            "skipped_verified_count": self.skipped_verified_count,
            "unmatched_swing": [r.to_dict() for r in self.unmatched_swing],
            "unmatched_stacker_or_slider": [
                r.to_dict() for r in self.unmatched_stacker_or_slider
            ],
            "unmatched_window": [r.to_dict() for r in self.unmatched_window],
            "physical_opening_authenticated": False,
            "measurement_authorized": False,
            "commercial_publishable": False,
            "official_frozen120_score_change": 0,
        }


def _host_key(hosts: Sequence[int]) -> frozenset[int]:
    return frozenset(int(v) for v in hosts)


def census_unmatched_external_opening_instances(
    drawings: Sequence[Mapping[str, Any] | object],
    source_words: Sequence[Any],
    *,
    page_index: int = -1,
    already_verified_host_keys: Sequence[frozenset[int]] = (),
) -> ExternalOpeningInstanceCensus:
    """List unmatched exterior openings; skip already-verified host pairs."""
    verified = {frozenset(k) for k in already_verified_host_keys}
    skipped = 0

    swings: list[ExternalOpeningInstanceReceipt] = []
    for bridge in detect_exterior_swing_door_footprint_bridges(
        drawings, source_words, page_index=page_index,
    ):
        hosts = (int(bridge.first_host_path_id), int(bridge.second_host_path_id))
        key = _host_key(hosts)
        if key in verified:
            skipped += 1
            continue
        swings.append(
            ExternalOpeningInstanceReceipt(
                kind="external_swing_door",
                host_path_ids=hosts,
                frame_path_ids=tuple(bridge.jamb_cap_path_ids),
                bounds_pdf_pts=tuple(bridge.bounds_pdf_pts),
                page_index=page_index,
            )
        )

    sliders: list[ExternalOpeningInstanceReceipt] = []
    for bridge in detect_exterior_sliding_door_footprint_bridges(
        drawings, source_words, page_index=page_index,
    ):
        hosts = (int(bridge.first_host_path_id), int(bridge.second_host_path_id))
        key = _host_key(hosts)
        if key in verified:
            skipped += 1
            continue
        label = str(getattr(bridge, "label_text", "") or "")
        kind = (
            "external_stacker_door"
            if "stacker" in label.casefold()
            else "external_sliding_door"
        )
        sliders.append(
            ExternalOpeningInstanceReceipt(
                kind=kind,
                host_path_ids=hosts,
                frame_path_ids=tuple(bridge.jamb_cap_path_ids),
                bounds_pdf_pts=tuple(bridge.bounds_pdf_pts),
                page_index=page_index,
                label_text=label,
            )
        )

    windows: list[ExternalOpeningInstanceReceipt] = []
    for bridge in detect_exterior_window_footprint_bridges(
        drawings, source_words,
    ):
        hosts = (
            int(getattr(bridge, "left_host_path_id", -1)),
            int(getattr(bridge, "right_host_path_id", -1)),
        )
        if min(hosts) < 0:
            continue
        key = _host_key(hosts)
        if key in verified:
            skipped += 1
            continue
        jambs = tuple(
            int(v) for v in (
                getattr(bridge, "marker_path_ids", None)
                or getattr(bridge, "jamb_cap_path_ids", None)
                or ()
            )
            if type(v) is int
        )
        windows.append(
            ExternalOpeningInstanceReceipt(
                kind="external_window",
                host_path_ids=hosts,
                frame_path_ids=jambs,
                bounds_pdf_pts=tuple(bridge.bounds_pdf_pts),
                page_index=page_index,
                label_text=str(getattr(bridge, "label_text", "") or ""),
            )
        )

    return ExternalOpeningInstanceCensus(
        unmatched_swing=tuple(swings),
        unmatched_stacker_or_slider=tuple(sliders),
        unmatched_window=tuple(windows),
        skipped_verified_count=skipped,
        status="CANDIDATE",
        reason="unmatched_external_opening_census_review_only",
    )
