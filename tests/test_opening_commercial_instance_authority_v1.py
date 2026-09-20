"""Adversarial tests for pb_opening_commercial_instance_authority.py (Item 35
Phase C / PR 3): the commercial count reconciliation authority.

Every "positive" fixture here goes through real, unmocked infrastructure --
a real in-memory PDF ingested through SourceVisibilityProducer, real G17
six-segment visible apertures (two wall faces each continuing on both sides
of one gap, plus two jambs) independently provable via the real, unmodified
PhysicalOpeningAuthority, a real authenticated TagObservation/TagBindingEvidence
pair, and a real OpeningUniverseCompletenessAuthority/OpeningScheduleCountAuthority.
This module never accepts a pre-computed positive OpeningTagBindingResult --
it always replays OpeningIdentityResolver.resolve_tag_binding() itself, so
these tests build the raw evidence that replay consumes, not a shortcut
result object.

Only the two identity-graph-consistency tests (SAME/SAME/DISTINCT
contradiction, and a bare CONFLICT comparison) use a minimal local test
double for PhysicalOpeningAuthority.compare_identity(): G17's real identity
comparison is equality of a deterministic hash and is therefore always
transitively consistent by construction -- it cannot itself produce a
non-transitive graph. Those two tests exist to prove this module's own
defensive graph-consistency code does not blindly trust transitivity
either, independent of whether the real dependency could ever supply such
an input.
"""
from __future__ import annotations

from dataclasses import dataclass

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_commercial_instance_authority import (
    COMMERCIAL_COUNT_AMBIGUOUS_SCHEDULE_ROWS,
    COMMERCIAL_COUNT_INCONSISTENT_IDENTITY_GRAPH,
    COMMERCIAL_COUNT_NO_PHYSICAL_INSTANCES,
    COMMERCIAL_COUNT_NO_SCHEDULE_ROW,
    COMMERCIAL_COUNT_RECORD_UNAVAILABLE,
    COMMERCIAL_COUNT_SCHEDULE_PHYSICAL_MISMATCH,
    COMMERCIAL_COUNT_UNIVERSE_INCOMPLETE,
    OpeningCommercialInstanceProducer,
    OpeningCommercialInstanceSelector,
    OpeningInstanceEvidenceBundle,
    _resolve_physical_identity_count,
)
from pb_opening_schedule_count_authority import OpeningScheduleCountProducer
from pb_opening_schedule_v171 import ScheduleEntry, parse_schedule_rows
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessProducer,
)
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_IDENTITIES_DISTINCT,
    PHYSICAL_OPENING_IDENTITY_UNRESOLVED,
    PhysicalOpeningAuthority,
    PhysicalOpeningIdentityResult,
)
from pb_source_observation_authority import (
    ObservationSelector,
    SourceDecodeCoverageRecord,
)
from pb_source_opening_candidate_authority import (
    AuthenticatedViewportDecision,
    SourceToleranceProvenance,
    TagBindingEvidence,
    TagBindingRelationKind,
    TagObservation,
    authenticate_tag_binding_evidence,
    authenticate_viewport_decision,
    create_opening_candidate,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import SegmentedViewport
from pb_viewport_view_class_authority import (
    VIEW_KIND_FLOOR_PLAN,
    ViewportViewClassProducer,
    ViewportViewClassSelector,
)

pytestmark = pytest.mark.filterwarnings("ignore")

_DECISION_SCOPE_ID = "scope_p1"


@dataclass
class _Instance:
    mark: str
    page_id: str
    existence_selector: ObservationSelector
    tag_observation: TagObservation
    binding_evidence: TagBindingEvidence
    candidate: object


def _viewport_decision(
    *, document_id: str, revision_id: str, source_sha256: str, snapshot_id: str
) -> AuthenticatedViewportDecision:
    """Build a real, CORROBORATED AuthenticatedViewportDecision scoped to one
    fixture's actual (content-derived) document/revision/sha/snapshot.

    create_opening_candidate() cross-checks viewport_decision.selector
    against the candidate's own scope fields and demotes the candidate to
    RAW on any mismatch -- and OpeningIdentityResolver.resolve_tag_binding()
    refuses to bind a tag to a non-CANDIDATE-status candidate at all
    ("non_candidate_cannot_bind_tag"). A single module-level decision with
    fixed placeholder scope fields would silently demote every fixture's
    candidates to RAW, since each fixture's real revision/sha/snapshot are
    content-derived and differ per PDF -- so this must be built fresh per
    environment, not shared.
    """
    selector = ViewportViewClassSelector(
        document_id=document_id,
        revision_id=revision_id,
        source_sha256=source_sha256,
        snapshot_id=snapshot_id,
        viewport_id="vp-1",
    )
    producer = ViewportViewClassProducer.create()
    producer.publish(
        selector,
        view_kind=VIEW_KIND_FLOOR_PLAN,
        evidence_observation_ids=("obs_view_title",),
    )
    viewport = SegmentedViewport(
        view_id="vp-1",
        page_number=1,
        view_type="floor_plan",
        label="GROUND FLOOR PLAN",
        title_bbox=(0.0, 0.0, 50.0, 20.0),
        bounding_box=(0.0, 0.0, 5000.0, 400.0),
        status="resolved",
        boundary_source="vector_frame",
        confidence=1.0,
    )
    return authenticate_viewport_decision(
        viewport=viewport,
        view_class_authority=producer.authority(),
        selector=selector,
    )


def _build_environment(*, marks: list[str], page_ids: list[str] | None = None) -> dict:
    """Build one shared in-memory PDF with a real, independently
    G17-provable aperture per mark, plus a real tag positioned inside that
    aperture for each, all in one SourceVisibilityAuthority/document scope.

    G17's PhysicalOpeningAuthority only returns CORROBORATED/PHYSICAL_OPENING_EXISTS
    via its "visible" path (SourceVisibilityProducer, a real 6-segment
    two-face-continuation-plus-two-jambs pattern) -- the plain
    SourceObservationAuthority-backed "raw" path only ever reaches CANDIDATE
    status, exactly because a candidate must never be treated as proven
    physical existence (see pb_physical_opening_authority.py, and Hard Gate 1
    in pb_opening_commercial_instance_authority.py). SourceVisibilityProducer
    auto-derives the 6 NATIVE_PDF_VISIBLE_SEGMENT observations from plain
    drawn lines -- no manual publish_derived_observation needed.
    """
    n = len(marks)
    if page_ids is None:
        page_ids = ["1"] * n
    spacing = 300.0
    doc = fitz.open()
    pages_by_id: dict[str, fitz.Page] = {}
    tag_points: list[tuple[float, float]] = []
    for i in range(n):
        pid = page_ids[i]
        if pid not in pages_by_id:
            pages_by_id[pid] = doc.new_page(width=100.0 + spacing * n, height=100.0 + spacing * n)
        page = pages_by_id[pid]
        ox = spacing * i
        # Every instance also gets its own y-band (oy), not just its own
        # x-range. G17's visible-existence matching treats ANY two mutually
        # collinear segments as one continuous face regardless of how far
        # apart they are -- with every instance's face lines at the SAME y,
        # face pieces from DIFFERENT instances are collinear with each
        # other too, and the algorithm can pair instance A's left jamb with
        # instance B's right jamb into a spurious "aperture" spanning both,
        # making prove_existence() correctly (but unhelpfully, for this
        # fixture) return CONFLICT for ambiguous candidate membership. A
        # distinct oy per instance keeps every instance's faces on their
        # own line, so only genuine same-instance segments are ever collinear.
        oy = spacing * i
        # Two wall faces, each continuing visibly on both sides of one
        # common [100+ox, 140+ox] gap, plus two jambs -- the exact pattern
        # tests/test_g17_visible_opening_existence_v1.py proves resolves to
        # a real CORROBORATED PHYSICAL_OPENING_EXISTS.
        for a, b in (
            ((20.0 + ox, 100.0 + oy), (100.0 + ox, 100.0 + oy)),
            ((140.0 + ox, 100.0 + oy), (220.0 + ox, 100.0 + oy)),
            ((20.0 + ox, 110.0 + oy), (100.0 + ox, 110.0 + oy)),
            ((140.0 + ox, 110.0 + oy), (220.0 + ox, 110.0 + oy)),
            ((100.0 + ox, 100.0 + oy), (100.0 + ox, 110.0 + oy)),
            ((140.0 + ox, 100.0 + oy), (140.0 + ox, 110.0 + oy)),
        ):
            page.draw_line(fitz.Point(*a), fitz.Point(*b))
        # Insertion origin chosen so the rendered glyph bbox (which extends
        # up and slightly below the baseline origin) centers inside the
        # aperture rectangle [100+ox,140+ox] x [100+oy,110+oy] --
        # resolve_tag_binding() has its own independent proximity pre-filter
        # (tag CENTER within a sub-point tolerance of the candidate bbox),
        # separate from and in addition to authenticate_tag_binding_evidence()'s
        # relation check, so the tag must genuinely sit inside/near the
        # aperture, not just be linked to it by a distant leader line.
        tag_pt = (105.0 + ox, 108.0 + oy)
        page.insert_text(fitz.Point(*tag_pt), marks[i], fontsize=8)
        tag_points.append(tag_pt)
    payload = doc.tobytes()
    doc.close()

    producer = SourceVisibilityProducer(producer_method="phase_c_test", producer_version="1.0")
    published = producer.ingest_native_pdf_bytes(
        document_id="doc_phase_c", source_bytes=payload, source_locator="memory://phase_c.pdf"
    )
    visibility = producer.authority()
    # SourceVisibilityProducer deliberately does not expose the underlying
    # generic SourceObservationAuthority via a public method (see its
    # docstring) -- but tag-binding replay needs one, and it is the exact
    # same authority the visibility layer itself wraps and resolves through,
    # for the identical document/revision/snapshot scope. Reaching for it
    # here is the same "reach the private seal/attribute when a test
    # genuinely needs it" pattern already used elsewhere in this suite.
    source = visibility._source_authority
    rev = published.revision
    snapshot_id = published.snapshot.snapshot_id
    viewport_decision = _viewport_decision(
        document_id=rev.document_id,
        revision_id=rev.revision_id,
        source_sha256=rev.source_sha256,
        snapshot_id=snapshot_id,
    )

    def sel(observation_id: str) -> ObservationSelector:
        return ObservationSelector(
            document_id=rev.document_id,
            revision_id=rev.revision_id,
            source_sha256=rev.source_sha256,
            snapshot_id=snapshot_id,
            observation_id=observation_id,
        )

    def bucket(x: float) -> int | None:
        for i in range(n):
            ox = spacing * i
            if ox - 1.0 <= x <= ox + spacing - 1.0:
                return i
        return None

    existence_by_index: dict[int, ObservationSelector] = {}
    for observation_id in published.visible_observation_ids:
        result = source.resolve(sel(observation_id))
        obs = result.observation
        if obs is None or len(obs.geometry) < 4:
            continue
        gx0 = float(obs.geometry[0])
        index = bucket(min(gx0, float(obs.geometry[2])))
        if index is not None and index not in existence_by_index:
            existence_by_index[index] = sel(observation_id)
    assert len(existence_by_index) == n, "not every instance resolved a visible aperture segment"

    tag_obs_id_by_index: dict[int, str] = {}
    for observation_id in published.snapshot.observation_ids:
        result = source.resolve(sel(observation_id))
        obs = result.observation
        if obs is None or len(obs.geometry) < 4:
            continue
        if obs.observation_kind not in ("native_pdf_word", "native_pdf_text"):
            continue
        gx0, gx1 = float(obs.geometry[0]), float(obs.geometry[2])
        index = bucket(min(gx0, gx1))
        if index is not None and obs.raw_text.strip() == marks[index]:
            tag_obs_id_by_index[index] = observation_id

    assert len(tag_obs_id_by_index) == n, "tag words not all resolved"

    physical = PhysicalOpeningAuthority(visibility)
    instances: list[_Instance] = []
    for i in range(n):
        ox = spacing * i
        oy = spacing * i
        existence_selector = existence_by_index[i]

        tag_resolved = source.resolve(sel(tag_obs_id_by_index[i]))
        assert tag_resolved.status == EvidenceResolutionStatus.CORROBORATED
        tag_rec = tag_resolved.observation
        tag_observation = TagObservation.from_source_observation(tag_rec, viewport_id="vp-1")
        candidate_geometry = (100.0 + ox, 100.0 + oy, 140.0 + ox, 110.0 + oy)
        candidate = create_opening_candidate(
            document_id=rev.document_id,
            revision_id=rev.revision_id,
            source_sha256=rev.source_sha256,
            snapshot_id=snapshot_id,
            page_id=page_ids[i],
            viewport_id="vp-1",
            geometry=candidate_geometry,
            structural_pattern="door_swing_arc",
            source_observation_ids=(existence_selector.observation_id,),
            source_lineage_root_ids=(existence_selector.observation_id,),
            tolerance_provenance=_TOLERANCE,
            viewport_decision=viewport_decision,
            viewport_bbox=(0.0, 0.0, 100.0 + spacing * n, 100.0 + spacing * n),
            wall_lines=[(100.0 + ox, 100.0 + oy, 140.0 + ox, 100.0 + oy)],
            semantic_family="openings",
        )
        binding_evidence = authenticate_tag_binding_evidence(
            tag=tag_observation,
            candidate=candidate,
            relation_kind=TagBindingRelationKind.EXPLICIT_APERTURE_TAG,
            relation_observation_ids=(existence_selector.observation_id,),
            source_observation_authority=source,
        )
        assert binding_evidence.status == EvidenceResolutionStatus.CORROBORATED, binding_evidence.reason_codes

        instances.append(
            _Instance(
                mark=marks[i],
                page_id=page_ids[i],
                existence_selector=existence_selector,
                tag_observation=tag_observation,
                binding_evidence=binding_evidence,
                candidate=candidate,
            )
        )

    return {
        "producer": producer,
        "source": source,
        "document_id": rev.document_id,
        "revision_id": rev.revision_id,
        "source_sha256": rev.source_sha256,
        "snapshot_id": snapshot_id,
        "physical_opening_authority": physical,
        "viewport_decision": viewport_decision,
        "instances": instances,
    }


_TOLERANCE = SourceToleranceProvenance.from_scale_and_stroke(
    scale_ratio=100.0, stroke_width_pt=0.7, scale_residual_mm=1.5, raster_dpi=300.0
)


def _bundle(instance: _Instance, env: dict) -> OpeningInstanceEvidenceBundle:
    return OpeningInstanceEvidenceBundle(
        existence_selector=instance.existence_selector,
        candidate=instance.candidate,
        nearby_tags=(instance.tag_observation,),
        binding_evidences=(instance.binding_evidence,),
        viewport_decision=env["viewport_decision"],
        expected_semantic_family="openings",
        source_observation_authority=env["source"],
    )


def _complete_universe(env: dict, *, page_ids: list[str] | None = None) -> object:
    producer = OpeningUniverseCompletenessProducer(
        producer_method="phase_c_test", producer_version="1.0"
    )
    pages = tuple(dict.fromkeys(page_ids or ["1"]))
    coverage = SourceDecodeCoverageRecord(
        document_id=env["document_id"],
        revision_id=env["revision_id"],
        total_pages=len(pages),
        decoded_pages=tuple(int(p) for p in pages),
        failed_pages=(),
        state="complete",
    )
    producer.publish_enumeration(
        decision_scope_id=_DECISION_SCOPE_ID,
        decision_scope_kind="page_scope",
        document_id=env["document_id"],
        revision_id=env["revision_id"],
        source_sha256=env["source_sha256"],
        snapshot_id=env["snapshot_id"],
        page_ids=pages,
        viewport_id=None,
        coverage=coverage,
        source_primitives=(),
        enumerated_primitives=(),
        optional_content_state="known_visible",
        xobject_traversal_truncated=False,
    )
    return producer.authority()


def _empty_universe_authority() -> object:
    return OpeningUniverseCompletenessProducer(
        producer_method="phase_c_test", producer_version="1.0"
    ).authority()


def _schedule_authority(env: dict, *entries: ScheduleEntry) -> object:
    producer = OpeningScheduleCountProducer.create()
    producer.publish_scope(
        document_id=env["document_id"],
        revision_id=env["revision_id"],
        source_sha256=env["source_sha256"],
        snapshot_id=env["snapshot_id"],
        decision_scope_id=_DECISION_SCOPE_ID,
        schedule_rows=[(entry, ("schedule_row_obs",)) for entry in entries],
    )
    return producer.authority()


def _resolve(env: dict, mark: str, *, universe_authority, schedule_authority, bundles=None):
    """Convenience: publish_scope() for a single mark, then resolve() it
    straight back out through the real Selector/Authority boundary --
    exercises the full producer-then-selector path, not a shortcut."""
    results = _publish(
        env, [mark], universe_authority=universe_authority,
        schedule_authority=schedule_authority, bundles=bundles,
    )
    return results[0]


def _publish(env: dict, marks: list[str], *, universe_authority, schedule_authority, bundles=None):
    if bundles is None:
        bundles = [_bundle(i, env) for i in env["instances"]]
    producer = OpeningCommercialInstanceProducer.create()
    producer.publish_scope(
        document_id=env["document_id"],
        revision_id=env["revision_id"],
        source_sha256=env["source_sha256"],
        snapshot_id=env["snapshot_id"],
        decision_scope_id=_DECISION_SCOPE_ID,
        marks=marks,
        instance_evidence=bundles,
        physical_opening_authority=env["physical_opening_authority"],
        universe_completeness_authority=universe_authority,
        schedule_count_authority=schedule_authority,
    )
    authority = producer.authority()
    return [
        authority.resolve(
            OpeningCommercialInstanceSelector(
                document_id=env["document_id"],
                revision_id=env["revision_id"],
                source_sha256=env["source_sha256"],
                snapshot_id=env["snapshot_id"],
                decision_scope_id=_DECISION_SCOPE_ID,
                normalized_mark=mark,
            )
        )
        for mark in marks
    ]


# ---------------------------------------------------------------------------
# 1. COMPLETE universe + physical == explicit schedule -> CORROBORATED
# ---------------------------------------------------------------------------
def test_complete_universe_physical_equals_schedule_corroborates() -> None:
    env = _build_environment(marks=["W1", "W1", "W1"])
    universe = _complete_universe(env)
    schedule = _schedule_authority(
        env, ScheduleEntry(type_mark="W1", width_mm=1200, height_mm=1200, count=3, count_explicit=True)
    )
    result = _resolve(env, "W1", universe_authority=universe, schedule_authority=schedule)
    assert result.status == EvidenceResolutionStatus.CORROBORATED
    assert result.count == 3
    assert result.physical_count == 3
    assert result.schedule_count == 3
    assert result.record is not None
    assert len(result.record.physical_existence_record_ids) == 3
    assert result.record.universe_completeness_record_id is not None


# ---------------------------------------------------------------------------
# 2. COMPLETE universe + physical > schedule -> CONFLICT (never min/max)
# ---------------------------------------------------------------------------
def test_physical_exceeds_schedule_never_publishes_min_or_max() -> None:
    env = _build_environment(marks=["W1", "W1", "W1"])
    universe = _complete_universe(env)
    schedule = _schedule_authority(
        env, ScheduleEntry(type_mark="W1", width_mm=1200, height_mm=1200, count=2, count_explicit=True)
    )
    result = _resolve(env, "W1", universe_authority=universe, schedule_authority=schedule)
    assert result.status == EvidenceResolutionStatus.CONFLICT
    assert result.count is None
    assert result.count != 2
    assert result.count != 3
    assert result.physical_count == 3
    assert result.schedule_count == 2
    assert COMMERCIAL_COUNT_SCHEDULE_PHYSICAL_MISMATCH in result.reason_codes


# ---------------------------------------------------------------------------
# 3. COMPLETE universe + physical < schedule -> CONFLICT
# ---------------------------------------------------------------------------
def test_schedule_exceeds_physical_conflicts() -> None:
    env = _build_environment(marks=["D1"])
    universe = _complete_universe(env)
    schedule = _schedule_authority(
        env, ScheduleEntry(type_mark="D1", width_mm=900, height_mm=2100, count=5, count_explicit=True)
    )
    result = _resolve(env, "D1", universe_authority=universe, schedule_authority=schedule)
    assert result.status == EvidenceResolutionStatus.CONFLICT
    assert result.count is None
    assert result.physical_count == 1
    assert result.schedule_count == 5


# ---------------------------------------------------------------------------
# 4. COMPLETE universe + explicit schedule > 0 + zero physical instances -> CONFLICT
# ---------------------------------------------------------------------------
def test_complete_universe_zero_physical_with_explicit_schedule_conflicts() -> None:
    env = _build_environment(marks=["D9"])
    universe = _complete_universe(env)
    schedule = _schedule_authority(
        env, ScheduleEntry(type_mark="D9", width_mm=800, height_mm=2000, count=2, count_explicit=True)
    )
    # No instance_evidence submitted at all for D9 -- zero physical instances.
    result = _resolve(env, "D9", universe_authority=universe, schedule_authority=schedule, bundles=[])
    assert result.status == EvidenceResolutionStatus.CONFLICT
    assert result.count is None
    assert result.physical_count == 0
    assert result.schedule_count == 2
    assert COMMERCIAL_COUNT_NO_PHYSICAL_INSTANCES in result.reason_codes


# ---------------------------------------------------------------------------
# 5. Universe completeness never published for this scope -> ABSTAIN, even
#    though physical and schedule counts would otherwise agree exactly.
# ---------------------------------------------------------------------------
def test_incomplete_universe_abstains_despite_apparent_count_agreement() -> None:
    env = _build_environment(marks=["W1", "W1", "W1"])
    universe = _empty_universe_authority()  # nothing published for scope_p1
    schedule = _schedule_authority(
        env, ScheduleEntry(type_mark="W1", width_mm=1200, height_mm=1200, count=3, count_explicit=True)
    )
    result = _resolve(env, "W1", universe_authority=universe, schedule_authority=schedule)
    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert result.count is None
    assert COMMERCIAL_COUNT_UNIVERSE_INCOMPLETE in result.reason_codes


# ---------------------------------------------------------------------------
# 6. COMPLETE universe, real proven physical instances, but no explicit
#    schedule count at all -> ABSTAIN (Case F)
# ---------------------------------------------------------------------------
def test_no_explicit_schedule_count_abstains() -> None:
    env = _build_environment(marks=["D1"])
    universe = _complete_universe(env)
    schedule = _schedule_authority(env)  # nothing published
    result = _resolve(env, "D1", universe_authority=universe, schedule_authority=schedule)
    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert result.count is None
    assert result.physical_count == 1
    assert COMMERCIAL_COUNT_NO_SCHEDULE_ROW in result.reason_codes


# ---------------------------------------------------------------------------
# 7 & 8. A schedule row whose count column is absent or malformed defaults
#    count=1 with count_explicit=False (pb_opening_schedule_v171.py) -- that
#    default must never become authoritative commercial evidence.
# ---------------------------------------------------------------------------
def test_missing_count_column_never_becomes_authoritative_one() -> None:
    rows = [{"text": "MARK\tWIDTH\tHEIGHT", "bounds": [(0, 40), (40, 90), (90, 140)]},
            {"text": "D1\t900\t2100", "bounds": [(0, 40), (40, 90), (90, 140)]}]
    entries = parse_schedule_rows(rows, page_no=1)
    assert len(entries) == 1
    assert entries[0].count == 1
    assert entries[0].count_explicit is False

    env = _build_environment(marks=["D1"])
    universe = _complete_universe(env)
    schedule = _schedule_authority(env, entries[0])
    result = _resolve(env, "D1", universe_authority=universe, schedule_authority=schedule)
    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert result.count is None


def test_malformed_count_value_never_becomes_authoritative_one() -> None:
    rows = [{"text": "MARK\tWIDTH\tHEIGHT\tQTY", "bounds": [(0, 40), (40, 90), (90, 140), (140, 180)]},
            {"text": "D1\t900\t2100\tsix", "bounds": [(0, 40), (40, 90), (90, 140), (140, 180)]}]
    entries = parse_schedule_rows(rows, page_no=1)
    assert len(entries) == 1
    assert entries[0].count == 1
    assert entries[0].count_explicit is False

    env = _build_environment(marks=["D1"])
    universe = _complete_universe(env)
    schedule = _schedule_authority(env, entries[0])
    result = _resolve(env, "D1", universe_authority=universe, schedule_authority=schedule)
    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert result.count is None


# ---------------------------------------------------------------------------
# 9. Tag resolved, real proven physical instance, but no matching schedule
#    row at all (the real Murera "W-6" shape) -> ABSTAIN
# ---------------------------------------------------------------------------
def test_tag_with_no_matching_schedule_row_abstains() -> None:
    env = _build_environment(marks=["W6"])
    universe = _complete_universe(env)
    schedule = _schedule_authority(
        env, ScheduleEntry(type_mark="W1", width_mm=1200, height_mm=1200, count=3, count_explicit=True)
    )
    result = _resolve(env, "W6", universe_authority=universe, schedule_authority=schedule)
    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert result.count is None
    assert result.physical_count == 1
    assert COMMERCIAL_COUNT_NO_SCHEDULE_ROW in result.reason_codes


# ---------------------------------------------------------------------------
# 10. Multiple independently discovered, non-equivalent schedule rows for
#     one mark -> CONFLICT (never pick first/highest/sum/max/min)
# ---------------------------------------------------------------------------
def test_ambiguous_duplicate_schedule_rows_conflicts() -> None:
    env = _build_environment(marks=["W2"])
    universe = _complete_universe(env)
    schedule = _schedule_authority(
        env,
        ScheduleEntry(type_mark="W2", width_mm=1200, height_mm=1200, count=1, count_explicit=True),
        ScheduleEntry(type_mark="W2", width_mm=1500, height_mm=1200, count=1, count_explicit=True, page_no=2),
    )
    result = _resolve(env, "W2", universe_authority=universe, schedule_authority=schedule)
    assert result.status == EvidenceResolutionStatus.CONFLICT
    assert result.count is None
    assert COMMERCIAL_COUNT_AMBIGUOUS_SCHEDULE_ROWS in result.reason_codes


# ---------------------------------------------------------------------------
# 11. Two instances of the same mark on different pages -> G17 compare_identity
#     itself returns a real, genuine scope-mismatch ABSTAIN (not SAME or
#     DISTINCT) -- the whole mark blocks rather than guessing.
# ---------------------------------------------------------------------------
def test_cross_page_instances_block_the_whole_mark() -> None:
    env = _build_environment(marks=["D3", "D3"], page_ids=["1", "2"])
    universe = _complete_universe(env, page_ids=["1", "2"])
    schedule = _schedule_authority(
        env, ScheduleEntry(type_mark="D3", width_mm=900, height_mm=2100, count=2, count_explicit=True)
    )
    result = _resolve(env, "D3", universe_authority=universe, schedule_authority=schedule)
    assert result.count is None
    assert result.status in (EvidenceResolutionStatus.ABSTAINED, EvidenceResolutionStatus.CONFLICT)


# ---------------------------------------------------------------------------
# 12 & 13. Defensive identity-graph consistency, exercised via a minimal
#     local test double -- see module docstring for why real G17 identity
#     cannot itself produce these inputs.
# ---------------------------------------------------------------------------
class _FakeIdentityAuthority:
    def __init__(self, table: dict[frozenset, PhysicalOpeningIdentityResult]) -> None:
        self._table = table

    def compare_identity(self, left, right):
        key = frozenset((left.observation_id, right.observation_id))
        return self._table[key]


def _same(reason: str = "same") -> PhysicalOpeningIdentityResult:
    return PhysicalOpeningIdentityResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        physical_opening_identity="same_test_id",
        proven_same=True,
        reason_codes=(reason,),
    )


def _distinct(reason: str = "distinct") -> PhysicalOpeningIdentityResult:
    return PhysicalOpeningIdentityResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        physical_opening_identity=PHYSICAL_OPENING_IDENTITIES_DISTINCT,
        proven_same=False,
        reason_codes=(reason,),
    )


def _unresolved(reason: str = "unresolved") -> PhysicalOpeningIdentityResult:
    return PhysicalOpeningIdentityResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        physical_opening_identity=PHYSICAL_OPENING_IDENTITY_UNRESOLVED,
        proven_same=False,
        reason_codes=(reason,),
    )


def _fake_selector(observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id="doc_fake", revision_id="rev_fake", source_sha256="f" * 64,
        snapshot_id="snap_fake", observation_id=observation_id,
    )


@dataclass
class _FakeEligible:
    key: str
    existence_selector: ObservationSelector


def test_one_unresolved_identity_pair_blocks_entire_mark() -> None:
    a, b = _fake_selector("a"), _fake_selector("b")
    fake = _FakeIdentityAuthority({frozenset(("a", "b")): _unresolved()})
    from pb_opening_commercial_instance_authority import _EligibleInstance

    eligible = [
        _EligibleInstance(key="a", mark="D1", existence_selector=a, existence_record_id="rec_a", tag_observation_id="tag_a"),
        _EligibleInstance(key="b", mark="D1", existence_selector=b, existence_record_id="rec_b", tag_observation_id="tag_b"),
    ]
    count, status, _reasons = _resolve_physical_identity_count(
        eligible, physical_opening_authority=fake
    )
    assert count is None
    assert status == EvidenceResolutionStatus.ABSTAINED


def test_contradictory_same_same_distinct_graph_conflicts_not_collapses() -> None:
    from pb_opening_commercial_instance_authority import _EligibleInstance

    fake = _FakeIdentityAuthority({
        frozenset(("a", "b")): _same(),
        frozenset(("b", "c")): _same(),
        frozenset(("a", "c")): _distinct(),
    })
    eligible = [
        _EligibleInstance(key=k, mark="D1", existence_selector=_fake_selector(k), existence_record_id=f"rec_{k}", tag_observation_id=f"tag_{k}")
        for k in ("a", "b", "c")
    ]
    count, status, reasons = _resolve_physical_identity_count(
        eligible, physical_opening_authority=fake
    )
    assert count is None
    assert count != 1
    assert count != 2
    assert status == EvidenceResolutionStatus.CONFLICT
    assert COMMERCIAL_COUNT_INCONSISTENT_IDENTITY_GRAPH in reasons


# ---------------------------------------------------------------------------
# 14. A caller-constructed, fake CORROBORATED/PROVEN_SAME tag_binding cannot
#     mint a commercial count -- this module always replays resolve_tag_binding
#     itself and never trusts a pre-set field.
# ---------------------------------------------------------------------------
def test_fake_caller_constructed_tag_binding_cannot_mint_count() -> None:
    env = _build_environment(marks=["W1"])
    universe = _complete_universe(env)
    schedule = _schedule_authority(
        env, ScheduleEntry(type_mark="W1", width_mm=1200, height_mm=1200, count=1, count_explicit=True)
    )
    instance = env["instances"][0]
    # Deliberately supply NO real tags/relation evidence in the bundle --
    # only the existence selector and candidate. If this module trusted a
    # pre-set candidate.tag_binding field it would count this instance;
    # since it always replays resolve_tag_binding() from nearby_tags/
    # binding_evidences, an empty evidence set must resolve to nothing.
    bundle = OpeningInstanceEvidenceBundle(
        existence_selector=instance.existence_selector,
        candidate=instance.candidate,
        nearby_tags=(),
        binding_evidences=(),
        viewport_decision=env["viewport_decision"],
        expected_semantic_family="openings",
        source_observation_authority=env["source"],
    )
    result = _resolve(env, "W1", universe_authority=universe, schedule_authority=schedule, bundles=[bundle])
    assert result.status != EvidenceResolutionStatus.CORROBORATED
    assert result.count is None
    assert result.physical_count == 0


# ---------------------------------------------------------------------------
# 15. Two marks in one decision scope do not cross-contaminate.
# ---------------------------------------------------------------------------
def test_two_marks_in_one_scope_do_not_cross_contaminate() -> None:
    env = _build_environment(marks=["D1", "D1", "W1"])
    universe = _complete_universe(env)
    schedule = _schedule_authority(
        env,
        ScheduleEntry(type_mark="D1", width_mm=900, height_mm=2100, count=2, count_explicit=True),
        ScheduleEntry(type_mark="W1", width_mm=1200, height_mm=1200, count=5, count_explicit=True),  # deliberate mismatch
    )
    # One publish_scope() call for BOTH marks -- exercises the real
    # multi-mark grouping (instances are replayed once and grouped by
    # their discovered mark), not two independent single-mark calls.
    d1, w1 = _publish(env, ["D1", "W1"], universe_authority=universe, schedule_authority=schedule)
    assert d1.status == EvidenceResolutionStatus.CORROBORATED
    assert d1.count == 2
    assert w1.status == EvidenceResolutionStatus.CONFLICT
    assert w1.count is None


# ---------------------------------------------------------------------------
# 17. A selector for a mark never included in publish_scope()'s `marks`
#     resolves to a safe, explicit ABSTAIN -- never an exception, a stale
#     result, or (worse) silently falling through to some other mark's data.
# ---------------------------------------------------------------------------
def test_unpublished_mark_selector_abstains_safely() -> None:
    env = _build_environment(marks=["D1"])
    universe = _complete_universe(env)
    schedule = _schedule_authority(
        env, ScheduleEntry(type_mark="D1", width_mm=900, height_mm=2100, count=1, count_explicit=True)
    )
    producer = OpeningCommercialInstanceProducer.create()
    producer.publish_scope(
        document_id=env["document_id"],
        revision_id=env["revision_id"],
        source_sha256=env["source_sha256"],
        snapshot_id=env["snapshot_id"],
        decision_scope_id=_DECISION_SCOPE_ID,
        marks=["D1"],
        instance_evidence=[_bundle(i, env) for i in env["instances"]],
        physical_opening_authority=env["physical_opening_authority"],
        universe_completeness_authority=universe,
        schedule_count_authority=schedule,
    )
    authority = producer.authority()
    never_asked_about = authority.resolve(
        OpeningCommercialInstanceSelector(
            document_id=env["document_id"],
            revision_id=env["revision_id"],
            source_sha256=env["source_sha256"],
            snapshot_id=env["snapshot_id"],
            decision_scope_id=_DECISION_SCOPE_ID,
            normalized_mark="W9",
        )
    )
    assert never_asked_about.status == EvidenceResolutionStatus.ABSTAINED
    assert never_asked_about.count is None
    assert COMMERCIAL_COUNT_RECORD_UNAVAILABLE in never_asked_about.reason_codes


# ---------------------------------------------------------------------------
# 16. Empty input -> clean ABSTAIN, no crash.
# ---------------------------------------------------------------------------
def test_empty_input_abstains_cleanly() -> None:
    env = _build_environment(marks=["D1"])
    universe = _empty_universe_authority()
    schedule = _schedule_authority(env)
    result = _resolve(env, "D1", universe_authority=universe, schedule_authority=schedule, bundles=[])
    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert result.count is None
