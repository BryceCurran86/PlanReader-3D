"""Default-off, read-only OPENING OCCUPANCY of plan callout anchors, strictly SHADOW.

Question answered: for each named callout anchor (a trusted opening-tag word's proven visible envelope box,
else its text box) on one plan page, does the anchor lie inside the jamb-bounded aperture of exactly one
physical opening that the producer's own authority CORROBORATES, and inside the aperture of no other
candidate the producer discovered on that page?

It is the relation the schedule-to-opening binder already uses to own a plan tag ("plan tags must be inside
the actual jamb-bounded opening aperture"): the aperture is built by the binder's own `_opening_aperture`
from the opening's own source observations and the anchor is tested with the binder's own
`_aperture_contains_bbox` (centre inside both the along range and the face-band normal range). Nothing is
re-implemented or loosened here, there is no distance, no nearest choice and no letter test; the only
inputs are producer candidates, producer existence proofs and the anchors a caller names.

What a positive result means: the anchor is positioned inside one corroborated opening's gap and no
rival candidate contests that. What it never means: that the tag labels that opening, that the opening is
a door or a window, which wall hosts it, what it measures, or that the tag is not also a type mark of other
instances. It decides nothing about any strip. It never produces a `PhysicalOpeningExistenceRecord` and it
imports nothing from the live issuer, the host binder, the count producer or any live quantity code.

Isolation: every authority call runs on the producer's own independent replay of the immutable source bytes
(`fork_native_source_shadow`), so no producer-level memo of the caller's source is filled.

Abstains (typed) rather than choosing: an anchor inside several candidate apertures (contested), inside one
that is not corroborated, inside none, a record that is not the candidate it was proven from, a candidate whose
aperture cannot be built (that makes every anchor's contest unprovable, so the whole inventory abstains), a
published observation that fails authentication, or a work bound.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, fields
from typing import Callable, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,
    VISIBLE_SOURCE_AUTHORITY_REQUIRED,
)
from pb_source_plan_glazing_strip_callout_shadow import (
    OCCUPANCY_BASIS_ENVELOPE,
    OCCUPANCY_BASIS_TEXT,
    PRODUCER_INPUT_PROVENANCE,
    ClaimantOccupancy,
    SourceOwnership,
)

OPENING_OCCUPANCY_SCHEMA_VERSION = "1.0.0"
OPENING_OCCUPANCY_METHOD = "plan_tag_opening_occupancy_shadow"

OCCUPANCY_DISABLED = "plan_tag_opening_occupancy_disabled"
OCCUPANCY_BUDGET_EXCEEDED = "plan_tag_opening_occupancy_budget_exceeded"
OCCUPANCY_CENSUS_PRODUCED = "plan_tag_opening_occupancy_census_produced"
CANDIDATE_APERTURE_UNAVAILABLE = "plan_candidate_aperture_unavailable"
PAGE_CANDIDATE_CENSUS_UNAVAILABLE = "plan_page_candidate_census_unavailable"

OUTCOME_OCCUPIED = "occupied_by_one_corroborated_opening"
OUTCOME_NONE = "anchor_in_no_candidate_aperture"
OUTCOME_CONTESTED = "anchor_in_several_candidate_apertures"
OUTCOME_NOT_CORROBORATED = "anchor_in_one_candidate_not_corroborated"
OUTCOME_RECORD_MISMATCH = "occupying_record_differs_from_its_candidate"

TAG_TYPE_VS_INSTANCE_UNPROVED = "tag_type_vs_instance_unproved"
OCCUPANCY_IS_LOCATION_NOT_KIND_OR_HOST = "occupancy_is_location_not_kind_host_or_identity"
# An occupancy is only as sound as the producer's own existence proof: a corroborated aperture that is not a real
# opening (for example an internal glazing subdivision gap) would be a false witness until that authority vetoes it.
OCCUPANCY_INHERITS_EXISTENCE_AUTHORITY_ERRORS = "occupancy_inherits_physical_opening_existence_authority_errors"
STANDING_LIMITS = (TAG_TYPE_VS_INSTANCE_UNPROVED, OCCUPANCY_IS_LOCATION_NOT_KIND_OR_HOST,
                   OCCUPANCY_INHERITS_EXISTENCE_AUTHORITY_ERRORS)

# Work bounds only: they stop a pathological page from being analysed, they decide nothing.
_MAX_CANDIDATES = 50_000
_MAX_ANCHORS = 20_000
# The binder's own tolerance (`_COORD_TOL` there): the same relation, not a new threshold.
_CONTAINMENT_TOL = 1e-6

_GRANT_FLAGS = (
    "physical_opening_granted", "host_granted", "opening_kind_granted", "frame_granted", "scale_granted",
    "metric_granted", "count_granted", "quantity_granted", "wall_binding_granted",
    "commercial_projection_allowed", "customer_publication_granted", "takeoff_eligible", "deduction_authority",
    "existence_record_issued",
)


# --------------------------------------------------------------------------------------
# records
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class TagAnchor:
    """Where a trusted opening-tag word's callout symbol is anchored, as named by the caller."""

    word_observation_id: str
    anchor_box: tuple[float, float, float, float]
    basis: str

    def __post_init__(self) -> None:
        if (type(self.word_observation_id) is not str or not self.word_observation_id
                or self.basis not in (OCCUPANCY_BASIS_ENVELOPE, OCCUPANCY_BASIS_TEXT)
                or type(self.anchor_box) is not tuple or len(self.anchor_box) != 4
                or not all(type(v) in (int, float) and math.isfinite(v) for v in self.anchor_box)
                or self.anchor_box[0] > self.anchor_box[2] or self.anchor_box[1] > self.anchor_box[3]):
            raise ValueError("a tag anchor needs a word id, a finite ordered box and a known basis")


@dataclass(frozen=True)
class ApertureFrame:
    axis: tuple[float, float]
    normal: tuple[float, float]
    along: tuple[float, float]
    normal_range: tuple[float, float]


@dataclass(frozen=True)
class CandidateAperture:
    candidate_id: str
    member_observation_ids: tuple[str, ...]
    frame: Optional[ApertureFrame]


@dataclass(frozen=True)
class ExistenceFact:
    """What the producer's own existence proof said about one candidate (all fields supplied by the adapter)."""

    status: EvidenceResolutionStatus
    record_id: Optional[str]
    record_observation_ids: tuple[str, ...]
    record_frame: Optional[ApertureFrame]


@dataclass(frozen=True)
class AnchorOccupancyDiagnostic:
    word_observation_id: str
    basis: str
    outcome: str
    containing_candidate_ids: tuple[str, ...]
    containing_existence: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class OpeningOccupancyInventory:
    ownership: Optional[SourceOwnership]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    standing_limits: tuple[str, ...]
    candidate_count: int
    occupancies: tuple[ClaimantOccupancy, ...]
    diagnostics: tuple[AnchorOccupancyDiagnostic, ...]
    record_id: Optional[str]
    shadow_only: bool = True
    physical_opening_granted: bool = False
    host_granted: bool = False
    opening_kind_granted: bool = False
    frame_granted: bool = False
    scale_granted: bool = False
    metric_granted: bool = False
    count_granted: bool = False
    quantity_granted: bool = False
    wall_binding_granted: bool = False
    commercial_projection_allowed: bool = False
    customer_publication_granted: bool = False
    takeoff_eligible: bool = False
    deduction_authority: bool = False
    existence_record_issued: bool = False
    schema_version: str = OPENING_OCCUPANCY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.shadow_only is not True:
            raise ValueError("an occupancy inventory cannot leave shadow mode")
        for name in _GRANT_FLAGS:
            if getattr(self, name) is not False:
                raise ValueError(f"an occupancy inventory cannot grant {name}")
        if not {f.name for f in fields(self)} >= set(_GRANT_FLAGS):
            raise ValueError("grant flag set is out of date")
        if self.status not in (EvidenceResolutionStatus.CANDIDATE, EvidenceResolutionStatus.ABSTAINED):
            raise ValueError("an occupancy inventory is CANDIDATE or ABSTAINED only")
        if self.status is not EvidenceResolutionStatus.CANDIDATE and (self.occupancies or self.diagnostics):
            raise ValueError("an abstained inventory carries no occupancy or diagnostic")
        occupied = {d.word_observation_id for d in self.diagnostics if d.outcome == OUTCOME_OCCUPIED}
        if {o.word_observation_id for o in self.occupancies} != occupied:
            raise ValueError("occupancy records and occupied diagnostics must name the same words")


# --------------------------------------------------------------------------------------
# pure core
# --------------------------------------------------------------------------------------


def frame_contains(frame: ApertureFrame, box: Sequence[float]) -> bool:
    """The binder's tag containment: the box centre inside both the along range and the normal range."""
    cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
    along = cx * frame.axis[0] + cy * frame.axis[1]
    normal = cx * frame.normal[0] + cy * frame.normal[1]
    return bool(frame.along[0] - _CONTAINMENT_TOL <= along <= frame.along[1] + _CONTAINMENT_TOL
                and frame.normal_range[0] - _CONTAINMENT_TOL <= normal <= frame.normal_range[1] + _CONTAINMENT_TOL)


def evaluate_occupancy(
    *, ownership: SourceOwnership, candidates: Sequence[CandidateAperture], anchors: Sequence[TagAnchor],
    existence_for: Callable[[CandidateAperture], ExistenceFact],
) -> tuple[tuple[ClaimantOccupancy, ...], tuple[AnchorOccupancyDiagnostic, ...]]:
    """Every anchor is evaluated against EVERY candidate aperture; nothing is ranked or chosen.

    `existence_for` is called only for the single candidate that contains an anchor, at most once per
    candidate; it must never be consulted for choosing between candidates."""
    ids = [a.word_observation_id for a in anchors]
    if len(ids) != len(set(ids)):
        raise ValueError("an anchor is named once per word")
    cand_ids = [c.candidate_id for c in candidates]
    if len(cand_ids) != len(set(cand_ids)):
        raise ValueError("candidate ids are unique")
    if any(c.frame is None for c in candidates):
        raise ValueError("every candidate needs an aperture frame; an unbuildable one must abstain upstream")
    cache: dict[str, ExistenceFact] = {}

    def fact(candidate: CandidateAperture) -> ExistenceFact:
        if candidate.candidate_id not in cache:
            cache[candidate.candidate_id] = existence_for(candidate)
        return cache[candidate.candidate_id]

    occupancies: list[ClaimantOccupancy] = []
    diagnostics: list[AnchorOccupancyDiagnostic] = []
    for anchor in sorted(anchors, key=lambda a: a.word_observation_id):
        containing = [c for c in candidates if frame_contains(c.frame, anchor.anchor_box)]
        containing.sort(key=lambda c: c.candidate_id)
        cids = tuple(c.candidate_id for c in containing)
        if not containing:
            diagnostics.append(AnchorOccupancyDiagnostic(anchor.word_observation_id, anchor.basis, OUTCOME_NONE, (), ()))
            continue
        # existence is read for every containing candidate (a diagnostic) but only a unique one can occupy
        existence = tuple((c.candidate_id, fact(c).status.value) for c in containing)
        if len(containing) > 1:
            diagnostics.append(AnchorOccupancyDiagnostic(
                anchor.word_observation_id, anchor.basis, OUTCOME_CONTESTED, cids, existence))
            continue
        candidate, proof = containing[0], fact(containing[0])
        if proof.status is not EvidenceResolutionStatus.CORROBORATED or proof.record_id is None:
            diagnostics.append(AnchorOccupancyDiagnostic(
                anchor.word_observation_id, anchor.basis, OUTCOME_NOT_CORROBORATED, cids, existence))
            continue
        if (set(proof.record_observation_ids) != set(candidate.member_observation_ids)
                or len(proof.record_observation_ids) != len(set(proof.record_observation_ids))
                or proof.record_frame is None or not frame_contains(proof.record_frame, anchor.anchor_box)):
            diagnostics.append(AnchorOccupancyDiagnostic(
                anchor.word_observation_id, anchor.basis, OUTCOME_RECORD_MISMATCH, cids, existence))
            continue
        f = proof.record_frame
        occupancies.append(ClaimantOccupancy(
            ownership=ownership, word_observation_id=anchor.word_observation_id, occupied_record_id=proof.record_id,
            occupied_observation_ids=tuple(sorted(proof.record_observation_ids)), aperture_axis=f.axis,
            aperture_normal=f.normal, aperture_along=f.along, aperture_normal_range=f.normal_range,
            anchor_box=anchor.anchor_box, basis=anchor.basis, competing_candidate_count=0))
        diagnostics.append(AnchorOccupancyDiagnostic(
            anchor.word_observation_id, anchor.basis, OUTCOME_OCCUPIED, cids, existence))
    return tuple(occupancies), tuple(diagnostics)


def _inventory(ownership, status, reasons, candidate_count, occupancies, diagnostics) -> OpeningOccupancyInventory:
    record_id = None
    if status is EvidenceResolutionStatus.CANDIDATE:
        record_id = stable_contract_id("shadow_plan_tag_opening_occupancy", {
            "ownership": (ownership.document_id, ownership.revision_id, ownership.snapshot_id, ownership.source_sha256),
            "candidates": candidate_count,
            "occupancies": tuple((o.word_observation_id, o.occupied_record_id, o.occupied_observation_ids, o.basis)
                                 for o in occupancies),
            "diagnostics": tuple((d.word_observation_id, d.outcome, d.containing_candidate_ids,
                                  d.containing_existence) for d in diagnostics),
        }, digest_chars=24)
    return OpeningOccupancyInventory(
        ownership=ownership, status=status, reason_codes=tuple(reasons), standing_limits=STANDING_LIMITS,
        candidate_count=candidate_count, occupancies=tuple(occupancies), diagnostics=tuple(diagnostics),
        record_id=record_id)


# --------------------------------------------------------------------------------------
# producer adapter: the only place that reads a SourceVisibilityProducer
# --------------------------------------------------------------------------------------


class PlanTagOpeningOccupancyShadow:
    """Opt-in census. `enabled` must be an explicit bool; the default is off and off touches nothing."""

    def __init__(self, source, *, enabled: bool = False):
        if type(enabled) is not bool:
            raise TypeError("enabled must be an explicit bool")
        self._source = source
        self._enabled = enabled

    def _abstain(self, ownership, *codes) -> OpeningOccupancyInventory:
        return _inventory(ownership, EvidenceResolutionStatus.ABSTAINED, codes, 0, (), ())

    def _fork_for(self, revision_id: str, published):
        """An independent replay whose revision, snapshot and visible observation ids equal the original's."""
        try:
            fork, _ = self._source.fork_native_source_shadow(revision_id)
            replayed = fork.published_snapshot_for_revision(revision_id)
            same = (replayed is not None
                    and replayed.revision.source_sha256 == published.revision.source_sha256
                    and replayed.snapshot.snapshot_id == published.snapshot.snapshot_id
                    and tuple(replayed.visible_observation_ids) == tuple(published.visible_observation_ids))
            return fork if same else None
        except (ValueError, RuntimeError):
            return None

    def inventory(self, *, revision_id: str, page_id: int, anchors: Sequence[TagAnchor]) -> OpeningOccupancyInventory:
        if not self._enabled:
            return self._abstain(None, OCCUPANCY_DISABLED)
        if (type(revision_id) is not str or type(page_id) is not int or isinstance(page_id, bool)
                or isinstance(anchors, (str, bytes)) or any(type(a) is not TagAnchor for a in anchors)):
            raise ValueError("revision id, integer page id and TagAnchor records required")
        ids = [a.word_observation_id for a in anchors]
        if len(ids) != len(set(ids)):
            raise ValueError("an anchor is named once per word")

        from pb_schedule_opening_instance_binding_authority import _opening_aperture
        from pb_source_observation_authority import ObservationSelector

        source = self._source
        published = source.published_snapshot_for_revision(revision_id)
        if published is None:
            return self._abstain(None, VISIBLE_SOURCE_AUTHORITY_REQUIRED)
        document_id = published.revision.document_id
        ownership = SourceOwnership(
            document_id=document_id, revision_id=revision_id, snapshot_id=published.snapshot.snapshot_id,
            source_sha256=published.revision.source_sha256, input_provenance=PRODUCER_INPUT_PROVENANCE)
        if (page_id not in tuple(int(v) for v in published.coverage.decoded_pages)
                or int(page_id) in tuple(int(v) for v in published.coverage.failed_pages)
                or source._producer.current_revision_id(document_id) != revision_id):
            return self._abstain(ownership, VISIBLE_SOURCE_AUTHORITY_REQUIRED)
        if len(anchors) > _MAX_ANCHORS:
            return self._abstain(ownership, OCCUPANCY_BUDGET_EXCEEDED)

        def selector(observation_id: str) -> ObservationSelector:
            return ObservationSelector(
                document_id=document_id, revision_id=revision_id, source_sha256=ownership.source_sha256,
                snapshot_id=ownership.snapshot_id, observation_id=observation_id)

        fork = self._fork_for(revision_id, published)
        if fork is None:
            return self._abstain(ownership, SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE)
        authority = fork.physical_opening_authority()
        visibility = fork.authority()
        # any visible observation of the page names the page whose candidates are wanted
        page_observation = None
        for observation_id in published.visible_observation_ids:
            resolved = visibility.resolve_visible(selector(observation_id))
            if resolved.observation is not None and str(resolved.observation.page_id) == str(page_id):
                page_observation = observation_id
                break
        if page_observation is None:
            return self._abstain(ownership, PAGE_CANDIDATE_CENSUS_UNAVAILABLE)
        structures = authority.visible_candidate_structures(selector(page_observation))
        if structures.status is not EvidenceResolutionStatus.CANDIDATE or structures.page_id != str(page_id):
            return self._abstain(ownership, PAGE_CANDIDATE_CENSUS_UNAVAILABLE)
        if len(structures.candidates) > _MAX_CANDIDATES:
            return self._abstain(ownership, OCCUPANCY_BUDGET_EXCEEDED)

        def frame_of(observation_ids: Sequence[str]) -> Optional[ApertureFrame]:
            records = []
            for observation_id in observation_ids:
                resolved = visibility.resolve_visible(selector(observation_id))
                if resolved.status is not EvidenceResolutionStatus.CORROBORATED or resolved.observation is None:
                    return None
                records.append(resolved.observation)
            ap = _opening_aperture(records)
            if ap is None:
                return None
            return ApertureFrame(
                axis=(float(ap.axis[0]), float(ap.axis[1])), normal=(float(ap.normal[0]), float(ap.normal[1])),
                along=(float(ap.along_min), float(ap.along_max)),
                normal_range=(float(ap.normal_min), float(ap.normal_max)))

        candidates: list[CandidateAperture] = []
        for candidate in structures.candidates:
            members = tuple(candidate.source_observation_ids)
            # A published candidate is a source-owned record, not merely geometrically plausible ids: a foreign,
            # stale, empty or duplicated one cannot be discarded as "not containing" an anchor.
            if (candidate.document_id != document_id or candidate.revision_id != revision_id
                    or candidate.source_sha256 != ownership.source_sha256
                    or candidate.snapshot_id != ownership.snapshot_id or candidate.page_id != str(page_id)
                    or not members or len(members) != len(set(members))):
                return self._abstain(ownership, SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE)
            frame = frame_of(members)
            if frame is None:
                # without its aperture the candidate's contest of any anchor is unprovable
                return self._abstain(ownership, CANDIDATE_APERTURE_UNAVAILABLE)
            candidates.append(CandidateAperture(candidate.candidate_id, tuple(sorted(members)), frame))

        def existence_for(candidate: CandidateAperture) -> ExistenceFact:
            # EVERY member of the candidate is proven, not one chosen member: a member shared with a rival
            # candidate is ambiguous, and one member's corroboration must not hide another's conflict.
            statuses, records = [], []
            for member in candidate.member_observation_ids:
                outcome = authority.prove_existence(selector(member))
                record = outcome.existence_record
                if (outcome.status is not EvidenceResolutionStatus.CORROBORATED or record is None
                        or record.status is not EvidenceResolutionStatus.CORROBORATED
                        or record.proposition != PHYSICAL_OPENING_EXISTS
                        or record.document_id != document_id or record.revision_id != revision_id
                        or record.source_sha256 != ownership.source_sha256
                        or record.snapshot_id != ownership.snapshot_id or str(record.page_id) != str(page_id)):
                    # A positive wrapper with a missing/foreign/invalid record
                    # is an abstention, not a positive candidate member. Keeping
                    # CORROBORATED here also left no negative for the final
                    # reduction and raised StopIteration instead of failing closed.
                    statuses.append(EvidenceResolutionStatus.ABSTAINED
                                    if outcome.status is EvidenceResolutionStatus.CORROBORATED else outcome.status)
                    continue
                statuses.append(EvidenceResolutionStatus.CORROBORATED)
                records.append((str(record.record_id), tuple(record.source_observation_ids)))
            if len(records) == len(candidate.member_observation_ids) and len(set(records)) == 1:
                record_id, record_ids = records[0]
                return ExistenceFact(EvidenceResolutionStatus.CORROBORATED, record_id, record_ids, frame_of(record_ids))
            if EvidenceResolutionStatus.CONFLICT in statuses or len(set(records)) > 1:
                return ExistenceFact(EvidenceResolutionStatus.CONFLICT, None, (), None)
            return ExistenceFact(next(s for s in statuses if s is not EvidenceResolutionStatus.CORROBORATED), None, (), None)

        occupancies, diagnostics = evaluate_occupancy(
            ownership=ownership, candidates=candidates, anchors=list(anchors), existence_for=existence_for)
        return _inventory(ownership, EvidenceResolutionStatus.CANDIDATE, (OCCUPANCY_CENSUS_PRODUCED,),
                          len(candidates), occupancies, diagnostics)


__all__ = [
    "AnchorOccupancyDiagnostic", "ApertureFrame", "CandidateAperture", "ExistenceFact", "OpeningOccupancyInventory",
    "PlanTagOpeningOccupancyShadow", "TagAnchor", "evaluate_occupancy", "frame_contains", "STANDING_LIMITS",
]
