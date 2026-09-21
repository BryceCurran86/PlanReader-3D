"""Generic opening-count recovery and physical instance aggregation authority (Item 23 / F24).

Aggregates authenticated physical opening instances into deterministic counts by
family and mark. Schedule quantities may corroborate an independently established
instance universe; they never manufacture missing physical openings.

Authority rules:
- Physical instance identity is preserved; duplicate observations count once.
- Distinct equal-size openings count separately.
- Record-id dedup is never trusted alone: every pair of distinct openings is
  independently re-proven via ``PhysicalOpeningAuthority.compare_identity()``;
  an unresolved pair ABSTAINS and a contradiction (proven same despite
  distinct record ids) CONFLICTs.
- Caller ``non_plan_viewport_ids`` / ``schedule_declared_counts`` are diagnostic
  only and never decide authority.
- Viewport class comes from producer-owned ``ViewportViewClassAuthority``.
- Schedule quantity comes from producer-owned ``ScheduleRowQuantityAuthority``,
  keyed by exact schedule-row observation ids; distinct rows that happen to
  declare the same value never collapse into one agreeing count.
- Schedule vs physical mismatch fails closed with CONFLICT. Never
  ``min()``/``max()``.
- Incomplete schedule or opening universes ABSTAIN.
- Unknown count is not zero.

Source coverage and the OCR/raster extension point:
This authority is source-agnostic by construction -- ``publish()`` only ever
calls the public ``PhysicalOpeningAuthority`` / ``ScheduleOpeningInstanceBindingAuthority``
/ ``OpeningUniverseCompletenessAuthority`` contracts, never anything specific
to native-vector PDFs. The current native-vector source adapter intentionally authenticates only
raw visible-segment coverage; it does NOT claim semantic physical-opening
completeness and therefore never attaches this module's private commercial
completeness seal. Until a producer-owned semantic opening enumerator exists,
the real source-derived path ABSTAINS via
``GENERIC_OPENING_COUNT_COMPLETENESS_NOT_SOURCE_AUTHENTICATED``. This is
intentional fail-closed behavior: complete source decoding is not the same
proposition as a complete semantic opening universe.

Extending to raster/OCR requires no change to this module. It requires two
new producers, each satisfying an existing contract from OCR-derived
evidence instead of native-vector evidence:
1. A raster-backed ``SourceVisibilityAuthority`` (or ``SourceObservationAuthority``)
   populated from OCR/raster-vectorized segments, so
   ``PhysicalOpeningAuthority(raster_visibility_authority)`` is a real,
   strictly-typed ``PhysicalOpeningAuthority`` instance G17's existing
   matching logic (``prove_existence`` / ``compare_identity``) already knows
   how to run against -- reusing G17's deterministic geometry matching
   rather than duplicating it for raster.
2. An OCR-sourced binder mirroring ``ScheduleOpeningInstanceBindingProducer``'s
   own discipline: independently re-derive the tag/row match from raw OCR
   text each call, never trust a caller-supplied pre-computed binding (the
   same rule ``OpeningTagBindingResult`` already needs elsewhere in this
   codebase, since it carries no seal of its own).
Once both exist, ``GenericOpeningCountProducer.from_authorities()`` accepts
them unchanged -- the strict ``type(x) is PhysicalOpeningAuthority`` checks
below only require the concrete class, not a vector-specific origin.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Optional

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_migration_contracts import (
    EvidenceResolutionStatus,
    QuantityEvidence,
    stable_contract_id,
)
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessAuthority,
    OpeningUniverseSelector,
)
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningAuthority,
    PhysicalOpeningExistenceRecord,
)
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingAuthority,
    ScheduleOpeningInstanceBindingSelector,
)
from pb_schedule_row_quantity_authority import (
    ScheduleRowQuantityAuthority,
    ScheduleRowQuantitySelector,
)
from pb_source_observation_authority import ObservationSelector
from pb_page_view_class_source_adapter import page_viewport_id
from pb_viewport_view_class_authority import (
    VIEW_KIND_FLOOR_PLAN,
    ViewportViewClassAuthority,
    ViewportViewClassSelector,
)

GENERIC_OPENING_COUNT_SCHEMA_VERSION = "1.0.0"

GENERIC_OPENING_COUNT_RESOLVED = "generic_opening_count_resolved"
GENERIC_OPENING_COUNT_UNAVAILABLE = "generic_opening_count_unavailable"
GENERIC_OPENING_COUNT_LINEAGE_MISMATCH = "generic_opening_count_lineage_mismatch"
GENERIC_OPENING_COUNT_AMBIGUOUS = "generic_opening_count_ambiguous"
GENERIC_OPENING_COUNT_SCHEDULE_MISMATCH = "generic_opening_count_schedule_mismatch"
GENERIC_OPENING_COUNT_SCOPE_INCOMPLETE = "generic_opening_count_scope_incomplete"
GENERIC_OPENING_COUNT_COMPLETENESS_NOT_SOURCE_AUTHENTICATED = "generic_opening_count_completeness_not_source_authenticated"
GENERIC_OPENING_COUNT_NON_PLAN_VIEW = "generic_opening_count_non_plan_view"
GENERIC_OPENING_COUNT_NO_PHYSICAL_INSTANCES = (
    "generic_opening_count_no_physical_instances"
)
GENERIC_OPENING_COUNT_PHYSICAL_INSTANCE_UNRESOLVED = (
    "generic_opening_count_physical_instance_unresolved"
)
GENERIC_OPENING_COUNT_VIEWPORT_CLASS_UNAVAILABLE = (
    "generic_opening_count_viewport_class_unavailable"
)
GENERIC_OPENING_COUNT_CALLER_NON_PLAN_NOT_AUTHORITY = (
    "generic_opening_count_caller_non_plan_viewport_ids_not_authority"
)
GENERIC_OPENING_COUNT_CALLER_SCHEDULE_COUNTS_NOT_AUTHORITY = (
    "generic_opening_count_caller_schedule_declared_counts_not_authority"
)
GENERIC_OPENING_COUNT_SCHEDULE_ONLY_NOT_PHYSICAL = (
    "generic_opening_count_schedule_only_does_not_mint_physical_instances"
)
GENERIC_OPENING_COUNT_IDENTITY_CONTRADICTION = (
    "generic_opening_count_identity_contradiction"
)
GENERIC_OPENING_COUNT_IDENTITY_PAIRWISE_UNRESOLVED = (
    "generic_opening_count_identity_pairwise_unresolved"
)
GENERIC_OPENING_COUNT_MEMBER_CLASSIFICATION_UNRESOLVED = (
    "generic_opening_count_member_classification_unresolved"
)
GENERIC_OPENING_COUNT_SCHEDULE_ROW_DUPLICATE = (
    "generic_opening_count_schedule_row_duplicate"
)

_COUNT_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_SOURCE_AUTHENTICATED_COMPLETENESS_SEAL = object()

_Key = tuple[str, str, str, str, str, Optional[str], Optional[str]]


def _require_nonempty(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be a non-empty string")
    return text


@dataclass(frozen=True)
class OpeningCountDiagnosticRequest:
    """Caller request bag: diagnostic only; never measurement authority."""

    non_plan_viewport_ids: tuple[str, ...] = ()
    schedule_declared_counts: Mapping[str, int] = MappingProxyType({})

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "non_plan_viewport_ids",
            tuple(str(v).strip() for v in self.non_plan_viewport_ids if str(v).strip()),
        )
        cleaned = {
            str(k).strip().upper(): int(v)
            for k, v in dict(self.schedule_declared_counts).items()
            if str(k).strip()
        }
        object.__setattr__(
            self, "schedule_declared_counts", MappingProxyType(cleaned)
        )


@dataclass(frozen=True)
class GenericOpeningCountSelector:
    """Consumer addressing only: never a caller-authored count universe."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str
    opening_family: Optional[str] = None
    opening_mark: Optional[str] = None

    def __post_init__(self) -> None:
        _require_nonempty(self.document_id, "document_id")
        _require_nonempty(self.revision_id, "revision_id")
        _require_nonempty(self.source_sha256, "source_sha256")
        _require_nonempty(self.snapshot_id, "snapshot_id")
        _require_nonempty(self.decision_scope_id, "decision_scope_id")
        if self.opening_family is not None:
            clean_fam = str(self.opening_family).strip().lower()
            if not clean_fam:
                raise ValueError("opening_family cannot be empty when provided")
            object.__setattr__(self, "opening_family", clean_fam)
        if self.opening_mark is not None:
            clean_mark = str(self.opening_mark).strip().upper()
            if not clean_mark:
                raise ValueError("opening_mark cannot be empty when provided")
            object.__setattr__(self, "opening_mark", clean_mark)

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.decision_scope_id,
            self.opening_family,
            self.opening_mark,
        )


@dataclass(frozen=True)
class GenericOpeningCountRecord:
    """Deterministic auditable physical opening count publication record."""

    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str
    opening_family: Optional[str]
    opening_mark: Optional[str]
    count: int
    physical_instance_record_ids: tuple[str, ...]
    schedule_corroborated: bool
    schedule_row_ids: tuple[str, ...] = ()
    quantity_evidence: Optional[QuantityEvidence] = None
    schema_version: str = GENERIC_OPENING_COUNT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_nonempty(self.record_id, "record_id")
        _require_nonempty(self.document_id, "document_id")
        _require_nonempty(self.revision_id, "revision_id")
        _require_nonempty(self.source_sha256, "source_sha256")
        _require_nonempty(self.snapshot_id, "snapshot_id")
        _require_nonempty(self.decision_scope_id, "decision_scope_id")
        if self.count < 0:
            raise ValueError("count must be non-negative")
        if len(self.physical_instance_record_ids) != self.count:
            raise ValueError("count must match length of physical_instance_record_ids")
        if len(set(self.physical_instance_record_ids)) != len(
            self.physical_instance_record_ids
        ):
            raise ValueError("physical_instance_record_ids must be unique")


@dataclass(frozen=True)
class GenericOpeningCountResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[GenericOpeningCountRecord] = None
    schema_version: str = GENERIC_OPENING_COUNT_SCHEMA_VERSION


def _blocked(
    status: EvidenceResolutionStatus,
    reason: str,
    *extra_reasons: str,
) -> GenericOpeningCountResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    reasons = tuple(dict.fromkeys([reason, *(r for r in extra_reasons if r)]))
    return GenericOpeningCountResult(
        status=status,
        reason_codes=reasons,
        record=None,
    )


class GenericOpeningCountAuthority:
    """Read-only exact-scope selector lookup for generic opening counts."""

    def __init__(
        self,
        results: Mapping[_Key, GenericOpeningCountResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("GenericOpeningCountAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(
        self, selector: GenericOpeningCountSelector
    ) -> GenericOpeningCountResult:
        if type(selector) is not GenericOpeningCountSelector:
            raise TypeError("selector must be GenericOpeningCountSelector")
        return self._results.get(
            selector.key,
            _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                GENERIC_OPENING_COUNT_UNAVAILABLE,
            ),
        )


class GenericOpeningCountProducer:
    """Trusted boundary establishing generic opening counts from producer authorities."""

    def __init__(
        self,
        opening_universe_authority: OpeningUniverseCompletenessAuthority,
        physical_opening_authority: PhysicalOpeningAuthority,
        viewport_view_class_authority: ViewportViewClassAuthority,
        schedule_binding_authority: Optional[
            ScheduleOpeningInstanceBindingAuthority
        ] = None,
        schedule_row_quantity_authority: Optional[
            ScheduleRowQuantityAuthority
        ] = None,
        diagnostic_request: Optional[OpeningCountDiagnosticRequest] = None,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _COUNT_PRODUCER_SEAL:
            raise TypeError(
                "GenericOpeningCountProducer must be obtained from from_authorities()"
            )
        if type(opening_universe_authority) is not OpeningUniverseCompletenessAuthority:
            raise TypeError(
                "opening_universe_authority must be producer-owned "
                "OpeningUniverseCompletenessAuthority"
            )
        if type(physical_opening_authority) is not PhysicalOpeningAuthority:
            raise TypeError(
                "physical_opening_authority must be producer-owned PhysicalOpeningAuthority"
            )
        if type(viewport_view_class_authority) is not ViewportViewClassAuthority:
            raise TypeError(
                "viewport_view_class_authority must be producer-owned "
                "ViewportViewClassAuthority"
            )
        if (
            schedule_binding_authority is not None
            and type(schedule_binding_authority)
            is not ScheduleOpeningInstanceBindingAuthority
        ):
            raise TypeError(
                "schedule_binding_authority must be producer-owned "
                "ScheduleOpeningInstanceBindingAuthority"
            )
        if (
            schedule_row_quantity_authority is not None
            and type(schedule_row_quantity_authority) is not ScheduleRowQuantityAuthority
        ):
            raise TypeError(
                "schedule_row_quantity_authority must be producer-owned "
                "ScheduleRowQuantityAuthority"
            )
        self._universe = opening_universe_authority
        self._physical = physical_opening_authority
        self._view_class = viewport_view_class_authority
        self._binding = schedule_binding_authority
        self._schedule_qty = schedule_row_quantity_authority
        self._diagnostic = diagnostic_request or OpeningCountDiagnosticRequest()
        self._results: dict[_Key, GenericOpeningCountResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        opening_universe_authority: OpeningUniverseCompletenessAuthority,
        physical_opening_authority: PhysicalOpeningAuthority,
        viewport_view_class_authority: ViewportViewClassAuthority,
        schedule_binding_authority: Optional[
            ScheduleOpeningInstanceBindingAuthority
        ] = None,
        schedule_row_quantity_authority: Optional[
            ScheduleRowQuantityAuthority
        ] = None,
        diagnostic_request: Optional[OpeningCountDiagnosticRequest] = None,
        # Reject legacy caller-authority kwargs explicitly.
        schedule_declared_counts: Any = None,
        non_plan_viewport_ids: Any = None,
    ) -> "GenericOpeningCountProducer":
        if schedule_declared_counts is not None or non_plan_viewport_ids is not None:
            raise TypeError(
                "schedule_declared_counts and non_plan_viewport_ids are not authority "
                "inputs; pass OpeningCountDiagnosticRequest as diagnostic_request only"
            )
        return cls(
            opening_universe_authority=opening_universe_authority,
            physical_opening_authority=physical_opening_authority,
            viewport_view_class_authority=viewport_view_class_authority,
            schedule_binding_authority=schedule_binding_authority,
            schedule_row_quantity_authority=schedule_row_quantity_authority,
            diagnostic_request=diagnostic_request,
            _seal=_COUNT_PRODUCER_SEAL,
        )

    def authority(self) -> GenericOpeningCountAuthority:
        return GenericOpeningCountAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def _store(
        self,
        selector: GenericOpeningCountSelector,
        result: GenericOpeningCountResult,
    ) -> GenericOpeningCountResult:
        self._results[selector.key] = result
        return result

    def _diagnostic_reasons(self) -> tuple[str, ...]:
        reasons: list[str] = []
        if self._diagnostic.non_plan_viewport_ids:
            reasons.append(GENERIC_OPENING_COUNT_CALLER_NON_PLAN_NOT_AUTHORITY)
        if self._diagnostic.schedule_declared_counts:
            reasons.append(GENERIC_OPENING_COUNT_CALLER_SCHEDULE_COUNTS_NOT_AUTHORITY)
        return tuple(reasons)

    def publish(
        self, selector: GenericOpeningCountSelector
    ) -> GenericOpeningCountResult:
        if type(selector) is not GenericOpeningCountSelector:
            raise TypeError("selector must be GenericOpeningCountSelector")

        diagnostic_reasons = self._diagnostic_reasons()

        # Current public OpeningUniverseCompletenessProducer can be fed
        # caller-supplied source/enumerated primitive collections. Only an
        # internal source-bound adapter may attach this private seal after
        # deriving completeness from authenticated source decode.
        if getattr(self._universe, "_source_authentication_seal", None) is not _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    GENERIC_OPENING_COUNT_COMPLETENESS_NOT_SOURCE_AUTHENTICATED,
                    *diagnostic_reasons,
                ),
            )

        univ_sel = OpeningUniverseSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            decision_scope_id=selector.decision_scope_id,
        )
        univ_res = self._universe.resolve(univ_sel)
        if (
            univ_res.status is not EvidenceResolutionStatus.CORROBORATED
            or univ_res.record is None
            or not getattr(univ_res.record, "decision_scope_complete", False)
        ):
            return self._store(
                selector,
                _blocked(
                    univ_res.status,
                    GENERIC_OPENING_COUNT_SCOPE_INCOMPLETE,
                    *(getattr(univ_res, "reason_codes", ()) or ()),
                    *diagnostic_reasons,
                ),
            )

        univ_rec = univ_res.record
        if (
            univ_rec.document_id != selector.document_id
            or univ_rec.revision_id != selector.revision_id
            or univ_rec.source_sha256 != selector.source_sha256
            or univ_rec.snapshot_id != selector.snapshot_id
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    GENERIC_OPENING_COUNT_LINEAGE_MISMATCH,
                    *diagnostic_reasons,
                ),
            )

        accounted_ids = tuple(
            getattr(univ_rec, "accounted_source_observation_ids", ()) or ()
        )
        if not accounted_ids:
            # Backward-compatible fallback for legacy/test completeness records.
            accounted_ids = tuple(univ_rec.accounted_member_ids or ())
        distinct_openings: dict[str, PhysicalOpeningExistenceRecord] = {}
        opening_marks: dict[str, Optional[str]] = {}
        opening_families: dict[str, str] = {}
        schedule_row_ids: list[str] = []
        binding_by_opening: dict[str, Any] = {}
        representative_selectors: dict[str, ObservationSelector] = {}

        for member_id in accounted_ids:
            obs_sel = ObservationSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                observation_id=member_id,
            )
            exist_res = self._physical.prove_existence(obs_sel)
            if (
                exist_res.status is not EvidenceResolutionStatus.CORROBORATED
                or exist_res.existence_record is None
                or exist_res.proposition != PHYSICAL_OPENING_EXISTS
            ):
                return self._store(
                    selector,
                    _blocked(
                        exist_res.status,
                        GENERIC_OPENING_COUNT_PHYSICAL_INSTANCE_UNRESOLVED,
                        *(getattr(exist_res, "reason_codes", ()) or ()),
                        *diagnostic_reasons,
                    ),
                )

            p_rec = exist_res.existence_record
            if (
                p_rec.document_id != selector.document_id
                or p_rec.revision_id != selector.revision_id
                or p_rec.source_sha256 != selector.source_sha256
                or p_rec.snapshot_id != selector.snapshot_id
            ):
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.CONFLICT,
                        GENERIC_OPENING_COUNT_LINEAGE_MISMATCH,
                        *diagnostic_reasons,
                    ),
                )

            resolved_viewport_id = p_rec.viewport_id
            if (
                resolved_viewport_id is None
                and univ_rec.decision_scope_kind == "pages"
            ):
                resolved_viewport_id = page_viewport_id(p_rec.page_id)
            if resolved_viewport_id is None:
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        GENERIC_OPENING_COUNT_VIEWPORT_CLASS_UNAVAILABLE,
                        *diagnostic_reasons,
                    ),
                )

            # Producer-owned view class only — never caller ID lists or name guessing.
            vp_sel = ViewportViewClassSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                viewport_id=resolved_viewport_id,
            )
            vp_res = self._view_class.resolve(vp_sel)
            if (
                vp_res.status is not EvidenceResolutionStatus.CORROBORATED
                or vp_res.record is None
            ):
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        GENERIC_OPENING_COUNT_VIEWPORT_CLASS_UNAVAILABLE,
                        *(getattr(vp_res, "reason_codes", ()) or ()),
                        *diagnostic_reasons,
                    ),
                )
            if vp_res.record.view_kind != VIEW_KIND_FLOOR_PLAN:
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.CONFLICT,
                        GENERIC_OPENING_COUNT_NON_PLAN_VIEW,
                        f"opening_{p_rec.record_id}_view_kind_{vp_res.record.view_kind}",
                        *diagnostic_reasons,
                    ),
                )

            distinct_openings[p_rec.record_id] = p_rec
            representative_selectors.setdefault(p_rec.record_id, obs_sel)

            mark: Optional[str] = None
            family: str = "unknown"
            if self._binding is not None:
                b_sel = ScheduleOpeningInstanceBindingSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    decision_scope_id=selector.decision_scope_id,
                    opening_record_id=p_rec.record_id,
                )
                b_res = self._binding.resolve(b_sel)
                if b_res.status is EvidenceResolutionStatus.CONFLICT:
                    return self._store(
                        selector,
                        _blocked(
                            EvidenceResolutionStatus.CONFLICT,
                            GENERIC_OPENING_COUNT_AMBIGUOUS,
                            *(getattr(b_res, "reason_codes", ()) or ()),
                            *diagnostic_reasons,
                        ),
                    )
                if (
                    b_res.status is EvidenceResolutionStatus.CORROBORATED
                    and b_res.record is not None
                ):
                    b_rec = b_res.record
                    binding_by_opening[p_rec.record_id] = b_rec
                    mark = (
                        getattr(b_rec, "schedule_row_type_mark", None)
                        or getattr(b_rec, "tag_mark", None)
                    )
                    if mark:
                        mark = str(mark).strip().upper()
                    row_obs = getattr(b_rec, "schedule_row_observation_ids", ()) or ()
                    if row_obs:
                        schedule_row_ids.extend(str(x) for x in row_obs)
                    if mark:
                        if mark.startswith("D") and not mark.startswith("DW"):
                            family = "door"
                        elif mark.startswith("W"):
                            family = "window"
                        elif mark.startswith("DW") or mark.startswith("WD"):
                            family = "door_window"

            opening_marks[p_rec.record_id] = mark
            opening_families[p_rec.record_id] = family

        # Defense-in-depth: G17 record_id equality is the cheap dedup signal
        # used above, but it is only trustworthy if independently re-proven
        # existence agrees with it for every pair of distinct openings.
        # compare_identity() re-derives existence from scratch for each side
        # and never reuses the loop's cached PhysicalOpeningExistenceRecord,
        # so this catches non-determinism or scope-matching bugs the cheap
        # dict-keyed dedup above could not detect on its own.
        distinct_ids = sorted(distinct_openings.keys())
        for i in range(len(distinct_ids)):
            for j in range(i + 1, len(distinct_ids)):
                left_id, right_id = distinct_ids[i], distinct_ids[j]
                identity_cmp = self._physical.compare_identity(
                    representative_selectors[left_id],
                    representative_selectors[right_id],
                )
                if identity_cmp.status is not EvidenceResolutionStatus.CORROBORATED:
                    return self._store(
                        selector,
                        _blocked(
                            EvidenceResolutionStatus.ABSTAINED,
                            GENERIC_OPENING_COUNT_IDENTITY_PAIRWISE_UNRESOLVED,
                            f"{left_id}_vs_{right_id}",
                            *(identity_cmp.reason_codes or ()),
                            *diagnostic_reasons,
                        ),
                    )
                if identity_cmp.proven_same:
                    return self._store(
                        selector,
                        _blocked(
                            EvidenceResolutionStatus.CONFLICT,
                            GENERIC_OPENING_COUNT_IDENTITY_CONTRADICTION,
                            f"{left_id}_vs_{right_id}",
                            *diagnostic_reasons,
                        ),
                    )

        # Filtered counts are only valid if every physical member in the
        # claimed-complete universe can be ruled in or ruled out for that
        # selector.  A physically proven opening with unresolved mark/family
        # classification may still belong to the requested subset; silently
        # skipping it would turn "known W1s" into "all W1s".
        if selector.opening_mark is not None:
            unresolved_mark_ids = tuple(
                op_id
                for op_id in sorted(distinct_openings)
                if not opening_marks.get(op_id)
            )
            if unresolved_mark_ids:
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        GENERIC_OPENING_COUNT_MEMBER_CLASSIFICATION_UNRESOLVED,
                        "opening_mark_unresolved_for_" + ",".join(unresolved_mark_ids),
                        *diagnostic_reasons,
                    ),
                )

        if selector.opening_family is not None:
            unresolved_family_ids = tuple(
                op_id
                for op_id in sorted(distinct_openings)
                if opening_families.get(op_id, "unknown") == "unknown"
            )
            if unresolved_family_ids:
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        GENERIC_OPENING_COUNT_MEMBER_CLASSIFICATION_UNRESOLVED,
                        "opening_family_unresolved_for_"
                        + ",".join(unresolved_family_ids),
                        *diagnostic_reasons,
                    ),
                )

        matched_instance_ids: list[str] = []
        for op_id in sorted(distinct_openings.keys()):
            op_fam = opening_families.get(op_id, "unknown")
            op_mark = opening_marks.get(op_id)
            if selector.opening_family is not None:
                if selector.opening_family.lower() != op_fam.lower():
                    continue
            if selector.opening_mark is not None:
                if op_mark is None or selector.opening_mark.upper() != op_mark.upper():
                    continue
            matched_instance_ids.append(op_id)

        count = len(matched_instance_ids)

        # Caller schedule_declared_counts never decide corroboration or conflict.
        schedule_corroborated = False
        if (
            selector.opening_mark is not None
            and self._schedule_qty is not None
            and matched_instance_ids
        ):
            # Keyed by the exact row-observation-id set, never by the
            # declared value alone: two DISTINCT schedule rows that happen
            # to declare the same count must never collapse into one
            # agreeing value -- that would hide a real duplicate/conflicting
            # schedule entry behind a coincidental match.
            qty_by_row: dict[tuple[str, ...], int] = {}
            for op_id in matched_instance_ids:
                b_rec = binding_by_opening.get(op_id)
                if b_rec is None:
                    continue
                row_ids = tuple(
                    sorted(getattr(b_rec, "schedule_row_observation_ids", ()) or ())
                )
                page_id = getattr(b_rec, "schedule_page_id", None)
                if not row_ids or not page_id:
                    continue
                q_sel = ScheduleRowQuantitySelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    schedule_page_id=str(page_id),
                    schedule_row_observation_ids=row_ids,
                )
                q_res = self._schedule_qty.resolve(q_sel)
                if (
                    q_res.status is EvidenceResolutionStatus.CORROBORATED
                    and q_res.record is not None
                ):
                    qty_by_row[row_ids] = int(q_res.record.declared_count)
            if len(qty_by_row) > 1:
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.CONFLICT,
                        GENERIC_OPENING_COUNT_SCHEDULE_ROW_DUPLICATE,
                        "schedule_row_quantity_multiple_distinct_rows",
                        *diagnostic_reasons,
                    ),
                )
            if len(qty_by_row) == 1:
                declared = next(iter(qty_by_row.values()))
                if declared != count:
                    return self._store(
                        selector,
                        _blocked(
                            EvidenceResolutionStatus.CONFLICT,
                            GENERIC_OPENING_COUNT_SCHEDULE_MISMATCH,
                            f"schedule_qty_{declared}_vs_physical_instances_{count}",
                            *diagnostic_reasons,
                        ),
                    )
                schedule_corroborated = True

        # Schedule-only: authenticated schedule with zero physical instances.
        if count == 0 and selector.opening_mark is not None:
            caller_declared = self._diagnostic.schedule_declared_counts.get(
                selector.opening_mark.upper()
            )
            extra = list(diagnostic_reasons)
            if caller_declared is not None:
                extra.append(GENERIC_OPENING_COUNT_SCHEDULE_ONLY_NOT_PHYSICAL)
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    GENERIC_OPENING_COUNT_NO_PHYSICAL_INSTANCES,
                    *extra,
                ),
            )

        if count == 0 and selector.opening_family is not None:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    GENERIC_OPENING_COUNT_NO_PHYSICAL_INSTANCES,
                    *diagnostic_reasons,
                ),
            )

        semantic_key = "opening_count"
        if selector.opening_family:
            semantic_key += f":{selector.opening_family}"
        if selector.opening_mark:
            semantic_key += f":{selector.opening_mark}"

        qty_payload = {
            "family": "opening_count",
            "semantic_key": semantic_key,
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "count": count,
            "matched_ids": matched_instance_ids,
        }
        physical_evidence_ids = tuple(
            obs_id
            for op_id in matched_instance_ids
            for obs_id in distinct_openings[op_id].source_observation_ids
        )
        corroborating_schedule_ids = (
            tuple(sorted(set(schedule_row_ids))) if schedule_corroborated else ()
        )
        evidence_ids = tuple(
            dict.fromkeys((*physical_evidence_ids, *corroborating_schedule_ids))
        )
        qty = QuantityEvidence(
            quantity_id=stable_contract_id("qty_opening_count", qty_payload),
            family="opening_count",
            semantic_key=semantic_key,
            value=float(count),
            unit="ea",
            input_entity_ids=tuple(matched_instance_ids),
            formula="sum_of_authenticated_physical_opening_instances",
            formula_version=GENERIC_OPENING_COUNT_SCHEMA_VERSION,
            evidence_ids=evidence_ids,
            authority=MeasurementAuthorityType.PDF_SCALED.value,
            status=AuthorityStatus.FIRM.value,
            confidence=1.0,
            abstained=False,
            metadata={
                "schedule_corroborated": schedule_corroborated,
                "opening_mark": selector.opening_mark,
                "opening_family": selector.opening_family,
            },
        )

        rec_payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "decision_scope_id": selector.decision_scope_id,
            "opening_family": selector.opening_family,
            "opening_mark": selector.opening_mark,
            "count": count,
            "physical_instance_record_ids": tuple(matched_instance_ids),
            "schedule_corroborated": schedule_corroborated,
            "schedule_row_ids": tuple(sorted(set(schedule_row_ids))),
        }
        record = GenericOpeningCountRecord(
            record_id=stable_contract_id(
                "generic_opening_count", rec_payload, digest_chars=32
            ),
            quantity_evidence=qty,
            **rec_payload,
        )
        reasons = [GENERIC_OPENING_COUNT_RESOLVED, *diagnostic_reasons]
        return self._store(
            selector,
            GenericOpeningCountResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=tuple(dict.fromkeys(reasons)),
                record=record,
            ),
        )


__all__ = [
    "GENERIC_OPENING_COUNT_AMBIGUOUS",
    "GENERIC_OPENING_COUNT_CALLER_NON_PLAN_NOT_AUTHORITY",
    "GENERIC_OPENING_COUNT_CALLER_SCHEDULE_COUNTS_NOT_AUTHORITY",
    "GENERIC_OPENING_COUNT_COMPLETENESS_NOT_SOURCE_AUTHENTICATED",
    "GENERIC_OPENING_COUNT_IDENTITY_CONTRADICTION",
    "GENERIC_OPENING_COUNT_IDENTITY_PAIRWISE_UNRESOLVED",
    "GENERIC_OPENING_COUNT_MEMBER_CLASSIFICATION_UNRESOLVED",
    "GENERIC_OPENING_COUNT_LINEAGE_MISMATCH",
    "GENERIC_OPENING_COUNT_NON_PLAN_VIEW",
    "GENERIC_OPENING_COUNT_NO_PHYSICAL_INSTANCES",
    "GENERIC_OPENING_COUNT_PHYSICAL_INSTANCE_UNRESOLVED",
    "GENERIC_OPENING_COUNT_RESOLVED",
    "GENERIC_OPENING_COUNT_SCHEDULE_MISMATCH",
    "GENERIC_OPENING_COUNT_SCHEDULE_ONLY_NOT_PHYSICAL",
    "GENERIC_OPENING_COUNT_SCHEDULE_ROW_DUPLICATE",
    "GENERIC_OPENING_COUNT_SCHEMA_VERSION",
    "GENERIC_OPENING_COUNT_SCOPE_INCOMPLETE",
    "GENERIC_OPENING_COUNT_UNAVAILABLE",
    "GENERIC_OPENING_COUNT_VIEWPORT_CLASS_UNAVAILABLE",
    "GenericOpeningCountAuthority",
    "GenericOpeningCountProducer",
    "GenericOpeningCountRecord",
    "GenericOpeningCountResult",
    "GenericOpeningCountSelector",
    "OpeningCountDiagnosticRequest",
]
