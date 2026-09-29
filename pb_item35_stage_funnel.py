"""Diagnostic-only stage funnel over the Item 35 production-authority shadow.

This module is a pure reader.  It consumes the dictionary returned by
``pb_item35_production_authority_shadow.collect_item35_authority_shadow`` (or
``empty_item35_authority_shadow``) and reports, per stage, what that shadow
actually exposes.  It never runs a source, physical-opening, semantic,
completeness, view-class or count authority itself, so there is exactly one
diagnostic execution path.

Observable stages (in pipeline order)::

    source_visibility
    -> semantic_opening_enumeration
    -> structural_enumeration_completeness
    -> physical_opening_universe_completeness
    -> generic_count_publication

The Item 35 shadow does NOT expose per-opening ``prove_existence()`` results,
``compare_identity()`` results or host-binding decisions.  Those three stages
are always reported as ``observed=False``.  No corroborated / abstained /
conflict count is inferred for them.  Real per-opening identity metrics need a
producer-owned diagnostic seam and a separate architecture review.

Authority rules kept here:

* The funnel can only preserve or lower authority.  A status is asserted only
  where the shadow exposes one: ``conflict`` stays ``CONFLICT``, an absent
  semantic record stays ``ABSTAINED``, an incomplete completeness flag is
  ``ABSTAINED`` ("incomplete universes abstain"), and the generic count status
  is passed through unchanged.  Nothing is ever raised to ``CORROBORATED``.
* Placeholder defaults in an empty shadow shell (``False`` flags, ``0`` counts,
  ``generic_count_status="abstained"``) are not observations.  They are
  reported as ``observed=False`` with ``None`` counts, never as ``0`` / ``False``.
* ``shadow_reported_commercial_count_unlocked`` is copied verbatim for
  inspection only.  ``commercial_authority_granted`` is a constant ``False``
  that cannot be constructed as ``True``.
* Gold-free: no benchmark expectation, mapping, tolerance or accepted row is
  read.  Reason codes are passed through from the shadow (semantic codes are
  the constants exported by ``pb_semantic_opening_enumeration_authority``).
* Output is deterministic: reason codes are de-duplicated and sorted, the
  record id comes from ``stable_contract_id``, the input mapping is never
  mutated and is never aliased by the result.

Production code (the extractor, JobHub, the commercial adapters) must not
import this module.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Optional

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_semantic_opening_enumeration_authority import (
    SEMANTIC_OPENING_CANDIDATE_UNIVERSE_COMPLETE,
    SEMANTIC_OPENING_LINEAGE_MISMATCH,
    SEMANTIC_OPENING_NO_VISIBLE_SEGMENTS,
    SEMANTIC_OPENING_PHYSICAL_CONFLICT,
    SEMANTIC_OPENING_RESIDUAL_SOURCE_EVIDENCE,
    SEMANTIC_OPENING_STRUCTURAL_ENUMERATION_COMPLETE,
    SEMANTIC_OPENING_UNIVERSE_EXHAUSTIVENESS_UNPROVEN,
    SEMANTIC_OPENING_VISIBLE_OBSERVATION_UNRESOLVED,
)


ITEM35_STAGE_FUNNEL_SCHEMA_VERSION = "1.0.0"

# Shadow schema versions whose field semantics were reviewed against this
# module.  A shadow schema bump must be reviewed here before it is accepted.
SUPPORTED_ITEM35_SHADOW_SCHEMA_VERSIONS = frozenset({"1.0.0"})

STAGE_SOURCE_VISIBILITY = "source_visibility"
STAGE_SEMANTIC_OPENING_ENUMERATION = "semantic_opening_enumeration"
STAGE_STRUCTURAL_ENUMERATION_COMPLETENESS = "structural_enumeration_completeness"
STAGE_PHYSICAL_OPENING_UNIVERSE_COMPLETENESS = (
    "physical_opening_universe_completeness"
)
STAGE_GENERIC_COUNT_PUBLICATION = "generic_count_publication"

OBSERVABLE_STAGES = (
    STAGE_SOURCE_VISIBILITY,
    STAGE_SEMANTIC_OPENING_ENUMERATION,
    STAGE_STRUCTURAL_ENUMERATION_COMPLETENESS,
    STAGE_PHYSICAL_OPENING_UNIVERSE_COMPLETENESS,
    STAGE_GENERIC_COUNT_PUBLICATION,
)

# Stages the Item 35 shadow does not expose (see module docstring).
STAGE_PHYSICAL_OPENING_EXISTENCE = "physical_opening_existence_per_opening"
STAGE_PHYSICAL_OPENING_IDENTITY = "physical_opening_identity_comparison"
STAGE_OPENING_HOST_BINDING = "opening_host_binding"

UNOBSERVED_IDENTITY_STAGES = (
    STAGE_PHYSICAL_OPENING_EXISTENCE,
    STAGE_PHYSICAL_OPENING_IDENTITY,
    STAGE_OPENING_HOST_BINDING,
)

NOT_OBSERVED_IDENTITY_NOT_EXPOSED = (
    "item35_shadow_does_not_expose_per_opening_results"
)
NOT_OBSERVED_SHADOW_SCOPE_ABSENT = "item35_shadow_scope_absent"
NOT_OBSERVED_SHADOW_NOT_COLLECTED = "item35_shadow_not_collected"
NOT_OBSERVED_SEMANTIC_RECORD_ABSENT = "semantic_record_absent"

# Histogram label for an observed row whose stage exposes no status.
STATUS_NOT_EXPOSED = "status_not_exposed"

# Semantic-record reason codes the semantic authority documents as gating each
# completeness flag (pb_semantic_opening_enumeration_authority, ``_publish_scope``:
# ``structural_complete`` / ``physical_universe_complete``).  Every semantic code
# always stays on the semantic-enumeration row verbatim; these subsets are
# additional per-flag views of the same list.
_STRUCTURAL_GATE_CODES = frozenset(
    {
        SEMANTIC_OPENING_NO_VISIBLE_SEGMENTS,
        SEMANTIC_OPENING_VISIBLE_OBSERVATION_UNRESOLVED,
        SEMANTIC_OPENING_LINEAGE_MISMATCH,
        SEMANTIC_OPENING_PHYSICAL_CONFLICT,
        SEMANTIC_OPENING_RESIDUAL_SOURCE_EVIDENCE,
        SEMANTIC_OPENING_STRUCTURAL_ENUMERATION_COMPLETE,
    }
)
_PHYSICAL_UNIVERSE_GATE_CODES = frozenset(
    {
        SEMANTIC_OPENING_UNIVERSE_EXHAUSTIVENESS_UNPROVEN,
        SEMANTIC_OPENING_CANDIDATE_UNIVERSE_COMPLETE,
    }
)

_SHADOW_STATUSES = frozenset({"abstained", "conflict", "evidence_present"})
_SCOPE_KEYS = ("document_id", "revision_id", "source_sha256", "snapshot_id")
_COUNT_KEYS = (
    "visible_observation_count",
    "semantic_opening_count",
    "support_observation_count",
    "residual_visible_observation_count",
)
_FLAG_KEYS = (
    "structural_enumeration_complete",
    "physical_opening_universe_complete",
)
_LIST_KEYS = (
    "semantic_reason_codes",
    "semantic_opening_record_ids",
    "representative_observation_ids",
    "generic_count_reason_codes",
)
_REQUIRED_KEYS = (
    "schema_version",
    "status",
    "reason",
    *_SCOPE_KEYS,
    *_COUNT_KEYS,
    *_FLAG_KEYS,
    "semantic_reason_codes",
    "semantic_record_id",
    "semantic_opening_record_ids",
    "representative_observation_ids",
    "generic_count_status",
    "generic_count_reason_codes",
    "generic_count",
    "commercial_count_unlocked",
)
# Every key the funnel reviewed and reads.  A shadow that gains a key must be
# reviewed here first; tests pin the shadow's emitted keys to this set.
REVIEWED_ITEM35_SHADOW_KEYS = frozenset(_REQUIRED_KEYS)

# The extractor's own pre-collection placeholder (``pb_planreader_pdf_extractor``
# ``__init__``).  It carries no schema version and no stage data.
_NOT_COLLECTED_KEYS = frozenset({"status", "reason", "commercial_count_unlocked"})
_NOT_COLLECTED_REASON = "not_collected"


def _codes(values: Iterable[str]) -> tuple[str, ...]:
    """Canonical reason-code view: de-duplicated and sorted (order-invariant)."""
    return tuple(sorted(set(values)))


@dataclass(frozen=True)
class StageObservation:
    """What the Item 35 shadow exposes for one stage.

    ``status`` is an ``EvidenceResolutionStatus`` only when the shadow exposes
    (or the stage's incompleteness rule implies) one; otherwise ``None``.
    ``blocking`` is ``None`` when the stage is unobserved.  ``complete`` is only
    set for the two completeness stages.  Counts are ``None`` when unknown;
    an unknown count is never reported as zero.
    """

    stage: str
    observed: bool
    status: Optional[EvidenceResolutionStatus] = None
    input_count: Optional[int] = None
    output_count: Optional[int] = None
    complete: Optional[bool] = None
    blocking: Optional[bool] = None
    reason_codes: tuple[str, ...] = ()
    detail_counts: tuple[tuple[str, int], ...] = ()
    not_observed_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if self.stage not in OBSERVABLE_STAGES + UNOBSERVED_IDENTITY_STAGES:
            raise ValueError(f"unknown funnel stage: {self.stage!r}")
        if self.stage in UNOBSERVED_IDENTITY_STAGES and self.observed:
            raise ValueError(
                "the Item 35 shadow exposes no per-opening identity stage; "
                f"{self.stage} must stay observed=False"
            )
        if self.status is not None and not isinstance(
            self.status, EvidenceResolutionStatus
        ):
            raise TypeError("status must be an EvidenceResolutionStatus or None")
        if self.reason_codes != _codes(self.reason_codes):
            raise ValueError("reason_codes must be de-duplicated and sorted")
        if self.detail_counts != tuple(sorted(self.detail_counts)):
            raise ValueError("detail_counts must be sorted")
        if not self.observed:
            if (
                self.status is not None
                or self.input_count is not None
                or self.output_count is not None
                or self.complete is not None
                or self.blocking is not None
                or self.reason_codes
                or self.detail_counts
            ):
                raise ValueError("an unobserved stage carries no observations")
            if not self.not_observed_reason:
                raise ValueError("an unobserved stage must say why")
        elif self.not_observed_reason is not None:
            raise ValueError("an observed stage has no not_observed_reason")
        elif self.blocking is None:
            raise ValueError("an observed stage must state whether it blocks")

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "observed": self.observed,
            "status": self.status.value if self.status is not None else None,
            "input_count": self.input_count,
            "output_count": self.output_count,
            "complete": self.complete,
            "blocking": self.blocking,
            "reason_codes": list(self.reason_codes),
            "detail_counts": {name: value for name, value in self.detail_counts},
            "not_observed_reason": self.not_observed_reason,
        }


def _unobserved(stage: str, reason: str) -> StageObservation:
    return StageObservation(stage=stage, observed=False, not_observed_reason=reason)


def _funnel_payload(
    *,
    schema_version: str,
    shadow_schema_version: Optional[str],
    shadow_status: str,
    shadow_reason: str,
    document_id: Optional[str],
    revision_id: Optional[str],
    source_sha256: Optional[str],
    snapshot_id: Optional[str],
    semantic_record_id: Optional[str],
    stages: tuple[StageObservation, ...],
    unobserved_identity_stages: tuple[StageObservation, ...],
    blocking_stages: tuple[str, ...],
    first_blocker_stage: Optional[str],
    first_unobserved_stage: Optional[str],
    shadow_reported_commercial_count_unlocked: bool,
    commercial_authority_granted: bool,
) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "shadow_schema_version": shadow_schema_version,
        "shadow_status": shadow_status,
        "shadow_reason": shadow_reason,
        "document_id": document_id,
        "revision_id": revision_id,
        "source_sha256": source_sha256,
        "snapshot_id": snapshot_id,
        "semantic_record_id": semantic_record_id,
        "stages": [stage.to_dict() for stage in stages],
        "unobserved_identity_stages": [
            stage.to_dict() for stage in unobserved_identity_stages
        ],
        "blocking_stages": list(blocking_stages),
        "first_blocker_stage": first_blocker_stage,
        "first_unobserved_stage": first_unobserved_stage,
        "shadow_reported_commercial_count_unlocked": (
            shadow_reported_commercial_count_unlocked
        ),
        "commercial_authority_granted": commercial_authority_granted,
    }


@dataclass(frozen=True)
class Item35StageFunnel:
    """Immutable stage funnel for one Item 35 shadow result.

    ``first_blocker_stage`` is the earliest observed stage that blocks.  It is
    ``None`` both when nothing observed blocks and when the funnel is
    undetermined; ``first_unobserved_stage`` disambiguates (a non-``None``
    value before any observed blocker means the shadow never reached it).
    """

    record_id: str
    shadow_schema_version: Optional[str]
    shadow_status: str
    shadow_reason: str
    document_id: Optional[str]
    revision_id: Optional[str]
    source_sha256: Optional[str]
    snapshot_id: Optional[str]
    semantic_record_id: Optional[str]
    stages: tuple[StageObservation, ...]
    unobserved_identity_stages: tuple[StageObservation, ...]
    blocking_stages: tuple[str, ...]
    first_blocker_stage: Optional[str]
    first_unobserved_stage: Optional[str]
    shadow_reported_commercial_count_unlocked: bool
    commercial_authority_granted: bool = False
    schema_version: str = ITEM35_STAGE_FUNNEL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.commercial_authority_granted is not False:
            raise ValueError("a diagnostic funnel never grants commercial authority")
        if tuple(stage.stage for stage in self.stages) != OBSERVABLE_STAGES:
            raise ValueError("stages must be the observable stages in pipeline order")
        if (
            tuple(stage.stage for stage in self.unobserved_identity_stages)
            != UNOBSERVED_IDENTITY_STAGES
        ):
            raise ValueError("identity stages must be the unobserved identity stages")
        blocking = tuple(stage.stage for stage in self.stages if stage.blocking)
        if self.blocking_stages != blocking:
            raise ValueError("blocking_stages must match the stage rows")
        if self.first_blocker_stage != (blocking[0] if blocking else None):
            raise ValueError("first_blocker_stage must match the stage rows")
        unobserved = tuple(
            stage.stage for stage in self.stages if not stage.observed
        )
        if self.first_unobserved_stage != (unobserved[0] if unobserved else None):
            raise ValueError("first_unobserved_stage must match the stage rows")
        if self.record_id != stable_contract_id(
            "item35_stage_funnel", self._payload(), digest_chars=32
        ):
            raise ValueError("record_id does not match the funnel content")

    def _payload(self) -> dict[str, Any]:
        return _funnel_payload(
            schema_version=self.schema_version,
            shadow_schema_version=self.shadow_schema_version,
            shadow_status=self.shadow_status,
            shadow_reason=self.shadow_reason,
            document_id=self.document_id,
            revision_id=self.revision_id,
            source_sha256=self.source_sha256,
            snapshot_id=self.snapshot_id,
            semantic_record_id=self.semantic_record_id,
            stages=self.stages,
            unobserved_identity_stages=self.unobserved_identity_stages,
            blocking_stages=self.blocking_stages,
            first_blocker_stage=self.first_blocker_stage,
            first_unobserved_stage=self.first_unobserved_stage,
            shadow_reported_commercial_count_unlocked=(
                self.shadow_reported_commercial_count_unlocked
            ),
            commercial_authority_granted=self.commercial_authority_granted,
        )

    def to_dict(self) -> dict[str, Any]:
        """Fresh JSON-ready mapping; mutating it never changes the funnel."""
        payload = self._payload()
        payload["record_id"] = self.record_id
        return payload


def _fail(message: str) -> ValueError:
    return ValueError(f"invalid Item 35 shadow: {message}")


def _optional_text(shadow: Mapping[str, Any], key: str) -> Optional[str]:
    value = shadow[key]
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise _fail(f"{key} must be a non-empty string or None")
    return value


def _count(shadow: Mapping[str, Any], key: str) -> int:
    value = shadow[key]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _fail(f"{key} must be a non-negative integer")
    return value


def _flag(shadow: Mapping[str, Any], key: str) -> bool:
    value = shadow[key]
    if not isinstance(value, bool):
        raise _fail(f"{key} must be a bool")
    return value


def _text_list(shadow: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = shadow[key]
    if not isinstance(value, (list, tuple)) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise _fail(f"{key} must be a list of non-empty strings")
    return tuple(value)


@dataclass(frozen=True)
class _ShadowView:
    """Validated, detached copy of the shadow fields the funnel reads."""

    schema_version: str
    status: str
    reason: str
    scope: dict[str, Optional[str]]
    counts: dict[str, int]
    flags: dict[str, bool]
    semantic_reason_codes: tuple[str, ...]
    semantic_record_id: Optional[str]
    generic_count_status: EvidenceResolutionStatus
    generic_count_reason_codes: tuple[str, ...]
    generic_count: Optional[int]
    commercial_count_unlocked: bool

    @property
    def scope_present(self) -> bool:
        return all(self.scope[key] is not None for key in _SCOPE_KEYS)

    @property
    def record_present(self) -> bool:
        return self.semantic_record_id is not None


def _read_shadow(shadow: Mapping[str, Any]) -> _ShadowView:
    missing = [key for key in _REQUIRED_KEYS if key not in shadow]
    if missing:
        raise _fail("missing keys " + ", ".join(missing))
    version = shadow["schema_version"]
    if version not in SUPPORTED_ITEM35_SHADOW_SCHEMA_VERSIONS:
        raise _fail(f"unsupported shadow schema_version {version!r}")
    status = shadow["status"]
    if status not in _SHADOW_STATUSES:
        raise _fail(f"unknown shadow status {status!r}")
    reason = shadow["reason"]
    if not isinstance(reason, str) or not reason:
        raise _fail("reason must be a non-empty string")

    scope = {key: _optional_text(shadow, key) for key in _SCOPE_KEYS}
    counts = {key: _count(shadow, key) for key in _COUNT_KEYS}
    flags = {key: _flag(shadow, key) for key in _FLAG_KEYS}
    lists = {key: _text_list(shadow, key) for key in _LIST_KEYS}
    semantic_record_id = _optional_text(shadow, "semantic_record_id")

    try:
        generic_status = EvidenceResolutionStatus(shadow["generic_count_status"])
    except ValueError:
        raise _fail(
            f"unknown generic_count_status {shadow['generic_count_status']!r}"
        ) from None
    generic_count = shadow["generic_count"]
    if generic_count is not None and (
        isinstance(generic_count, bool)
        or not isinstance(generic_count, int)
        or generic_count < 0
    ):
        raise _fail("generic_count must be a non-negative integer or None")
    unlocked = shadow["commercial_count_unlocked"]
    if not isinstance(unlocked, bool):
        raise _fail("commercial_count_unlocked must be a bool")

    view = _ShadowView(
        schema_version=version,
        status=status,
        reason=reason,
        scope=scope,
        counts=counts,
        flags=flags,
        semantic_reason_codes=lists["semantic_reason_codes"],
        semantic_record_id=semantic_record_id,
        generic_count_status=generic_status,
        generic_count_reason_codes=lists["generic_count_reason_codes"],
        generic_count=generic_count,
        commercial_count_unlocked=unlocked,
    )

    # Coherence, all of it fixed by construction in the shadow module.
    present = [scope[key] is not None for key in _SCOPE_KEYS]
    if any(present) and not all(present):
        raise _fail("scope ids must be all present or all absent")
    if unlocked != (generic_count is not None):
        raise _fail("commercial_count_unlocked must equal (generic_count is not None)")
    if generic_count is not None and generic_status is not EvidenceResolutionStatus.CORROBORATED:
        raise _fail("a published generic_count requires a corroborated status")
    if flags["physical_opening_universe_complete"] and not flags[
        "structural_enumeration_complete"
    ]:
        raise _fail("a complete physical universe requires complete structure")
    if view.record_present:
        if not view.scope_present:
            raise _fail("a semantic record requires scope ids")
        if status == "abstained":
            raise _fail("a semantic record cannot coexist with status 'abstained'")
        opening_ids = lists["semantic_opening_record_ids"]
        representatives = lists["representative_observation_ids"]
        if not (
            len(opening_ids)
            == len(representatives)
            == counts["semantic_opening_count"]
        ):
            raise _fail("semantic opening id lists must match semantic_opening_count")
    else:
        if status != "abstained":
            raise _fail(f"status {status!r} requires a semantic record")
        if any(counts.values()) or any(flags.values()):
            raise _fail("counts and flags must be defaults without a semantic record")
        if lists["semantic_opening_record_ids"] or lists["representative_observation_ids"]:
            raise _fail("opening id lists must be empty without a semantic record")
        if not view.scope_present and (
            view.semantic_reason_codes
            or view.generic_count_reason_codes
            or generic_count is not None
            or generic_status is not EvidenceResolutionStatus.ABSTAINED
        ):
            raise _fail("a shadow without scope ids must carry only shell defaults")
    return view


def _all_unobserved_funnel(
    *,
    shadow_schema_version: Optional[str],
    shadow_status: str,
    shadow_reason: str,
    reported_unlocked: bool,
    why: str,
) -> Item35StageFunnel:
    return _make_funnel(
        shadow_schema_version=shadow_schema_version,
        shadow_status=shadow_status,
        shadow_reason=shadow_reason,
        scope={key: None for key in _SCOPE_KEYS},
        semantic_record_id=None,
        stages=tuple(_unobserved(stage, why) for stage in OBSERVABLE_STAGES),
        reported_unlocked=reported_unlocked,
    )


def _make_funnel(
    *,
    shadow_schema_version: Optional[str],
    shadow_status: str,
    shadow_reason: str,
    scope: Mapping[str, Optional[str]],
    semantic_record_id: Optional[str],
    stages: tuple[StageObservation, ...],
    reported_unlocked: bool,
) -> Item35StageFunnel:
    identity_stages = tuple(
        _unobserved(stage, NOT_OBSERVED_IDENTITY_NOT_EXPOSED)
        for stage in UNOBSERVED_IDENTITY_STAGES
    )
    blocking = tuple(stage.stage for stage in stages if stage.blocking)
    unobserved = tuple(stage.stage for stage in stages if not stage.observed)
    fields: dict[str, Any] = {
        "schema_version": ITEM35_STAGE_FUNNEL_SCHEMA_VERSION,
        "shadow_schema_version": shadow_schema_version,
        "shadow_status": shadow_status,
        "shadow_reason": shadow_reason,
        "document_id": scope["document_id"],
        "revision_id": scope["revision_id"],
        "source_sha256": scope["source_sha256"],
        "snapshot_id": scope["snapshot_id"],
        "semantic_record_id": semantic_record_id,
        "stages": stages,
        "unobserved_identity_stages": identity_stages,
        "blocking_stages": blocking,
        "first_blocker_stage": blocking[0] if blocking else None,
        "first_unobserved_stage": unobserved[0] if unobserved else None,
        "shadow_reported_commercial_count_unlocked": reported_unlocked,
        "commercial_authority_granted": False,
    }
    record_id = stable_contract_id(
        "item35_stage_funnel", _funnel_payload(**fields), digest_chars=32
    )
    return Item35StageFunnel(record_id=record_id, **fields)


def _stages_from_view(view: _ShadowView) -> tuple[StageObservation, ...]:
    if not view.scope_present:
        return tuple(
            _unobserved(stage, NOT_OBSERVED_SHADOW_SCOPE_ABSENT)
            for stage in OBSERVABLE_STAGES
        )

    counts = view.counts
    record_present = view.record_present
    visible = counts["visible_observation_count"] if record_present else None

    # Source visibility: the shadow reports scope ids once a snapshot exists, but
    # it exposes no status.  The visible count is a real observation only when
    # a semantic record exists; otherwise the shell default 0 is not one.
    source_visibility = StageObservation(
        stage=STAGE_SOURCE_VISIBILITY,
        observed=True,
        output_count=visible,
        blocking=False,
    )

    # Semantic enumeration.  The shadow collapses every non-conflict record
    # status into "evidence_present", so no status is asserted for it.
    if view.status == "conflict":
        semantic_status: Optional[EvidenceResolutionStatus] = (
            EvidenceResolutionStatus.CONFLICT
        )
    elif view.status == "abstained":
        semantic_status = EvidenceResolutionStatus.ABSTAINED
    else:
        semantic_status = None
    semantic = StageObservation(
        stage=STAGE_SEMANTIC_OPENING_ENUMERATION,
        observed=True,
        status=semantic_status,
        input_count=visible,
        output_count=counts["semantic_opening_count"] if record_present else None,
        blocking=view.status != "evidence_present",
        reason_codes=_codes(view.semantic_reason_codes),
        detail_counts=(
            (("support_observation_count", counts["support_observation_count"]),)
            if record_present
            else ()
        ),
    )

    def flag_stage(
        stage: str,
        flag: str,
        gate_codes: frozenset[str],
        *,
        input_count: Optional[int],
        output_count_when_complete: Optional[int],
        detail_counts: tuple[tuple[str, int], ...],
    ) -> StageObservation:
        if not record_present:
            return _unobserved(stage, NOT_OBSERVED_SEMANTIC_RECORD_ABSENT)
        complete = view.flags[flag]
        return StageObservation(
            stage=stage,
            observed=True,
            # Incomplete evidence abstains; a complete flag asserts no status
            # because the shadow exposes none for it.
            status=None if complete else EvidenceResolutionStatus.ABSTAINED,
            input_count=input_count,
            output_count=output_count_when_complete if complete else None,
            complete=complete,
            blocking=not complete,
            reason_codes=_codes(
                code for code in view.semantic_reason_codes if code in gate_codes
            ),
            detail_counts=detail_counts,
        )

    structural = flag_stage(
        STAGE_STRUCTURAL_ENUMERATION_COMPLETENESS,
        "structural_enumeration_complete",
        _STRUCTURAL_GATE_CODES,
        input_count=visible,
        output_count_when_complete=None,
        detail_counts=(
            (
                "residual_visible_observation_count",
                counts["residual_visible_observation_count"],
            ),
        ),
    )
    physical = flag_stage(
        STAGE_PHYSICAL_OPENING_UNIVERSE_COMPLETENESS,
        "physical_opening_universe_complete",
        _PHYSICAL_UNIVERSE_GATE_CODES,
        input_count=None,
        output_count_when_complete=counts["semantic_opening_count"],
        detail_counts=(),
    )

    # Generic count publication: status and reason codes are the count
    # authority's own, passed through.  Only a corroborated status with a
    # published count passes; everything else blocks.
    published = (
        view.generic_count_status is EvidenceResolutionStatus.CORROBORATED
        and view.generic_count is not None
    )
    generic = StageObservation(
        stage=STAGE_GENERIC_COUNT_PUBLICATION,
        observed=True,
        status=view.generic_count_status,
        output_count=view.generic_count,
        blocking=not published,
        reason_codes=_codes(view.generic_count_reason_codes),
    )
    return (source_visibility, semantic, structural, physical, generic)


def build_item35_stage_funnel(shadow: Mapping[str, Any]) -> Item35StageFunnel:
    """Build the stage funnel from one Item 35 shadow result.

    Raises ``TypeError`` for a non-mapping and ``ValueError`` for a shadow this
    module has not reviewed (unsupported schema version, missing or incoherent
    fields).  It never mutates ``shadow`` and never runs an authority.
    """
    if not isinstance(shadow, Mapping):
        raise TypeError("shadow must be a mapping")

    if "schema_version" not in shadow:
        if (
            set(shadow) <= _NOT_COLLECTED_KEYS
            and shadow.get("status") == "abstained"
            and shadow.get("reason") == _NOT_COLLECTED_REASON
            and shadow.get("commercial_count_unlocked") is False
        ):
            return _all_unobserved_funnel(
                shadow_schema_version=None,
                shadow_status="abstained",
                shadow_reason=_NOT_COLLECTED_REASON,
                reported_unlocked=False,
                why=NOT_OBSERVED_SHADOW_NOT_COLLECTED,
            )
        raise _fail("missing schema_version and not the extractor's not_collected placeholder")

    view = _read_shadow(shadow)
    return _make_funnel(
        shadow_schema_version=view.schema_version,
        shadow_status=view.status,
        shadow_reason=view.reason,
        scope=view.scope,
        semantic_record_id=view.semantic_record_id,
        stages=_stages_from_view(view),
        reported_unlocked=view.commercial_count_unlocked,
    )


def _sorted_counts(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def aggregate_item35_stage_funnels(
    funnels: Iterable[Item35StageFunnel],
) -> dict[str, Any]:
    """Deterministic, order-invariant tally over many funnels.

    Ties for the dominant first blocker are all reported; none is chosen by
    order, name or size.  ``no_observed_blocker_funnel_count`` counts funnels
    where no observable stage blocks.  It is NOT a pass: the three identity
    stages are always unobserved, and ``undetermined_funnel_count`` (a stage the
    shadow never reached) is tallied separately.
    """
    ordered = sorted(list(funnels), key=lambda item: getattr(item, "record_id", ""))
    if not all(isinstance(item, Item35StageFunnel) for item in ordered):
        raise TypeError("funnels must be Item35StageFunnel instances")

    per_stage: dict[str, dict[str, Any]] = {}
    for stage in OBSERVABLE_STAGES + UNOBSERVED_IDENTITY_STAGES:
        rows = [
            row
            for funnel in ordered
            for row in funnel.stages + funnel.unobserved_identity_stages
            if row.stage == stage
        ]
        observed = [row for row in rows if row.observed]
        status_counts: Counter[str] = Counter(
            row.status.value if row.status is not None else STATUS_NOT_EXPOSED
            for row in observed
        )
        code_counts: Counter[str] = Counter(
            code for row in observed for code in row.reason_codes
        )
        per_stage[stage] = {
            "observed": len(observed),
            "unobserved": len(rows) - len(observed),
            "blocking": sum(1 for row in observed if row.blocking),
            "complete_true": sum(1 for row in observed if row.complete is True),
            "complete_false": sum(1 for row in observed if row.complete is False),
            "status_counts": _sorted_counts(status_counts),
            "reason_code_counts": _sorted_counts(code_counts),
        }

    first_blocker: Counter[str] = Counter()
    first_unobserved: Counter[str] = Counter()
    first_blocker_codes: dict[str, Counter[str]] = {}
    undetermined = 0
    no_observed_blocker = 0
    for funnel in ordered:
        if funnel.first_unobserved_stage is not None:
            first_unobserved[funnel.first_unobserved_stage] += 1
        if funnel.first_blocker_stage is not None:
            first_blocker[funnel.first_blocker_stage] += 1
            row = next(
                item for item in funnel.stages if item.stage == funnel.first_blocker_stage
            )
            first_blocker_codes.setdefault(funnel.first_blocker_stage, Counter()).update(
                row.reason_codes
            )
        elif funnel.first_unobserved_stage is not None:
            undetermined += 1
        else:
            no_observed_blocker += 1

    top = max(first_blocker.values(), default=0)
    dominant = tuple(sorted(stage for stage, n in first_blocker.items() if n == top)) if top else ()
    payload: dict[str, Any] = {
        "schema_version": ITEM35_STAGE_FUNNEL_SCHEMA_VERSION,
        "funnel_count": len(ordered),
        "funnel_record_ids": [item.record_id for item in ordered],
        "per_stage": per_stage,
        "first_blocker_stage_counts": _sorted_counts(first_blocker),
        "first_blocker_reason_code_counts": {
            stage: _sorted_counts(first_blocker_codes[stage])
            for stage in sorted(first_blocker_codes)
        },
        "dominant_first_blocker_stages": list(dominant),
        "first_unobserved_stage_counts": _sorted_counts(first_unobserved),
        "undetermined_funnel_count": undetermined,
        "no_observed_blocker_funnel_count": no_observed_blocker,
        "shadow_status_counts": _sorted_counts(
            Counter(item.shadow_status for item in ordered)
        ),
        "shadow_reason_counts": _sorted_counts(
            Counter(item.shadow_reason for item in ordered)
        ),
        "shadow_reported_commercial_count_unlocked_count": sum(
            1 for item in ordered if item.shadow_reported_commercial_count_unlocked
        ),
        "unobserved_identity_stages": list(UNOBSERVED_IDENTITY_STAGES),
        "commercial_authority_granted": False,
    }
    payload["record_id"] = stable_contract_id(
        "item35_stage_funnel_summary", payload, digest_chars=32
    )
    return payload


__all__ = [
    "ITEM35_STAGE_FUNNEL_SCHEMA_VERSION",
    "Item35StageFunnel",
    "NOT_OBSERVED_IDENTITY_NOT_EXPOSED",
    "NOT_OBSERVED_SEMANTIC_RECORD_ABSENT",
    "NOT_OBSERVED_SHADOW_NOT_COLLECTED",
    "NOT_OBSERVED_SHADOW_SCOPE_ABSENT",
    "OBSERVABLE_STAGES",
    "REVIEWED_ITEM35_SHADOW_KEYS",
    "STAGE_GENERIC_COUNT_PUBLICATION",
    "STAGE_OPENING_HOST_BINDING",
    "STAGE_PHYSICAL_OPENING_EXISTENCE",
    "STAGE_PHYSICAL_OPENING_IDENTITY",
    "STAGE_PHYSICAL_OPENING_UNIVERSE_COMPLETENESS",
    "STAGE_SEMANTIC_OPENING_ENUMERATION",
    "STAGE_SOURCE_VISIBILITY",
    "STAGE_STRUCTURAL_ENUMERATION_COMPLETENESS",
    "STATUS_NOT_EXPOSED",
    "SUPPORTED_ITEM35_SHADOW_SCHEMA_VERSIONS",
    "StageObservation",
    "UNOBSERVED_IDENTITY_STAGES",
    "aggregate_item35_stage_funnels",
    "build_item35_stage_funnel",
]
