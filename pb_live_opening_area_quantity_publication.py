"""Source-closed opening-area quantity publication.

Consumes only typed LiveCanonicalOpeningObject instances. It never discovers an
opening, reads benchmark truth, or repairs missing measurement evidence. A
quantity is published only when the canonical physical identity is present,
door/window semantic kind is resolved, a positive area exists, and the exact
measurement evidence backing that area is retained on the object.
"""
from __future__ import annotations

import math

from pb_live_physical_opening_void_composition import (
    LiveCanonicalOpeningObject,
    LivePhysicalOpeningVoidComposition,
)
from pb_migration_contracts import QuantityEvidence, stable_contract_id


LIVE_OPENING_AREA_QUANTITY_SCHEMA_VERSION = "1.0.0"
LIVE_OPENING_AREA_QUANTITY_RESOLVED = "live_opening_area_quantity_resolved"
LIVE_OPENING_FIGURED_AREA_QUANTITY_AUTHORITY = (
    "pb_opening_label_dimension_authority.figured_opening_label_area"
)
LIVE_OPENING_GEOMETRY_AREA_QUANTITY_AUTHORITY = (
    "pb_live_physical_opening_void_composition.resolved_opening_geometry_area"
)
LIVE_OPENING_FRAME_SCHEDULE_AREA_QUANTITY_AUTHORITY = (
    "pb_schedule_opening_instance_binding_authority.authenticated_figured_frame_area"
)
LIVE_OPENING_ELEVATION_FRAME_AREA_QUANTITY_AUTHORITY = (
    "pb_opening_elevation_frame_area_authority.authenticated_elevation_frame_area"
)


def _opening_quantity(
    opening: LiveCanonicalOpeningObject,
) -> QuantityEvidence | None:
    if type(opening) is not LiveCanonicalOpeningObject:
        raise TypeError("opening must be LiveCanonicalOpeningObject")

    canonical_id = str(opening.canonical_opening_id or "").strip()
    physical_id = str(opening.physical_opening_id or "").strip()
    viewport_id = str(opening.viewport_id or "").strip()
    host_wall_id = str(opening.host_wall_id or "").strip()
    host_binding_record_id = str(opening.host_binding_record_id or "").strip()
    host_frame_record_id = str(opening.host_frame_record_id or "").strip()
    opening_kind = str(opening.opening_kind or "").strip().lower()
    basis = str(opening.area_basis or "").strip()
    if (
        not canonical_id
        or canonical_id != physical_id
        or not all(
            str(value or "").strip()
            for value in (
                opening.document_id,
                opening.revision_id,
                opening.source_sha256,
                opening.snapshot_id,
                opening.page_id,
                opening.representative_observation_id,
            )
        )
        or not viewport_id
        or not host_wall_id
        or not (host_binding_record_id or host_frame_record_id)
        or opening_kind not in {"door", "window"}
        or not basis
        or opening.area_m2 is None
    ):
        return None

    # Never turn bool/string area values or synthetically stringified source
    # receipt IDs into an authenticated physical opening quantity.
    required_source_ids = (
        opening.canonical_opening_id, opening.physical_opening_id,
        opening.document_id, opening.revision_id, opening.source_sha256,
        opening.snapshot_id, opening.page_id, opening.viewport_id,
        opening.host_wall_id, opening.representative_observation_id,
    )
    if (
        type(opening.area_m2) not in (int, float)
        or any(type(value) is not str or not value or value != value.strip()
               for value in required_source_ids)
        or any(type(value) is not str or not value or value != value.strip()
               for value in (opening.host_binding_record_id, opening.host_frame_record_id)
               if value not in (None, ""))
        or not isinstance(opening.evidence_ids, (tuple, list))
        or not opening.evidence_ids
        or any(type(value) is not str or not value or value != value.strip()
               for value in opening.evidence_ids)
        or len(set(opening.evidence_ids)) != len(opening.evidence_ids)
    ):
        return None

    try:
        value = float(opening.area_m2)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(value) or value <= 0.0:
        return None

    evidence_ids = tuple(sorted(opening.evidence_ids))
    source_observation_ids = opening.source_observation_ids
    source_sha256 = opening.source_sha256
    if (
        not evidence_ids
        or len(source_sha256) != 64
        or any(letter not in "0123456789abcdefABCDEF" for letter in source_sha256)
        or not isinstance(source_observation_ids, (tuple, list))
        or not source_observation_ids
        or any(type(identity) is not str or not identity
               or identity != identity.strip() for identity in source_observation_ids)
        or len(set(source_observation_ids)) != len(source_observation_ids)
        or opening.representative_observation_id not in source_observation_ids
        or opening.representative_observation_id not in evidence_ids
    ):
        return None
    # A caller-replayed host string alone cannot certify the physical opening
    # owner. The composer retains each authenticated host binding/frame record
    # on canonical evidence; require that receipt at quantity publication.
    if any(
        receipt_id and receipt_id not in evidence_ids
        for receipt_id in (host_binding_record_id, host_frame_record_id)
    ):
        return None

    measurement_record_id = None
    quantity_authority = None
    if basis == "figured_opening_label":
        measurement_record_id = opening.figured_area_record_id
        if (type(measurement_record_id) is not str
                or not measurement_record_id
                or measurement_record_id != measurement_record_id.strip()
                or measurement_record_id not in evidence_ids):
            return None
        # Some authenticated figured-label quantities have independent
        # canonical metric axes, while older source-proven labels legitimately
        # lack those unresolved fields. When BOTH axes are present, prevent a
        # replayed area from disagreeing with their physical product. A
        # 0.005 m2 allowance covers an original two-decimal printed area;
        # absence of axes does not replace signed figured-label authority.
        if opening.width_m is not None and opening.height_m is not None:
            if (
                type(opening.width_m) not in (int, float)
                or type(opening.height_m) not in (int, float)
            ):
                return None
            width = float(opening.width_m)
            height = float(opening.height_m)
            if (
                not math.isfinite(width)
                or not math.isfinite(height)
                or width <= 0.0
                or height <= 0.0
                or not math.isclose(
                    value, width * height, rel_tol=0.0, abs_tol=0.0050001
                )
            ):
                return None
        quantity_authority = LIVE_OPENING_FIGURED_AREA_QUANTITY_AUTHORITY
    elif basis == "resolved_opening_geometry":
        measurement_record_id = opening.opening_void_record_id
        if (type(measurement_record_id) is not str
                or not measurement_record_id
                or measurement_record_id != measurement_record_id.strip()
                or measurement_record_id not in evidence_ids):
            return None
        # Producer-authenticated geometry area is *defined* by complete,
        # metrically resolved orthogonal width and height. Do not let a
        # replayed positive area ride the physical-void receipt alone when
        # the supporting metric axes are missing, conflicted or different.
        # Figured label/elevation/schedule bases retain their independent
        # authority paths and are not silently changed to geometry.
        width_m = opening.width_m
        height_m = opening.height_m
        if (
            opening.geometry_complete is not True
            or type(width_m) not in (int, float)
            or type(height_m) not in (int, float)
        ):
            return None
        try:
            width_value = float(width_m)
            height_value = float(height_m)
        except (ValueError, TypeError, OverflowError):
            return None
        if (
            not math.isfinite(width_value)
            or not math.isfinite(height_value)
            or width_value <= 0.0
            or height_value <= 0.0
            or not math.isclose(
                value, width_value * height_value,
                rel_tol=0.0, abs_tol=1e-6,
            )
        ):
            return None
        quantity_authority = LIVE_OPENING_GEOMETRY_AREA_QUANTITY_AUTHORITY
    elif basis == "authenticated_elevation_frame":
        # Preserve the producer-owned source receipt exactly.  Coercing a
        # malformed value here would make the later str check meaningless.
        measurement_record_id = opening.figured_area_record_id
        if (type(measurement_record_id) is not str
                or not measurement_record_id
                or measurement_record_id != measurement_record_id.strip()
                or measurement_record_id not in evidence_ids):
            return None
        quantity_authority = LIVE_OPENING_ELEVATION_FRAME_AREA_QUANTITY_AUTHORITY
    elif basis == "authenticated_frame_schedule":
        measurement_record_id = opening.schedule_binding_record_id
        if (
            type(measurement_record_id) is not str
            or not measurement_record_id
            or measurement_record_id != measurement_record_id.strip()
            or measurement_record_id not in evidence_ids
            or str(opening.schedule_row_dimension_basis or "").strip().lower()
            != "frame"
        ):
            return None
        # This area's source-backed schedule explicitly supplies the OUTER
        # FRAME dimensions in mm. Verify the canonical area is their product,
        # not an independently replayed number that happens to carry a valid
        # source binding receipt. A leaf size is never substituted for frame.
        width_mm = opening.schedule_declared_width_mm
        height_mm = opening.schedule_declared_height_mm
        if type(width_mm) not in (int, float) or type(height_mm) not in (int, float):
            return None
        try:
            width_value = float(width_mm)
            height_value = float(height_mm)
        except (TypeError, ValueError, OverflowError):
            return None
        if (
            not math.isfinite(width_value)
            or not math.isfinite(height_value)
            or width_value <= 0.0 or height_value <= 0.0
        ):
            return None
        frame_area = width_value * height_value / 1_000_000.0
        if not math.isfinite(frame_area) or not math.isclose(
            value, frame_area, rel_tol=0.0, abs_tol=1e-6,
        ):
            return None
        quantity_authority = LIVE_OPENING_FRAME_SCHEDULE_AREA_QUANTITY_AUTHORITY
    else:
        # Unknown area bases cannot silently become commercial quantities.
        return None

    payload = {
        "schema_version": LIVE_OPENING_AREA_QUANTITY_SCHEMA_VERSION,
        "canonical_opening_id": canonical_id,
        "opening_kind": opening_kind,
        "area_m2": value,
        "area_basis": basis,
        "measurement_record_id": measurement_record_id,
        "source_sha256": opening.source_sha256,
        "revision_id": opening.revision_id,
    }
    quantity_id = stable_contract_id(
        "opening_area",
        payload,
        digest_chars=32,
    )
    return QuantityEvidence(
        quantity_id=quantity_id,
        family="opening_area",
        semantic_key=f"{opening_kind}_area:{canonical_id}",
        value=value,
        unit="m2",
        input_entity_ids=(canonical_id,),
        formula=(
            "authenticated figured opening-label dimension product"
            if basis == "figured_opening_label"
            else (
                "authenticated figured elevation outer-frame dimension product"
                if basis == "authenticated_elevation_frame"
                else (
                    "authenticated outer-frame schedule width * height"
                    if basis == "authenticated_frame_schedule"
                    else "authenticated physical opening width * height"
                )
            )
        ),
        formula_version=LIVE_OPENING_AREA_QUANTITY_SCHEMA_VERSION,
        evidence_ids=evidence_ids,
        authority=quantity_authority,
        status="corroborated",
        confidence=1.0,
        abstained=False,
        blocking_reasons=(),
        reason_codes=(LIVE_OPENING_AREA_QUANTITY_RESOLVED,),
        metadata={
            "document_id": opening.document_id,
            "revision_id": opening.revision_id,
            "source_sha256": opening.source_sha256,
            "snapshot_id": opening.snapshot_id,
            "page_no": opening.page_id,
            "viewport_id": viewport_id,
            "canonical_opening_id": canonical_id,
            "physical_opening_id": physical_id,
            "host_wall_id": host_wall_id,
            "host_binding_record_id": host_binding_record_id or None,
            "host_frame_record_id": host_frame_record_id or None,
            "opening_kind": opening_kind,
            "area_basis": basis,
            "measurement_record_id": measurement_record_id,
            "schedule_row_dimension_basis": (
                opening.schedule_row_dimension_basis or None
            ),
            "schedule_row_basis_source": (
                opening.schedule_row_basis_source or None
            ),
            "commercial_projection_allowed": True,
            "section": "Openings",
            "element": f"{opening_kind.title()} area",
            "location": str(opening.type_mark or "").strip() or opening_kind.title(),
            "substrate": "Other",
            "inclusion_status": "PROVISIONAL",
            "row_role": "",
        },
    )


def publish_live_opening_area_quantities(
    composition: LivePhysicalOpeningVoidComposition,
) -> tuple[QuantityEvidence, ...]:
    """Publish one deterministic area quantity per source-proven opening."""
    if type(composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError(
            "composition must be LivePhysicalOpeningVoidComposition"
        )

    # Check the *whole producer-owned canonical inventory* before narrowing
    # it to quantities. If an unsupported/ABSTAIN opening reuses the physical
    # identity of a FIRM opening, filtering first would silently publish the
    # favourable member and conceal contradictory identity lineage.
    canonical_ids: set[str] = set()
    physical_ids: set[str] = set()
    source_scope: tuple[str, str, str] | None = None
    for opening in composition.canonical_openings:
        if type(opening) is not LiveCanonicalOpeningObject:
            raise TypeError("canonical_openings must contain LiveCanonicalOpeningObject")
        # One published source-visibility snapshot owns this canonical
        # composition. A foreign document/hash/snapshot cannot hide among
        # unsupported openings while the matching member seals FIRM area.
        # Different source PAGES within the same PDF remain independent
        # eligible physical openings.
        owner = (
            opening.document_id,
            opening.source_sha256,
            opening.snapshot_id,
        )
        if source_scope is None:
            source_scope = owner
        elif source_scope != owner:
            raise ValueError(
                "canonical opening source snapshot conflicts with quantity composition"
            )
        # A stale foreign-revision member cannot be filtered out as
        # unsupported while the favourable member becomes a commercial
        # quantity. The canonical composition is revision-scoped.
        if str(opening.revision_id or "").strip() != str(composition.revision_id or "").strip():
            raise ValueError(
                "canonical opening revision conflicts with quantity composition"
            )
        canonical_id = str(opening.canonical_opening_id or "").strip()
        physical_id = str(opening.physical_opening_id or "").strip()
        if canonical_id and canonical_id in canonical_ids:
            raise ValueError(
                f"duplicate canonical opening identity in quantity publication: {canonical_id}"
            )
        if physical_id and physical_id in physical_ids:
            raise ValueError(
                f"duplicate physical opening identity in quantity publication: {physical_id}"
            )
        if canonical_id:
            canonical_ids.add(canonical_id)
        if physical_id:
            physical_ids.add(physical_id)

    quantities: list[QuantityEvidence] = []
    seen_quantity_ids: set[str] = set()
    for opening in sorted(
        composition.canonical_openings,
        key=lambda item: item.canonical_opening_id,
    ):
        quantity = _opening_quantity(opening)
        if quantity is None:
            continue
        if quantity.quantity_id in seen_quantity_ids:
            raise ValueError(
                f"duplicate opening quantity id: {quantity.quantity_id}"
            )
        seen_quantity_ids.add(quantity.quantity_id)
        quantities.append(quantity)
    return tuple(quantities)


__all__ = [
    "LIVE_OPENING_FIGURED_AREA_QUANTITY_AUTHORITY",
    "LIVE_OPENING_GEOMETRY_AREA_QUANTITY_AUTHORITY",
    "LIVE_OPENING_FRAME_SCHEDULE_AREA_QUANTITY_AUTHORITY",
    "LIVE_OPENING_ELEVATION_FRAME_AREA_QUANTITY_AUTHORITY",
    "LIVE_OPENING_AREA_QUANTITY_RESOLVED",
    "LIVE_OPENING_AREA_QUANTITY_SCHEMA_VERSION",
    "publish_live_opening_area_quantities",
]
