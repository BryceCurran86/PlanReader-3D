"""Original Acacia room/schedule correspondence without invented geometry.

All classifications are review-only. Exact regional original packet must have
been authenticated separately; printed key labels and schedule *prototypes*
do not prove a measured room boundary or an installed opening on floor p2.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from pb_gpt1_acacia_source_packet import (
    ACACIA_ORIGINAL_SHA256, ACACIA_REQUIRED_ROLES, AcaciaOriginalPackage,
)

ROOM_KEY = {
    1: ("ENTRY PORTICO", "external"),
    2: ("ENTRY", "interior_candidate"),
    3: ("LIVING", "interior_candidate"),
    4: ("POWDER ROOM", "interior_candidate"),
    5: ("LAUNDRY", "interior_candidate"),
    6: ("KITCHEN", "interior_candidate"),
    7: ("MEALS", "interior_candidate"),
    8: ("BEDROOM 1", "interior_candidate"),
    9: ("BATHROOM", "interior_candidate"),
    10: ("BEDROOM 2", "interior_candidate"),
    11: ("CARPORT", "external"),
    12: ("LIVING COURT", "external"),
    13: ("WINTER COURT", "external"),
    14: ("WATER TANK", "not_a_room"),
    15: ("SERVICES", "not_a_room"),
}
# p10 is a *schedule of examples*, not a count of installed instances.
# W1/D1 is one COMPOSITE glazed/door frame assembly, not two identical
# independent openings in the wall. Mirrored/alternate SD examples are
# separate schedule codes, not additional proven installed openings.
SCHEDULE_CODES = tuple(
    [f"W{x}" for x in range(1, 8)]
    + ["D1", "D2"]
    + [f"SD{x}" for x in range(1, 8)]
)
SCHEDULE_COMPOSITE = frozenset({"W1", "D1"})


@dataclass(frozen=True)
class AcaciaRoomReview:
    status: str
    reason: str
    legend_id: int
    printed_name: str | None
    scope: str
    indoor_floor_finish_authorized: bool = False
    floor_or_wall_quantity_authorized: bool = False


@dataclass(frozen=True)
class AcaciaOpeningWitness:
    schedule_code: str
    original_source_sha256: str
    floor_page_index: int
    schedule_page_index: int
    floor_host_native_path_ids: tuple[int, ...]
    schedule_native_path_ids: tuple[int, ...]
    original_host_ink_authenticated: bool
    physical_aperture_identity: str
    assembly_identity: str


@dataclass(frozen=True)
class AcaciaScheduleHostReview:
    status: str
    reasons: tuple[str, ...]
    authenticated_candidate_codes: tuple[str, ...] = ()
    candidate_assembly_ids: tuple[str, ...] = ()
    composite_assembly_count: int = 0
    installed_opening_quantity_authorized: bool = False
    customer_row_authorized: bool = False


def _admitted(packet: AcaciaOriginalPackage) -> bool:
    return bool(
        isinstance(packet, AcaciaOriginalPackage)
        and packet.status == "ORIGINAL_ROLES_AUTHENTICATED_REVIEW_ONLY"
        and packet.original_byte_roles_verified
        and len(packet.sheets) == 4
        and tuple((s.page_index, s.drawing_title, s.scale)
                  for s in packet.sheets) == ACACIA_REQUIRED_ROLES
        and packet.source_sha256 == ACACIA_ORIGINAL_SHA256.get(packet.region)
        and not packet.customer_quantities_authorized
        and not packet.finish_material_authorized
    )


def review_acacia_legend_room(
    packet: AcaciaOriginalPackage, legend_id: int,
    *,
    source_key_transcribed: str | None = None,
) -> AcaciaRoomReview:
    """Exclude original OUTDOOR keys from all indoor finish candidates.

    Text on the original is CAD-outline ink; a label in the printed key is
    NOT a source-to-physical-floor-face relationship. Indoor labels remain
    unmeasured until a real original room polygon is independently accepted.
    """
    if not _admitted(packet):
        return AcaciaRoomReview(
            "ABSTAINED", "original_four_sheet_roles_unverified",
            legend_id, None, "unknown",
        )
    if type(legend_id) is not int or legend_id not in ROOM_KEY:
        return AcaciaRoomReview(
            "ABSTAINED", "legend_identity_unknown",
            legend_id, None, "unknown",
        )
    label, scope = ROOM_KEY[legend_id]
    if source_key_transcribed is not None and (
        " ".join(str(source_key_transcribed).strip().upper().replace('"', "").split())
        != label
    ):
        return AcaciaRoomReview(
            "ABSTAINED", "legend_source_name_mismatch",
            legend_id, label, scope,
        )
    if scope != "interior_candidate":
        return AcaciaRoomReview(
            "EXCLUDED_FROM_ENCLOSED_FINISH",
            "outdoor_or_service_label_cannot_be_an_internal_finished_room",
            legend_id, label, scope,
        )
    return AcaciaRoomReview(
        "ROOM_LABEL_ONLY_NEEDS_PHYSICAL_FACE",
        "original_inside_wall_face_and_threshold_not_authenticated",
        legend_id, label, scope,
    )


def _opening_kind(code: str) -> str:
    if code.startswith("SD"):
        return "sliding_door"
    if code.startswith("W"):
        return "window"
    if code.startswith("D"):
        return "hinged_door"
    raise ValueError("acacia_unknown_schedule_code")


def reconcile_acacia_schedule_hosts(
    packet: AcaciaOriginalPackage,
    instances: Iterable[AcaciaOpeningWitness],
) -> AcaciaScheduleHostReview:
    """Validate evidence identity, never assume schedule = installed count.

    One physical host may have composite W1/D1 components, but must not be
    counted twice as TWO WHOLE wall-aperture areas. Distinct otherwise codes
    may repeat only on *distinct* source-hosted floor-plan apertures.
    """
    if not _admitted(packet):
        return AcaciaScheduleHostReview(
            "ABSTAINED", ("original_four_sheet_roles_unverified",),
        )
    try:
        receipts = tuple(instances)
    except (TypeError, ValueError):
        return AcaciaScheduleHostReview(
            "ABSTAINED", ("schedule_host_receipts_invalid",),
        )
    if not receipts:
        return AcaciaScheduleHostReview(
            "ABSTAINED", ("schedule_codes_not_installed_host_evidence",),
        )
    source_ids: set[tuple[str, str]] = set()
    aperture_owners: dict[str, list[AcaciaOpeningWitness]] = {}
    code_list: list[str] = []
    for r in receipts:
        if not isinstance(r, AcaciaOpeningWitness):
            return AcaciaScheduleHostReview(
                "ABSTAINED", ("schedule_host_receipt_type_invalid",),
            )
        if r.schedule_code not in SCHEDULE_CODES:
            return AcaciaScheduleHostReview(
                "ABSTAINED", ("schedule_code_not_in_original_sheet",),
            )
        floor_count = packet.sheets[0].source_page_path_count
        schedule_count = packet.sheets[3].source_page_path_count
        if (
            r.original_source_sha256 != packet.source_sha256
            or r.floor_page_index != 1 or r.schedule_page_index != 9
            or any(n >= floor_count for n in r.floor_host_native_path_ids)
            or any(n >= schedule_count for n in r.schedule_native_path_ids)
            or not r.floor_host_native_path_ids
            or not r.schedule_native_path_ids
            or any(type(x) is not int or x < 0 for x in (
                *r.floor_host_native_path_ids, *r.schedule_native_path_ids,
            ))
            or len(set(r.floor_host_native_path_ids))
               != len(r.floor_host_native_path_ids)
            or len(set(r.schedule_native_path_ids))
               != len(r.schedule_native_path_ids)
            or not r.original_host_ink_authenticated
            or not r.physical_aperture_identity
            or not r.assembly_identity
        ):
            return AcaciaScheduleHostReview(
                "ABSTAINED", ("unproved_floor_or_schedule_source_host",),
            )
        key = (r.physical_aperture_identity, r.schedule_code)
        if key in source_ids:
            return AcaciaScheduleHostReview(
                "ABSTAINED", ("duplicate_physical_aperture_schedule_code",),
            )
        source_ids.add(key)
        aperture_owners.setdefault(r.physical_aperture_identity, []).append(r)
        code_list.append(r.schedule_code)
    assembly_groups: dict[str, set[str]] = {}
    composite_count = 0
    for instance_id, hosted in aperture_owners.items():
        codes = {r.schedule_code for r in hosted}
        assemblies = {r.assembly_identity for r in hosted}
        # Two unrelated schedule labels on one original host are not a
        # legitimate physical opening, even if the drawings share ink.
        if len(codes) > 1 and (not codes.issubset(SCHEDULE_COMPOSITE)
                               or len(assemblies) != 1):
            return AcaciaScheduleHostReview(
                "ABSTAINED", ("competing_schedule_codes_one_physical_host",),
            )
        if codes == SCHEDULE_COMPOSITE:
            composite_count += 1
        for r in hosted:
            assembly_groups.setdefault(r.assembly_identity, set()).add(r.physical_aperture_identity)
    # A fabrication "assembly" is a single placed object and cannot claim
    # arbitrary, far-apart host openings. Composite W1/D1 may share ONE.
    if any(len(ids) > 1 for ids in assembly_groups.values()):
        return AcaciaScheduleHostReview(
            "ABSTAINED", ("one_assembly_reused_on_distinct_floor_hosts",),
        )
    return AcaciaScheduleHostReview(
        "HOST_SCHEDULE_CORRESPONDENCE_REVIEW_ONLY",
        ("source_hosted_components_require_metric_frame_and_customer_verification",),
        tuple(sorted(set(code_list))),
        tuple(sorted(assembly_groups)),
        composite_count,
    )


@dataclass(frozen=True)
class AcaciaCrossSheetDimension:
    kind: str
    source_sha256: str
    reference_page_index: int
    floor_page_index: int
    floor_wall_face_native_path_ids: tuple[int, ...]
    reference_figure_native_path_ids: tuple[int, ...]
    figured_value_mm: float
    source_role_and_physical_host_independently_verified: bool


def review_acacia_dimension_or_height(
    packet: AcaciaOriginalPackage, witness: AcaciaCrossSheetDimension,
) -> tuple[str, str]:
    """Accept a cross-page *review* only with actual physical source host."""
    if not _admitted(packet) or not isinstance(witness, AcaciaCrossSheetDimension):
        return "ABSTAINED", "original_four_sheet_roles_unverified"
    required_page = {"figured_setout": 8, "section_height": 7}.get(witness.kind)
    if required_page is None:
        return "ABSTAINED", "unknown_source_dimension_role"
    if (witness.source_sha256 != packet.source_sha256
            or witness.floor_page_index != 1
            or witness.reference_page_index != required_page
            or not witness.floor_wall_face_native_path_ids
            or not witness.reference_figure_native_path_ids
            or any(type(n) is not int or n < 0 for n in (
                *witness.floor_wall_face_native_path_ids,
                *witness.reference_figure_native_path_ids,
            ))
            or type(witness.figured_value_mm) not in (float, int)
            or not 0 < witness.figured_value_mm < 100000
            or not witness.source_role_and_physical_host_independently_verified):
        return "ABSTAINED", "original_cross_page_physical_host_or_figure_unverified"
    return ("SOURCE_FIGURE_AND_PHYSICAL_HOST_REVIEW_ONLY",
            "no_finished_face_or_customer_metric_authority_from_source_figure_alone")


def review_acacia_finishes(packet: AcaciaOriginalPackage) -> tuple[str, str]:
    """Acacia 'Design Options' spec is referred to, but not supplied."""
    if not _admitted(packet):
        return "ABSTAINED", "original_four_sheet_roles_unverified"
    return ("ABSTAINED", "acacia_house_design_options_material_specification_missing")
