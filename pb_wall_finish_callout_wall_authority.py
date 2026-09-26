"""Shadow source-owned finish-callout -> physical-wall binding authority.

This is the wall-identity stage immediately upstream of Item 19B semantic-face
binding.  It deliberately stops before wall role, physical face identity,
finish-scope completeness, opening deductions, net wall, or quantity
publication.

Positive path:
trusted or #897-raster-corroborated finish annotation
-> endpoint-connected native leader
-> filled native terminator
-> locally complete terminator owner universe
-> one physical-wall equivalence group.

Global viewport completeness is not required for this *local* proposition.
Instead, every structural source primitive that wall authority withheld because
it crossed / ambiguously occupied the viewport boundary is replayed at the
terminator.  If any such primitive intersects the terminator, or its geometry
cannot be replayed, the local owner universe is not proven and this authority
abstains.

No nearest-wall, first-candidate, confidence ranking, caller geometry, project
identity, benchmark value, or quantity participates.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

import fitz

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_pdf_text_integrity_authority import TEXT_GLYPH_MAPPING_UNVERIFIED
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_raster_text_corroboration_authority import (
    RasterTextCorroborationProducer,
    RasterTextCorroborationSelector,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import assign_bbox_to_viewport
from pb_wall_finish_face_binding_authority import (
    SOURCE_EVIDENCE_KIND_NATIVE_DIRECT_CALLOUT,
    _bbox_union,
    _authoritative_viewports,
    _filled_terminators,
    _leader_paths,
    _page_visible_lines,
    _segment_intersects_bbox,
    _target_from_terminator,
    _viewport_owned_lines,
)


WALL_FINISH_CALLOUT_WALL_BINDING_SCHEMA_VERSION = "1.0.0"
FINISH_CALLOUT_WALL_BINDING_RESOLVED = "wall_finish_callout_wall_binding_resolved"
FINISH_CALLOUT_WALL_BINDING_UNAVAILABLE = "wall_finish_callout_wall_binding_unavailable"
FINISH_CALLOUT_WALL_LOCAL_UNIVERSE_INCOMPLETE = (
    "wall_finish_callout_wall_local_owner_universe_incomplete"
)
FINISH_CALLOUT_WALL_SOURCE_INTEGRITY_FAILURE = (
    "wall_finish_callout_wall_source_integrity_failure"
)

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()


@dataclass(frozen=True)
class WallFinishCalloutWallScopeSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    decision_scope_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "viewport_id",
            "decision_scope_id",
        ):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"{name} must be non-empty")

    @property
    def key(self) -> tuple[str, ...]:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            self.viewport_id,
            self.decision_scope_id,
        )


@dataclass(frozen=True)
class WallFinishCalloutWallBindingRecord:
    binding_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    decision_scope_id: str
    physical_wall_decision_scope_id: str
    physical_wall_id: str
    raw_owner_wall_ids: tuple[str, ...]
    equivalence_group_wall_ids: tuple[str, ...]
    equivalence_pair_classifications: tuple[tuple[str, str, str], ...]
    source_wall_primitive_ids: tuple[str, ...]
    trusted_annotation_text: str
    annotation_observation_ids: tuple[str, ...]
    leader_path_ids: tuple[str, ...]
    terminator_primitive_ids: tuple[str, ...]
    source_evidence_ids: tuple[str, ...]
    source_evidence_kind: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    schema_version: str = WALL_FINISH_CALLOUT_WALL_BINDING_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("WallFinishCalloutWallBindingRecord is producer-owned")
        if self.status is not EvidenceResolutionStatus.CORROBORATED:
            raise ValueError("positive wall binding record must be CORROBORATED")
        if not self.raw_owner_wall_ids:
            raise ValueError("raw_owner_wall_ids must retain target provenance")
        if not self.equivalence_group_wall_ids:
            raise ValueError("equivalence_group_wall_ids must retain target identity")
        if self.physical_wall_id not in self.equivalence_group_wall_ids:
            raise ValueError("physical_wall_id must belong to equivalence group")
        if not self.source_wall_primitive_ids:
            raise ValueError("source wall primitive evidence is required")


@dataclass(frozen=True)
class WallFinishCalloutWallScopeResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    bindings: tuple[WallFinishCalloutWallBindingRecord, ...] = ()
    schema_version: str = WALL_FINISH_CALLOUT_WALL_BINDING_SCHEMA_VERSION


def _blocked(reason: str) -> WallFinishCalloutWallScopeResult:
    return WallFinishCalloutWallScopeResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=(reason,),
        bindings=(),
    )


def _candidate_finish_blocks_with_raster_corroboration(
    source: SourceVisibilityProducer,
    published,
    page_id: str,
):
    """Return trusted finish blocks, corroborating only glyph-only candidate words.

    Native raw text is used only to discover a *candidate block*. It never
    becomes trusted output. Once a block has finish semantics, every word in
    that block must independently resolve either through PdfTextIntegrity or
    through the existing producer-owned RasterTextCorroborationAuthority.
    """
    text_authority = source.text_integrity_authority()
    raw_blocks: dict[
        int,
        list[
            tuple[
                int,
                str,
                str,
                tuple[float, ...],
                object,
            ]
        ],
    ] = {}

    for observation_id in published.text_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = text_authority.resolve_text(selector)
        receipt = result.receipt
        if (
            receipt is None
            or receipt.page_id != page_id
            or receipt.block_no is None
            or receipt.line_no is None
            or receipt.word_no is None
        ):
            continue
        raw_blocks.setdefault(int(receipt.block_no), []).append(
            (
                int(receipt.line_no) * 10000 + int(receipt.word_no),
                observation_id,
                str(receipt.raw_text or ""),
                tuple(receipt.geometry),
                result,
            )
        )

    candidate_blocks = []
    for block_no, values in sorted(raw_blocks.items()):
        ordered = sorted(values, key=lambda item: (item[0], item[1]))
        raw_claim = " ".join(item[2] for item in ordered)
        semantics = _finish_semantics(raw_claim)
        if semantics:
            candidate_blocks.append((block_no, ordered, semantics))

    if not candidate_blocks:
        return ()

    raster_producer = None
    out = []
    for block_no, ordered, semantics in candidate_blocks:
        trusted_words = []
        block_ok = True
        for _order, observation_id, _raw_claim, geometry, integrity in ordered:
            receipt = integrity.receipt
            if (
                integrity.status is EvidenceResolutionStatus.CORROBORATED
                and receipt is not None
                and receipt.trusted
            ):
                trusted = str(integrity.trusted_text or "")
            elif (
                receipt is not None
                and integrity.status is EvidenceResolutionStatus.ABSTAINED
                and tuple(receipt.reason_codes) == (TEXT_GLYPH_MAPPING_UNVERIFIED,)
                and tuple(integrity.reason_codes) == tuple(receipt.reason_codes)
            ):
                if raster_producer is None:
                    raster_producer = (
                        RasterTextCorroborationProducer.from_source_visibility_producer(
                            source
                        )
                    )
                corroborated = raster_producer.publish(
                    RasterTextCorroborationSelector(
                        document_id=published.revision.document_id,
                        revision_id=published.revision.revision_id,
                        source_sha256=published.revision.source_sha256,
                        snapshot_id=published.snapshot.snapshot_id,
                        observation_id=observation_id,
                    )
                )
                if (
                    corroborated.status is not EvidenceResolutionStatus.CORROBORATED
                    or corroborated.record is None
                    or not str(corroborated.corroborated_text or "")
                ):
                    block_ok = False
                    break
                trusted = str(corroborated.corroborated_text)
            else:
                block_ok = False
                break

            trusted_words.append(
                (observation_id, trusted, tuple(geometry))
            )

        if not block_ok or len(trusted_words) != len(ordered):
            continue

        trusted_text = " ".join(word[1] for word in trusted_words)
        trusted_semantics = _finish_semantics(trusted_text)
        if trusted_semantics != semantics:
            # The candidate claim and the independently trusted composition
            # must carry exactly the same finish proposition.
            continue

        geometries = [word[2] for word in trusted_words]
        out.append(
            (
                block_no,
                trusted_text,
                trusted_semantics,
                tuple(word[0] for word in trusted_words),
                _bbox_union(geometries),
                __import__("statistics").median(
                    max(0.1, geom[3] - geom[1]) for geom in geometries
                ),
            )
        )
    return tuple(out)


def _local_owner_universe_safe(*, terminator, page_lines, wall_scope) -> bool:
    """Prove that no source primitive omitted by viewport ownership hits target.

    This is intentionally local.  It never upgrades wall_scope.scope_complete.
    A globally cropped viewport can still prove a local callout owner only when
    every boundary/ambiguous structural observation can be replayed and none of
    those exact primitives intersects the terminator.
    """
    questionable = tuple(
        dict.fromkeys(
            (
                *tuple(getattr(wall_scope, "scope_boundary_observation_ids", ()) or ()),
                *tuple(getattr(wall_scope, "ambiguous_source_observation_ids", ()) or ()),
            )
        )
    )
    if not questionable:
        return True

    by_observation: dict[str, list[object]] = {}
    for line in page_lines:
        by_observation.setdefault(str(line.observation_id), []).append(line)

    for observation_id in questionable:
        candidates = by_observation.get(str(observation_id))
        if not candidates:
            # The withheld structural primitive cannot be replayed here.  Its
            # relationship to the terminator is unknown, so uniqueness cannot
            # be certified.
            return False
        if any(
            _segment_intersects_bbox(line.geometry, terminator.bbox)
            for line in candidates
        ):
            return False
    return True


def _finish_callout_candidate_claim(text: str) -> bool:
    """Candidate generation only; never positive semantic authority.

    Raw native text may be used to decide which source blocks are worth
    independently corroborating.  A wrong claim can therefore only create
    extra work or a false negative; it cannot create a positive binding.
    """
    value = " ".join(str(text or "").lower().split())
    return (
        ("wall" in value or "walling" in value)
        and "finish" in value
        and any(token in value for token in ("key", "plaster", "paint"))
    )


def _trusted_finish_callout_blocks_with_raster(
    source: SourceVisibilityProducer,
    published,
    page_id: str,
):
    """Return source blocks whose *trusted* words prove a wall-finish callout.

    Stage 1 groups producer-owned native receipts and uses the raw claim only
    for conservative candidate generation.  Stage 2 independently trusts each
    word through native PdfTextIntegrity or the already-approved #897 raster
    corroboration authority.  Stage 3 reconstructs the block only from those
    trusted words.  The final block must itself still contain generic wall +
    finish semantics; uncorroborated words never contribute to that decision.

    This wall-binding layer intentionally does not require or publish the
    external/internal face direction.  That proposition remains downstream.
    """
    integrity = source.text_integrity_authority()

    receipts_by_block: dict[
        int,
        list[tuple[int, str, object, object]],
    ] = {}
    for observation_id in published.text_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = integrity.resolve_text(selector)
        receipt = result.receipt
        if (
            receipt is None
            or receipt.page_id != page_id
            or receipt.block_no is None
            or receipt.line_no is None
            or receipt.word_no is None
        ):
            continue
        receipts_by_block.setdefault(int(receipt.block_no), []).append(
            (
                int(receipt.line_no) * 10000 + int(receipt.word_no),
                observation_id,
                receipt,
                result,
            )
        )

    candidate_blocks = {
        block_no
        for block_no, values in receipts_by_block.items()
        if _finish_callout_candidate_claim(
            " ".join(
                str(item[2].raw_text or "")
                for item in sorted(values, key=lambda item: (item[0], item[1]))
            )
        )
    }
    if not candidate_blocks:
        return ()

    raster = RasterTextCorroborationProducer.from_source_visibility_producer(source)
    out = []
    for block_no in sorted(candidate_blocks):
        values = sorted(
            receipts_by_block[block_no],
            key=lambda item: (item[0], item[1]),
        )
        trusted: list[tuple[int, str, str, tuple[float, ...]]] = []
        for order, observation_id, receipt, result in values:
            trusted_text = None
            if result.status is EvidenceResolutionStatus.CORROBORATED:
                trusted_text = str(result.trusted_text or "")
            elif (
                result.status is EvidenceResolutionStatus.ABSTAINED
                and tuple(receipt.reason_codes) == (TEXT_GLYPH_MAPPING_UNVERIFIED,)
                and tuple(result.reason_codes) == tuple(receipt.reason_codes)
            ):
                raster_result = raster.publish(
                    RasterTextCorroborationSelector(
                        document_id=published.revision.document_id,
                        revision_id=published.revision.revision_id,
                        source_sha256=published.revision.source_sha256,
                        snapshot_id=published.snapshot.snapshot_id,
                        observation_id=observation_id,
                    )
                )
                if raster_result.status is EvidenceResolutionStatus.CORROBORATED:
                    trusted_text = str(raster_result.corroborated_text or "")
            if trusted_text:
                trusted.append(
                    (
                        order,
                        observation_id,
                        trusted_text,
                        tuple(receipt.geometry),
                    )
                )

        if not trusted:
            continue
        text = " ".join(item[2] for item in trusted)
        if not _finish_callout_candidate_claim(text):
            continue

        geometries = [item[3] for item in trusted]
        heights = sorted(max(0.1, geometry[3] - geometry[1]) for geometry in geometries)
        mid = len(heights) // 2
        median_height = (
            heights[mid]
            if len(heights) % 2
            else (heights[mid - 1] + heights[mid]) / 2.0
        )
        out.append(
            (
                block_no,
                text,
                tuple(item[1] for item in trusted),
                _bbox_union(geometries),
                median_height,
            )
        )
    return tuple(out)


def _target_provenance(*, terminator, wall_lines, wall_scope, target):
    raw_hits = {
        line.raw_id
        for line in wall_lines
        if _segment_intersects_bbox(line.geometry, terminator.bbox)
    }
    matching = [
        record
        for record in wall_scope.records
        if raw_hits & set(record.physical_identity.source_primitive_ids)
    ]
    raw_owner_ids = tuple(sorted({record.wall_candidate_id for record in matching}))

    target_id = str(target.wall_candidate_id)
    group = (target_id,)
    equivalence = getattr(wall_scope, "equivalence", None)
    if equivalence is not None:
        for candidate_group in tuple(equivalence.equivalence_groups or ()):
            if target_id in candidate_group:
                group = tuple(sorted(candidate_group))
                break

    relevant = set(group) | set(raw_owner_ids)
    pair_classifications = ()
    if equivalence is not None:
        pair_classifications = tuple(
            sorted(
                row
                for row in tuple(equivalence.pair_classifications or ())
                if row[0] in relevant and row[1] in relevant
            )
        )
    return raw_owner_ids, group, pair_classifications


class WallFinishCalloutWallAuthority:
    def __init__(
        self,
        results: Mapping[tuple[str, ...], WallFinishCalloutWallScopeResult],
        *,
        _seal=None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("WallFinishCalloutWallAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve_scope(
        self,
        selector: WallFinishCalloutWallScopeSelector,
    ) -> WallFinishCalloutWallScopeResult:
        if type(selector) is not WallFinishCalloutWallScopeSelector:
            raise TypeError("selector must be WallFinishCalloutWallScopeSelector")
        return self._results.get(
            selector.key,
            _blocked(FINISH_CALLOUT_WALL_BINDING_UNAVAILABLE),
        )


class WallFinishCalloutWallProducer:
    def __init__(
        self,
        results: Mapping[tuple[str, ...], WallFinishCalloutWallScopeResult],
        *,
        _seal=None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "WallFinishCalloutWallProducer must be obtained "
                "from_source_visibility_producer()"
            )
        self._results = MappingProxyType(dict(results))

    @classmethod
    def from_source_visibility_producer(
        cls,
        source_visibility_producer: SourceVisibilityProducer,
        *,
        page_ids: Optional[Sequence[str]] = None,
    ) -> "WallFinishCalloutWallProducer":
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError(
                "source_visibility_producer must be an actual SourceVisibilityProducer"
            )
        selected = (
            None
            if page_ids is None
            else tuple(
                sorted(
                    {str(page).strip() for page in page_ids if str(page).strip()},
                    key=int,
                )
            )
        )
        if page_ids is not None and not selected:
            raise ValueError("page_ids must contain at least one source page")

        wall_authority = PhysicalWallCandidateProducer.from_authenticated_viewports(
            source_visibility_producer,
            page_ids=selected,
        ).authority()
        results: dict[tuple[str, ...], WallFinishCalloutWallScopeResult] = {}
        store = source_visibility_producer._producer._store

        for revision_id, published in sorted(
            source_visibility_producer._published_by_revision.items()
        ):
            if (
                source_visibility_producer._producer.current_revision_id(
                    published.revision.document_id
                )
                != revision_id
            ):
                continue
            source_bytes = store.source_bytes_by_revision.get(revision_id)
            if (
                source_bytes is None
                or hashlib.sha256(source_bytes).hexdigest()
                != published.revision.source_sha256
            ):
                raise RuntimeError(FINISH_CALLOUT_WALL_SOURCE_INTEGRITY_FAILURE)

            page_list = selected or tuple(
                str(int(page_number))
                for page_number in sorted(published.coverage.decoded_pages)
            )
            doc = fitz.open(stream=source_bytes, filetype="pdf")
            try:
                for page_id in page_list:
                    page_number = int(page_id)
                    if not 1 <= page_number <= doc.page_count:
                        continue
                    page = doc.load_page(page_number - 1)
                    viewports = _authoritative_viewports(page, page_number)
                    page_lines = _page_visible_lines(
                        source_visibility_producer,
                        published,
                        page_id,
                    )

                    for (
                        _block_id,
                        trusted_annotation_text,
                        annotation_ids,
                        annotation_bbox,
                        text_height,
                    ) in _trusted_finish_callout_blocks_with_raster(
                        source_visibility_producer,
                        published,
                        page_id,
                    ):
                        viewport = assign_bbox_to_viewport(
                            annotation_bbox,
                            viewports,
                            allow_derived=True,
                        )
                        if viewport is None or viewport.bounding_box is None:
                            continue
                        wall_selector = wall_authority.selector_for_viewport(
                            document_id=published.revision.document_id,
                            revision_id=published.revision.revision_id,
                            source_sha256=published.revision.source_sha256,
                            snapshot_id=published.snapshot.snapshot_id,
                            page_id=page_id,
                            viewport_id=viewport.view_id,
                        )
                        if wall_selector is None:
                            continue
                        wall_scope = wall_authority.resolve_scope(wall_selector)
                        if wall_scope.status is not EvidenceResolutionStatus.CORROBORATED:
                            continue

                        leader_lines = _viewport_owned_lines(
                            page_lines,
                            viewport,
                            viewports,
                        )
                        wall_observation_ids = set(wall_scope.source_observation_ids)
                        wall_lines = tuple(
                            line
                            for line in page_lines
                            if line.observation_id in wall_observation_ids
                        )
                        terminators = tuple(
                            term
                            for term in _filled_terminators(page, text_height)
                            if viewport.bounding_box[0]
                            <= term.center[0]
                            <= viewport.bounding_box[2]
                            and viewport.bounding_box[1]
                            <= term.center[1]
                            <= viewport.bounding_box[3]
                        )
                        paths = _leader_paths(
                            annotation_bbox,
                            leader_lines,
                            terminators,
                        )
                        if not paths:
                            continue

                        accepted: dict[
                            tuple[str, tuple[str, ...]],
                            WallFinishCalloutWallBindingRecord,
                        ] = {}
                        for leader_ids, terminator in paths:
                            if not _local_owner_universe_safe(
                                terminator=terminator,
                                page_lines=page_lines,
                                wall_scope=wall_scope,
                            ):
                                continue

                            target, source_segments, target_status = (
                                _target_from_terminator(
                                    terminator,
                                    wall_lines,
                                    wall_scope,
                                )
                            )
                            if (
                                target_status
                                is not EvidenceResolutionStatus.CORROBORATED
                                or target is None
                            ):
                                continue

                            (
                                raw_owner_ids,
                                equivalence_group,
                                pair_classifications,
                            ) = _target_provenance(
                                terminator=terminator,
                                wall_lines=wall_lines,
                                wall_scope=wall_scope,
                                target=target,
                            )
                            if not raw_owner_ids:
                                continue

                            payload = {
                                "document_id": published.revision.document_id,
                                "revision_id": published.revision.revision_id,
                                "source_sha256": published.revision.source_sha256,
                                "snapshot_id": published.snapshot.snapshot_id,
                                "page_id": page_id,
                                "viewport_id": viewport.view_id,
                                "physical_wall_decision_scope_id": (
                                    wall_scope.decision_scope_id
                                ),
                                "physical_wall_id": target.wall_candidate_id,
                                "raw_owner_wall_ids": raw_owner_ids,
                                "equivalence_group_wall_ids": equivalence_group,
                                "source_wall_primitive_ids": tuple(
                                    sorted(source_segments)
                                ),
                                "trusted_annotation_text": trusted_annotation_text,
                                "annotation_observation_ids": tuple(
                                    annotation_ids
                                ),
                                "leader_path_ids": tuple(leader_ids),
                                "terminator_primitive_ids": (
                                    terminator.primitive_id,
                                ),
                            }
                            binding_id = stable_contract_id(
                                "wall_finish_callout_wall_binding",
                                payload,
                                digest_chars=32,
                            )
                            evidence_ids = tuple(
                                dict.fromkeys(
                                    (
                                        *annotation_ids,
                                        *leader_ids,
                                        terminator.primitive_id,
                                        *tuple(sorted(source_segments)),
                                    )
                                )
                            )
                            record = WallFinishCalloutWallBindingRecord(
                                binding_id=binding_id,
                                document_id=published.revision.document_id,
                                revision_id=published.revision.revision_id,
                                source_sha256=published.revision.source_sha256,
                                snapshot_id=published.snapshot.snapshot_id,
                                page_id=page_id,
                                viewport_id=viewport.view_id,
                                decision_scope_id=(
                                    f"finish-callout-wall:{viewport.view_id}"
                                ),
                                physical_wall_decision_scope_id=(
                                    wall_scope.decision_scope_id
                                ),
                                physical_wall_id=target.wall_candidate_id,
                                raw_owner_wall_ids=raw_owner_ids,
                                equivalence_group_wall_ids=equivalence_group,
                                equivalence_pair_classifications=(
                                    pair_classifications
                                ),
                                source_wall_primitive_ids=tuple(
                                    sorted(source_segments)
                                ),
                                trusted_annotation_text=trusted_annotation_text,
                                annotation_observation_ids=tuple(
                                    annotation_ids
                                ),
                                leader_path_ids=tuple(leader_ids),
                                terminator_primitive_ids=(
                                    terminator.primitive_id,
                                ),
                                source_evidence_ids=evidence_ids,
                                source_evidence_kind=(
                                    SOURCE_EVIDENCE_KIND_NATIVE_DIRECT_CALLOUT
                                ),
                                status=EvidenceResolutionStatus.CORROBORATED,
                                reason_codes=(
                                    FINISH_CALLOUT_WALL_BINDING_RESOLVED,
                                ),
                                _seal=_RECORD_SEAL,
                            )
                            signature = (
                                record.physical_wall_id,
                                tuple(record.annotation_observation_ids),
                            )
                            prior = accepted.get(signature)
                            if prior is None or record.binding_id < prior.binding_id:
                                accepted[signature] = record

                        bindings = tuple(
                            sorted(
                                accepted.values(),
                                key=lambda record: record.binding_id,
                            )
                        )
                        if not bindings:
                            continue
                        selector = WallFinishCalloutWallScopeSelector(
                            document_id=published.revision.document_id,
                            revision_id=published.revision.revision_id,
                            source_sha256=published.revision.source_sha256,
                            snapshot_id=published.snapshot.snapshot_id,
                            page_id=page_id,
                            viewport_id=viewport.view_id,
                            decision_scope_id=(
                                f"finish-callout-wall:{viewport.view_id}"
                            ),
                        )
                        result = WallFinishCalloutWallScopeResult(
                            status=EvidenceResolutionStatus.CORROBORATED,
                            reason_codes=(
                                FINISH_CALLOUT_WALL_BINDING_RESOLVED,
                            ),
                            bindings=bindings,
                        )
                        previous = results.get(selector.key)
                        if previous is None:
                            results[selector.key] = result
                        else:
                            merged = {
                                record.binding_id: record
                                for record in (
                                    *previous.bindings,
                                    *result.bindings,
                                )
                            }
                            results[selector.key] = WallFinishCalloutWallScopeResult(
                                status=EvidenceResolutionStatus.CORROBORATED,
                                reason_codes=(
                                    FINISH_CALLOUT_WALL_BINDING_RESOLVED,
                                ),
                                bindings=tuple(
                                    sorted(
                                        merged.values(),
                                        key=lambda record: record.binding_id,
                                    )
                                ),
                            )
            finally:
                doc.close()

        return cls(results, _seal=_PRODUCER_SEAL)

    def authority(self) -> WallFinishCalloutWallAuthority:
        return WallFinishCalloutWallAuthority(
            self._results,
            _seal=_AUTHORITY_SEAL,
        )

    def published_results(self) -> tuple[WallFinishCalloutWallScopeResult, ...]:
        return tuple(self._results[key] for key in sorted(self._results))


__all__ = [
    "FINISH_CALLOUT_WALL_BINDING_RESOLVED",
    "FINISH_CALLOUT_WALL_BINDING_UNAVAILABLE",
    "FINISH_CALLOUT_WALL_LOCAL_UNIVERSE_INCOMPLETE",
    "FINISH_CALLOUT_WALL_SOURCE_INTEGRITY_FAILURE",
    "WALL_FINISH_CALLOUT_WALL_BINDING_SCHEMA_VERSION",
    "WallFinishCalloutWallAuthority",
    "WallFinishCalloutWallBindingRecord",
    "WallFinishCalloutWallProducer",
    "WallFinishCalloutWallScopeResult",
    "WallFinishCalloutWallScopeSelector",
]
