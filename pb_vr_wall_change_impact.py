"""Fail-closed construction impact preview for a proposed VR wall.

Only server-owned assembly rates and page registrations may enter this module.
It deliberately does not create a wall, revise an issued drawing, or approve a quote.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
import json
import re
from typing import Mapping, Sequence

from pb_vr_wall_assembly_dependencies import WallConstructionPackage

_CENT = Decimal("0.01")
_MAX = Decimal("1000000000000")
_KEY = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_SHA = re.compile(r"[0-9a-fA-F]{64}\Z")


def _money(value: Decimal) -> Decimal:
    if not value.is_finite() or abs(value) > _MAX:
        raise ValueError("construction_cost_out_of_range")
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _decimal(text: str, field: str) -> Decimal:
    if type(text) is not str or not 1 <= len(text) <= 40:
        raise ValueError(field + "_invalid")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(field + "_invalid") from exc
    if not value.is_finite() or value < 0 or value > _MAX:
        raise ValueError(field + "_invalid")
    return value


@dataclass(frozen=True)
class ProposedWallUnitRate:
    """Tenant-authenticated, project-specific rate; NEVER accepted from JSON."""
    rate_id: str
    trade: str
    element: str
    unit: str
    unit_cost: str
    source_evidence_id: str

    def __post_init__(self):
        for field in ("rate_id", "source_evidence_id"):
            if not _KEY.fullmatch(getattr(self, field) or ""):
                raise ValueError("rate_" + field + "_invalid")
        if not all(type(v) is str and 0 < len(v) <= 160 for v in
                   (self.trade, self.element, self.unit)):
            raise ValueError("rate_target_invalid")
        _decimal(self.unit_cost, "unit_cost")


@dataclass(frozen=True)
class ProposedWallRateBook:
    tenant_id: str
    workspace_id: str
    assembly_profile_id: str
    revision: str
    currency: str
    rates: tuple[ProposedWallUnitRate, ...]

    def __post_init__(self):
        for field in ("tenant_id", "workspace_id", "assembly_profile_id", "revision"):
            value = getattr(self, field)
            if type(value) is not str or not _KEY.fullmatch(value):
                raise ValueError("ratebook_" + field + "_invalid")
        if type(self.currency) is not str or not re.fullmatch("[A-Z]{3}", self.currency):
            raise ValueError("ratebook_currency_invalid")
        if type(self.rates) is not tuple or len(self.rates) > 3000:
            raise ValueError("ratebook_rates_invalid")
        keys = set()
        for rate in self.rates:
            if type(rate) is not ProposedWallUnitRate:
                raise ValueError("ratebook_untrusted_rate")
            key = (rate.trade, rate.element, rate.unit)
            if key in keys:
                raise ValueError("ratebook_ambiguous_line_rate")
            keys.add(key)


@dataclass(frozen=True)
class ProposedRelatedPage:
    """One independently authenticated page registration for drawing coordination."""
    page_index: int
    sheet_id: str
    registration_evidence_id: str
    affected: bool

    def __post_init__(self):
        if type(self.page_index) is not int or self.page_index < 0:
            raise ValueError("related_page_index_invalid")
        if not _KEY.fullmatch(self.sheet_id or "") or not _KEY.fullmatch(
            self.registration_evidence_id or ""
        ):
            raise ValueError("related_page_evidence_invalid")
        if type(self.affected) is not bool:
            raise ValueError("related_page_affected_invalid")


@dataclass(frozen=True)
class ProposedRelatedPageCensus:
    """Trusted producer's complete SAME-DOCUMENT universe, never client input."""
    source_sha256: str
    complete: bool
    pages: tuple[ProposedRelatedPage, ...]

    def __post_init__(self):
        if type(self.source_sha256) is not str or not _SHA.fullmatch(self.source_sha256):
            raise ValueError("related_page_source_invalid")
        if type(self.complete) is not bool or type(self.pages) is not tuple:
            raise ValueError("related_page_census_invalid")
        if not self.pages or len(self.pages) > 1000 or any(
            type(p) is not ProposedRelatedPage for p in self.pages
        ):
            raise ValueError("related_page_census_entries_invalid")
        if len({p.page_index for p in self.pages}) != len(self.pages):
            raise ValueError("related_page_index_duplicate")
        if len({p.sheet_id for p in self.pages}) != len(self.pages):
            raise ValueError("related_page_sheet_duplicate")


def preview_proposed_wall_impact(
    package: WallConstructionPackage, *,
    tenant_id: str,
    workspace_id: str,
    source_sha256: str,
    assembly_profile_id: str,
    rate_book: ProposedWallRateBook | None,
    page_census: ProposedRelatedPageCensus | None,
) -> dict:
    """Produce a deterministic priced and sheet-coordination REVIEW receipt.

    A missing rate, uncertain route, incomplete sheet universe or unapproved
    construction detail is explicitly blocked; 0 is never guessed for missing work.
    This output MUST NOT be treated as a persisted revision or construction quote.
    """
    if type(package) is not WallConstructionPackage:
        raise TypeError("trusted_construction_package_required")
    if not all(type(v) is str and _KEY.fullmatch(v) for v in
               (tenant_id, workspace_id, assembly_profile_id)):
        raise ValueError("preview_scope_invalid")
    if type(source_sha256) is not str or not _SHA.fullmatch(source_sha256):
        raise ValueError("preview_source_invalid")
    if rate_book is not None and (
        type(rate_book) is not ProposedWallRateBook or
        (rate_book.tenant_id, rate_book.workspace_id, rate_book.assembly_profile_id)
        != (tenant_id, workspace_id, assembly_profile_id)
    ):
        raise ValueError("foreign_or_untrusted_ratebook")
    if page_census is not None and (
        type(page_census) is not ProposedRelatedPageCensus or
        page_census.source_sha256.lower() != source_sha256.lower()
    ):
        raise ValueError("foreign_or_untrusted_page_census")

    lookup = {(r.trade, r.element, r.unit): r for r in rate_book.rates} if rate_book else {}
    lines = []
    missing = []
    total = Decimal("0.00")
    for line in package.quantities:
        rate = lookup.get((line.trade, line.element, line.unit))
        if rate is None:
            missing.append({"lineId": line.line_id, "reason": "company_rate_missing"})
            continue
        # Values come from typed server geometry calculations, not the browser.
        qty = Decimal(str(line.value))
        if qty < 0 or not qty.is_finite():
            raise ValueError("untrusted_derived_quantity")
        amount = _money(qty * _decimal(rate.unit_cost, "unit_cost"))
        total += amount
        lines.append({
            "lineId": line.line_id, "trade": line.trade, "element": line.element,
            "quantity": str(qty), "unit": line.unit,
            "rateId": rate.rate_id, "rateEvidenceId": rate.source_evidence_id,
            "unitCost": rate.unit_cost, "lineCost": format(amount, ".2f"),
        })
    total = _money(total)
    affected = sorted(
        (p for p in page_census.pages if p.affected), key=lambda p: p.page_index
    ) if page_census else []
    page_ready = bool(page_census and page_census.complete and affected)
    holds = list(package.coordination_required)
    if rate_book is None:
        holds.append("authenticated_company_ratebook_unavailable")
    if missing:
        holds.append("construction_line_rates_incomplete")
    if not page_ready:
        holds.append("related_page_registration_incomplete")
    holds = sorted(set(holds))
    source = {
        "scope": package.revision_scope_key,
        "tenant": tenant_id,
        "workspace": workspace_id,
        "source": source_sha256.lower(),
        "profile": assembly_profile_id,
        "rateRevision": rate_book.revision if rate_book else None,
        "lines": lines, "unpriced": missing,
        "affectedPages": [
            {"pageIndex": p.page_index, "sheetId": p.sheet_id,
             "registrationEvidenceId": p.registration_evidence_id}
            for p in affected
        ],
        "holds": holds,
    }
    digest = sha256(json.dumps(source, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "accepted": True, "reviewOnly": True, "persisted": False,
        "wallCreated": False, "relatedPagesRevised": False,
        "commercialPublicationAllowed": False, "quoteReady": False,
        "proposalId": package.proposal_id, "revisionScopeKey": package.revision_scope_key,
        "currency": rate_book.currency if rate_book else None,
        "rateBookRevision": rate_book.revision if rate_book else None,
        "pricedLines": lines, "unpricedLines": missing,
        "pricedSubtotalOnly": format(total, ".2f"),
        "pricedComplete": bool(rate_book and not missing and lines),
        "relatedPagesVerified": page_ready,
        "affectedPages": source["affectedPages"],
        "constructionHolds": holds,
        "impactReceiptSha256": digest,
    }
