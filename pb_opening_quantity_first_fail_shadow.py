"""Classify the first authority that blocks a live opening-area quantity.

OBSERVED: ``publish_live_opening_area_quantities`` requires a unique
``host_wall_id``, a host-binding or host-frame receipt, and a finite
``area_m2``. A single figured callout such as 870 CS owns one millimetre
value and leaves ``area_m2`` None. W7 host binding can still be unique
while the quantity stays unpublished.

INFERENCE: an unmatched opening that already has source-closed host
evidence and a one-axis label is lost at figured second-axis / area
publication, not at unique-host identity.

PROPOSED: report the first failing authority only. This module does not
publish a quantity, invent a typical height, join by nearest box, edit
identity maps, or call live wall authority.

BENCHMARK object names, expected areas, and project IDs must not enter
this classifier.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


_TEXT_UNAVAILABLE = frozenset({
    "abstained",
    "opening_label_dimension_text_unavailable",
    "opening_label_dimension_unavailable",
    "opening_label_dimension_geometry_unavailable",
    "opening_label_dimension_source_scope_unavailable",
})
_AMBIGUOUS = frozenset({
    "conflict",
    "ambiguous",
    "opening_label_dimension_ambiguous",
    "opening_label_dimension_semantic_conflict",
})
_RESOLVED = frozenset({
    "corroborated",
    "resolved",
    "opening_label_dimension_resolved",
})


def _finite_positive(value: Any) -> bool:
    if type(value) not in (int, float) or isinstance(value, bool):
        return False
    number = float(value)
    return math.isfinite(number) and number > 0.0


def _dimension_values_mm(values: Sequence[Any] | None) -> tuple[float, ...]:
    owned: list[float] = []
    if values is None:
        return ()
    for value in values:
        if type(value) not in (int, float) or isinstance(value, bool):
            continue
        number = float(value)
        if math.isfinite(number) and number > 0.0:
            owned.append(number)
    return tuple(owned)


def classify_opening_quantity_first_fail(
    *,
    host_wall_id_present: bool,
    host_binding_present: bool,
    host_frame_present: bool,
    area_m2: float | None,
    label_status: str,
    label_dimension_values_mm: Sequence[Any] | None,
    label_area_m2: float | None,
    exact_frozen_location_join: bool | None = True,
    quantity_family: str = "opening_area",
) -> dict[str, Any]:
    """Return why one producer-shaped opening cannot publish live area.

    Callers supply host receipts, the sealed area if any, and the figured-
    label result. Empty or conflicting label text fails closed. A missing
    second owned millimetre value does not become 2100 mm.
    """
    family = str(quantity_family or "").strip()
    if family and family not in {"opening_area", "door", "window"}:
        return {
            "first_failing_authority": "family_not_opening_area_quantity",
            "unique_host_identity_present": False,
            "would_publish_live_opening_area": False,
            "invented_second_axis_mm": None,
            "diagnostic_only": True,
        }
    if exact_frozen_location_join is False:
        return {
            "first_failing_authority": "exact_source_location_join_unavailable",
            "unique_host_identity_present": bool(
                host_wall_id_present and (host_binding_present or host_frame_present)
            ),
            "would_publish_live_opening_area": False,
            "invented_second_axis_mm": None,
            "diagnostic_only": True,
        }
    if exact_frozen_location_join is None:
        return {
            "first_failing_authority": "frozen_source_location_unavailable",
            "unique_host_identity_present": bool(
                host_wall_id_present and (host_binding_present or host_frame_present)
            ),
            "would_publish_live_opening_area": False,
            "invented_second_axis_mm": None,
            "diagnostic_only": True,
        }

    host_ok = bool(host_wall_id_present) and bool(
        host_binding_present or host_frame_present
    )
    if _finite_positive(area_m2) and host_ok:
        return {
            "first_failing_authority": "none_area_already_published",
            "unique_host_identity_present": True,
            "would_publish_live_opening_area": True,
            "invented_second_axis_mm": None,
            "diagnostic_only": True,
        }
    if not host_ok:
        return {
            "first_failing_authority": "unique_host_identity_unavailable",
            "unique_host_identity_present": False,
            "would_publish_live_opening_area": False,
            "invented_second_axis_mm": None,
            "diagnostic_only": True,
        }

    status = str(label_status or "").strip().lower()
    dims = _dimension_values_mm(label_dimension_values_mm)
    if status in _AMBIGUOUS:
        return {
            "first_failing_authority": "opening_label_dimension_ambiguous",
            "unique_host_identity_present": True,
            "would_publish_live_opening_area": False,
            "invented_second_axis_mm": None,
            "diagnostic_only": True,
        }
    if status in _TEXT_UNAVAILABLE or (status not in _RESOLVED and not dims):
        return {
            "first_failing_authority": "opening_label_dimension_text_unavailable",
            "unique_host_identity_present": True,
            "would_publish_live_opening_area": False,
            "invented_second_axis_mm": None,
            "diagnostic_only": True,
        }
    if len(dims) < 2 and not _finite_positive(label_area_m2):
        return {
            "first_failing_authority": "figured_label_second_axis_unavailable",
            "unique_host_identity_present": True,
            "would_publish_live_opening_area": False,
            "invented_second_axis_mm": None,
            "diagnostic_only": True,
        }
    if not _finite_positive(area_m2) and not _finite_positive(label_area_m2):
        return {
            "first_failing_authority": "opening_area_unavailable",
            "unique_host_identity_present": True,
            "would_publish_live_opening_area": False,
            "invented_second_axis_mm": None,
            "diagnostic_only": True,
        }
    return {
        "first_failing_authority": "none_area_already_published",
        "unique_host_identity_present": True,
        "would_publish_live_opening_area": True,
        "invented_second_axis_mm": None,
        "diagnostic_only": True,
    }


def classify_opening_quantity_first_fail_from_producer(
    canonical: Mapping[str, Any],
    label_result: Mapping[str, Any] | None,
    *,
    exact_frozen_location_join: bool | None = True,
    quantity_family: str = "opening_area",
) -> dict[str, Any]:
    """Adapt one canonical opening plus its figured-label result."""
    evidence = {}
    status = ""
    if isinstance(label_result, Mapping):
        status = str(label_result.get("status") or "")
        raw_evidence = label_result.get("evidence")
        if isinstance(raw_evidence, Mapping):
            evidence = raw_evidence
    return classify_opening_quantity_first_fail(
        host_wall_id_present=bool(str(canonical.get("host_wall_id") or "").strip()),
        host_binding_present=bool(
            str(canonical.get("host_binding_record_id") or "").strip()
        ),
        host_frame_present=bool(
            str(canonical.get("host_frame_record_id") or "").strip()
        ),
        area_m2=canonical.get("area_m2"),
        label_status=status,
        label_dimension_values_mm=evidence.get("dimension_values_mm"),
        label_area_m2=evidence.get("area_m2"),
        exact_frozen_location_join=exact_frozen_location_join,
        quantity_family=quantity_family,
    )
