"""PlanReader Builder Edition Architecture & Multi-Trade Aggregation Engine (AG-30).

Provides the unified commercial aggregation engine for PlanReader Builder Edition:
1. Composite Trade Package Aggregator:
   Hierarchically groups canonical 21-field takeoff rows into 11 master trade packages:
   - 01: Substructure & Groundworks
   - 02: Concrete & Formwork
   - 03: Post-Tensioning & Stressing
   - 04: Structural Steel & Metalwork
   - 05: Masonry & Blockwork
   - 06: Carpentry & Framing
   - 07: Flooring & Tiling
   - 08: Linings & Plasterboard
   - 09: Painting & Protective Coatings
   - 10: Plumbing & Drainage
   - 11: Electrical & Communications

2. Commercial Pricing Engine:
   Computes line-item costs, trade subtotals, builder preliminaries/overheads (%),
   contingency allowances (%), and builder gross margin (%), deriving the final Contract Sum.

3. Bill of Quantities (BoQ) Export:
   Generates clean, hierarchical BoQ datasets with strict provenance, units, and audit trails.

4. Project Health & Completeness Dashboard:
   Evaluates project coverage, pricing completeness, provisional risk, and overall readiness score.

Strictly complies with:
- pb_takeoff_row_contract (21-field core contract)
- TAKEOFF_UNITS: ('m²', 'lm', 'No.', 'item', 'L', 'allowance')

The legacy engine above is separate from canonical costing
(``price_canonical_quantities``): company rates applied to verified canonical
trade quantities without changing their identity.  That path has its own unit
rule (it also prices m³) and its own margin basis (gross margin on sell price;
the legacy ``builder_margin_pct`` is markup on cost).
"""
from __future__ import annotations

import csv
import io
import json
import math
import numbers
from dataclasses import asdict, dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pb_takeoff_row_contract as takeoff_contract
from pb_cross_trade_geometry_reuse import (
    DerivedTradeQuantity,
    normalise_trade_unit,
    require_evidence_ids,
)
from pb_migration_contracts import stable_contract_id

BUILDER_EDITION_VERSION = "2.0.0"
DEFAULT_BUILDER_MARGIN_PCT = 15.0
DEFAULT_PRELIMINARIES_PCT = 8.0
DEFAULT_CONTINGENCY_PCT = 5.0

MASTER_TRADE_PACKAGES: Dict[str, Tuple[str, ...]] = {
    "01_substructure": ("Footings", "Substructure", "Slab on ground", "Trenching", "Groundworks"),
    "02_concrete_formwork": ("Concrete", "Formwork", "Suspended slab", "Columns", "Beams", "Stairs"),
    "03_post_tensioning": ("Post-Tension", "PT", "Stressing", "Tendon", "Grouting"),
    "04_structural_steel": ("Steel", "Structural steel", "Purlins", "Bracing", "Lintels"),
    "05_masonry": ("Masonry", "Brickwork", "Blockwork", "Brick", "Block"),
    "06_carpentry": ("Carpentry", "Framing", "Studs", "Trusses", "Subfloor", "Eaves", "Cladding"),
    "07_flooring_tiling": ("Flooring", "Tiling", "Tiles", "Carpet", "Timber", "Screed", "Waterproofing"),
    "08_linings_plasterboard": ("Linings", "Plasterboard", "Ceilings", "Bulkheads", "Cornices"),
    "09_painting": ("Painting", "Paint", "Finishes", "Sealer", "Coatings"),
    "10_plumbing_drainage": ("Plumbing", "Drainage", "Hydraulic", "Sanitary", "Water supply", "Sewer"),
    "11_electrical_comms": ("Electrical", "Lighting", "Power", "GPO", "Comms", "Data", "Switchboard"),
}


def classify_trade_package(row: Mapping[str, Any]) -> str:
    """Classify a 21-field takeoff row into its canonical master trade package."""
    element = str(row.get("element") or "").lower()
    substrate = str(row.get("substrate") or "").lower()
    section = str(row.get("section") or "").lower()
    notes = str(row.get("notes") or "").lower()
    source_ref = str(row.get("source_reference") or "").lower()
    combined = f"{element} {substrate} {section} {notes} {source_ref}"

    if any(k in combined for k in ("electrical", "switchboard", "gpo", "downlight", "luminaire", "cat6", "conduit", "tray")):
        return "11_electrical_comms"
    if any(k in combined for k in ("plumbing", "drainage", "sewer", "basin", "toilet", "tap", "sink", "pex", "stack", "dwv")):
        return "10_plumbing_drainage"
    if any(k in combined for k in ("post-tension", "pt slab", "strand", "tendon", "stressing")):
        return "03_post_tensioning"
    if any(k in combined for k in ("structural steel", "steel beam", "steel column", "ub40", "uc46", "shs", "pfc", "purlin", "rafter", "cleat", "steel")):
        return "04_structural_steel"
    if any(k in combined for k in ("brick", "blockwork", "mortar", "core fill", "cavity tie")):
        return "05_masonry"
    if any(k in combined for k in ("carpet", "timber floor", "hybrid", "tiled", "tile", "screed", "waterproofing", "quad beading")):
        return "07_flooring_tiling"
    if any(k in combined for k in ("plasterboard", "ceiling lining", "cornice", "bulkhead", "gyprock")):
        return "08_linings_plasterboard"
    if any(k in combined for k in ("paint", "acrylic", "sealer", "primer", "coats")):
        return "09_painting"
    if any(k in combined for k in ("framing", "stud", "plates", "truss", "joist", "fascia", "weatherboard")):
        return "06_carpentry"
    if any(k in combined for k in ("formwork", "soffit", "drop panel", "edge board")):
        return "02_concrete_formwork"
    if any(k in combined for k in ("concrete", "footing", "pier", "slab on ground", "dpm")):
        return "01_substructure"

    # Default fallback based on section
    if "external" in section:
        return "05_masonry"
    return "08_linings_plasterboard"


@dataclass
class PricedLineItem:
    """A commercial line item in the Builder Edition bill of quantities."""
    item_no: str
    package_code: str
    section: str
    element: str
    location: str
    substrate: str
    quantity: float
    unit: str
    rate_per_unit: float
    direct_cost: float
    quantity_status: str
    inclusion_status: str
    confidence: str
    notes: str
    source_reference: str


@dataclass
class TradePackageSummary:
    """Financial and volumetric summary of a single trade package."""
    package_code: str
    package_name: str
    item_count: int
    direct_cost: float
    builder_margin_pct: float
    builder_margin_amount: float
    total_package_price: float
    items: List[PricedLineItem] = field(default_factory=list)


@dataclass
class ProjectCommercialEstimate:
    """Whole-of-project commercial estimate with margins, overheads, and grand total."""
    workspace_id: int
    job_no: str
    job_name: str
    direct_cost_subtotal: float
    preliminaries_pct: float
    preliminaries_amount: float
    contingency_pct: float
    contingency_amount: float
    builder_margin_pct: float
    builder_margin_amount: float
    grand_total_contract_sum: float
    packages: Dict[str, TradePackageSummary] = field(default_factory=dict)
    total_line_items: int = 0


@dataclass
class ProjectHealthReport:
    """Audit report measuring estimation completeness, data integrity, and risk."""
    workspace_id: int
    total_rows: int
    measured_rows: int
    estimated_rows: int
    provisional_rows: int
    rated_rows: int
    unrated_rows: int
    pricing_completeness_pct: float
    active_trade_packages: int
    readiness_score_pct: float
    warnings: List[str] = field(default_factory=list)
    healthy: bool = True


# ---------------------------------------------------------------------------
# Canonical costing: company rates applied to canonical trade quantities.
#
# Contract: a company rate NEVER changes a canonical object id, geometry, a
# measured quantity, or a quantity id.  Pricing is a pure function of
# (verified quantities, company rates); changing a rate reprices, it does not
# remeasure.  A quantity with no usable rate is UNPRICED with an explicit
# reason -- never zero-cost.  Units compare exactly after normalising aliases of
# the same unit; currencies are never guessed or mixed.
#
# Money maths (all arithmetic in Decimal, rounded half-up to the cent per
# component so every line foots exactly):
#   direct          = material + material waste + labour + subcontract + plant
#   cost_before_margin = direct + direct * overhead%
#   sell            = cost_before_margin / (1 - gross_margin%)
#   margin          = sell - cost_before_margin
# gross_margin_pct is margin ON SELL PRICE (see MARGIN_BASIS_GROSS_ON_SELL).
# It is NOT markup on cost, which is what the legacy BuilderEditionEngine
# below applies under the similar name builder_margin_pct.
# ---------------------------------------------------------------------------

MARGIN_BASIS_GROSS_ON_SELL = "gross_margin_on_sell_price"
UNPRICED_NO_RATE_KEY = "no_rate_key"
UNPRICED_NO_RATE_BINDING_EVIDENCE = "no_rate_binding_evidence"
UNPRICED_RATE_KEY_NOT_IN_RATE_SET = "rate_key_not_in_rate_set"

_COST_COMPONENT_FIELDS = (
    "material_cost_per_unit",
    "labour_cost_per_unit",
    "subcontract_cost_per_unit",
    "plant_cost_per_unit",
)
_PERCENT_FIELDS = ("material_waste_pct", "overhead_pct", "gross_margin_pct")
_CENT = Decimal("0.01")
_HUNDRED = Decimal(100)


def _real_number(name: str, value: Any) -> float:
    """A finite, non-negative real number; bool and numeric strings are rejected."""

    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be a real number, got {type(value).__name__}")
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")
    return number


def _decimal(value: float) -> Decimal:
    return Decimal(repr(float(value)))


def _cents(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CanonicalCompanyRate:
    """One company-owned unit-rate definition, independent of geometry.

    ``currency`` has no default: a guessed currency would let a rate silently
    price in the wrong money.  At least one cost component must be positive: a
    rate that prices nothing is indistinguishable from a missing rate, and a
    missing rate is UNPRICED, not zero-cost.
    """

    rate_key: str
    unit: str
    currency: str
    material_cost_per_unit: float = 0.0
    labour_cost_per_unit: float = 0.0
    subcontract_cost_per_unit: float = 0.0
    plant_cost_per_unit: float = 0.0
    material_waste_pct: float = 0.0
    overhead_pct: float = 0.0
    gross_margin_pct: float = 0.0
    evidence_ids: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        key = str(self.rate_key or "").strip()
        unit = normalise_trade_unit(self.unit)
        currency = str(self.currency or "").strip().upper()
        evidence = require_evidence_ids(self.evidence_ids, "evidence_ids")
        if not key:
            raise ValueError("rate_key must be non-empty")
        if not unit:
            raise ValueError("unit must be non-empty")
        if len(currency) != 3 or not (currency.isascii() and currency.isalpha()):
            raise ValueError("currency must be an explicit three-letter code")
        if not evidence:
            raise ValueError("company rate requires config/source provenance")
        numbers_by_field = {
            name: _real_number(name, getattr(self, name))
            for name in _COST_COMPONENT_FIELDS + _PERCENT_FIELDS
        }
        if not any(numbers_by_field[name] > 0.0 for name in _COST_COMPONENT_FIELDS):
            raise ValueError(
                "company rate needs at least one positive cost component "
                "(material, labour, subcontract or plant); leave the quantity "
                "unrated instead of pricing it at zero"
            )
        if numbers_by_field["gross_margin_pct"] >= 100.0:
            raise ValueError("gross_margin_pct must be less than 100")
        for name, number in numbers_by_field.items():
            object.__setattr__(self, name, number)
        object.__setattr__(self, "rate_key", key)
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "evidence_ids", evidence)


@dataclass(frozen=True)
class CanonicalCostLine:
    canonical_quantity_id: str
    rate_key: str
    host_object_id: str
    host_object_type: str
    trade_scope: str
    section: str
    element: str
    location: str
    substrate: str
    quantity: float
    unit: str
    quantity_status: str
    quantity_confidence: str
    currency: str
    material_base_cost: float
    material_waste_cost: float
    labour_cost: float
    subcontract_cost: float
    plant_cost: float
    direct_cost: float
    overhead_cost: float
    cost_before_margin: float
    gross_margin_pct: float
    margin_basis: str
    margin_amount: float
    sell_price: float
    rate_unit: str
    rate_material_cost_per_unit: float
    rate_labour_cost_per_unit: float
    rate_subcontract_cost_per_unit: float
    rate_plant_cost_per_unit: float
    rate_material_waste_pct: float
    rate_overhead_pct: float
    quantity_evidence_ids: Tuple[str, ...]
    spec_evidence_ids: Tuple[str, ...]
    rate_binding_evidence_ids: Tuple[str, ...]
    rate_evidence_ids: Tuple[str, ...]
    derivation_formula: str


@dataclass(frozen=True)
class CanonicalUnpricedQuantity:
    """A canonical quantity that could not be priced, and exactly why."""

    canonical_quantity_id: str
    reason: str
    rate_key: Optional[str]
    host_object_id: str
    host_object_type: str
    trade_scope: str
    element: str
    quantity: float
    unit: str


@dataclass(frozen=True)
class CanonicalCostingResult:
    """Priced lines plus every unpriced quantity, both in canonical-id order.

    ``complete`` is True only when at least one quantity was priced and none
    were left unpriced; totals over a partial result are partial totals.
    """

    lines: Tuple[CanonicalCostLine, ...]
    unpriced: Tuple[CanonicalUnpricedQuantity, ...]
    currency: Optional[str]
    direct_cost_total: float
    overhead_total: float
    margin_total: float
    sell_price_total: float
    complete: bool

    @property
    def unrated_quantity_ids(self) -> Tuple[str, ...]:
        return tuple(item.canonical_quantity_id for item in self.unpriced)


def _identity_text(value: object) -> str:
    return str(value or "").strip()


def _identity_ids(values: Sequence[str]) -> Tuple[str, ...]:
    return tuple(sorted({_identity_text(value) for value in values if _identity_text(value)}))


def canonical_quantity_id(quantity: DerivedTradeQuantity) -> str:
    """Stable identity of one canonical trade quantity.

    Covers every field that distinguishes one quantity from another (host,
    trade scope, section, element, location, substrate, value, unit, formula
    and the host/spec evidence sets) and nothing about company rates.
    Evidence ids are a set (order-insensitive) and text is whitespace-trimmed,
    so the same physical quantity always gets the same id.
    """

    if type(quantity) is not DerivedTradeQuantity:
        raise TypeError("quantity must be DerivedTradeQuantity")
    return stable_contract_id(
        "canonical_trade_quantity",
        {
            "host_object_id": _identity_text(quantity.host_object_id),
            "host_object_type": _identity_text(quantity.host_object_type),
            "trade_scope": _identity_text(quantity.trade_scope),
            "section": _identity_text(quantity.section),
            "element": _identity_text(quantity.element),
            "location": _identity_text(quantity.location),
            "substrate": _identity_text(quantity.substrate),
            "quantity": float(quantity.quantity) + 0.0,
            "unit": normalise_trade_unit(quantity.unit),
            "derivation_formula": _identity_text(quantity.derivation_formula),
            "host_evidence_ids": _identity_ids(quantity.host_evidence_ids),
            "spec_evidence_ids": _identity_ids(quantity.spec_evidence_ids),
        },
        digest_chars=32,
    )


def _unpriced_reason(
    quantity: DerivedTradeQuantity,
    rate_by_key: Mapping[str, CanonicalCompanyRate],
) -> Optional[str]:
    rate_key = str(quantity.rate_key or "").strip()
    if not rate_key:
        return UNPRICED_NO_RATE_KEY
    if not quantity.rate_binding_evidence_ids:
        return UNPRICED_NO_RATE_BINDING_EVIDENCE
    if rate_key not in rate_by_key:
        return UNPRICED_RATE_KEY_NOT_IN_RATE_SET
    return None


def price_canonical_quantities(
    quantities: Sequence[DerivedTradeQuantity],
    rates: Sequence[CanonicalCompanyRate],
) -> CanonicalCostingResult:
    """Apply company rate inputs without mutating source geometry or quantities.

    Fails closed (ValueError) on a duplicate canonical quantity, a duplicate
    rate key, a rate/quantity unit mismatch, or mixed currencies.  A quantity
    with no usable rate is reported in ``unpriced`` with a reason code.
    """

    quantities = tuple(quantities)
    rates = tuple(rates)

    rate_by_key: Dict[str, CanonicalCompanyRate] = {}
    for rate in rates:
        if type(rate) is not CanonicalCompanyRate:
            raise TypeError("rates must contain CanonicalCompanyRate values")
        if rate.rate_key in rate_by_key:
            raise ValueError(f"duplicate company rate_key {rate.rate_key!r}")
        rate_by_key[rate.rate_key] = rate

    prepared: List[Tuple[str, DerivedTradeQuantity]] = []
    seen_ids: set[str] = set()
    for quantity in quantities:
        if type(quantity) is not DerivedTradeQuantity:
            raise TypeError("quantities must contain DerivedTradeQuantity values")
        quantity_id = canonical_quantity_id(quantity)
        if quantity_id in seen_ids:
            raise ValueError(
                f"duplicate canonical quantity {quantity_id}: "
                "one quantity cannot be priced twice"
            )
        seen_ids.add(quantity_id)
        prepared.append((quantity_id, quantity))
    prepared.sort(key=lambda item: item[0])

    lines: List[CanonicalCostLine] = []
    unpriced: List[CanonicalUnpricedQuantity] = []
    currencies: set[str] = set()
    totals = {"direct": Decimal(0), "overhead": Decimal(0), "margin": Decimal(0), "sell": Decimal(0)}

    for quantity_id, quantity in prepared:
        reason = _unpriced_reason(quantity, rate_by_key)
        if reason is not None:
            unpriced.append(
                CanonicalUnpricedQuantity(
                    canonical_quantity_id=quantity_id,
                    reason=reason,
                    rate_key=(str(quantity.rate_key or "").strip() or None),
                    host_object_id=quantity.host_object_id,
                    host_object_type=quantity.host_object_type,
                    trade_scope=quantity.trade_scope,
                    element=quantity.element,
                    quantity=quantity.quantity,
                    unit=quantity.unit,
                )
            )
            continue

        rate_key = str(quantity.rate_key).strip()
        rate = rate_by_key[rate_key]
        quantity_unit = normalise_trade_unit(quantity.unit)
        if rate.unit != quantity_unit:
            raise ValueError(
                f"rate unit {rate.unit!r} does not match quantity unit "
                f"{quantity_unit!r} for {quantity_id}"
            )
        currencies.add(rate.currency)
        if len(currencies) > 1:
            raise ValueError("one canonical costing result cannot mix currencies")

        try:
            qty = _decimal(quantity.quantity)
            material_exact = qty * _decimal(rate.material_cost_per_unit)
            material_base = _cents(material_exact)
            material_waste = _cents(
                material_exact * _decimal(rate.material_waste_pct) / _HUNDRED
            )
            labour = _cents(qty * _decimal(rate.labour_cost_per_unit))
            subcontract = _cents(qty * _decimal(rate.subcontract_cost_per_unit))
            plant = _cents(qty * _decimal(rate.plant_cost_per_unit))
            direct = material_base + material_waste + labour + subcontract + plant
            overhead = _cents(direct * _decimal(rate.overhead_pct) / _HUNDRED)
            before_margin = direct + overhead
            margin_ratio = _decimal(rate.gross_margin_pct) / _HUNDRED
            sell = (
                _cents(before_margin / (Decimal(1) - margin_ratio))
                if margin_ratio > 0
                else before_margin
            )
            margin = sell - before_margin
        except InvalidOperation as exc:
            raise ValueError(f"cost out of range for {quantity_id}") from exc

        totals["direct"] += direct
        totals["overhead"] += overhead
        totals["margin"] += margin
        totals["sell"] += sell
        lines.append(
            CanonicalCostLine(
                canonical_quantity_id=quantity_id,
                rate_key=rate_key,
                host_object_id=quantity.host_object_id,
                host_object_type=quantity.host_object_type,
                trade_scope=quantity.trade_scope,
                section=quantity.section,
                element=quantity.element,
                location=quantity.location,
                substrate=quantity.substrate,
                quantity=quantity.quantity,
                unit=quantity_unit,
                quantity_status=quantity.status,
                quantity_confidence=quantity.confidence,
                currency=rate.currency,
                material_base_cost=float(material_base),
                material_waste_cost=float(material_waste),
                labour_cost=float(labour),
                subcontract_cost=float(subcontract),
                plant_cost=float(plant),
                direct_cost=float(direct),
                overhead_cost=float(overhead),
                cost_before_margin=float(before_margin),
                gross_margin_pct=rate.gross_margin_pct,
                margin_basis=MARGIN_BASIS_GROSS_ON_SELL,
                margin_amount=float(margin),
                sell_price=float(sell),
                rate_unit=rate.unit,
                rate_material_cost_per_unit=rate.material_cost_per_unit,
                rate_labour_cost_per_unit=rate.labour_cost_per_unit,
                rate_subcontract_cost_per_unit=rate.subcontract_cost_per_unit,
                rate_plant_cost_per_unit=rate.plant_cost_per_unit,
                rate_material_waste_pct=rate.material_waste_pct,
                rate_overhead_pct=rate.overhead_pct,
                quantity_evidence_ids=tuple(quantity.host_evidence_ids),
                spec_evidence_ids=tuple(quantity.spec_evidence_ids),
                rate_binding_evidence_ids=tuple(quantity.rate_binding_evidence_ids),
                rate_evidence_ids=tuple(rate.evidence_ids),
                derivation_formula=quantity.derivation_formula,
            )
        )

    return CanonicalCostingResult(
        lines=tuple(lines),
        unpriced=tuple(unpriced),
        currency=(next(iter(currencies)) if currencies else None),
        direct_cost_total=float(totals["direct"]),
        overhead_total=float(totals["overhead"]),
        margin_total=float(totals["margin"]),
        sell_price_total=float(totals["sell"]),
        complete=bool(lines) and not unpriced,
    )


class BuilderEditionEngine:
    """Core processing engine for PlanReader Builder Edition."""

    PACKAGE_NAMES: Dict[str, str] = {
        "01_substructure": "01 Substructure & Groundworks",
        "02_concrete_formwork": "02 Concrete & Formwork",
        "03_post_tensioning": "03 Post-Tensioning & Stressing",
        "04_structural_steel": "04 Structural Steel & Metalwork",
        "05_masonry": "05 Masonry, Brickwork & Blockwork",
        "06_carpentry": "06 Carpentry, Framing & Cladding",
        "07_flooring_tiling": "07 Flooring, Tiling & Screeds",
        "08_linings_plasterboard": "08 Linings, Plasterboard & Ceilings",
        "09_painting": "09 Painting & Protective Coatings",
        "10_plumbing_drainage": "10 Plumbing & Drainage",
        "11_electrical_comms": "11 Electrical & Communications",
    }

    def __init__(
        self,
        builder_margin_pct: float = DEFAULT_BUILDER_MARGIN_PCT,
        preliminaries_pct: float = DEFAULT_PRELIMINARIES_PCT,
        contingency_pct: float = DEFAULT_CONTINGENCY_PCT,
    ):
        self.builder_margin_pct = builder_margin_pct
        self.preliminaries_pct = preliminaries_pct
        self.contingency_pct = contingency_pct

    def aggregate_and_price_workspace(
        self,
        rows: Sequence[Mapping[str, Any]],
        workspace_id: int,
        job_no: str = "JOB-001",
        job_name: str = "Project",
    ) -> ProjectCommercialEstimate:
        """Group rows by master trade package, calculate direct costs, margins, and totals."""
        packages_dict: Dict[str, List[PricedLineItem]] = {code: [] for code in self.PACKAGE_NAMES}

        for idx, row in enumerate(rows):
            pkg = classify_trade_package(row)
            qty = float(row.get("quantity") or 0.0)
            rate = float(row.get("rate_per_unit") or 0.0)
            unit = str(row.get("unit") or "item")
            assert unit in takeoff_contract.TAKEOFF_UNITS, f"Invalid unit {unit}"

            direct_cost = round(qty * rate, 2)
            item_no = f"{pkg[:2]}.{len(packages_dict[pkg]) + 1:02d}"

            item = PricedLineItem(
                item_no=item_no,
                package_code=pkg,
                section=str(row.get("section") or ""),
                element=str(row.get("element") or ""),
                location=str(row.get("location") or ""),
                substrate=str(row.get("substrate") or ""),
                quantity=round(qty, 2),
                unit=unit,
                rate_per_unit=round(rate, 2),
                direct_cost=direct_cost,
                quantity_status=str(row.get("quantity_status") or "Measured"),
                inclusion_status=str(row.get("inclusion_status") or "INCLUSION"),
                confidence=str(row.get("confidence") or "Verified"),
                notes=str(row.get("notes") or ""),
                source_reference=str(row.get("source_reference") or ""),
            )
            packages_dict[pkg].append(item)

        direct_cost_subtotal = 0.0
        package_summaries: Dict[str, TradePackageSummary] = {}

        for code, pkg_name in self.PACKAGE_NAMES.items():
            items = packages_dict[code]
            pkg_direct = round(sum(i.direct_cost for i in items), 2)
            pkg_margin = round(pkg_direct * (self.builder_margin_pct / 100.0), 2)
            pkg_total = round(pkg_direct + pkg_margin, 2)
            direct_cost_subtotal += pkg_direct

            package_summaries[code] = TradePackageSummary(
                package_code=code,
                package_name=pkg_name,
                item_count=len(items),
                direct_cost=pkg_direct,
                builder_margin_pct=self.builder_margin_pct,
                builder_margin_amount=pkg_margin,
                total_package_price=pkg_total,
                items=items,
            )

        direct_cost_subtotal = round(direct_cost_subtotal, 2)
        prelims = round(direct_cost_subtotal * (self.preliminaries_pct / 100.0), 2)
        contingency = round(direct_cost_subtotal * (self.contingency_pct / 100.0), 2)
        base_with_overheads = direct_cost_subtotal + prelims + contingency
        margin = round(base_with_overheads * (self.builder_margin_pct / 100.0), 2)
        grand_total = round(base_with_overheads + margin, 2)

        return ProjectCommercialEstimate(
            workspace_id=int(workspace_id),
            job_no=str(job_no),
            job_name=str(job_name),
            direct_cost_subtotal=direct_cost_subtotal,
            preliminaries_pct=self.preliminaries_pct,
            preliminaries_amount=prelims,
            contingency_pct=self.contingency_pct,
            contingency_amount=contingency,
            builder_margin_pct=self.builder_margin_pct,
            builder_margin_amount=margin,
            grand_total_contract_sum=grand_total,
            packages=package_summaries,
            total_line_items=len(rows),
        )

    def export_bill_of_quantities_csv(self, estimate: ProjectCommercialEstimate) -> str:
        """Export hierarchical Bill of Quantities to CSV format."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Item No", "Package", "Section", "Element", "Location", "Substrate",
            "Quantity", "Unit", "Rate ($)", "Direct Cost ($)", "Status", "Notes", "Source Reference"
        ])

        for pkg in estimate.packages.values():
            if not pkg.items:
                continue
            writer.writerow([])
            writer.writerow([f"--- {pkg.package_name} ---", "", "", "", "", "", "", "", "", f"${pkg.direct_cost:,.2f}", "", "", ""])
            for item in pkg.items:
                writer.writerow([
                    item.item_no,
                    pkg.package_name,
                    item.section,
                    item.element,
                    item.location,
                    item.substrate,
                    f"{item.quantity:.2f}",
                    item.unit,
                    f"{item.rate_per_unit:.2f}",
                    f"{item.direct_cost:.2f}",
                    item.quantity_status,
                    item.notes,
                    item.source_reference,
                ])

        writer.writerow([])
        writer.writerow(["SUMMARY", "", "", "", "", "", "", "", "Direct Cost Subtotal", f"${estimate.direct_cost_subtotal:,.2f}"])
        writer.writerow(["SUMMARY", "", "", "", "", "", "", "", f"Preliminaries ({estimate.preliminaries_pct}%)", f"${estimate.preliminaries_amount:,.2f}"])
        writer.writerow(["SUMMARY", "", "", "", "", "", "", "", f"Contingency ({estimate.contingency_pct}%)", f"${estimate.contingency_amount:,.2f}"])
        writer.writerow(["SUMMARY", "", "", "", "", "", "", "", f"Builder Margin ({estimate.builder_margin_pct}%)", f"${estimate.builder_margin_amount:,.2f}"])
        writer.writerow(["SUMMARY", "", "", "", "", "", "", "", "GRAND TOTAL CONTRACT SUM", f"${estimate.grand_total_contract_sum:,.2f}"])

        return output.getvalue()

    def audit_project_health(self, rows: Sequence[Mapping[str, Any]], workspace_id: int) -> ProjectHealthReport:
        """Evaluate estimation coverage, missing rates, provisional risk, and project readiness."""
        total = len(rows)
        if total == 0:
            return ProjectHealthReport(
                workspace_id=workspace_id,
                total_rows=0,
                measured_rows=0,
                estimated_rows=0,
                provisional_rows=0,
                rated_rows=0,
                unrated_rows=0,
                pricing_completeness_pct=0.0,
                active_trade_packages=0,
                readiness_score_pct=0.0,
                warnings=["Workspace has zero takeoff rows."],
                healthy=False,
            )

        measured = sum(1 for r in rows if str(r.get("quantity_status")).lower() == "measured")
        estimated = sum(1 for r in rows if str(r.get("quantity_status")).lower() == "estimated")
        provisional = sum(1 for r in rows if str(r.get("quantity_status")).lower() == "provisional")
        rated = sum(1 for r in rows if float(r.get("rate_per_unit") or 0.0) > 0.0)
        unrated = total - rated

        active_pkgs = len(set(classify_trade_package(r) for r in rows))
        pricing_completeness = round((rated / total) * 100.0, 1)

        # Readiness score weights: measured coverage (50%), pricing completeness (30%), multi-trade breadth (20%)
        meas_score = (measured / total) * 50.0
        price_score = (rated / total) * 30.0
        trade_score = min(20.0, (active_pkgs / 7.0) * 20.0)
        readiness = round(meas_score + price_score + trade_score, 1)

        warnings: List[str] = []
        if unrated > 0:
            warnings.append(f"{unrated} of {total} items are missing unit rates.")
        if provisional > (total * 0.20):
            warnings.append(f"High provisional risk: {provisional} items ({provisional/total*100:.1f}%) are Provisional.")
        if active_pkgs < 3:
            warnings.append(f"Low trade diversity: Only {active_pkgs} trade packages are represented.")

        healthy = (readiness >= 70.0 and len(warnings) <= 1)

        return ProjectHealthReport(
            workspace_id=workspace_id,
            total_rows=total,
            measured_rows=measured,
            estimated_rows=estimated,
            provisional_rows=provisional,
            rated_rows=rated,
            unrated_rows=unrated,
            pricing_completeness_pct=pricing_completeness,
            active_trade_packages=active_pkgs,
            readiness_score_pct=readiness,
            warnings=warnings,
            healthy=healthy,
        )
