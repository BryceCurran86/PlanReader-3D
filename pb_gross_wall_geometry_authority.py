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
)


GROSS_WALL_GEOMETRY_SCHEMA_VERSION = "1.0.0"

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
        wall_height_authority: object,
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
        self._wall_candidates = physical_wall_candidate_authority
        self._frame = host_frame_authority
        self._scale = physical_scale_authority
        self._height = wall_height_authority
        self._results: dict[_Key, GrossWallGeometryResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        host_frame_authority: OpeningHostFrameAuthority,
        physical_scale_authority: PhysicalScaleAuthority,
        wall_height_authority: object,
    ) -> "GrossWallGeometryProducer":
        return cls(
            physical_wall_candidate_authority,
            host_frame_authority,
            physical_scale_authority,
            wall_height_authority,
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

        # Ensure selector.physical_wall_id is present in candidate records
        matching_candidates = [
            r
            for r in getattr(candidates_result, "records", ())
            if getattr(r, "wall_candidate_id", None) == selector.physical_wall_id
            or getattr(getattr(r, "physical_identity", None), "physical_wall_id", None)
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

        # Check for ambiguous equivalence
        equivalence = getattr(candidates_result, "equivalence", None)
        if equivalence is not None and hasattr(equivalence, "is_ambiguous"):
            if equivalence.is_ambiguous(selector.physical_wall_id):
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.CONFLICT,
                        GROSS_WALL_GEOMETRY_WALL_UNRESOLVED,
                        "ambiguous_physical_wall_identity",
                    ),
                )

        # 2. Resolve Whole-Wall Frame from OpeningHostFrameAuthority
        matching_frames: list[OpeningHostFrameEvidence] = []
        if hasattr(self._frame, "_results"):
            for key, res in self._frame._results.items():
                ev = getattr(res, "evidence", None)
                if (
                    ev is not None
                    and res.status is EvidenceResolutionStatus.CORROBORATED
                ):
                    is_match = (
                        ev.host_wall_id == selector.physical_wall_id
                        or selector.physical_wall_id
                        in getattr(ev, "whole_wall_candidate_ids", ())
                    )
                    if is_match:
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

        if not matching_frames:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    GROSS_WALL_GEOMETRY_FRAME_UNRESOLVED,
                ),
            )

        # Check for multiple distinct whole-wall frames on the same wall
        distinct_frame_ids = {ev.whole_wall_frame_id for ev in matching_frames}
        if len(distinct_frame_ids) > 1:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    GROSS_WALL_GEOMETRY_FRAME_UNRESOLVED,
                    "ambiguous_whole_wall_frame",
                ),
            )

        frame_evidence = matching_frames[0]
        wall_local_frame_id = frame_evidence.whole_wall_frame_id
        length_pt = abs(float(frame_evidence.u1_pt) - float(frame_evidence.u0_pt))
        if not math.isfinite(length_pt) or length_pt <= 0:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    GROSS_WALL_GEOMETRY_INVALID,
                ),
            )

        # 3. Resolve Scale from PhysicalScaleAuthority
        viewport_id = getattr(frame_evidence, "viewport_id", None)
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

        # 4. Resolve Wall Height from WallHeightAuthority
        height_qty = None
        if hasattr(self._height, "resolve"):
            height_qty = self._height.resolve(selector)
        elif isinstance(self._height, Mapping):
            height_qty = self._height.get(selector.key) or self._height.get(
                selector.physical_wall_id
            )

        if height_qty is None:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    GROSS_WALL_GEOMETRY_HEIGHT_UNRESOLVED,
                ),
            )
        if hasattr(height_qty, "quantity"):
            height_qty = height_qty.quantity
        if not isinstance(height_qty, QuantityEvidence):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    GROSS_WALL_GEOMETRY_HEIGHT_UNRESOLVED,
                ),
            )

        # Validate FIRM wall height
        if (
            height_qty.abstained
            or height_qty.value is None
            or height_qty.family != WALL_HEIGHT_FAMILY
            or height_qty.unit not in ("m", "metre", "meter")
            or height_qty.status != AuthorityStatus.FIRM.value
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    GROSS_WALL_GEOMETRY_HEIGHT_UNRESOLVED,
                    *(getattr(height_qty, "blocking_reasons", ()) or ()),
                ),
            )

        # Enforce exact physical wall identity match (no cross-wiring!)
        if height_qty.input_entity_ids != (selector.physical_wall_id,):
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
        target_entity_id = h_meta.get("target_entity_id")
        if (
            target_entity_id is not None
            and target_entity_id != selector.physical_wall_id
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    GROSS_WALL_GEOMETRY_HEIGHT_UNRESOLVED,
                    "wall_height_target_mismatch",
                ),
            )

        # Lineage check on height
        h_sha = h_meta.get("source_sha256")
        h_rev = h_meta.get("revision_id")
        h_page = h_meta.get("page_id")
        h_snap = h_meta.get("evidence_snapshot_id")
        if (
            (h_sha and h_sha != selector.source_sha256)
            or (h_rev and h_rev != selector.revision_id)
            or (h_page and h_page != selector.page_id)
            or (h_snap and h_snap != selector.snapshot_id)
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    GROSS_WALL_GEOMETRY_LINEAGE_MISMATCH,
                ),
            )

        # Forbid default / assumed wall height
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
