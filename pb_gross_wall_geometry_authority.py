"""Producer-owned gross wall geometry authority.

This module proves one proposition only: the authenticated 2D gross wall-local
geometry for an exact physical wall. The gross geometry is defined in wall-local
Euclidean coordinates (u, z) in metres:
- u runs along the wall baseline from 0.0 to length_m;
- z runs vertically from 0.0 to height_m.

The gross wall polygon is box(0.0, 0.0, length_m, height_m).
The wall_local_frame_id ties this gross wall to the exact same wall-local
coordinate frame used by physical opening voids on this wall.

No caller-supplied raw area, polygon, or scalar dimensions can mint authority.
Every positive GrossWallGeometryRecord is re-resolved from sealed upstream
authorities (physical wall candidate authority, whole-wall host frame authority,
physical scale authority, and wall height authority) and joined on exact
physical wall identity and source lineage.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping, Optional, Sequence
from shapely.geometry import box

from pb_geometry_takeoff_model import AuthorityStatus
from pb_migration_contracts import (
    EvidenceResolutionStatus,
    QuantityEvidence,
    stable_contract_id,
)
from pb_opening_host_frame_authority import (
    OpeningHostFrameAuthority,
    OpeningHostFrameEvidence,
    OpeningHostFrameSelector,
)
from pb_physical_scale_authority import (
    PhysicalScaleAuthority,
    PhysicalScaleSelector,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateSelector,
)
from pb_wall_height_authority import (
    WALL_HEIGHT_FAMILY,
    WallHeightAuthority,
    WallHeightSelector,
)
from pb_zero_opening_wall_frame_authority import (
    ZeroOpeningWallFrameAuthority,
    ZeroOpeningWallFrameSelector,
)


GROSS_WALL_GEOMETRY_SCHEMA_VERSION = "1.1.0"

GROSS_WALL_GEOMETRY_RESOLVED = "gross_wall_geometry_resolved"
GROSS_WALL_GEOMETRY_WALL_UNRESOLVED = "gross_wall_geometry_wall_unresolved"
GROSS_WALL_GEOMETRY_HEIGHT_UNRESOLVED = "gross_wall_geometry_height_unresolved"
GROSS_WALL_GEOMETRY_FRAME_UNRESOLVED = "gross_wall_geometry_frame_unresolved"
GROSS_WALL_GEOMETRY_SCALE_UNRESOLVED = "gross_wall_geometry_scale_unresolved"
GROSS_WALL_GEOMETRY_LINEAGE_MISMATCH = "gross_wall_geometry_lineage_mismatch"
GROSS_WALL_GEOMETRY_RECORD_UNAVAILABLE = "gross_wall_geometry_record_unavailable"
GROSS_WALL_GEOMETRY_INVALID = "gross_wall_geometry_invalid"
METRE = "metre"

_AUTHORITY_SEAL = object()
_PRODUCER_SEAL = object()
_Key = tuple[str, str, str, str, str, str, str]

_FORBIDDEN_DEFAULT_TOKENS = frozenset({
    "default",
    "assumed",
    "fallback",
    "legacy_default",
    "model_default",
    "estimated",
})


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


def _is_forbidden_default_height(quantity: QuantityEvidence) -> bool:
    formula = str(quantity.formula or "").lower()
    if any(tok in formula for tok in _FORBIDDEN_DEFAULT_TOKENS):
        return True
    meta = quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
    for key in ("default", "assumed", "is_default", "is_assumed", "legacy_default"):
        if bool(meta.get(key)):
            return True
    origin = str(meta.get("origin") or "").strip().lower()
    if origin in _FORBIDDEN_DEFAULT_TOKENS:
        return True
    method = str(meta.get("method") or "").strip().lower()
    if any(tok in method for tok in _FORBIDDEN_DEFAULT_TOKENS):
        return True
    return False


@dataclass(frozen=True)
class GrossWallGeometrySelector:
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
class GrossWallGeometryRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    physical_wall_id: str
    wall_local_frame_id: str
    length_m: float
    height_m: float
    gross_area_m2: float
    polygon_wkb_hex: str
    member_wall_candidate_ids: tuple[str, ...] = ()
    coordinate_unit: str = METRE
    schema_version: str = GROSS_WALL_GEOMETRY_SCHEMA_VERSION


@dataclass(frozen=True)
class GrossWallGeometryResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: GrossWallGeometryRecord | None = None
    schema_version: str = GROSS_WALL_GEOMETRY_SCHEMA_VERSION


def _blocked(
    status: EvidenceResolutionStatus,
    reason: str,
    *upstream_reasons: str,
) -> GrossWallGeometryResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    return GrossWallGeometryResult(
        status=status,
        reason_codes=tuple(
            dict.fromkeys([reason, *(str(r) for r in upstream_reasons if str(r))])
        ),
        record=None,
    )


class GrossWallGeometryAuthority:
    """Sealed selector-only lookup for published gross wall geometry records."""

    def __init__(
        self,
        results: Mapping[_Key, GrossWallGeometryResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("GrossWallGeometryAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: GrossWallGeometrySelector) -> GrossWallGeometryResult:
        if type(selector) is not GrossWallGeometrySelector:
            raise TypeError("selector must be GrossWallGeometrySelector")
        return self._results.get(
            selector.key,
            _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                GROSS_WALL_GEOMETRY_RECORD_UNAVAILABLE,
            ),
        )


class GrossWallGeometryProducer:
    """Trusted writer boundary for authenticated gross wall geometry."""

    def __init__(
        self,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        host_frame_authority: OpeningHostFrameAuthority,
        physical_scale_authority: PhysicalScaleAuthority,
        wall_height_authority: WallHeightAuthority,
        zero_opening_wall_frame_authority: ZeroOpeningWallFrameAuthority | None = None,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("GrossWallGeometryProducer must be obtained from from_authorities()")
        if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError("physical_wall_candidate_authority must be producer-owned PhysicalWallCandidateAuthority")
        if type(host_frame_authority) is not OpeningHostFrameAuthority:
            raise TypeError("host_frame_authority must be producer-owned OpeningHostFrameAuthority")
        if type(physical_scale_authority) is not PhysicalScaleAuthority:
            raise TypeError("physical_scale_authority must be producer-owned PhysicalScaleAuthority")
        if type(wall_height_authority) is not WallHeightAuthority:
            raise TypeError(
                "wall_height_authority must be a producer-owned WallHeightAuthority obtained from "
                "WallHeightProducer.from_authorities().authority(); duck-typed resolvers and plain "
                "Mappings are not accepted."
            )
        if (
            zero_opening_wall_frame_authority is not None
            and type(zero_opening_wall_frame_authority)
            is not ZeroOpeningWallFrameAuthority
        ):
            raise TypeError(
                "zero_opening_wall_frame_authority must be producer-owned"
            )
        self._wall_candidates = physical_wall_candidate_authority
        self._frame = host_frame_authority
        self._scale = physical_scale_authority
        self._height = wall_height_authority
        self._zero_opening_frame = zero_opening_wall_frame_authority
        self._results: dict[_Key, GrossWallGeometryResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        host_frame_authority: OpeningHostFrameAuthority,
        physical_scale_authority: PhysicalScaleAuthority,
        wall_height_authority: WallHeightAuthority,
        zero_opening_wall_frame_authority: ZeroOpeningWallFrameAuthority | None = None,
    ) -> "GrossWallGeometryProducer":
        return cls(
            physical_wall_candidate_authority,
            host_frame_authority,
            physical_scale_authority,
            wall_height_authority,
            zero_opening_wall_frame_authority,
            _seal=_PRODUCER_SEAL,
        )

    def authority(self) -> GrossWallGeometryAuthority:
        return GrossWallGeometryAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def _store(
        self,
        selector: GrossWallGeometrySelector,
        result: GrossWallGeometryResult,
    ) -> GrossWallGeometryResult:
        self._results[selector.key] = result
        return result

    def publish_scope(self, selector: GrossWallGeometrySelector) -> GrossWallGeometryResult:
        return self.publish(selector)

    def publish(self, selector: GrossWallGeometrySelector) -> GrossWallGeometryResult:
        if type(selector) is not GrossWallGeometrySelector:
            raise TypeError("selector must be GrossWallGeometrySelector")

        # 1. Resolve Physical Wall Candidates and Equivalence
        cand_scope_id = f"wall-source:page-{selector.page_id}"
        wall_sel = PhysicalWallCandidateSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=cand_scope_id,
        )
        candidates_result = self._wall_candidates.resolve_scope(wall_sel)
        if (
            candidates_result.status is not EvidenceResolutionStatus.CORROBORATED
            and selector.decision_scope_id != cand_scope_id
        ):
            try:
                wall_sel_alt = PhysicalWallCandidateSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    page_id=selector.page_id,
                    decision_scope_id=selector.decision_scope_id,
                )
                alt_res = self._wall_candidates.resolve_scope(wall_sel_alt)
                if alt_res.status is EvidenceResolutionStatus.CORROBORATED:
                    candidates_result = alt_res
            except Exception:
                pass
        if (
            candidates_result.status is not EvidenceResolutionStatus.CORROBORATED
            or not getattr(candidates_result, "scope_complete", False)
        ):
            return self._store(
                selector,
                _blocked(
                    candidates_result.status,
                    GROSS_WALL_GEOMETRY_WALL_UNRESOLVED,
                    *(getattr(candidates_result, "reason_codes", ()) or ()),
                ),
            )
        if (
            candidates_result.document_id != selector.document_id
            or candidates_result.revision_id != selector.revision_id
            or candidates_result.source_sha256 != selector.source_sha256
            or candidates_result.snapshot_id != selector.snapshot_id
            or candidates_result.page_id != selector.page_id
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    GROSS_WALL_GEOMETRY_LINEAGE_MISMATCH,
                ),
            )

        candidate_records = tuple(getattr(candidates_result, "records", ()))
        selector_matches_candidate = any(
            getattr(record, "wall_candidate_id", None) == selector.physical_wall_id
            or getattr(
                getattr(record, "physical_identity", None),
                "physical_wall_id",
                None,
            )
            == selector.physical_wall_id
            for record in candidate_records
        )

        # Resolve either an opening-derived whole-wall frame or a producer-owned
        # zero-opening wall frame. The two authorities prove disjoint positive
        # propositions: the zero-opening authority itself refuses any wall class
        # intersecting a sealed opening host frame.
        matching_frames: list[OpeningHostFrameEvidence] = []
        if hasattr(self._frame, "_results"):
            for _key, res in self._frame._results.items():
                ev = getattr(res, "evidence", None)
                if (
                    ev is None
                    or res.status is not EvidenceResolutionStatus.CORROBORATED
                ):
                    continue
                is_match = (
                    ev.whole_wall_frame_id == selector.physical_wall_id
                    or selector.physical_wall_id
                    in getattr(ev, "whole_wall_candidate_ids", ())
                    or ev.host_wall_id == selector.physical_wall_id
                )
                if not is_match:
                    continue
                frame_sel = ev.selector
                if (
                    frame_sel.document_id != selector.document_id
                    or frame_sel.revision_id != selector.revision_id
                    or frame_sel.source_sha256 != selector.source_sha256
                    or frame_sel.snapshot_id != selector.snapshot_id
                    or frame_sel.page_id != selector.page_id
                ):
                    return self._store(
                        selector,
                        _blocked(
                            EvidenceResolutionStatus.CONFLICT,
                            GROSS_WALL_GEOMETRY_LINEAGE_MISMATCH,
                        ),
                    )
                matching_frames.append(ev)

        zero_frame_result = None
        zero_frame_record = None
        if (
            not matching_frames
            and selector_matches_candidate
            and self._zero_opening_frame is not None
        ):
            zero_frame_result = self._zero_opening_frame.resolve(
                ZeroOpeningWallFrameSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    page_id=selector.page_id,
                    decision_scope_id=selector.decision_scope_id,
                    physical_wall_id=selector.physical_wall_id,
                )
            )
            if (
                zero_frame_result.status is EvidenceResolutionStatus.CORROBORATED
                and zero_frame_result.record is not None
            ):
                zero_frame_record = zero_frame_result.record

        if not matching_frames and zero_frame_record is None:
            return self._store(
                selector,
                _blocked(
                    (
                        zero_frame_result.status
                        if zero_frame_result is not None
                        else EvidenceResolutionStatus.ABSTAINED
                    ),
                    (
                        GROSS_WALL_GEOMETRY_FRAME_UNRESOLVED
                        if selector_matches_candidate
                        else GROSS_WALL_GEOMETRY_WALL_UNRESOLVED
                    ),
                    *(
                        tuple(zero_frame_result.reason_codes)
                        if zero_frame_result is not None
                        else ()
                    ),
                ),
            )

        member_addressed = False
        if matching_frames:
            distinct_frame_ids = {
                ev.whole_wall_frame_id for ev in matching_frames
            }
            if len(distinct_frame_ids) > 1:
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.CONFLICT,
                        GROSS_WALL_GEOMETRY_FRAME_UNRESOLVED,
                        "ambiguous_whole_wall_frame",
                    ),
                )

            distinct_memberships = {
                tuple(sorted(str(item) for item in ev.whole_wall_candidate_ids))
                for ev in matching_frames
            }
            if len(distinct_memberships) != 1:
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.CONFLICT,
                        GROSS_WALL_GEOMETRY_FRAME_UNRESOLVED,
                        "inconsistent_whole_wall_membership",
                    ),
                )

            frame_evidence = matching_frames[0]
            frame_member_ids = tuple(
                sorted(
                    dict.fromkeys(
                        str(item)
                        for item in frame_evidence.whole_wall_candidate_ids
                        if str(item)
                    )
                )
            )
            if not frame_member_ids:
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        GROSS_WALL_GEOMETRY_FRAME_UNRESOLVED,
                        "whole_wall_membership_unavailable",
                    ),
                )

            frame_addressed = (
                selector.physical_wall_id
                == frame_evidence.whole_wall_frame_id
            )
            member_addressed = frame_addressed
            wall_local_frame_id = frame_evidence.whole_wall_frame_id
            # u0/u1 are the opening interval inside this shared wall frame.
            # Gross wall extent must come from the independently sealed whole
            # wall length, never from the opening width.
            whole_wall_length_pt = getattr(
                frame_evidence, "whole_wall_length_pt", None
            )
            if whole_wall_length_pt is None:
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        GROSS_WALL_GEOMETRY_FRAME_UNRESOLVED,
                        "whole_wall_length_unavailable",
                    ),
                )
            length_pt = float(whole_wall_length_pt)
            viewport_id = getattr(frame_evidence, "viewport_id", None)
        else:
            assert zero_frame_record is not None
            if zero_frame_record.physical_wall_id != selector.physical_wall_id:
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.CONFLICT,
                        GROSS_WALL_GEOMETRY_LINEAGE_MISMATCH,
                    ),
                )
            frame_member_ids = tuple(
                sorted(
                    dict.fromkeys(
                        str(item)
                        for item in zero_frame_record.member_wall_candidate_ids
                        if str(item)
                    )
                )
            )
            if not frame_member_ids:
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        GROSS_WALL_GEOMETRY_FRAME_UNRESOLVED,
                        "zero_opening_wall_membership_unavailable",
                    ),
                )
            member_addressed = True
            frame_addressed = False
            wall_local_frame_id = zero_frame_record.wall_local_frame_id
            length_pt = float(zero_frame_record.length_pt)
            viewport_id = zero_frame_record.scale_viewport_id

        records_by_candidate_id = {
            str(getattr(record, "wall_candidate_id", "")): record
            for record in candidate_records
            if str(getattr(record, "wall_candidate_id", ""))
        }
        if member_addressed:
            if any(
                member_id not in records_by_candidate_id
                for member_id in frame_member_ids
            ):
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        GROSS_WALL_GEOMETRY_WALL_UNRESOLVED,
                        "whole_wall_member_unresolved",
                    ),
                )
        else:
            matching_candidates = [
                record
                for record in candidate_records
                if getattr(record, "wall_candidate_id", None)
                == selector.physical_wall_id
                or getattr(
                    getattr(record, "physical_identity", None),
                    "physical_wall_id",
                    None,
                )
                == selector.physical_wall_id
            ]
            if not matching_candidates:
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        GROSS_WALL_GEOMETRY_WALL_UNRESOLVED,
                    ),
                )

        # Candidate-level ambiguity remains fail-closed. Whole-wall and
        # zero-opening frame addresses must have every sealed member free of
        # unresolved physical-wall equivalence.
        equivalence = getattr(candidates_result, "equivalence", None)
        if equivalence is not None and hasattr(equivalence, "is_ambiguous"):
            ambiguity_targets = (
                frame_member_ids
                if member_addressed
                else (selector.physical_wall_id,)
            )
            if any(
                equivalence.is_ambiguous(target_id)
                for target_id in ambiguity_targets
            ):
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.CONFLICT,
                        GROSS_WALL_GEOMETRY_WALL_UNRESOLVED,
                        "ambiguous_physical_wall_identity",
                    ),
                )

        if not math.isfinite(length_pt) or length_pt <= 0:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    GROSS_WALL_GEOMETRY_INVALID,
                ),
            )

        # 3. Resolve Scale from PhysicalScaleAuthority
        scale_sel = PhysicalScaleSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            viewport_id=viewport_id,
        )
        scale_result = self._scale.resolve(scale_sel)
        if (
            scale_result.status is not EvidenceResolutionStatus.CORROBORATED
            or scale_result.evidence is None
        ):
            return self._store(
                selector,
                _blocked(
                    scale_result.status,
                    GROSS_WALL_GEOMETRY_SCALE_UNRESOLVED,
                    *getattr(scale_result, "reason_codes", ()),
                ),
            )
        scale_ev = scale_result.evidence
        if (
            scale_ev.selector.document_id != selector.document_id
            or scale_ev.selector.revision_id != selector.revision_id
            or scale_ev.selector.source_sha256 != selector.source_sha256
            or scale_ev.selector.snapshot_id != selector.snapshot_id
            or scale_ev.selector.page_id != selector.page_id
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    GROSS_WALL_GEOMETRY_LINEAGE_MISMATCH,
                ),
            )
        mm_per_point = float(scale_ev.mm_per_point)
        if not math.isfinite(mm_per_point) or mm_per_point <= 0:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    GROSS_WALL_GEOMETRY_INVALID,
                ),
            )
        length_m = round((length_pt * mm_per_point) / 1000.0, 12)
        if not math.isfinite(length_m) or length_m <= 0:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    GROSS_WALL_GEOMETRY_INVALID,
                ),
            )

        # 4. Resolve Wall Height from WallHeightAuthority.
        # Cross-sheet registration is candidate-addressed because source sheets
        # contain producer-owned candidate geometry, not synthetic frame IDs.
        # For a frame-addressed wall, only candidate IDs sealed into that exact
        # whole-wall frame may support the shared wall height.
        height_target_ids = (
            frame_member_ids
            if member_addressed
            else (selector.physical_wall_id,)
        )
        height_candidates: list[tuple[str, QuantityEvidence]] = []
        raw_height_quantities: list[QuantityEvidence] = []
        for height_target_id in height_target_ids:
            height_selector = WallHeightSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
                decision_scope_id=selector.decision_scope_id,
                physical_wall_id=height_target_id,
            )
            candidate_quantity = self._height.resolve(height_selector)
            if not isinstance(candidate_quantity, QuantityEvidence):
                continue
            raw_height_quantities.append(candidate_quantity)
            if (
                not candidate_quantity.abstained
                and candidate_quantity.value is not None
                and candidate_quantity.family == WALL_HEIGHT_FAMILY
                and candidate_quantity.unit in ("m", "metre", "meter")
                and candidate_quantity.status == AuthorityStatus.FIRM.value
            ):
                height_candidates.append(
                    (height_target_id, candidate_quantity)
                )

        if not height_candidates:
            upstream_reasons = tuple(
                dict.fromkeys(
                    reason
                    for quantity in raw_height_quantities
                    for reason in (
                        getattr(quantity, "blocking_reasons", ())
                        or getattr(quantity, "reason_codes", ())
                    )
                    if str(reason)
                )
            )
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    GROSS_WALL_GEOMETRY_HEIGHT_UNRESOLVED,
                    *upstream_reasons,
                ),
            )

        distinct_height_values = {
            round(float(quantity.value), 9)
            for _target_id, quantity in height_candidates
            if quantity.value is not None
        }
        if len(distinct_height_values) != 1:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    GROSS_WALL_GEOMETRY_HEIGHT_UNRESOLVED,
                    "conflicting_whole_wall_member_heights",
                ),
            )

        height_target_id, height_qty = sorted(
            height_candidates,
            key=lambda item: (item[0], item[1].quantity_id),
        )[0]

        # Enforce exact producer-owned candidate identity for the source height.
        if height_qty.input_entity_ids != (height_target_id,):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    GROSS_WALL_GEOMETRY_HEIGHT_UNRESOLVED,
                    "wall_height_target_mismatch",
                ),
            )

        h_meta = (
            height_qty.metadata if isinstance(height_qty.metadata, Mapping) else {}
        )
        if h_meta.get("target_entity_id") != height_target_id:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    GROSS_WALL_GEOMETRY_HEIGHT_UNRESOLVED,
                    "wall_height_target_mismatch",
                ),
            )
        if h_meta.get("identity_binding_kind") != "cross_sheet_registration":
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    GROSS_WALL_GEOMETRY_HEIGHT_UNRESOLVED,
                    "wall_height_exact_identity_binding_unavailable",
                ),
            )
        registration_record_id = str(
            h_meta.get("cross_sheet_registration_record_id") or ""
        ).strip()
        target_physical_element_id = str(
            h_meta.get("target_physical_element_id") or ""
        ).strip()
        height_evidence_page_id = str(
            h_meta.get("height_evidence_page_id") or ""
        ).strip()
        if (
            not registration_record_id
            or not target_physical_element_id
            or not height_evidence_page_id
            or height_evidence_page_id == selector.page_id
            or registration_record_id not in tuple(height_qty.evidence_ids)
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    GROSS_WALL_GEOMETRY_HEIGHT_UNRESOLVED,
                    "wall_height_cross_sheet_binding_incomplete",
                ),
            )

        if (
            h_meta.get("source_sha256") != selector.source_sha256
            or h_meta.get("revision_id") != selector.revision_id
            or h_meta.get("evidence_snapshot_id") != selector.snapshot_id
            or h_meta.get("source_page_id") != selector.page_id
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    GROSS_WALL_GEOMETRY_LINEAGE_MISMATCH,
                ),
            )

        if _is_forbidden_default_height(height_qty):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    GROSS_WALL_GEOMETRY_HEIGHT_UNRESOLVED,
                    "default_or_assumed_height_forbidden",
                ),
            )

        height_m = float(height_qty.value)
        if not math.isfinite(height_m) or height_m <= 0:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    GROSS_WALL_GEOMETRY_INVALID,
                ),
            )
        height_m = round(height_m, 12)

        # 5. Mint GrossWallGeometryRecord only from authenticated propositions
        polygon = box(0.0, 0.0, length_m, height_m)
        gross_area_m2 = round(length_m * height_m, 12)
        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "decision_scope_id": selector.decision_scope_id,
            "physical_wall_id": selector.physical_wall_id,
            "wall_local_frame_id": wall_local_frame_id,
            "length_m": length_m,
            "height_m": height_m,
            "gross_area_m2": gross_area_m2,
            "polygon_wkb_hex": polygon.wkb_hex,
            "member_wall_candidate_ids": frame_member_ids,
            "coordinate_unit": METRE,
            "schema_version": GROSS_WALL_GEOMETRY_SCHEMA_VERSION,
        }
        record_id = stable_contract_id(
            "gross_wall_geometry", payload, digest_chars=32
        )
        record = GrossWallGeometryRecord(record_id=record_id, **payload)
        result = GrossWallGeometryResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(GROSS_WALL_GEOMETRY_RESOLVED,),
            record=record,
        )
        return self._store(selector, result)
