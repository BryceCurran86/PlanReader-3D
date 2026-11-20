"""Exact-cent, source-checked PlanReader VR what-if costing.

This is a PRICE PREVIEW over an existing authenticated correction quantity
preview, NEVER a source of quantities, a correction, a rate editor, or a quote.
Company rates are selected only by trusted server callbacks. Uses the same
component order, ROUND_HALF_UP and true gross margin basis as canonical
price_canonical_quantities(), extended by explicitly supplied contingency and
tax percentages. No estimated values or currencies are silently defaulted.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from pb_builder_edition_architecture import CanonicalCompanyRate
from pb_cross_trade_geometry_reuse import normalise_trade_unit, require_evidence_ids
from pb_editable_3d_quantity_recalculation import RecalculationTarget
from pb_takeoff_output_authority import TakeoffOutputRow
from pb_vr_editor_scene_manifest import VerifiedSourceWitness
from pb_vr_editor_readonly_wsgi import AuthorizedSceneWorkspace, EditorPrincipal

_CENT = Decimal("0.01")
_MAX_QTY = Decimal("100000000")
_MAX_AMOUNT = Decimal("1000000000000")
_HUNDRED = Decimal("100")
_CURRENCY = re.compile(r"[A-Z]{3}\Z")
_ALLOWED = frozenset(target.value for target in RecalculationTarget) - {
    RecalculationTarget.MANUAL_REVIEW_REQUIRED.value
}


def _decimal(value: object, name: str, upper: Decimal) -> Decimal:
    # Accept exact strings or finite Python floats from the trusted geometry
    # preview; reject bool, negative values, infinity and unbounded exponents.
    if type(value) not in (str, int, float) or (
        type(value) is str and (not value or len(value) > 48)
    ):
        raise ValueError(f"{name}_must_be_decimal")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{name}_invalid_decimal") from exc
    if not amount.is_finite() or amount < 0 or amount > upper:
        raise ValueError(f"{name}_out_of_range")
    return amount


def _money(amount: Decimal) -> Decimal:
    if not amount.is_finite() or abs(amount) > _MAX_AMOUNT:
        raise ValueError("cost_out_of_range")
    return amount.quantize(_CENT, rounding=ROUND_HALF_UP)


def _str(amount: Decimal) -> str:
    return format(amount, "f")


def _pct(value: object, name: str, *, less_than_100: bool = False) -> Decimal:
    v = _decimal(value, name, _HUNDRED)
    if less_than_100 and v >= _HUNDRED:
        raise ValueError(f"{name}_must_be_below_100")
    return v


@dataclass(frozen=True)
class LiveRateBinding:
    """Server-owned, explicit canonical-object/quantity-target rate selection.

    A wall's gross/net surface quantities may NOT both be charged through
    this engine. The original issued quantities retain authority elsewhere.
    """
    canonical_object_id: str
    target: str
    rate: CanonicalCompanyRate
    binding_evidence_ids: tuple[str, ...]

    def __post_init__(self):
        if not isinstance(self.canonical_object_id, str) or not self.canonical_object_id:
            raise ValueError("canonical_object_id_required")
        if self.target not in _ALLOWED:
            raise ValueError("unsupported_pricing_target")
        if type(self.rate) is not CanonicalCompanyRate:
            raise TypeError("rate_requires_canonical_company_rate")
        if not self.rate.evidence_ids:
            raise ValueError("rate_provenance_missing")
        evidence = require_evidence_ids(self.binding_evidence_ids, "binding_evidence_ids")
        if not evidence:
            raise ValueError("rate_binding_provenance_missing")
        object.__setattr__(self, "binding_evidence_ids", evidence)


@dataclass(frozen=True)
class LiveCostBook:
    """Read from the logged-in tenant's rate repository, never browser JSON."""
    tenant_id: str
    workspace_id: str
    source_sha256: str
    snapshot_id: str
    revision: str
    currency: str
    tax_pct: str
    contingency_pct: str
    bindings: tuple[LiveRateBinding, ...]
    evidence_ids: tuple[str, ...]

    def __post_init__(self):
        if not all(type(x) is str and x and len(x) <= 128 for x in (
            self.tenant_id, self.workspace_id, self.snapshot_id, self.revision
        )):
            raise ValueError("rate_book_scope_required")
        if type(self.source_sha256) is not str or re.fullmatch(
            "[a-fA-F0-9]{64}", self.source_sha256
        ) is None:
            raise ValueError("rate_book_source_sha_required")
        if type(self.currency) is not str or _CURRENCY.fullmatch(self.currency) is None:
            raise ValueError("rate_book_currency_required")
        _pct(self.tax_pct, "tax_pct")
        _pct(self.contingency_pct, "contingency_pct")
        if type(self.bindings) is not tuple or len(self.bindings) > 2000:
            raise ValueError("rate_book_bindings_invalid")
        evidence = require_evidence_ids(self.evidence_ids, "book_evidence_ids")
        if not evidence:
            raise ValueError("rate_book_evidence_required")
        object.__setattr__(self, "evidence_ids", evidence)
        seen = set()
        by_object: dict[str, set[str]] = {}
        for item in self.bindings:
            if type(item) is not LiveRateBinding:
                raise TypeError("untrusted_rate_binding_type")
            key = (item.canonical_object_id, item.target)
            if key in seen:
                raise ValueError("duplicate_object_quantity_rate")
            seen.add(key)
            by_object.setdefault(item.canonical_object_id, set()).add(item.target)
            if item.rate.currency != self.currency:
                raise ValueError("mixed_rate_currencies")
        for targets in by_object.values():
            if {"wall_gross_area", "wall_net_area"}.issubset(targets):
                raise ValueError("wall_gross_net_double_pricing_forbidden")


def _components(quantity: Decimal, rate: CanonicalCompanyRate,
                book: LiveCostBook) -> dict[str, Decimal]:
    # Identical per-component rounding and true margin calculation to
    # canonical price_canonical_quantities() when contingency_pct=0.
    material_exact = quantity * _decimal(
        rate.material_cost_per_unit, "material_cost_per_unit", _MAX_QTY
    )
    material = _money(material_exact)
    waste = _money(material_exact * _pct(rate.material_waste_pct, "waste_pct") / _HUNDRED)
    labour = _money(quantity * _decimal(rate.labour_cost_per_unit, "labour_rate", _MAX_QTY))
    subcontract = _money(quantity * _decimal(
        rate.subcontract_cost_per_unit, "subcontract_rate", _MAX_QTY
    ))
    plant = _money(quantity * _decimal(rate.plant_cost_per_unit, "plant_rate", _MAX_QTY))
    direct = _money(material + waste + labour + subcontract + plant)
    overhead = _money(direct * _pct(rate.overhead_pct, "overhead_pct") / _HUNDRED)
    contingency = _money((direct + overhead) * _pct(
        book.contingency_pct, "contingency_pct"
    ) / _HUNDRED)
    cost_before_margin = _money(direct + overhead + contingency)
    margin_ratio = _pct(rate.gross_margin_pct, "gross_margin_pct",
                        less_than_100=True) / _HUNDRED
    sell = _money(cost_before_margin / (Decimal(1) - margin_ratio))
    margin = _money(sell - cost_before_margin)
    tax = _money(sell * _pct(book.tax_pct, "tax_pct") / _HUNDRED)
    gross = _money(sell + tax)
    return {
        "material": material, "waste": waste, "labour": labour,
        "subcontract": subcontract, "plant": plant, "direct": direct,
        "overhead": overhead, "contingency": contingency,
        "costBeforeMargin": cost_before_margin, "margin": margin,
        "sellExTax": sell, "tax": tax, "sellIncTax": gross,
    }


def price_live_correction_preview(
    command: Mapping[str, Any], quantity_preview: Mapping[str, Any], *,
    principal: EditorPrincipal, workspace: AuthorizedSceneWorkspace,
    book: LiveCostBook,
) -> dict[str, Any]:
    """Price ONLY server-verified original-source correction impacts.

    No browser supplied rate, quantity or canonical ID is trusted. Missing
    rate bindings, unsupported targets and manual review block completeness;
    subtotal amounts are always labelled PARTIAL until all impacts are priced.
    """
    if not isinstance(principal, EditorPrincipal) or not isinstance(
        workspace, AuthorizedSceneWorkspace
    ) or type(book) is not LiveCostBook:
        raise ValueError("trusted_server_context_required")
    scope = workspace.scope
    if (principal.tenant_id != workspace.tenant_id or
        scope.workspace_id not in principal.allowed_preview_workspace_ids or
        book.tenant_id != principal.tenant_id or
        book.workspace_id != scope.workspace_id or
        book.snapshot_id != scope.snapshot_id or
        book.source_sha256.lower() != scope.source_sha256.lower()):
        raise ValueError("cost_book_tenant_or_source_scope_mismatch")
    if not isinstance(command, Mapping) or not isinstance(quantity_preview, Mapping):
        raise ValueError("source_checked_correction_required")
    if (quantity_preview.get("accepted") is not True or
        quantity_preview.get("validationState") != "valid_preview_only" or
        quantity_preview.get("persisted") is not False or
        quantity_preview.get("commercialPublicationAllowed") is not False or
        quantity_preview.get("requiresApproval") is not True or
        quantity_preview.get("blockingReasons") != [] or
        quantity_preview.get("commandId") != command.get("commandId") or
        quantity_preview.get("targetObjectId") != command.get("targetObjectId") or
        quantity_preview.get("previousObjectRevision") != command.get("targetRevisionHash") or
        command.get("targetCanonicalId") != workspace.canonical_object_ids.get(
            command.get("targetObjectId")
        )):
        raise ValueError("unverified_or_stale_quantity_preview")
    impacts = quantity_preview.get("quantityImpacts")
    if not isinstance(impacts, list) or not 1 <= len(impacts) <= 100:
        raise ValueError("quantity_impacts_missing_or_excessive")
    canonical_id = command["targetCanonicalId"]
    by_target = {
        binding.target: binding for binding in book.bindings
        if binding.canonical_object_id == canonical_id
    }
    lines: list[dict[str, Any]] = []
    unpriced: list[dict[str, str]] = []
    seen_targets: set[str] = set()
    keys = ("material", "waste", "labour", "subcontract", "plant",
            "direct", "overhead", "contingency", "costBeforeMargin",
            "margin", "sellExTax", "tax", "sellIncTax")
    before_totals = {key: Decimal("0.00") for key in keys}
    after_totals = {key: Decimal("0.00") for key in keys}

    for impact in impacts:
        if not isinstance(impact, dict) or not isinstance(impact.get("target"), str):
            raise ValueError("malformed_quantity_impact")
        target = impact["target"]
        if target in seen_targets:
            raise ValueError("duplicate_quantity_impact")
        seen_targets.add(target)
        binding = by_target.get(target)
        raw_unit = impact.get("unit")
        if (impact.get("status") != "recalculated" or
            type(impact.get("oldValue")) not in (int, float) or
            type(impact.get("proposedValue")) not in (int, float)):
            unpriced.append({"target": target, "reason": "manual_review_or_missing_quantity"})
            continue
        if binding is None:
            unpriced.append({"target": target, "reason": "no_source_bound_company_rate"})
            continue
        if not isinstance(raw_unit, str) or (
            normalise_trade_unit(raw_unit) != binding.rate.unit
        ):
            unpriced.append({"target": target, "reason": "rate_unit_mismatch"})
            continue
        try:
            previous_qty = _decimal(impact["oldValue"], "old_quantity", _MAX_QTY)
            proposed_qty = _decimal(impact["proposedValue"], "new_quantity", _MAX_QTY)
            before = _components(previous_qty, binding.rate, book)
            after = _components(proposed_qty, binding.rate, book)
        except (ValueError, InvalidOperation, ArithmeticError):
            unpriced.append({"target": target, "reason": "nonfinite_or_unbounded_quantity"})
            continue
        for key in keys:
            before_totals[key] += before[key]
            after_totals[key] += after[key]
        lines.append({
            "target": target, "rateKey": binding.rate.rate_key,
            "rateRevision": book.revision,
            "rateEvidenceIds": list(binding.rate.evidence_ids),
            "bindingEvidenceIds": list(binding.binding_evidence_ids),
            "previousQuantity": _str(previous_qty),
            "proposedQuantity": _str(proposed_qty),
            "unit": binding.rate.unit,
            "before": {k: _str(v) for k, v in before.items()},
            "after": {k: _str(v) for k, v in after.items()},
            "deltaIncTax": _str(_money(after["sellIncTax"] - before["sellIncTax"])),
        })
    complete = bool(lines) and not unpriced
    before_sum = {key: _money(value) for key, value in before_totals.items()}
    after_sum = {key: _money(value) for key, value in after_totals.items()}
    receipt_data = {
        "workspace": scope.workspace_id, "snapshot": scope.snapshot_id,
        "source": scope.source_sha256.lower(), "modelRevision": scope.model_revision,
        "object": canonical_id, "commandId": quantity_preview["commandId"],
        "previousRevision": quantity_preview["previousObjectRevision"],
        "previewRevision": quantity_preview["previewObjectRevision"],
        "rateRevision": book.revision, "currency": book.currency,
        "lines": lines, "unpriced": unpriced,
    }
    receipt = sha256(json.dumps(receipt_data, sort_keys=True,
                                separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "accepted": True, "validationState": "cost_preview_only",
        "commandId": quantity_preview["commandId"],
        "targetObjectId": quantity_preview["targetObjectId"],
        "previousObjectRevision": quantity_preview["previousObjectRevision"],
        "previewObjectRevision": quantity_preview["previewObjectRevision"],
        "workspaceId": scope.workspace_id, "snapshotId": scope.snapshot_id,
        "rateBookRevision": book.revision, "currency": book.currency,
        "taxPct": _str(_pct(book.tax_pct, "tax_pct")),
        "contingencyPct": _str(_pct(book.contingency_pct, "contingency_pct")),
        "pricedComplete": complete, "partialTotalsOnly": not complete,
        "quoteReady": False, "requiresApproval": True,
        "persisted": False, "commercialPublicationAllowed": False,
        "lines": lines, "unpriced": unpriced,
        "totals": {
            "before": {k: _str(v) for k, v in before_sum.items()},
            "after": {k: _str(v) for k, v in after_sum.items()},
            "delta": {k: _str(_money(after_sum[k] - before_sum[k])) for k in keys},
        },
        "costPreviewReceiptSha256": receipt,
    }


@dataclass(frozen=True)
class CatalogueRateBinding:
    """Company rate explicitly attached to a catalogue selection and verified takeoff row."""
    catalogue_item_id: str
    quantity_id: str
    canonical_object_id: str
    rate_book_revision: str
    rate: CanonicalCompanyRate
    evidence_ids: tuple[str, ...]

    def __post_init__(self):
        if not all(isinstance(value, str) and 0 < len(value) <= 180 for value in (
            self.catalogue_item_id, self.quantity_id, self.canonical_object_id,
            self.rate_book_revision,
        )):
            raise ValueError("catalogue_rate_identity_required")
        if type(self.rate) is not CanonicalCompanyRate:
            raise TypeError("rate_requires_canonical_company_rate")
        evidence = require_evidence_ids(self.evidence_ids, "catalogue_binding_evidence")
        if not evidence:
            raise ValueError("catalogue_rate_binding_provenance_missing")
        object.__setattr__(self, "evidence_ids", evidence)


_SELECTION_FIELDS = frozenset({
    "requestId", "workspaceId", "projectId", "documentId", "revisionId",
    "sourceSha256", "snapshotId", "modelRevision", "objectId", "objectRevision",
    "canonicalObjectId", "quantityId", "catalogueItemId",
})


def resolve_catalogue_quantity(selection, *, principal, workspace, ledger, rows):
    """Find one current firm takeoff row from an authenticated ledger."""
    scope = workspace.scope
    if (principal.tenant_id != workspace.tenant_id or
        scope.workspace_id not in principal.allowed_preview_workspace_ids):
        raise ValueError("catalogue_cost_access_denied")
    if set(selection) != _SELECTION_FIELDS or not all(
        isinstance(selection[field], str) and 0 < len(selection[field]) <= 180
        for field in _SELECTION_FIELDS - {"modelRevision"}
    ):
        raise ValueError("catalogue_cost_request_schema")
    if (selection["workspaceId"] != scope.workspace_id or selection["projectId"] != scope.project_id or
        selection["documentId"] != scope.document_id or selection["revisionId"] != scope.revision_id or
        selection["sourceSha256"] != scope.source_sha256.lower() or selection["snapshotId"] != scope.snapshot_id or
        type(selection["modelRevision"]) is not int or selection["modelRevision"] != scope.model_revision):
        raise ValueError("catalogue_cost_source_scope_changed")
    object_id = selection["objectId"]
    obj = ledger.get_object(object_id)
    owner = next((entry for entry in workspace.objects if entry.object_id == object_id), None)
    witness = workspace.source_witnesses.get(object_id)
    if (obj is None or owner is None or obj.revision_hash != selection["objectRevision"] or
        obj.revision_hash != owner.revision_hash or
        selection["canonicalObjectId"] != workspace.canonical_object_ids.get(object_id) or
        not isinstance(witness, VerifiedSourceWitness) or not witness.matches(scope, obj) or
        not witness.matches(scope, owner)):
        raise ValueError("catalogue_cost_owner_unverified")
    quantity_id = selection["quantityId"]
    if quantity_id not in obj.dependent_quantity_ids or quantity_id not in owner.dependent_quantity_ids:
        raise ValueError("verified_quantity_not_linked")
    if len(rows) > 2000:
        raise ValueError("catalogue_quantity_safety_cap")
    matches = [row for row in rows if isinstance(row, TakeoffOutputRow) and row.quantity_id == quantity_id]
    if len(matches) != 1:
        raise ValueError("verified_quantity_missing_or_ambiguous")
    row = matches[0]
    if (row.geometry_ref != object_id or row.revision_hash != obj.revision_hash or
        row.source_page != witness.source_page or row.source_sheet != witness.source_sheet or
        row.authority_status != "firm" or row.is_publishable is not True or row.blocking_reasons):
        raise ValueError("quantity_not_verified_for_current_source")
    return row


def price_catalogue_selection(selection, *, row, workspace, book, binding):
    """Exact-cent preview using the existing company costing formula."""
    scope = workspace.scope
    if (type(book) is not LiveCostBook or type(binding) is not CatalogueRateBinding or
        book.workspace_id != scope.workspace_id or book.tenant_id != workspace.tenant_id or
        book.snapshot_id != scope.snapshot_id or book.source_sha256.lower() != scope.source_sha256.lower() or
        binding.catalogue_item_id != selection["catalogueItemId"] or
        binding.quantity_id != row.quantity_id or binding.canonical_object_id != selection["canonicalObjectId"] or
        binding.rate_book_revision != book.revision or binding.rate.currency != book.currency or
        binding.rate.unit != normalise_trade_unit(row.unit)):
        raise ValueError("catalogue_rate_missing_or_mismatched")
    quantity = _decimal(row.value, "catalogue_quantity", _MAX_QTY)
    if quantity <= 0:
        raise ValueError("catalogue_quantity_must_be_positive")
    total = _components(quantity, binding.rate, book)
    return {
        **selection, "accepted": True, "previewOnly": True, "commercialPublicationAllowed": False,
        "quantity": _str(quantity), "unit": binding.rate.unit,
        "currency": book.currency, "priceExTax": _str(total["sellExTax"]),
        "priceIncTax": _str(total["sellIncTax"]), "rateKey": binding.rate.rate_key,
        "rateBookRevision": book.revision, "rateEvidenceIds": list(binding.rate.evidence_ids),
        "bindingEvidenceIds": list(binding.evidence_ids),
    }
