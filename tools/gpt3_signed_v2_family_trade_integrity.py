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
    for quantity in sealed_quantities:
        refs = tuple(sorted(_field(quantity, "object_identity_refs") or ()))
        by_refs.setdefault(refs, []).append(quantity)

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
                        "mapped opening has no complete source-owned door/window kind"
                    )
                if trade != typed_trade:
                    raise ValueError(
                        "source-owned opening kind disagrees with benchmark trade"
                    )


__all__ = ["require_signed_v2_family_trade_integrity"]
