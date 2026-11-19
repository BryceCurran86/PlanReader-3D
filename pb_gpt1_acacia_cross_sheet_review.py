"""Original Acacia room/schedule correspondence without invented geometry.

All classifications are review-only. Exact regional original packet must have
been authenticated separately; printed key labels and schedule *prototypes*
do not prove a measured room boundary or an installed opening on floor p2.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
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
        and packet.original_byte_roles_verified is True
        and type(packet.source_pages) is int and packet.source_pages == 10
        and len(packet.sheets) == 4
        and tuple((s.page_index, s.drawing_title, s.scale)
                  for s in packet.sheets) == ACACIA_REQUIRED_ROLES
        # A right title and scale on the wrong original numbered sheet
        # cannot authenticate a physical source-role packet.
        and tuple(s.drawing_number for s in packet.sheets)
            == tuple(f"{i + 1}/10" for i, _title, _scale
                     in ACACIA_REQUIRED_ROLES)
        and all(type(s.source_page_path_count) is int
                and s.source_page_path_count > 0 for s in packet.sheets)
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
        # A foreign producer must not materialize an unbounded source receipt
        # generator before source identity is checked. Acacia's real installed
        # opening census is far below this deliberately generous safety cap.
        receipts = tuple(islice(iter(instances), 257))
    except (TypeError, ValueError, RuntimeError):
        return AcaciaScheduleHostReview(
            "ABSTAINED", ("schedule_host_receipts_invalid",),
        )
    if len(receipts) > 256:
        return AcaciaScheduleHostReview(
            "ABSTAINED", ("schedule_host_receipts_over_limit",),
        )
    if not receipts:
        return AcaciaScheduleHostReview(
            "ABSTAINED", ("schedule_codes_not_installed_host_evidence",),
        )
    source_ids: set[tuple[str, str]] = set()
    # An identical native host witness cannot prove two distinct installed
    # apertures merely because a producer assigned different string IDs.
    # W1/D1 composite components retain their ONE shared aperture identity.
    native_floor_host_owners: dict[tuple[int, ...], str] = {}
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
        floor_paths = r.floor_host_native_path_ids
        schedule_paths = r.schedule_native_path_ids
        if (
            r.original_source_sha256 != packet.source_sha256
            or r.floor_page_index != 1 or r.schedule_page_index != 9
            or type(floor_count) is not int or floor_count <= 0
            or type(schedule_count) is not int or schedule_count <= 0
            # A missing/mutable list of source paths is not an immutable
            # source witness. Check types BEFORE iterating or making a set
            # so malformed receipts fail closed rather than raise.
            or type(floor_paths) is not tuple or not floor_paths
            or type(schedule_paths) is not tuple or not schedule_paths
            or any(type(n) is not int or not 0 <= n < floor_count
                   for n in floor_paths)
            or any(type(n) is not int or not 0 <= n < schedule_count
                   for n in schedule_paths)
            or len(set(floor_paths)) != len(floor_paths)
            or len(set(schedule_paths)) != len(schedule_paths)
            or type(r.original_host_ink_authenticated) is not bool
            or not r.original_host_ink_authenticated
            or type(r.physical_aperture_identity) is not str
            or not r.physical_aperture_identity.strip()
            or type(r.assembly_identity) is not str
            or not r.assembly_identity.strip()
        ):
            return AcaciaScheduleHostReview(
                "ABSTAINED", ("unproved_floor_or_schedule_source_host",),
            )
        existing_host = native_floor_host_owners.setdefault(
            floor_paths, r.physical_aperture_identity,
        )
        if existing_host != r.physical_aperture_identity:
            return AcaciaScheduleHostReview(
                "ABSTAINED", ("native_host_witness_reused_for_distinct_apertures",),
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
    # Do not allow an apparent physical/figured link to borrow a path ID
    # from the wrong original sheet. These are *native per-page indices*,
    # not reusable global IDs or a geometry tolerance. They remain review
    # witnesses, never independent measurement/quantity authority.
    path_counts = {s.page_index: s.source_page_path_count for s in packet.sheets}
    floor_count = path_counts.get(1, 0)
    reference_count = path_counts.get(required_page, 0)
    floor_paths = witness.floor_wall_face_native_path_ids
    reference_paths = witness.reference_figure_native_path_ids
    if (witness.source_sha256 != packet.source_sha256
            or witness.floor_page_index != 1
            or witness.reference_page_index != required_page
            or type(floor_paths) is not tuple or not floor_paths
            or type(reference_paths) is not tuple or not reference_paths
            or any(type(n) is not int or not 0 <= n < floor_count
                   for n in floor_paths)
            or any(type(n) is not int or not 0 <= n < reference_count
                   for n in reference_paths)
            or len(set(floor_paths)) != len(floor_paths)
            or len(set(reference_paths)) != len(reference_paths)
            or type(witness.figured_value_mm) not in (float, int)
            or not 0 < witness.figured_value_mm < 100000
            or type(witness.source_role_and_physical_host_independently_verified)
               is not bool
            or not witness.source_role_and_physical_host_independently_verified):
        return "ABSTAINED", "original_cross_page_physical_host_or_figure_unverified"
    return ("SOURCE_FIGURE_AND_PHYSICAL_HOST_REVIEW_ONLY",
            "no_finished_face_or_customer_metric_authority_from_source_figure_alone")


def review_acacia_finishes(packet: AcaciaOriginalPackage) -> tuple[str, str]:
    """Acacia 'Design Options' spec is referred to, but not supplied."""
    if not _admitted(packet):
        return "ABSTAINED", "original_four_sheet_roles_unverified"
    return ("ABSTAINED", "acacia_house_design_options_material_specification_missing")
