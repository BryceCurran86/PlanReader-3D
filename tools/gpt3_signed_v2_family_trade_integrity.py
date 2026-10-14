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
from typing import Any, Iterable


def _field(record: Any, name: str) -> Any:
    if isinstance(record, Mapping):
        return record.get(name)
    return getattr(record, name)


_COMPATIBLE_TRADES = {
    "floor_area": frozenset({"flooring"}),
    "floor_finish_area": frozenset({"tiling", "flooring"}),
    "ceiling_area": frozenset({"ceilings"}),
    "ceiling_finish_area": frozenset({"ceilings"}),
    "opening_area": frozenset({"doors", "windows"}),
    "opening_count": frozenset({"doors", "windows"}),
}

_TYPED_OPENINGS = {
    "window_area:": "windows",
    "door_area:": "doors",
    "window_count:": "windows",
    "door_count:": "doors",
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
    items = {
        _field(item, "item_id"): item for item in verified_items
        if _field(item, "denominator_eligible") is True
    }
    by_refs: dict[tuple[str, ...], list[Any]] = {}
    for quantity in sealed_quantities:
        refs = tuple(sorted(_field(quantity, "object_identity_refs") or ()))
        by_refs.setdefault(refs, []).append(quantity)

    for binding in identity_bindings:
        item = items.get(_field(binding, "benchmark_item_id"))
        if item is None:
            # The unchanged frozen reconciler rejects unknown bound items.
            continue
        refs = tuple(sorted(_field(binding, "production_object_identity_refs") or ()))
        for quantity in by_refs.get(refs, ()):
            family = _field(quantity, "family")
            if (
                _field(binding, "production_family") is None
                or family != _field(binding, "production_family")
            ):
                raise ValueError(
                    "mapped quantity identity requires its explicit original production family"
                )
            trade = _field(item, "trade_category")
            allowed = _COMPATIBLE_TRADES.get(family)
            if allowed is not None and trade not in allowed:
                raise ValueError(
                    "bound production family cannot be reclassified as benchmark trade"
                )
            if family in {"opening_area", "opening_count"}:
                semantic_key = _field(quantity, "semantic_key")
                if type(semantic_key) is not str:
                    raise ValueError("source-owned opening semantic identity is missing")
                for prefix, source_trade in _TYPED_OPENINGS.items():
                    if semantic_key.startswith(prefix):
                        if trade != source_trade:
                            raise ValueError(
                                "source-owned opening kind disagrees with benchmark trade"
                            )
                        break


__all__ = ["require_signed_v2_family_trade_integrity"]
