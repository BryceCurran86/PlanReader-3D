"""Commercial-semantic veto for independently mapped signed Full Plan V2 inputs.

Source and frozen scorers remain independent: this ONLY rejects an already
proposed exact-identity mapping if its source-owned quantity family/kind is
incompatible with the benchmark trade. It NEVER discovers benchmark identity
from text, quantity size, position, name, expected amount, or object order.

Accepts the typed dataclasses used by the four-project audit and the raw
signature-verified JSON used by the original-byte project-only scorer.
"""
from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any, Iterable


def _field(record: Any, name: str) -> Any:
    if isinstance(record, Mapping):
        return record.get(name)
    return getattr(record, name, None)


_COMPATIBLE_TRADES = {
    "floor_area": frozenset({"flooring"}),
    "floor_finish_area": frozenset({"tiling", "flooring"}),
    "ceiling_area": frozenset({"ceilings"}),
    # Both current source producers issue the typed canonical ceiling_lining
    # family. An independently sealed/mapped original ceiling must not be
    # discarded just because older consumer receipts said ceiling_area.
    "ceiling_lining": frozenset({"ceilings"}),
    "ceiling_finish_area": frozenset({"ceilings"}),
    "opening_area": frozenset({"doors", "windows"}),
    "opening_count": frozenset({"doors", "windows"}),
}

# Dimensional constraints on already-sealed source units, independent of
# benchmark expected values. Not a measurement unit conversion mechanism.
_AREA_UNITS = frozenset({"m²", "m2", "sqm"})
_COUNT_UNITS = frozenset({"ea", "each", "nr", "no", "no.", "number"})
_SOURCE_FAMILY_UNITS = {
    "floor_area": _AREA_UNITS,
    "floor_finish_area": _AREA_UNITS,
    "ceiling_area": _AREA_UNITS,
    "ceiling_lining": _AREA_UNITS,
    "ceiling_finish_area": _AREA_UNITS,
    "opening_area": _AREA_UNITS,
    "opening_count": _COUNT_UNITS,
}

def require_signed_v2_family_trade_integrity(
    *,
    verified_items: Iterable[Any],
    sealed_quantities: Iterable[Any],
    identity_bindings: Iterable[Any],
) -> None:
    """Reject trading away source-owned family and opening-kind semantics.

    All three inputs must be authenticated by the caller before this check;
    this negative commercial guard does not itself authenticate source files.
    Unmapped quantities remain unmapped and are never given benchmark refs.
    """
    items: dict[str, Any] = {}
    for item in verified_items:
        if _field(item, "denominator_eligible") is not True:
            continue
        key = _field(item, "item_id")
        if type(key) is not str or not key:
            raise ValueError("eligible frozen item has no exact canonical identity")
        if key in items:
            raise ValueError("duplicate eligible frozen item identity in mapped trade veto")
        items[key] = item
    by_refs: dict[tuple[str, ...], list[Any]] = {}
    # Legacy V1 floor receipts may predate current production uniqueness
    # guards. Before an independently bound physical floor contributes to
    # frozen V2, veto competing geometric floor_area receipts even when their
    # semantic keys or GROUPS of physical members differ. A floor_finish_area
    # material layer remains an independent, valid family.
    physical_floor_area_claims: dict[str, int] = {}
    # Record SOURCE-OWNED kind, not trade identity or label similarity. One
    # canonical physical opening cannot become a window in its gross AREA
    # and a door in its independently issued COUNT. This is a negative
    # proof over the *actual* signed opening rows, not a new kind inference
    # or permission to mint counts.
    opening_kind_claims: dict[str, set[str]] = {}
    opening_family_claim_counts: dict[tuple[str, str], int] = {}
    for quantity in sealed_quantities:
        family = _field(quantity, "family")
        semantic_key = _field(quantity, "semantic_key")
        typed_kind = None
        if family in {"opening_area", "opening_count"} and type(semantic_key) is str:
            prefix_kind = (
                (("door_area:", "door"), ("window_area:", "window"))
                if family == "opening_area"
                else (("door_count:", "door"), ("window_count:", "window"))
            )
            typed_kind = next((
                kind for prefix, kind in prefix_kind
                if semantic_key.startswith(prefix)
            ), None)
        if family in {"opening_area", "opening_count"} and _field(quantity, "abstained") is False:
            for physical_id in _field(quantity, "object_identity_refs") or ():
                if type(physical_id) is str and physical_id:
                    original_claim = (family, physical_id)
                    opening_family_claim_counts[original_claim] = (
                        opening_family_claim_counts.get(original_claim, 0) + 1
                    )
                    if typed_kind is not None:
                        opening_kind_claims.setdefault(physical_id, set()).add(typed_kind)
        refs = tuple(sorted(_field(quantity, "object_identity_refs") or ()))
        by_refs.setdefault(refs, []).append(quantity)

        if (_field(quantity, "family") == "floor_area"
                and _field(quantity, "abstained") is False):
            for floor_id in refs:
                if type(floor_id) is str and floor_id:
                    physical_floor_area_claims[floor_id] = (
                        physical_floor_area_claims.get(floor_id, 0) + 1
                    )

    for binding in identity_bindings:
        item = items.get(_field(binding, "benchmark_item_id"))
        if item is None:
            # The unchanged frozen reconciler rejects unknown bound items.
            continue
        raw_refs = _field(binding, "production_object_identity_refs")
        if (
            type(raw_refs) not in (list, tuple)
            or not raw_refs
            or any(type(ref) is not str or not ref or ref != ref.strip()
                   for ref in raw_refs)
            or len(set(raw_refs)) != len(raw_refs)
        ):
            raise ValueError("bound production object identity refs are not canonical")
        refs = tuple(sorted(raw_refs))
        if any(physical_floor_area_claims.get(floor_id, 0) > 1
               for floor_id in refs):
            raise ValueError(
                "same original physical floor has duplicate source-signed "
                "geometric floor area claims across semantic keys"
            )
        # An eligible mapping for this exact physical source identity must
        # never score a contradictory source-owned door/window classification,
        # even when AREA and COUNT are mapped to separately compatible trades.
        if any(
            len(opening_kind_claims.get(physical_id, ())) > 1
            for physical_id in refs
        ):
            raise ValueError(
                "signed opening area/count disagree on original physical door/window kind"
            )
        if any(
            opening_family_claim_counts.get((family, physical_id), 0) > 1
            for physical_id in refs
            for family in ("opening_area", "opening_count")
        ):
            raise ValueError(
                "multiple source opening quantities claim the same physical "
                "opening and measurement family"
            )
        candidates = by_refs.get(refs, ())
        declared_family = _field(binding, "production_family")
        if candidates and (
            type(declared_family) is not str
            or declared_family != declared_family.strip()
        ):
            raise ValueError(
                "mapped quantity identity requires its explicit original production family"
            )
        typed_candidates = [
            quantity for quantity in candidates
            if _field(quantity, "family") == declared_family
        ]
        if candidates and not typed_candidates:
            raise ValueError(
                "mapped quantity identity requires its explicit original production family"
            )
        for quantity in candidates:
            family = _field(quantity, "family")
            if family != declared_family:
                # One independently sealed physical door can legitimately
                # produce BOTH an opening_area and an opening_count.  The
                # unchanged exact-identity reconciler independently joins on
                # refs PLUS production_family, so cross-family quantities
                # here are not mapped or misclassified by this binding.
                continue
            trade = _field(item, "trade_category")
            # An unknown source-owned family has NO audited trade meaning.
            # Never interpret absence from the allowlist as permission to
            # reclassify an independently bound item into any frozen trade.
            # Unmapped source quantities are unaffected.
            allowed = _COMPATIBLE_TRADES.get(family)
            if allowed is None:
                raise ValueError(
                    "mapped quantity family has no verified benchmark trade semantics"
                )
            if trade not in allowed:
                raise ValueError(
                    "bound production family cannot be reclassified as benchmark trade"
                )
            if family == "floor_finish_area" and trade == "tiling":
                # The real cross-view floor-finish producer signs
                # floor_finish_area:<canonical-floor>:<source-code>:<semantic>.
                # Its authenticated material definition allows TILE, VINYL
                # and EPOXY. A physical floor match alone cannot turn a
                # vinyl/epoxy finish into FT2/FT3 tiling benchmark credit.
                # Requiring source's signed terminal material role is a
                # NEGATIVE trade veto, never an independent material issuer.
                finish_key = _field(quantity, "semantic_key")
                parts = (
                    finish_key.split(":")
                    if type(finish_key) is str else ()
                )
                if (
                    len(parts) != 4
                    or parts[0] != "floor_finish_area"
                    or not all(
                        type(part) is str and part and part == part.strip()
                        for part in parts
                    )
                    or parts[-1] != "tile"
                    or len(refs) != 1
                    or parts[1] != refs[0]
                ):
                    raise ValueError(
                        "mapped tiling requires original source-signed tile "
                        "floor finish material semantics and exact physical floor identity"
                    )
            # The higher-level V1 signed receipt verifier guarantees a unit
            # exists. A missing unit in source-neutral helper-only test data
            # is left to that gate; a PRESENT incompatible source-owned unit
            # can never be silently reclassified as a benchmark area/count.
            unit = _field(quantity, "unit")
            if unit is not None and (
                type(unit) is not str
                or unit != unit.strip()
                or unit.casefold() not in _SOURCE_FAMILY_UNITS[family]
            ):
                raise ValueError(
                    "bound signed source unit disagrees with physical family dimension"
                )
            if family == "opening_count":
                # A source-authenticated count has an integer cardinality.
                # Do not accept a fractional, negative, boolean or nonfinite
                # signed count as an exact independently mapped door/window
                # item. Abstentions remain unscored by the unchanged evaluator.
                value = _field(quantity, "value")
                abstained = _field(quantity, "abstained")
                if abstained is False and value is None:
                    raise ValueError(
                        "mapped non-abstained opening count requires source-owned numeric cardinality"
                    )
                if value is not None and abstained is False:
                    if (
                        type(value) not in (int, float)
                        or not math.isfinite(value)
                        or value < 1
                        or value != int(value)
                    ):
                        raise ValueError(
                            "mapped opening count must be a positive whole number"
                        )
            if family in {"opening_area", "opening_count"}:
                semantic_key = _field(quantity, "semantic_key")
                if type(semantic_key) is not str:
                    raise ValueError("source-owned opening semantic identity is missing")
                typed_prefixes = (
                    ("window_area:", "windows"),
                    ("door_area:", "doors"),
                ) if family == "opening_area" else (
                    ("window_count:", "windows"),
                    ("door_count:", "doors"),
                )
                typed_trade = next(
                    (owned_trade for prefix, owned_trade in typed_prefixes
                     if semantic_key.startswith(prefix)),
                    None,
                )
                if typed_trade is None or (
                    semantic_key != semantic_key.strip()
                    or not any(
                        semantic_key.startswith(prefix)
                        and bool(semantic_key[len(prefix):].strip())
                        and semantic_key[len(prefix):] == semantic_key[len(prefix):].strip()
                        for prefix, _ in typed_prefixes
                    )
                ):
                    raise ValueError(
                        "mapped opening has no source-owned door/window kind or complete source identity"
                    )
                if trade != typed_trade:
                    raise ValueError(
                        "source-owned opening kind disagrees with benchmark trade"
                    )
                if family == "opening_area" and _field(quantity, "abstained") is False:
                    # The source opening AREA producer signs ONE canonical
                    # physical opening in BOTH its semantic suffix and input
                    # entity IDs. A valid signature/kind alone may not be
                    # rebound to a different physical opening or a group.
                    # Opening COUNT has its own source-complete scope and is
                    # intentionally not subject to this one-area identity.
                    signed_opening_id = semantic_key.split(":", 1)[1]
                    if len(refs) != 1 or signed_opening_id != refs[0]:
                        raise ValueError(
                            "mapped source-signed opening area identity disagrees "
                            "with its exact physical opening source member"
                        )


__all__ = ["require_signed_v2_family_trade_integrity"]
