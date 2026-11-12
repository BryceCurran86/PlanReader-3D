"""Default-off consumer: ONE published opening-area quantity for ONE source-proven physical aperture (option A).

Why. ``compose_live_physical_opening_voids`` makes one canonical opening per physical-opening existence record
(``canonical_opening_id == physical_opening_id == record_id``) and ``publish_live_opening_area_quantities`` rejects only an IDENTICAL
id. Two existence records of one drawn aperture therefore each publish, and the customer is sold the same opening twice. The COUNT
authority already abstains on a pair whose identity is not corroborated; the area publication had no equivalent.

What it does (only when ``enabled`` is exactly ``True``). For every measured canonical opening it
  1. re-proves the existence record through the producer-owned ``PhysicalOpeningAuthority`` (a caller's ids certify nothing),
  2. asks the authority for the re-proven pairwise ``partition_receipt`` of every pair on one source page and verifies it,
  3. groups the openings with the shadow rule of ``pb_opening_aperture_equivalence_shadow`` (overlapping extent AND the very same
     printed-figure words, area and PHYSICAL host; anything else not proven apart is ambiguous),
  4. keeps ONE real member of a proven class only when its source observations STRICTLY CONTAIN every other member's (an
     order-independent evidence owner; never the first, nearest or smallest) and every member's quantity agrees in authority,
     status, unit, value and basis; otherwise the class is NOT consolidated and every member publishes exactly as before,
  5. returns a derived composition without the dropped members (or the SAME object when nothing consolidates) plus a record that
     keeps every member's id, source observations, quantity id and partition-receipt id.

It never adds a quantity, never raises authority, never edits an owner's quantity (the surviving row is the owner's own, byte for byte),
never touches the identity map, scorer or frozen files, and publishes nothing by itself: callers pass its composition to the existing
publication/export functions, so the seal and customer bijection see one consistent inventory. With ``enabled=False`` (the default)
the input composition is returned unchanged.

Authentication. Every pair verdict, printed-figure key and physical-host key comes from the producer-owned objects the public entry
points are given (``SourceVisibilityProducer`` and ``LiveWallOpeningAuthorityComposition``, both checked by exact type). The public
API has NO parameter through which a caller can supply a verdict, a record, a receipt or an evidence provider; the injectable core
(``_consolidate_with_provider``) is private and exists so tests can substitute the authority's answers.

This module replaces the quantity-level collapse that PR #4282 added inside ``publish_live_opening_area_quantities``. That collapse
(1) kept the first sorted member, (2) rewrote ``input_entity_ids`` to every member (the seal refuses a quantity that is not exactly one
canonical opening, and also any quantity that is not byte-identical to the owner's own recomputed one), (3) dropped every ambiguous or
unclassified quantity, and (4) trusted caller-supplied pair verdicts. It could not be repaired in place: it receives only quantities,
so it can neither authenticate a verdict nor keep the canonical inventory (which other publishers re-derive from the composition)
consistent. It has been removed; ``publish_live_opening_area_quantities`` is byte-identical to its pre-#4282 form.

Not wired into the live claim here: the integration publishes inside a function other lanes own (see the wiring note in the
architecture report). A caller that has the source producer, the wall-opening composition and the physical-void composition can call
``publish_live_opening_area_quantities_with_aperture_consolidation`` instead of ``publish_live_opening_area_quantities``.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import itertools
from typing import Any, Iterable, Mapping, Optional, Sequence

from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities
from pb_live_physical_opening_void_composition import LiveCanonicalOpeningObject, LivePhysicalOpeningVoidComposition
from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence, stable_contract_id
from pb_opening_aperture_equivalence_shadow import (
    DISTINCT, OVERLAPPING, UNPROVEN, ApertureClass, ApertureRecord, PairVerdict, resolve_aperture_equivalence,
)

SCHEMA_VERSION = "1.0.0"

CONSOLIDATED = "live_opening_aperture_consolidated_to_one_evidence_owner"
DISABLED = "live_opening_aperture_consolidation_disabled"
NO_OWNER = "aperture_class_has_no_order_independent_evidence_owner"
QUANTITIES_DIFFER = "aperture_class_members_differ_in_quantity_authority_status_unit_value_or_basis"
AMBIGUOUS = "aperture_class_equivalence_is_ambiguous"
NOT_REPROVEN = "opening_existence_not_reproven_by_the_physical_authority"
INVARIANT = "aperture_consolidation_publication_invariant_violated"


class ApertureConsolidationInvariantError(RuntimeError):
    """The consolidated publication is not exactly the original publication minus the dropped members' quantities."""


@dataclass(frozen=True)
class ApertureMember:
    physical_opening_id: str
    source_observation_ids: tuple[str, ...]
    quantity_id: str
    quantity_authority: str
    quantity_status: str
    area_basis: Optional[str]
    partition_receipt_ids: tuple[str, ...] = ()      # receipts of the pairs this member took part in, within its class


@dataclass(frozen=True)
class ConsolidatedAperture:
    class_id: str
    owner_physical_opening_id: str
    dropped_physical_opening_ids: tuple[str, ...]
    members: tuple[ApertureMember, ...]              # EVERY member, owner included, sorted by id
    area_m2: float
    reason_codes: tuple[str, ...] = (CONSOLIDATED,)


@dataclass(frozen=True)
class UnconsolidatedAperture:
    """A multi-member class that was NOT reduced: every member still publishes."""

    class_id: str
    member_physical_opening_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class ApertureConsolidationResult:
    enabled: bool
    composition: LivePhysicalOpeningVoidComposition
    consolidated: tuple[ConsolidatedAperture, ...] = ()
    unconsolidated: tuple[UnconsolidatedAperture, ...] = ()
    not_reproven_physical_opening_ids: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    grants_quantity: bool = False
    grants_firm_authority: bool = False
    schema_version: str = SCHEMA_VERSION

    @property
    def dropped_physical_opening_ids(self) -> tuple[str, ...]:
        return tuple(sorted(i for c in self.consolidated for i in c.dropped_physical_opening_ids))


# ----------------------------------------------------------------------------------------------------- pure rules
def evidence_owner(observations_by_member: Mapping[str, Iterable[str]]) -> Optional[str]:
    """The ONE member whose source observations strictly contain every other member's, or ``None``.

    Independent of member order. Equal sets, partial overlap and a tie for the largest set all return ``None``: nothing is
    chosen by id, size alone or position."""
    sets = {member: frozenset(values) for member, values in observations_by_member.items()}
    owners = [m for m, s in sets.items() if len(sets) > 1 and all(s > other for o, other in sets.items() if o != m)]
    return owners[0] if owners else None            # two members cannot each STRICTLY contain the other: at most one qualifies


def _quantity_signature(quantity: QuantityEvidence) -> tuple:
    return (quantity.authority, quantity.status, quantity.family, quantity.unit, quantity.value, quantity.metadata.get("area_basis"),
            quantity.metadata.get("opening_kind"))


def _member(opening: LiveCanonicalOpeningObject, quantity: QuantityEvidence, receipts: Iterable[str]) -> ApertureMember:
    return ApertureMember(
        physical_opening_id=opening.physical_opening_id, source_observation_ids=tuple(sorted(opening.source_observation_ids)),
        quantity_id=quantity.quantity_id, quantity_authority=str(quantity.authority), quantity_status=str(quantity.status),
        area_basis=quantity.metadata.get("area_basis"), partition_receipt_ids=tuple(sorted(set(receipts))))


def plan_consolidation(
    classes: Sequence[ApertureClass],
    openings: Mapping[str, LiveCanonicalOpeningObject],
    quantities: Mapping[str, QuantityEvidence],
    receipts: Mapping[frozenset, str],
) -> tuple[tuple[ConsolidatedAperture, ...], tuple[UnconsolidatedAperture, ...]]:
    """Pure: the classes that reduce to one owner, and every class that does not (a proven multi-member class with the reason it did
    not reduce, and every ambiguous record). Single-member classes the authority proves apart are not recorded."""
    consolidated: list[ConsolidatedAperture] = []
    unconsolidated: list[UnconsolidatedAperture] = []
    for aperture_class in sorted(classes, key=lambda c: c.class_id):
        members = tuple(sorted(aperture_class.member_ids))
        if aperture_class.is_ambiguous:             # an ambiguous record (one member or several) never disappears: it is recorded
            unconsolidated.append(UnconsolidatedAperture(aperture_class.class_id, members, (AMBIGUOUS, *aperture_class.reason_codes)))
            continue
        if len(members) < 2:
            continue
        if len({_quantity_signature(quantities[m]) for m in members}) != 1:
            unconsolidated.append(UnconsolidatedAperture(aperture_class.class_id, members, (QUANTITIES_DIFFER,)))
            continue
        owner = evidence_owner({m: openings[m].source_observation_ids for m in members})
        if owner is None:
            unconsolidated.append(UnconsolidatedAperture(aperture_class.class_id, members, (NO_OWNER,)))
            continue
        records = tuple(_member(openings[m], quantities[m], (r for pair, r in receipts.items() if m in pair and pair <= set(members)))
                        for m in members)
        consolidated.append(ConsolidatedAperture(
            class_id=aperture_class.class_id, owner_physical_opening_id=owner,
            dropped_physical_opening_ids=tuple(m for m in members if m != owner), members=records,
            area_m2=float(quantities[owner].value)))
    return tuple(consolidated), tuple(unconsolidated)


def derive_composition(composition: LivePhysicalOpeningVoidComposition, dropped: Iterable[str]) -> LivePhysicalOpeningVoidComposition:
    """The composition without the dropped canonical openings; the SAME object when none is dropped."""
    dropped = frozenset(dropped)
    if not dropped:
        return composition
    return replace(composition, canonical_openings=tuple(o for o in composition.canonical_openings
                                                          if o.physical_opening_id not in dropped))


# --------------------------------------------------------------------------------------- authority-backed evidence
class AuthorityEvidenceProvider:
    """Real evidence for one composition: re-proves existence, reads the printed figure and physical host, and verifies the pairwise
    partition receipt of the producer-owned ``PhysicalOpeningAuthority``. Tests substitute any object with the same four methods."""

    def __init__(self, *, source_visibility_producer, wall_opening_composition) -> None:
        from pb_live_wall_opening_authority_composition import LiveWallOpeningAuthorityComposition
        from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
        from pb_source_visibility_authority import SourceVisibilityProducer

        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        if type(wall_opening_composition) is not LiveWallOpeningAuthorityComposition:
            raise TypeError("wall_opening_composition must be LiveWallOpeningAuthorityComposition")
        self._authority = wall_opening_composition.physical_opening_authority
        self._traces = {t.opening_identity_id: t for t in wall_opening_composition.opening_bindings}
        self._labels = OpeningLabelDimensionProducer.from_source_visibility_producer(source_visibility_producer)
        self._selectors: dict[str, Any] = {}

    def _selector(self, opening: LiveCanonicalOpeningObject):
        from pb_source_observation_authority import ObservationSelector
        return ObservationSelector(
            document_id=opening.document_id, revision_id=opening.revision_id, source_sha256=opening.source_sha256,
            snapshot_id=opening.snapshot_id, observation_id=opening.representative_observation_id)

    def reproven(self, opening: LiveCanonicalOpeningObject) -> bool:
        """The authority independently re-issues exactly this opening's existence record (same checks as the append-only reproof)."""
        from pb_page_view_class_source_adapter import page_viewport_id
        from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority

        try:
            if type(self._authority) is not PhysicalOpeningAuthority:
                return False
            selector = self._selector(opening)
            proof = self._authority.prove_existence(selector)
            record = proof.existence_record
            observation = getattr(proof.source_observation, "observation", None)
            viewport = record.viewport_id if record is not None and record.viewport_id is not None else page_viewport_id(opening.page_id)
            ok = (proof.status is EvidenceResolutionStatus.CORROBORATED and proof.proposition == PHYSICAL_OPENING_EXISTS
                  and record is not None and observation is not None
                  and record.record_id == opening.physical_opening_id == opening.canonical_opening_id
                  and all(getattr(record, f) == getattr(opening, f) for f in (
                      "document_id", "revision_id", "source_sha256", "snapshot_id", "page_id", "semantic_class", "structural_pattern",
                      "source_observation_ids", "source_lineage_root_ids"))
                  and opening.viewport_id == viewport and observation.observation_id == opening.representative_observation_id)
            if ok:
                self._selectors[opening.physical_opening_id] = selector
            return bool(ok)
        except Exception:
            return False

    def record(self, opening: LiveCanonicalOpeningObject, quantity: QuantityEvidence) -> ApertureRecord:
        evidence = getattr(self._labels.publish_scope(self._selector(opening)), "evidence", None)
        figure = tuple(sorted(evidence.source_text_observation_ids)) if evidence is not None else ()
        trace = self._traces.get(opening.physical_opening_id)
        # the PHYSICAL host: the group of member wall candidates the host binding rests on (a per-record host id is derived from the
        # record itself, so two records of one aperture never share it)
        host = "|".join(sorted(trace.member_wall_candidate_ids)) if trace is not None else ""
        scope = f"{opening.document_id}|{opening.revision_id}|{opening.snapshot_id}|{opening.page_id}"
        return ApertureRecord(opening.physical_opening_id, scope, figure, float(quantity.value), host or None, (quantity.quantity_id,))

    def verdict(self, left: LiveCanonicalOpeningObject, right: LiveCanonicalOpeningObject) -> tuple[str, str]:
        """(verdict, receipt id) for one pair. A receipt that does not verify is UNPROVEN: it never makes anything distinct."""
        from pb_physical_opening_authority import PhysicalOpeningPartitionReceipt

        try:
            a, b = self._selectors[left.physical_opening_id], self._selectors[right.physical_opening_id]
            receipt = self._authority.partition_receipt(a, b)
            if (type(receipt) is not PhysicalOpeningPartitionReceipt or self._authority.verify_partition_receipt(receipt, a, b) is not True
                    or receipt.grants_quantity is not False or receipt.grants_firm_authority is not False):
                return UNPROVEN, ""
            word = DISTINCT if receipt.is_physically_distinct else OVERLAPPING if receipt.partition == "overlapping_extent" else UNPROVEN
            return word, str(receipt.receipt_id)
        except Exception:
            return UNPROVEN, ""


# ------------------------------------------------------------------------------------------------------ the consumer
def _consolidate_with_provider(
    composition: LivePhysicalOpeningVoidComposition, provider, enabled: bool,
) -> ApertureConsolidationResult:
    """The consumer over an injected evidence provider. PRIVATE: the public entry points build the authority-backed provider
    themselves, so a caller can never supply verdicts, records or receipts. Tests substitute the authority's answers here."""
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be a strict bool")
    if type(composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError("composition must be LivePhysicalOpeningVoidComposition")
    if not enabled:
        return ApertureConsolidationResult(enabled=False, composition=composition, reason_codes=(DISABLED,))
    if provider is None:
        raise TypeError("an enabled aperture consolidation needs an authority-backed evidence provider")
    quantities = {q.input_entity_ids[0]: q for q in publish_live_opening_area_quantities(composition)}
    openings = {o.physical_opening_id: o for o in composition.canonical_openings}
    measured = sorted(i for i in quantities if i in openings)
    reproven = [i for i in measured if provider.reproven(openings[i])]
    not_reproven = tuple(i for i in measured if i not in set(reproven))
    records = [provider.record(openings[i], quantities[i]) for i in reproven]
    verdicts, receipts = [], {}
    by_scope: dict[str, list[str]] = {}
    for r in records:
        by_scope.setdefault(r.scope_key, []).append(r.record_id)
    for ids in by_scope.values():
        for left, right in itertools.combinations(sorted(ids), 2):
            word, receipt_id = provider.verdict(openings[left], openings[right])
            verdicts.append(PairVerdict(left, right, word))
            if receipt_id:
                receipts[frozenset((left, right))] = receipt_id
    classes = resolve_aperture_equivalence(records, verdicts, enabled=True)
    consolidated, unconsolidated = plan_consolidation(classes, openings, quantities, receipts)
    derived = derive_composition(composition, (i for c in consolidated for i in c.dropped_physical_opening_ids))
    return ApertureConsolidationResult(
        enabled=True, composition=derived, consolidated=consolidated, unconsolidated=unconsolidated,
        not_reproven_physical_opening_ids=not_reproven,
        reason_codes=((CONSOLIDATED,) if consolidated else ()) + ((NOT_REPROVEN,) if not_reproven else ()))


def _publish_with_provider(
    composition: LivePhysicalOpeningVoidComposition, provider, enabled: bool,
) -> tuple[tuple[QuantityEvidence, ...], ApertureConsolidationResult]:
    result = _consolidate_with_provider(composition, provider, enabled)
    published = publish_live_opening_area_quantities(result.composition)
    if result.enabled:
        dropped = set(result.dropped_physical_opening_ids)
        expected = tuple(q for q in publish_live_opening_area_quantities(composition) if q.input_entity_ids[0] not in dropped)
        if published != expected:
            raise ApertureConsolidationInvariantError(INVARIANT)
    return published, result


def _authority_provider(source_visibility_producer, wall_opening_composition, enabled):
    """The real, authority-backed provider, built only for ``enabled is True`` (a strict bool is checked by the core)."""
    if enabled is not True:
        return None
    return AuthorityEvidenceProvider(
        source_visibility_producer=source_visibility_producer, wall_opening_composition=wall_opening_composition)


def consolidate_live_opening_apertures(
    *,
    source_visibility_producer=None,
    wall_opening_composition=None,
    composition: LivePhysicalOpeningVoidComposition,
    enabled: bool = False,
) -> ApertureConsolidationResult:
    """See the module docstring. The only evidence is what the producer-owned objects prove; a caller supplies no verdicts."""
    return _consolidate_with_provider(
        composition, _authority_provider(source_visibility_producer, wall_opening_composition, enabled), enabled)


def publish_live_opening_area_quantities_with_aperture_consolidation(
    *,
    source_visibility_producer=None,
    wall_opening_composition=None,
    composition: LivePhysicalOpeningVoidComposition,
    enabled: bool = False,
) -> tuple[tuple[QuantityEvidence, ...], ApertureConsolidationResult]:
    """``publish_live_opening_area_quantities`` with the default-off consolidation; the pair (quantities, record).

    Off: exactly the existing publication. On: the existing publication of the derived composition, which must equal the original
    publication minus the dropped members' quantities (every surviving quantity byte-identical), or the call fails closed."""
    return _publish_with_provider(
        composition, _authority_provider(source_visibility_producer, wall_opening_composition, enabled), enabled)


__all__ = [
    "AMBIGUOUS", "ApertureConsolidationInvariantError", "ApertureConsolidationResult", "ApertureMember", "AuthorityEvidenceProvider",
    "CONSOLIDATED", "ConsolidatedAperture", "DISABLED", "INVARIANT", "NOT_REPROVEN", "NO_OWNER", "QUANTITIES_DIFFER",
    "UnconsolidatedAperture", "consolidate_live_opening_apertures", "derive_composition", "evidence_owner", "plan_consolidation",
    "publish_live_opening_area_quantities_with_aperture_consolidation",
]
