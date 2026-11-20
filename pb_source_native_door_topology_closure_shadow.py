"""Shadow: cavity-slider and sliding/joinery topology-only doorway closures.

Cursor-04 (#4537). Authenticates native CS jamb receipts and double-leaf
sliding/joinery symbols as temporary room-topology barriers only. Never
promotes a doorway into a physical wall, FIRM area, or customer quantity.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pb_source_native_cavity_slider_jamb_shadow import (
    NativeCavitySliderThreshold,
    match_source_native_cavity_sliders,
)
from pb_source_sliding_door_footprint_continuity import (
    detect_exterior_sliding_door_footprint_bridges,
)


@dataclass(frozen=True)
class SourceNativeTopologyClosure:
    kind: str
    horizontal: bool
    band_pdf_pts: tuple[float, float]
    clear_interval_pdf_pts: tuple[float, float]
    native_path_ids: tuple[int, ...]
    host_path_ids: tuple[int, ...]
    page_index: int
    topology_only: bool = True
    physical_wall_authenticated: bool = False
    measurement_authorized: bool = False
    commercial_publishable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "horizontal": self.horizontal,
            "band_pdf_pts": list(self.band_pdf_pts),
            "clear_interval_pdf_pts": list(self.clear_interval_pdf_pts),
            "native_path_ids": list(self.native_path_ids),
            "host_path_ids": list(self.host_path_ids),
            "page_index": self.page_index,
            "topology_only": True,
            "doorway_is_not_physical_wall": True,
            "physical_wall_authenticated": False,
            "measurement_authorized": False,
            "commercial_publishable": False,
            "can_issue_area": False,
        }


@dataclass(frozen=True)
class SourceNativeDoorTopologyClosureCensus:
    cavity_slider_closures: tuple[SourceNativeTopologyClosure, ...]
    sliding_joinery_closures: tuple[SourceNativeTopologyClosure, ...]
    duplicate_cavity_gap_abstained: int
    status: str
    reason: str
    physical_wall_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "cavity_slider_count": len(self.cavity_slider_closures),
            "sliding_joinery_count": len(self.sliding_joinery_closures),
            "duplicate_cavity_gap_abstained": self.duplicate_cavity_gap_abstained,
            "cavity_slider_closures": [c.to_dict() for c in self.cavity_slider_closures],
            "sliding_joinery_closures": [
                c.to_dict() for c in self.sliding_joinery_closures
            ],
            "topology_only": True,
            "physical_wall_authenticated": False,
            "measurement_authorized": False,
            "commercial_publishable": False,
            "official_frozen120_score_change": 0,
        }


def _gap_key(horizontal: bool, band: tuple[float, float], clear: tuple[float, float]) -> tuple:
    return (
        bool(horizontal),
        round(float(band[0]), 2),
        round(float(band[1]), 2),
        round(float(clear[0]), 2),
        round(float(clear[1]), 2),
    )


def _cs_closure(receipt: NativeCavitySliderThreshold) -> SourceNativeTopologyClosure:
    native = tuple(
        sorted(
            {
                int(receipt.leaf_path_id),
                *receipt.host_path_ids,
                *receipt.jamb_path_ids,
            }
        )
    )
    return SourceNativeTopologyClosure(
        kind="topology_only_cavity_slider",
        horizontal=bool(receipt.horizontal),
        band_pdf_pts=tuple(receipt.band_pdf_pts),
        clear_interval_pdf_pts=tuple(receipt.clear_interval_pdf_pts),
        native_path_ids=native,
        host_path_ids=tuple(receipt.host_path_ids),
        page_index=int(receipt.page_index),
    )


def build_source_native_door_topology_closures(
    drawings: Sequence[Mapping[str, Any] | object],
    source_words: Sequence[Any],
    *,
    page_index: int = -1,
) -> SourceNativeDoorTopologyClosureCensus:
    """Inventory topology-only CS and sliding closures; never physical walls."""
    cs_receipts = match_source_native_cavity_sliders(
        drawings, source_words, page_index=page_index,
    )
    by_gap: dict[tuple, NativeCavitySliderThreshold] = {}
    duplicates = 0
    accepted_cs: list[SourceNativeTopologyClosure] = []
    for receipt in cs_receipts:
        key = _gap_key(
            receipt.horizontal, receipt.band_pdf_pts, receipt.clear_interval_pdf_pts,
        )
        prior = by_gap.get(key)
        if prior is not None:
            prior_ids = (
                prior.cs_word_index, prior.leaf_path_id,
                prior.host_path_ids, prior.jamb_path_ids,
            )
            next_ids = (
                receipt.cs_word_index, receipt.leaf_path_id,
                receipt.host_path_ids, receipt.jamb_path_ids,
            )
            if prior_ids != next_ids:
                duplicates += 1
                by_gap.pop(key, None)
                accepted_cs = [c for c in accepted_cs if _gap_key(
                    c.horizontal, c.band_pdf_pts, c.clear_interval_pdf_pts,
                ) != key]
            continue
        by_gap[key] = receipt
        accepted_cs.append(_cs_closure(receipt))

    sliding: list[SourceNativeTopologyClosure] = []
    for bridge in detect_exterior_sliding_door_footprint_bridges(
        drawings, source_words, page_index=page_index,
    ):
        host_a = int(getattr(bridge, "first_host_path_id", -1))
        host_b = int(getattr(bridge, "second_host_path_id", -1))
        if host_a < 0 or host_b < 0 or host_a == host_b:
            continue
        bounds = tuple(float(v) for v in bridge.bounds_pdf_pts)
        if len(bounds) != 4 or not all(map(lambda v: v == v, bounds)):
            continue
        x0, y0, x1, y1 = bounds
        horizontal = abs(x1 - x0) >= abs(y1 - y0)
        if horizontal:
            band = (min(y0, y1), max(y0, y1))
            clear = (min(x0, x1), max(x0, x1))
        else:
            band = (min(x0, x1), max(x0, x1))
            clear = (min(y0, y1), max(y0, y1))
        track_ids = tuple(
            int(v) for v in (getattr(bridge, "sliding_track_path_ids", ()) or ())
            if type(v) is int
        )
        jamb_ids = tuple(
            int(v) for v in (getattr(bridge, "jamb_cap_path_ids", ()) or ())
            if type(v) is int
        )
        sliding.append(
            SourceNativeTopologyClosure(
                kind="topology_only_sliding_joinery",
                horizontal=horizontal,
                band_pdf_pts=band,
                clear_interval_pdf_pts=clear,
                native_path_ids=tuple(sorted({host_a, host_b, *track_ids, *jamb_ids})),
                host_path_ids=(host_a, host_b),
                page_index=page_index,
            )
        )

    # Path-id uniqueness: no guessed duplicate doors sharing the same leaf.
    leaf_hits: dict[int, int] = {}
    for closure in (*accepted_cs, *sliding):
        for path_id in closure.native_path_ids:
            leaf_hits[path_id] = leaf_hits.get(path_id, 0) + 1
    if any(count > 1 for count in leaf_hits.values()):
        # Shared path ownership across distinct topology closures is ambiguous.
        return SourceNativeDoorTopologyClosureCensus(
            cavity_slider_closures=(),
            sliding_joinery_closures=(),
            duplicate_cavity_gap_abstained=duplicates + 1,
            status="ABSTAINED",
            reason="duplicate_native_path_across_topology_closures",
        )

    return SourceNativeDoorTopologyClosureCensus(
        cavity_slider_closures=tuple(accepted_cs),
        sliding_joinery_closures=tuple(sliding),
        duplicate_cavity_gap_abstained=duplicates,
        status="CANDIDATE",
        reason="topology_only_door_closures_not_physical_walls",
    )
