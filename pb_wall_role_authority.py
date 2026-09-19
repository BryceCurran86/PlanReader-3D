"""Producer-owned wall-role classification authority (Item 26).

Classifies each physical wall as exactly one of:
  - EXTERNAL: proven to bound the external building envelope.
  - INTERNAL: proven to divide enclosed internal spaces only.
  - GABLE: proven to be a gable-end wall (may also be external).
  - PARTY: proven shared wall between separate tenancies / units.
  - UNRESOLVED: classification cannot be established from available evidence.

Authority invariants:
  - Classification binds to exact physical_wall_id; distinct walls remain
    distinct — no "largest perimeter" merging.
  - Classification requires corroborated upstream physical wall candidate
    evidence on the same document/revision/source/snapshot/page lineage.
  - Candidate metadata (such as interior_exterior, thickness, caller labels)
    remains diagnostic only and CANNOT mint authoritative wall role.
  - Thickness alone never determines role (equal-thickness walls can be
    internal or external).
  - Gable is never inferred solely from wall length, position, or candidate flags.
  - Party wall is never inferred solely from proximity or candidate flags.
  - Perimeter rank alone never determines role.
  - Caller-supplied role labels cannot mint authority.
  - Topology evidence must bind to the exact physical wall and share exact lineage.
  - Stale evidence (mismatched lineage) fails closed.
  - Cross-page evidence must be registered before it can contribute.
  - Conflicting role evidence returns CONFLICT.
  - Ambiguous adjacency or topology returns UNRESOLVED (abstained).
  - All positive records are sealed with _PRODUCER_SEAL; no public constructor.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Dict, List, Mapping, Optional, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateSelector,
    _decision_scope_id,
    _source_page_segments,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_room_topology_room_faces import reconstruct_room_candidates
from pb_wall_room_topology_room_wall_relationships import (
    compute_wall_usage,
    derive_room_wall_relationships,
)
from pb_wall_room_topology_junction_classifier import classify_junctions
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
from pb_wall_room_topology_wall_assembly import assemble_wall_candidates


WALL_ROLE_SCHEMA_VERSION = "1.0.0"

# Public reason codes
WALL_ROLE_RESOLVED = "wall_role_resolved"
WALL_ROLE_UNRESOLVED = "wall_role_unresolved"
WALL_ROLE_WALL_UNRESOLVED = "wall_role_wall_candidate_unresolved"
WALL_ROLE_LINEAGE_MISMATCH = "wall_role_lineage_mismatch"
WALL_ROLE_AMBIGUOUS = "wall_role_ambiguous"
WALL_ROLE_STALE_EVIDENCE = "wall_role_stale_evidence"
WALL_ROLE_CALLER_LABEL_REJECTED = "wall_role_caller_label_rejected"
WALL_ROLE_CANDIDATE_LABEL_REJECTED = "wall_role_candidate_label_rejected"
WALL_ROLE_CROSS_PAGE_UNREGISTERED = "wall_role_cross_page_evidence_unregistered"
WALL_ROLE_RECORD_UNAVAILABLE = "wall_role_record_unavailable"
WALL_ROLE_THICKNESS_ONLY_REJECTED = "wall_role_thickness_only_classification_rejected"
WALL_ROLE_PERIMETER_ONLY_REJECTED = "wall_role_largest_perimeter_classification_rejected"
WALL_ROLE_TOPOLOGY_WRONG_WALL = "wall_role_topology_wrong_wall"
WALL_ROLE_CONFLICT = "wall_role_conflict"
WALL_ROLE_SOURCE_EVIDENCE_UNAVAILABLE = "wall_role_source_evidence_unavailable"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()

_Key = Tuple[str, str, str, str, str, str, str]  # doc/rev/sha/snap/page/scope/wall_id
_TopologyKey = Tuple[str, str, str, str, str, str]  # doc/rev/sha/snap/page/wall_id


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


class WallRoleClassification(str, Enum):
    """The proven classification for one physical wall."""

    EXTERNAL = "external"
    INTERNAL = "internal"
    GABLE = "gable"
    PARTY = "party"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class WallRoleSelector:
    """Sealed selector identifying the exact wall and context for role resolution."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    physical_wall_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "decision_scope_id",
            "physical_wall_id",
        ):
            _required(getattr(self, name), name)

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            self.decision_scope_id,
            self.physical_wall_id,
        )


@dataclass(frozen=True)
class WallRoleRecord:
    """Sealed, authenticated wall-role record. Never directly constructible."""

    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    physical_wall_id: str
    role: WallRoleClassification
    corroborating_evidence_ids: Tuple[str, ...]
    schema_version: str = WALL_ROLE_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("WallRoleRecord is producer-owned and cannot be constructed directly")


@dataclass(frozen=True)
class WallRoleResult:
    """Result of a wall-role authority resolution."""

    status: EvidenceResolutionStatus
    reason_codes: Tuple[str, ...]
    record: Optional[WallRoleRecord] = None
    schema_version: str = WALL_ROLE_SCHEMA_VERSION


def _abstained(reason: str, *extras: str) -> WallRoleResult:
    return WallRoleResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


def _conflict(reason: str, *extras: str) -> WallRoleResult:
    return WallRoleResult(
        status=EvidenceResolutionStatus.CONFLICT,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


# ── Independent evidence definitions ──────────────────────────────────────────


@dataclass(frozen=True)
class WallTopologyEvidence:
    """Producer-owned topology evidence linking a physical wall to room/envelope topology."""

    evidence_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    physical_wall_id: str
    bounds_exterior: bool
    enclosed_space_count: int
    enclosed_space_ids: Tuple[str, ...] = ()
    is_ambiguous: bool = False
    ambiguity_reason: Optional[str] = None
    schema_version: str = WALL_ROLE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "physical_wall_id",
        ):
            _required(getattr(self, name), name)


class WallTopologyAuthority:
    """Sealed lookup authority for wall topology evidence."""

    def __init__(
        self,
        records: Mapping[_TopologyKey, WallTopologyEvidence],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("WallTopologyAuthority is producer-owned and cannot be constructed directly")
        self._records = MappingProxyType(dict(records))

    def get_evidence(self, selector: WallRoleSelector) -> Optional[WallTopologyEvidence]:
        key = (
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
            selector.page_id,
            selector.physical_wall_id,
        )
        return self._records.get(key)


class WallTopologyProducer:
    """Producer for authenticated wall-room/envelope topology evidence."""

    def __init__(self, *, _seal: object = None) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("WallTopologyProducer must be obtained via create()")
        self._records: Dict[_TopologyKey, WallTopologyEvidence] = {}

    @classmethod
    def create(cls) -> WallTopologyProducer:
        return cls(_seal=_PRODUCER_SEAL)

    def publish(self, evidence: WallTopologyEvidence) -> None:
        raise TypeError(
            "caller-constructed WallTopologyEvidence is diagnostic only; "
            "source-derived evidence producer unavailable"
        )

    def authority(self) -> WallTopologyAuthority:
        return WallTopologyAuthority(self._records, _seal=_AUTHORITY_SEAL)

    @classmethod
    def from_physical_wall_candidate_authority(
        cls,
        *,
        source_visibility_producer: SourceVisibilityProducer,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
    ) -> "WallTopologyProducer":
        """The only legitimate way real WallTopologyEvidence comes to exist.

        Reuses the existing, already-tested W2-W6 pipeline unmodified --
        no new geometric inference happens here. Because
        ``PhysicalWallCandidateAuthority`` does not expose the intermediate
        Stage-A graph / edge-to-wall-candidate mapping that W5 (room-face
        reconstruction) and W6 (room<->wall relationships) need, this
        re-invokes the exact same real W2-W4 calls the candidate authority
        itself uses (see ``pb_physical_wall_candidate_authority._build_scope_result``)
        to obtain them.

        This is reconciliation, not re-authoring: a wall's topology evidence
        is only ever emitted when its independently-rederived
        ``candidate_id`` exactly matches one already present in the CALLER'S
        OWN already-authenticated ``physical_wall_candidate_authority``
        result for that same page. Any wall id that does not reconcile is
        silently excluded -- never guessed into alignment -- and a wall
        whose W6-resolved ``interior_exterior`` is still ``"unresolved"``,
        or flagged with an anomalous-usage reason code, never produces
        evidence either.
        """
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be an actual SourceVisibilityProducer")
        if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError(
                "physical_wall_candidate_authority must be a producer-owned PhysicalWallCandidateAuthority"
            )

        producer = cls(_seal=_PRODUCER_SEAL)
        published_by_revision = dict(source_visibility_producer._published_by_revision)
        store = source_visibility_producer._producer._store

        for revision_id, published in sorted(published_by_revision.items()):
            if (
                source_visibility_producer._producer.current_revision_id(
                    published.revision.document_id
                )
                != revision_id
            ):
                continue
            source_bytes = store.source_bytes_by_revision.get(revision_id)
            if source_bytes is None:
                continue
            digest = hashlib.sha256(source_bytes).hexdigest()
            if digest != published.revision.source_sha256:
                continue

            for page_number in published.coverage.decoded_pages:
                page_id = str(page_number)
                scope_id = _decision_scope_id(page_id)
                trusted_sel = PhysicalWallCandidateSelector(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    page_id=page_id,
                    decision_scope_id=scope_id,
                )
                trusted_result = physical_wall_candidate_authority.resolve_scope(trusted_sel)
                if trusted_result.status is not EvidenceResolutionStatus.CORROBORATED:
                    continue
                trusted_wall_ids = {r.wall_candidate_id for r in trusted_result.records}
                if not trusted_wall_ids:
                    continue

                try:
                    segments, _source_observation_ids, _page_w, _page_h = _source_page_segments(
                        source_producer=source_visibility_producer,
                        published=published,
                        source_bytes=source_bytes,
                        page_id=page_id,
                        decision_scope_id=scope_id,
                    )
                except RuntimeError:
                    continue

                graph = build_wall_graph_for_viewport(segments)
                junctions, relationships = classify_junctions(
                    graph,
                    document_id=published.revision.document_id,
                    page_id=page_id,
                    viewport_id=scope_id,
                )
                walls, edge_id_to_wall_candidate_id = assemble_wall_candidates(
                    graph, junctions, relationships, viewport_id=scope_id
                )

                # Only proceed with room-face/relationship reconstruction
                # using walls that reconcile with the trusted authority --
                # an unreconciled independent re-derivation is never a
                # legitimate basis for room topology either.
                reconciled_walls = [w for w in walls if w.candidate_id in trusted_wall_ids]
                if not reconciled_walls:
                    continue

                rooms = reconstruct_room_candidates(
                    graph,
                    edge_id_to_wall_candidate_id,
                    document_id=published.revision.document_id,
                    viewport_id=scope_id,
                    source_page=page_number,
                )
                if not rooms:
                    continue
                wall_usage = compute_wall_usage(rooms)
                _updated_rooms, updated_walls, _relationships = derive_room_wall_relationships(
                    rooms, reconciled_walls
                )

                for wall in updated_walls:
                    if wall.candidate_id not in trusted_wall_ids:
                        continue
                    if wall.interior_exterior not in ("interior", "exterior"):
                        continue
                    room_refs = tuple(dict.fromkeys(wall_usage.get(wall.candidate_id, ())))
                    bounds_exterior = wall.interior_exterior == "exterior"
                    expected_count = 1 if bounds_exterior else 2
                    if len(room_refs) != expected_count:
                        # W6 already proved this classification from exact
                        # room-usage counts; a mismatch here would mean this
                        # adapter's own bookkeeping disagrees with W6's --
                        # fail closed rather than publish a self-contradiction.
                        continue

                    payload = {
                        "document_id": published.revision.document_id,
                        "revision_id": published.revision.revision_id,
                        "source_sha256": published.revision.source_sha256,
                        "snapshot_id": published.snapshot.snapshot_id,
                        "page_id": page_id,
                        "physical_wall_id": wall.candidate_id,
                        "bounds_exterior": bounds_exterior,
                        "enclosed_space_count": expected_count,
                        "enclosed_space_ids": room_refs,
                    }
                    evidence_id = stable_contract_id("wall_topology", payload, digest_chars=32)
                    evidence = WallTopologyEvidence(
                        evidence_id=evidence_id,
                        document_id=published.revision.document_id,
                        revision_id=published.revision.revision_id,
                        source_sha256=published.revision.source_sha256,
                        snapshot_id=published.snapshot.snapshot_id,
                        page_id=page_id,
                        physical_wall_id=wall.candidate_id,
                        bounds_exterior=bounds_exterior,
                        enclosed_space_count=expected_count,
                        enclosed_space_ids=room_refs,
                        is_ambiguous=False,
                    )
                    key = (
                        evidence.document_id,
                        evidence.revision_id,
                        evidence.source_sha256,
                        evidence.snapshot_id,
                        evidence.page_id,
                        evidence.physical_wall_id,
                    )
                    producer._records[key] = evidence

        return producer


@dataclass(frozen=True)
class WallAnnotationEvidence:
    """Producer-owned explicit wall annotation (e.g. callout 'GABLE WALL', 'PARTY WALL')."""

    evidence_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    physical_wall_id: str
    role: WallRoleClassification
    annotation_text: str
    schema_version: str = WALL_ROLE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "physical_wall_id",
            "annotation_text",
        ):
            _required(getattr(self, name), name)


class WallAnnotationAuthority:
    """Sealed lookup authority for explicit wall annotation evidence."""

    def __init__(
        self,
        records: Mapping[_TopologyKey, WallAnnotationEvidence],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("WallAnnotationAuthority is producer-owned and cannot be constructed directly")
        self._records = MappingProxyType(dict(records))

    def get_evidence(self, selector: WallRoleSelector) -> Optional[WallAnnotationEvidence]:
        key = (
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
            selector.page_id,
            selector.physical_wall_id,
        )
        return self._records.get(key)


class WallAnnotationProducer:
    """Producer for authenticated explicit wall annotation evidence."""

    def __init__(self, *, _seal: object = None) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("WallAnnotationProducer must be obtained via create()")
        self._records: Dict[_TopologyKey, WallAnnotationEvidence] = {}

    @classmethod
    def create(cls) -> WallAnnotationProducer:
        return cls(_seal=_PRODUCER_SEAL)

    def publish(self, evidence: WallAnnotationEvidence) -> None:
        raise TypeError(
            "caller-constructed WallAnnotationEvidence is diagnostic only; "
            "source-derived evidence producer unavailable"
        )

    def authority(self) -> WallAnnotationAuthority:
        return WallAnnotationAuthority(self._records, _seal=_AUTHORITY_SEAL)


@dataclass(frozen=True)
class StructuralCrossSheetEvidence:
    """Producer-owned structural / cross-sheet evidence (e.g. roof truss elevation proving gable)."""

    evidence_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    physical_wall_id: str
    role: WallRoleClassification
    source_sheet_id: str
    is_registered: bool = True
    schema_version: str = WALL_ROLE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "physical_wall_id",
            "source_sheet_id",
        ):
            _required(getattr(self, name), name)


class StructuralCrossSheetAuthority:
    """Sealed lookup authority for structural cross-sheet evidence."""

    def __init__(
        self,
        records: Mapping[_TopologyKey, StructuralCrossSheetEvidence],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("StructuralCrossSheetAuthority is producer-owned and cannot be constructed directly")
        self._records = MappingProxyType(dict(records))

    def get_evidence(self, selector: WallRoleSelector) -> Optional[StructuralCrossSheetEvidence]:
        key = (
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
            selector.page_id,
            selector.physical_wall_id,
        )
        return self._records.get(key)


class StructuralCrossSheetProducer:
    """Producer for authenticated structural cross-sheet evidence."""

    def __init__(self, *, _seal: object = None) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("StructuralCrossSheetProducer must be obtained via create()")
        self._records: Dict[_TopologyKey, StructuralCrossSheetEvidence] = {}

    @classmethod
    def create(cls) -> StructuralCrossSheetProducer:
        return cls(_seal=_PRODUCER_SEAL)

    def publish(self, evidence: StructuralCrossSheetEvidence) -> None:
        raise TypeError(
            "caller-constructed StructuralCrossSheetEvidence is diagnostic only; "
            "source-derived evidence producer unavailable"
        )

    def authority(self) -> StructuralCrossSheetAuthority:
        return StructuralCrossSheetAuthority(self._records, _seal=_AUTHORITY_SEAL)


# ── Main Authority & Producer ─────────────────────────────────────────────────


class WallRoleAuthority:
    """Sealed selector-only lookup for published wall-role records."""

    def __init__(
        self,
        results: Mapping[_Key, WallRoleResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("WallRoleAuthority is producer-owned and cannot be constructed directly")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: WallRoleSelector) -> WallRoleResult:
        if type(selector) is not WallRoleSelector:
            raise TypeError("selector must be WallRoleSelector")
        return self._results.get(
            selector.key,
            _abstained(WALL_ROLE_RECORD_UNAVAILABLE),
        )


class WallRoleProducer:
    """Trusted writer boundary for authenticated wall-role classification.

    Callers may NOT supply a role label, thickness, perimeter claim, or candidate flag.
    No public caller-constructible topology/annotation/cross-sheet container is
    accepted as positive role authority. Until a genuinely source-derived upstream
    role-evidence producer is wired, this Item 26 boundary deliberately ABSTAINS
    after authenticating the physical wall candidate.
    """

    def __init__(
        self,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        *,
        wall_topology_authority: Optional[WallTopologyAuthority] = None,
        wall_annotation_authority: Optional[WallAnnotationAuthority] = None,
        structural_cross_sheet_authority: Optional[StructuralCrossSheetAuthority] = None,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("WallRoleProducer must be obtained via from_authorities()")
        if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError(
                "physical_wall_candidate_authority must be a producer-owned PhysicalWallCandidateAuthority"
            )
        if wall_topology_authority is not None and type(wall_topology_authority) is not WallTopologyAuthority:
            raise TypeError("wall_topology_authority must be a producer-owned WallTopologyAuthority")
        if wall_annotation_authority is not None and type(wall_annotation_authority) is not WallAnnotationAuthority:
            raise TypeError("wall_annotation_authority must be a producer-owned WallAnnotationAuthority")
        if structural_cross_sheet_authority is not None and type(structural_cross_sheet_authority) is not StructuralCrossSheetAuthority:
            raise TypeError("structural_cross_sheet_authority must be a producer-owned StructuralCrossSheetAuthority")

        # WallAnnotationAuthority/StructuralCrossSheetAuthority still wrap
        # publicly constructible evidence records with no source-derived
        # producer behind them -- a sealed wrapper alone does not establish
        # provenance for those two, so every positive injection path for
        # them remains rejected until a genuine annotation-extraction /
        # registered-structural-evidence producer exists.
        #
        # WallTopologyAuthority is different: its ONLY legitimate
        # construction path is now WallTopologyProducer.
        # from_physical_wall_candidate_authority(), which forces real
        # re-derivation from the existing W2-W6 pipeline and only ever
        # stores a record when it reconciles exactly against this same
        # physical_wall_candidate_authority's own authenticated wall ids
        # (see that method's docstring). A well-typed instance is therefore
        # real proof, not a caller-supplied bypass.
        if wall_annotation_authority is not None or structural_cross_sheet_authority is not None:
            raise TypeError(
                "caller-constructible role evidence authorities are not accepted; "
                "source-derived role evidence producer unavailable"
            )

        self._wall_candidates = physical_wall_candidate_authority
        self._wall_topology = wall_topology_authority
        self._wall_annotations = None
        self._structural_evidence = None
        self._results: Dict[_Key, WallRoleResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        wall_topology_authority: Optional[WallTopologyAuthority] = None,
        wall_annotation_authority: Optional[WallAnnotationAuthority] = None,
        structural_cross_sheet_authority: Optional[StructuralCrossSheetAuthority] = None,
    ) -> WallRoleProducer:
        return cls(
            physical_wall_candidate_authority,
            wall_topology_authority=wall_topology_authority,
            wall_annotation_authority=wall_annotation_authority,
            structural_cross_sheet_authority=structural_cross_sheet_authority,
            _seal=_PRODUCER_SEAL,
        )

    def authority(self) -> WallRoleAuthority:
        return WallRoleAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def _store(
        self,
        selector: WallRoleSelector,
        result: WallRoleResult,
    ) -> WallRoleResult:
        self._results[selector.key] = result
        return result

    def publish(
        self,
        selector: WallRoleSelector,
    ) -> WallRoleResult:
        """Publish authenticated wall role for selector.

        Strictly enforces the authority chain:
          authenticated physical wall
          +
          authenticated room/envelope topology
          or
          authenticated explicit wall annotation
          or
          authenticated structural/cross-sheet evidence
          → exact wall-role proposition
        """
        if type(selector) is not WallRoleSelector:
            raise TypeError("selector must be WallRoleSelector")

        # 1. Verify the physical wall candidate exists in the authority and is corroborated
        cand_scope_id = f"wall-source:page-{selector.page_id}"
        cand_sel = PhysicalWallCandidateSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=cand_scope_id,
        )
        cand_result = self._wall_candidates.resolve_scope(cand_sel)
        if cand_result.status is not EvidenceResolutionStatus.CORROBORATED:
            return self._store(
                selector,
                _abstained(
                    WALL_ROLE_WALL_UNRESOLVED,
                    *(getattr(cand_result, "reason_codes", ()) or ()),
                ),
            )

        matching_recs = [
            r for r in getattr(cand_result, "records", ())
            if getattr(r, "wall_candidate_id", None) == selector.physical_wall_id
            or getattr(getattr(r, "physical_identity", None), "physical_wall_id", None) == selector.physical_wall_id
        ]
        if not matching_recs:
            return self._store(selector, _abstained(WALL_ROLE_WALL_UNRESOLVED))
        rec = matching_recs[0]
        cand = rec.wall_candidate

        # 2. Diagnostic audit of candidate / caller claims (never promoted to authority)
        diagnostic_reasons = []
        if getattr(cand, "interior_exterior", None) in ("exterior", "interior", "gable", "party"):
            diagnostic_reasons.append(WALL_ROLE_CANDIDATE_LABEL_REJECTED)
        if getattr(cand, "thickness_m", None) is not None:
            diagnostic_reasons.append(WALL_ROLE_THICKNESS_ONLY_REJECTED)
        if getattr(cand, "metadata", None) and any(
            k in cand.metadata for k in ("perimeter_rank", "is_perimeter", "largest_perimeter")
        ):
            diagnostic_reasons.append(WALL_ROLE_PERIMETER_ONLY_REJECTED)

        # 3. Query independent producer-owned evidence sources.
        propositions: list[tuple[WallRoleClassification, str]] = []
        corroborating_ids: list[str] = []
        stale_reasons: list[str] = []
        ambiguous_reasons: list[str] = []

        # A. Room / envelope topology evidence
        if self._wall_topology is not None:
            topo = self._wall_topology.get_evidence(selector)
            if topo is not None:
                # Check lineage
                if (
                    topo.document_id != selector.document_id
                    or topo.revision_id != selector.revision_id
                    or topo.source_sha256 != selector.source_sha256
                    or topo.snapshot_id != selector.snapshot_id
                    or topo.page_id != selector.page_id
                ):
                    stale_reasons.append(WALL_ROLE_STALE_EVIDENCE)
                    stale_reasons.append(WALL_ROLE_LINEAGE_MISMATCH)
                elif topo.physical_wall_id != selector.physical_wall_id:
                    stale_reasons.append(WALL_ROLE_TOPOLOGY_WRONG_WALL)
                elif topo.is_ambiguous:
                    ambiguous_reasons.append(WALL_ROLE_AMBIGUOUS)
                    if topo.ambiguity_reason:
                        ambiguous_reasons.append(topo.ambiguity_reason)
                else:
                    if topo.bounds_exterior and topo.enclosed_space_count == 1:
                        propositions.append((WallRoleClassification.EXTERNAL, topo.evidence_id))
                        corroborating_ids.append(topo.evidence_id)
                    elif not topo.bounds_exterior and topo.enclosed_space_count == 2:
                        propositions.append((WallRoleClassification.INTERNAL, topo.evidence_id))
                        corroborating_ids.append(topo.evidence_id)
                    else:
                        ambiguous_reasons.append(WALL_ROLE_AMBIGUOUS)

        # B. Explicit wall annotation evidence
        if self._wall_annotations is not None:
            annot = self._wall_annotations.get_evidence(selector)
            if annot is not None:
                if (
                    annot.document_id != selector.document_id
                    or annot.revision_id != selector.revision_id
                    or annot.source_sha256 != selector.source_sha256
                    or annot.snapshot_id != selector.snapshot_id
                    or annot.page_id != selector.page_id
                ):
                    stale_reasons.append(WALL_ROLE_STALE_EVIDENCE)
                    stale_reasons.append(WALL_ROLE_LINEAGE_MISMATCH)
                elif annot.physical_wall_id != selector.physical_wall_id:
                    stale_reasons.append(WALL_ROLE_TOPOLOGY_WRONG_WALL)
                elif annot.role in (
                    WallRoleClassification.EXTERNAL,
                    WallRoleClassification.INTERNAL,
                    WallRoleClassification.GABLE,
                    WallRoleClassification.PARTY,
                ):
                    propositions.append((annot.role, annot.evidence_id))
                    corroborating_ids.append(annot.evidence_id)

        # C. Structural / cross-sheet evidence
        if self._structural_evidence is not None:
            struct = self._structural_evidence.get_evidence(selector)
            if struct is not None:
                if (
                    struct.document_id != selector.document_id
                    or struct.revision_id != selector.revision_id
                    or struct.source_sha256 != selector.source_sha256
                    or struct.snapshot_id != selector.snapshot_id
                    or struct.page_id != selector.page_id
                ):
                    stale_reasons.append(WALL_ROLE_STALE_EVIDENCE)
                    stale_reasons.append(WALL_ROLE_LINEAGE_MISMATCH)
                elif struct.physical_wall_id != selector.physical_wall_id:
                    stale_reasons.append(WALL_ROLE_TOPOLOGY_WRONG_WALL)
                elif not struct.is_registered:
                    stale_reasons.append(WALL_ROLE_CROSS_PAGE_UNREGISTERED)
                elif struct.role in (
                    WallRoleClassification.EXTERNAL,
                    WallRoleClassification.INTERNAL,
                    WallRoleClassification.GABLE,
                    WallRoleClassification.PARTY,
                ):
                    propositions.append((struct.role, struct.evidence_id))
                    corroborating_ids.append(struct.evidence_id)

        # 4. Fail-closed decision tree
        if stale_reasons:
            return self._store(selector, _abstained(stale_reasons[0], *stale_reasons[1:]))

        if ambiguous_reasons:
            return self._store(selector, _abstained(WALL_ROLE_AMBIGUOUS, *ambiguous_reasons))

        if not propositions:
            return self._store(selector, _abstained(WALL_ROLE_UNRESOLVED, *diagnostic_reasons))

        # Check for conflicts
        distinct_roles = set(p[0] for p in propositions)
        if len(distinct_roles) == 1:
            resolved_role = next(iter(distinct_roles))
        elif distinct_roles == {WallRoleClassification.EXTERNAL, WallRoleClassification.GABLE}:
            # Gable wall bounds external envelope: GABLE is the more specific exact wall-role proposition
            resolved_role = WallRoleClassification.GABLE
        else:
            return self._store(
                selector,
                _conflict(
                    WALL_ROLE_CONFLICT,
                    *(f"conflicting_role:{r.value}" for r in sorted(distinct_roles, key=lambda x: x.value)),
                ),
            )

        # 5. Positive resolution sealed with _RECORD_SEAL
        all_evidence_ids = (rec.wall_candidate_id, *corroborating_ids)
        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "decision_scope_id": selector.decision_scope_id,
            "physical_wall_id": selector.physical_wall_id,
            "role": resolved_role.value,
            "corroborating_evidence_ids": all_evidence_ids,
        }
        record_id = stable_contract_id("wall_role", payload, digest_chars=32)
        record = WallRoleRecord(
            record_id=record_id,
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
            physical_wall_id=selector.physical_wall_id,
            role=resolved_role,
            corroborating_evidence_ids=all_evidence_ids,
            _seal=_RECORD_SEAL,
        )
        return self._store(
            selector,
            WallRoleResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(WALL_ROLE_RESOLVED,),
                record=record,
            ),
        )


__all__ = [
    "WALL_ROLE_AMBIGUOUS",
    "WALL_ROLE_CALLER_LABEL_REJECTED",
    "WALL_ROLE_CANDIDATE_LABEL_REJECTED",
    "WALL_ROLE_CONFLICT",
    "WALL_ROLE_CROSS_PAGE_UNREGISTERED",
    "WALL_ROLE_LINEAGE_MISMATCH",
    "WALL_ROLE_PERIMETER_ONLY_REJECTED",
    "WALL_ROLE_RECORD_UNAVAILABLE",
    "WALL_ROLE_RESOLVED",
    "WALL_ROLE_SCHEMA_VERSION",
    "WALL_ROLE_STALE_EVIDENCE",
    "WALL_ROLE_SOURCE_EVIDENCE_UNAVAILABLE",
    "WALL_ROLE_THICKNESS_ONLY_REJECTED",
    "WALL_ROLE_TOPOLOGY_WRONG_WALL",
    "WALL_ROLE_UNRESOLVED",
    "WALL_ROLE_WALL_UNRESOLVED",
    "StructuralCrossSheetAuthority",
    "StructuralCrossSheetEvidence",
    "StructuralCrossSheetProducer",
    "WallAnnotationAuthority",
    "WallAnnotationEvidence",
    "WallAnnotationProducer",
    "WallRoleAuthority",
    "WallRoleClassification",
    "WallRoleProducer",
    "WallRoleRecord",
    "WallRoleResult",
    "WallRoleSelector",
    "WallTopologyAuthority",
    "WallTopologyEvidence",
    "WallTopologyProducer",
]
