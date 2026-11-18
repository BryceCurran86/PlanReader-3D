"""Authentic original Q5446 ceiling/door/tile height scope, NOT quantities.

A signed sales upgrade overrides standard nominal plate height only where
named. This source receipt never converts plate height into wall length,
finished ceiling height, opening measurements or full-height bathroom tiling.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from stat import S_ISREG

import fitz

from pb_gpt1_q5446_original_area_schedule_shadow import SOURCE_SHA256
from pb_gptmax_q5446_finish_support_shadow import SOURCE_IDS


@dataclass(frozen=True)
class Q5446VerticalScopeReview:
    status: str
    reason_codes: tuple[str, ...]
    authenticated_source_sha256s: tuple[str, ...] = ()
    standard_frame_plate_nominal_height_mm: int | None = None
    promoted_ground_dwelling_and_garage_height_mm: int | None = None
    first_floor_nominal_reference_height_mm: int | None = None
    promoted_hinged_sliding_alfresco_door_height_mm: int | None = None
    master_ensuite_full_height_wall_tile_scope: bool = False
    other_wet_rooms_full_height_tile_scope: bool = False
    physical_wall_height_authorized: bool = False
    finished_ceiling_height_authorized: bool = False
    installed_opening_height_authorized: bool = False
    commercial_quantity_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "authenticated_source_sha256s": list(self.authenticated_source_sha256s),
            "standard_frame_plate_nominal_height_mm": self.standard_frame_plate_nominal_height_mm,
            "promoted_ground_dwelling_and_garage_height_mm": self.promoted_ground_dwelling_and_garage_height_mm,
            "first_floor_nominal_reference_height_mm": self.first_floor_nominal_reference_height_mm,
            "promoted_hinged_sliding_alfresco_door_height_mm": self.promoted_hinged_sliding_alfresco_door_height_mm,
            "master_ensuite_full_height_wall_tile_scope": self.master_ensuite_full_height_wall_tile_scope,
            "other_wet_rooms_full_height_tile_scope": False,
            "physical_wall_height_authorized": False,
            "finished_ceiling_height_authorized": False,
            "installed_opening_height_authorized": False,
            "commercial_quantity_authorized": False,
        }


def _abstain(reason: str) -> Q5446VerticalScopeReview:
    return Q5446VerticalScopeReview("ABSTAINED", (reason,))


def _clean(text: str) -> str:
    return " ".join(text.casefold().split())


def correlate_authenticated_q5446_vertical_scope(
    inclusions_p1: str, sales_p4: str, sales_p5: str,
    *, plan_sha256: str, inclusions_sha256: str, sales_sha256: str,
) -> Q5446VerticalScopeReview:
    """Only original source roles and source-scoped upgrades may be recorded."""
    if ((plan_sha256, inclusions_sha256, sales_sha256)
            != (SOURCE_SHA256, SOURCE_IDS["standard_inclusions"],
                SOURCE_IDS["scope_and_allowance_reference"])):
        return _abstain("original_vertical_source_sha_or_role_mismatch")
    inc, p4, p5 = map(_clean, (inclusions_p1, sales_p4, sales_p5))
    if not re.search(
        r"2440\s*mm nominal internal ceiling height, measured overall to frame plates",
        inc,
    ):
        return _abstain("original_nominal_frame_plate_height_unverified")
    promotion = re.search(
        r"provide\s+2740\s*mm ceiling height to single storey/ground floor "
        r"of double storey dwelling and garage\s+including\s+roof tilers "
        r"guardrail in lieu of standard", p4,
    )
    if promotion is None:
        return _abstain("source_ground_floor_promotion_scope_unverified")
    promoted = {
        int(n) for n in re.findall(
            r"provide\s+(\d{4})\s*mm ceiling height", p4 + " " + p5,
        )
    }
    if promoted != {2740}:
        return _abstain("conflicting_or_ambiguous_original_ceiling_promotions")
    door = bool(re.search(
        r"provide\s+2400\s*mm high standard hinged, sliding, alfresco "
        r"door\(s\) in lieu of standard", p5,
    ))
    master = bool(re.search(
        r"provide full height ceramic wall tiling\s+"
        r"\(as per standard range and specification\)\s+"
        r"to master ensuite in lieu of standard", p4,
    ))
    return Q5446VerticalScopeReview(
        "SOURCE_CORROBORATED_VERTICAL_SCOPE_REVIEW",
        (
            "original_sales_ground_floor_upgrade_overrides_standard_nominal_only_in_named_scope",
            "first_floor_standard_is_nominal_not_a_finished_ceiling_measurement",
            "door_and_wet_tile_scope_require_installed_physical_hosts",
        ),
        (plan_sha256, inclusions_sha256, sales_sha256),
        2440, 2740, 2440, 2400 if door else None, master, False,
    )


def inspect_original_q5446_vertical_scope(
    original_plan: str | Path,
    original_inclusions: str | Path,
    original_sales: str | Path,
) -> Q5446VerticalScopeReview:
    """SHA-authenticate all three private originals before decoding roles."""
    paths = tuple(
        Path(p) for p in (original_plan, original_inclusions, original_sales)
    )
    try:
        if any(not S_ISREG(p.lstat().st_mode) for p in paths):
            return _abstain("original_vertical_source_regular_files_required")
        data = tuple(p.read_bytes() for p in paths)
        digests = tuple(sha256(b).hexdigest() for b in data)
        if digests != (
            SOURCE_SHA256, SOURCE_IDS["standard_inclusions"],
            SOURCE_IDS["scope_and_allowance_reference"],
        ):
            return _abstain("original_vertical_source_sha_or_role_mismatch")
        with fitz.open(stream=data[0], filetype="pdf") as plan, \
             fitz.open(stream=data[1], filetype="pdf") as inc, \
             fitz.open(stream=data[2], filetype="pdf") as sales:
            if (len(plan), len(inc), len(sales)) != (10, 2, 6):
                return _abstain("original_vertical_source_page_roster_invalid")
            return correlate_authenticated_q5446_vertical_scope(
                inc[0].get_text(), sales[3].get_text(), sales[4].get_text(),
                plan_sha256=digests[0], inclusions_sha256=digests[1],
                sales_sha256=digests[2],
            )
    except (OSError, RuntimeError, ValueError, TypeError, IndexError):
        return _abstain("original_vertical_source_unavailable")
