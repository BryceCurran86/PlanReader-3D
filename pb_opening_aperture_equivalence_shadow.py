"""Shadow-only diagnostic: which sealed opening records are ONE physical aperture published more than once?

Why. On the 3Laurel original the live opening-area publication seals one quantity per canonical opening record, and
the existing publication check only rejects an identical ``physical_opening_id``. Two existence records of one drawn
aperture (an outer and an inner frame line about a point apart, sharing one printed figure) therefore become two
quantities and two customer rows.

What it does. It takes the existing ``PhysicalOpeningAuthority`` verdict for each pair of records (the authority
re-proves both existence records; apertures that overlap are a CONFLICT there, apertures it proves apart are DISTINCT,
anything it cannot read is unproven) together with each record's printed-figure evidence, area and host, and groups the
records into aperture classes:

* ``distinct``: the authority proves the pair apart.
* ``equivalent``: the pair's apertures overlap AND both records rest on the very same printed-figure words, the very
  same area and the very same host. Nothing else makes two records one aperture: not proximity, not a similar size.
* anything else that is not proven apart (overlap with different evidence, area or host; an unproven pair; a pair the
  caller did not compare but that shares a printed figure) is AMBIGUOUS and every record it touches is reported
  ``ambiguous``: ambiguity never consolidates and never disappears.

A class of equivalent records must be a clique (every pair equivalent); otherwise it is ambiguous. A consolidated
class names every member and carries the single shared area: no member is dropped or preferred. The module is pure and
deterministic (independent of record, pair and side order), mutates nothing, is default off (``enabled`` must be a
strict bool) and grants no quantity. The default-off publication consumer
``pb_live_opening_aperture_equivalence_publication`` is the only production importer.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

SCHEMA_VERSION = "1.0.0"

DISTINCT = "distinct"
OVERLAPPING = "overlapping"
UNPROVEN = "unproven"
VERDICTS = (DISTINCT, OVERLAPPING, UNPROVEN)

CONSOLIDATED = "equivalent_records_one_aperture_same_figure_area_host_overlapping_extent_shadow"
SINGLE = "record_distinct_from_every_compared_record"
AMBIGUOUS_EVIDENCE = "overlapping_apertures_with_different_figure_area_or_host"
AMBIGUOUS_UNPROVEN = "aperture_identity_unproven_for_a_compared_pair"
AMBIGUOUS_NOT_CLIQUE = "equivalent_records_do_not_form_one_clique"
AMBIGUOUS_SHARED_FIGURE = "records_share_a_printed_figure_but_were_not_compared"
AMBIGUOUS_NO_FIGURE = "overlapping_records_without_printed_figure_evidence"
INVALID_INPUT = "aperture_equivalence_input_invalid"


@dataclass(frozen=True)
class ApertureRecord:
    record_id: str
    scope_key: str                          # document, revision, snapshot and page: records in other scopes are never related
    figure_key: tuple[str, ...]             # the printed-figure word observation ids the area came from (sorted by the producer)
    area_m2: Optional[float]
    host_key: Optional[str] = None          # the PHYSICAL host (e.g. the sorted member wall candidate ids), never a per-record host id
    receipt_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class PairVerdict:
    left_id: str
    right_id: str
    verdict: str                            # distinct | overlapping | unproven (the physical opening authority's answer)


@dataclass(frozen=True)
class ApertureClass:
    class_id: str
    status: EvidenceResolutionStatus        # CANDIDATE for a consolidated class, ABSTAINED for an ambiguous one, CORROBORATED never
    reason_codes: tuple[str, ...]
    member_ids: tuple[str, ...]
    area_m2: Optional[float] = None
    receipt_ids: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION

    @property
    def is_consolidated(self) -> bool:
        return self.status is EvidenceResolutionStatus.CANDIDATE and len(self.member_ids) > 1

    @property
    def is_ambiguous(self) -> bool:
        return self.status is EvidenceResolutionStatus.ABSTAINED


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _class(status, reasons, members, records, area=None) -> ApertureClass:
    members = tuple(sorted(members))
    receipts = tuple(sorted({r for m in members for r in records[m].receipt_ids}))
    payload = {"schema": SCHEMA_VERSION, "status": status.value, "reasons": tuple(reasons), "members": members, "area": area, "receipts": receipts}
    return ApertureClass(class_id=stable_contract_id("opening_aperture_equivalence_shadow", payload, digest_chars=32), status=status,
                         reason_codes=tuple(reasons), member_ids=members, area_m2=area, receipt_ids=receipts)


def _valid(records: Sequence[ApertureRecord], verdicts: Sequence[PairVerdict]) -> bool:
    ids = [r.record_id for r in records]
    if not all(r.record_id and isinstance(r.scope_key, str) and r.scope_key for r in records) or len(set(ids)) != len(ids):
        return False
    if any((r.area_m2 is not None and (not _finite(r.area_m2) or r.area_m2 <= 0)) for r in records):
        return False
    known = set(ids)
    seen = {}
    for v in verdicts:
        if v.verdict not in VERDICTS or v.left_id == v.right_id or v.left_id not in known or v.right_id not in known:
            return False
        key = tuple(sorted((v.left_id, v.right_id)))
        if key in seen and seen[key] != v.verdict:
            return False                    # the two sides of one pair disagree
        seen[key] = v.verdict
    return True


def resolve_aperture_equivalence(
    records: Sequence[ApertureRecord],
    verdicts: Sequence[PairVerdict],
    *,
    enabled: bool = False,
) -> tuple[ApertureClass, ...]:
    """Aperture classes covering every record exactly once, sorted by class id. Empty unless ``enabled`` is exactly ``True``."""
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be a strict bool")
    if not enabled:
        return ()
    if not _valid(records, verdicts):
        return (ApertureClass(class_id=stable_contract_id("opening_aperture_equivalence_shadow", {"invalid": True}, digest_chars=32),
                              status=EvidenceResolutionStatus.ABSTAINED, reason_codes=(INVALID_INPUT,), member_ids=()),)
    by_id = {r.record_id: r for r in records}
    pair_verdict = {tuple(sorted((v.left_id, v.right_id))): v.verdict for v in verdicts}
    equivalent: dict[str, set[str]] = {i: set() for i in by_id}
    ambiguous: dict[str, set[str]] = {i: set() for i in by_id}      # record -> reasons that make it ambiguous

    def same_evidence(a: ApertureRecord, b: ApertureRecord) -> bool:
        return (a.scope_key == b.scope_key and bool(a.figure_key) and a.figure_key == b.figure_key
                and a.area_m2 is not None and a.area_m2 == b.area_m2 and a.host_key is not None and a.host_key == b.host_key)

    for (left, right), verdict in sorted(pair_verdict.items()):
        a, b = by_id[left], by_id[right]
        if a.scope_key != b.scope_key or verdict == DISTINCT:
            continue
        if verdict == UNPROVEN:
            reason = AMBIGUOUS_UNPROVEN
        elif same_evidence(a, b):
            equivalent[left].add(right)
            equivalent[right].add(left)
            continue
        elif not a.figure_key or not b.figure_key:
            reason = AMBIGUOUS_NO_FIGURE
        else:
            reason = AMBIGUOUS_EVIDENCE
        ambiguous[left].add(reason)
        ambiguous[right].add(reason)
    # records that share a printed figure with another record in the same scope must have been compared and proven apart
    by_figure: dict[tuple, list[str]] = {}
    for r in records:
        if r.figure_key:
            by_figure.setdefault((r.scope_key, r.figure_key), []).append(r.record_id)
    for members in by_figure.values():
        for i, left in enumerate(sorted(members)):
            for right in sorted(members)[i + 1:]:
                if tuple(sorted((left, right))) not in pair_verdict:
                    ambiguous[left].add(AMBIGUOUS_SHARED_FIGURE)
                    ambiguous[right].add(AMBIGUOUS_SHARED_FIGURE)
    # connected components over the equivalence edges (and the ambiguity of any member taints the whole component)
    seen: set[str] = set()
    out: list[ApertureClass] = []
    for start in sorted(by_id):
        if start in seen:
            continue
        stack, component = [start], set()
        while stack:
            cur = stack.pop()
            if cur in component:
                continue
            component.add(cur)
            stack.extend(equivalent[cur] - component)
        seen |= component
        reasons = {reason for m in component for reason in ambiguous[m]}
        clique = all(other in equivalent[m] for m in component for other in component if other != m)
        if reasons:
            out.append(_class(EvidenceResolutionStatus.ABSTAINED, sorted(reasons), component, by_id))
        elif not clique:
            out.append(_class(EvidenceResolutionStatus.ABSTAINED, (AMBIGUOUS_NOT_CLIQUE,), component, by_id))
        elif len(component) > 1:
            out.append(_class(EvidenceResolutionStatus.CANDIDATE, (CONSOLIDATED,), component, by_id, area=by_id[start].area_m2))
        else:
            out.append(_class(EvidenceResolutionStatus.CANDIDATE, (SINGLE,), component, by_id, area=by_id[start].area_m2))
    return tuple(sorted(out, key=lambda c: c.class_id))


def classes_by_record(classes: Iterable[ApertureClass]) -> dict[str, ApertureClass]:
    return {m: c for c in classes for m in c.member_ids}


__all__ = [
    "AMBIGUOUS_EVIDENCE", "AMBIGUOUS_NOT_CLIQUE", "AMBIGUOUS_NO_FIGURE", "AMBIGUOUS_SHARED_FIGURE", "AMBIGUOUS_UNPROVEN",
    "ApertureClass", "ApertureRecord", "CONSOLIDATED", "DISTINCT", "INVALID_INPUT", "OVERLAPPING", "PairVerdict", "SINGLE",
    "UNPROVEN", "classes_by_record", "resolve_aperture_equivalence",
]
