"""Producer-owned source-space opening/host whole-wall frame authority.

This module publishes only source-space geometry (PDF points) for an exact G17
physical opening whose unique host binding has already been proved.  Unlike the
superseded opening-local implementation, the frame extent is derived from a
producer-owned connected whole-wall component built from the complete sealed
physical-wall candidate scope and all corroborated same-wall opening bindings.

A local host binding is an authenticated edge between wall-band fragments; it is
not itself global wall identity.  Aligned fragments outside the selected
connected component must be positively DISTINCT from every component member or
publication fails closed.  Geometry, confidence, nearest/first choice, candidate
IDs, or caller-provided completeness never establish physical identity.

This authority does not establish physical scale, metric geometry, opening
height/vertical placement, deduction permission, net wall area, FIRM/commercial
publication, or JobHub data.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
import pb_opening_host_binding_authority as host_geometry
from pb_opening_host_binding_authority import (
    OPENING_HOST_BINDING_RESOLVED,
    OpeningHostBindingAuthority,
    OpeningHostBindingSelector,
)
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningAuthority,
)
from pb_physical_wall_candidate_authority import (
    PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateSelector,
)
from pb_physical_wall_identity import PhysicalEquivalenceClass
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityAuthority

OPENING_HOST_FRAME_SCHEMA_VERSION = "1.2.0"
OPENING_HOST_FRAME_RESOLVED = "opening_host_frame_resolved"
OPENING_HOST_FRAME_OPENING_UNAVAILABLE = "opening_host_frame_opening_unavailable"
OPENING_HOST_FRAME_HOST_UNAVAILABLE = "opening_host_frame_host_unavailable"
OPENING_HOST_FRAME_WALL_UNAVAILABLE = "opening_host_frame_wall_unavailable"
OPENING_HOST_FRAME_WHOLE_WALL_UNPROVEN = "opening_host_frame_whole_wall_unproven"
OPENING_HOST_FRAME_SCOPE_MISMATCH = "opening_host_frame_scope_mismatch"
OPENING_HOST_FRAME_GEOMETRY_UNAVAILABLE = "opening_host_frame_geometry_unavailable"
OPENING_HOST_FRAME_GEOMETRY_INVALID = "opening_host_frame_geometry_invalid"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_Key = tuple[str, str, str, str, str, str, str]
_Point = tuple[float, float]
_Group = tuple[str, ...]
_BandNode = tuple[_Group, ...]
_COORD_TOL = 1e-6


def _require_nonempty(value: object, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be a non-empty string")
    return clean


def _dot(point: _Point, axis: _Point) -> float:
    return point[0] * axis[0] + point[1] * axis[1]


def _cross(left: _Point, right: _Point) -> float:
    return left[0] * right[1] - left[1] * right[0]


def _point_from_basis(u: float, n: float, axis: _Point, normal: _Point) -> _Point:
    return (
        u * axis[0] + n * normal[0],
        u * axis[1] + n * normal[1],
    )


def _cluster_offsets(values: list[float], tolerance: float) -> tuple[float, ...]:
    if not values:
        return ()
    groups: list[list[float]] = []
    for value in sorted(values):
        if not groups or abs(value - groups[-1][-1]) > tolerance:
            groups.append([value])
        else:
            groups[-1].append(value)
    return tuple(sum(group) / len(group) for group in groups)


def _equivalence_group_for(equivalence, wall_id: str) -> _Group:
    for group in equivalence.equivalence_groups:
        if wall_id in group:
            return tuple(sorted(str(member) for member in group))
    return (str(wall_id),)


def _band_node(side_ids: tuple[str, ...], equivalence) -> _BandNode:
    return tuple(
        sorted(
            {
                _equivalence_group_for(equivalence, wall_id)
                for wall_id in side_ids
            }
        )
    )


def _node_member_ids(node: _BandNode) -> tuple[str, ...]:
    return tuple(sorted({wall_id for group in node for wall_id in group}))


def _pair_lookup(equivalence) -> dict[tuple[str, str], PhysicalEquivalenceClass]:
    result: dict[tuple[str, str], PhysicalEquivalenceClass] = {}
    for left, right, raw in equivalence.pair_classifications:
        try:
            result[tuple(sorted((str(left), str(right))))] = PhysicalEquivalenceClass(raw)
        except ValueError:
            continue
    return result


@dataclass(frozen=True)
class OpeningHostFrameSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    opening_identity_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "decision_scope_id",
            "opening_identity_id",
        ):
            _require_nonempty(getattr(self, name), name)

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            self.decision_scope_id,
            self.opening_identity_id,
        )


@dataclass(frozen=True)
class OpeningHostFrameEvidence:
    selector: OpeningHostFrameSelector
    record_id: str
    opening_identity_id: str
    host_binding_record_id: str
    host_wall_id: str
    whole_wall_frame_id: str
    whole_wall_candidate_ids: tuple[str, ...]
    source_observation_ids: tuple[str, ...]
    origin_pt: tuple[float, float]
    axis_unit: tuple[float, float]
    normal_unit: tuple[float, float]
    u0_pt: float
    u1_pt: float
    wall_thickness_pt: float
    coordinate_unit: str = "pdf_point"
    schema_version: str = OPENING_HOST_FRAME_SCHEMA_VERSION


@dataclass(frozen=True)
class OpeningHostFrameResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    evidence: OpeningHostFrameEvidence | None = None
    schema_version: str = OPENING_HOST_FRAME_SCHEMA_VERSION


@dataclass(frozen=True)
class _ScopeBinding:
    opening: object
    geometry: object
    binding: object
    left_node: _BandNode
    right_node: _BandNode


@dataclass(frozen=True)
class _WholeWallFrame:
    origin: _Point
    axis: _Point
    normal: _Point
    u0: float
    u1: float
    wall_thickness: float
    frame_id: str
    candidate_ids: tuple[str, ...]
    source_observation_ids: tuple[str, ...]


def _blocked(
    status: EvidenceResolutionStatus,
    *reasons: str,
) -> OpeningHostFrameResult:
    clean = tuple(dict.fromkeys(str(reason) for reason in reasons if str(reason)))
    return OpeningHostFrameResult(
        status=status,
        reason_codes=clean or ("opening_host_frame_unavailable",),
        evidence=None,
    )


class OpeningHostFrameAuthority:
    """Sealed selector-only lookup for published source-space host frames."""

    def __init__(
        self,
        results: Mapping[_Key, OpeningHostFrameResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise ValueError("OpeningHostFrameAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: OpeningHostFrameSelector) -> OpeningHostFrameResult:
        if type(selector) is not OpeningHostFrameSelector:
            raise TypeError("selector must be OpeningHostFrameSelector")
        result = self._results.get(selector.key)
        if result is not None:
            return result
        return _blocked(
            EvidenceResolutionStatus.ABSTAINED,
            "opening_host_frame_record_unavailable",
        )


class OpeningHostFrameProducer:
    """Trusted writer that re-proves a shared whole-wall source-space frame."""

    def __init__(
        self,
        physical_opening_authority: PhysicalOpeningAuthority,
        host_binding_authority: OpeningHostBindingAuthority,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("OpeningHostFrameProducer must be obtained from from_authorities()")
        if type(physical_opening_authority) is not PhysicalOpeningAuthority:
            raise TypeError("physical_opening_authority must be producer-owned")
        if type(physical_opening_authority.source_visibility_authority()) is not SourceVisibilityAuthority:
            raise TypeError("physical_opening_authority must be visibility-backed")
        if type(host_binding_authority) is not OpeningHostBindingAuthority:
            raise TypeError("host_binding_authority must be producer-owned")
        if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError("physical_wall_candidate_authority must be producer-owned")
        self._opening = physical_opening_authority
        self._host = host_binding_authority
        self._walls = physical_wall_candidate_authority
        self._results: dict[_Key, OpeningHostFrameResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        physical_opening_authority: PhysicalOpeningAuthority,
        host_binding_authority: OpeningHostBindingAuthority,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
    ) -> "OpeningHostFrameProducer":
        return cls(
            physical_opening_authority,
            host_binding_authority,
            physical_wall_candidate_authority,
            _seal=_PRODUCER_SEAL,
        )

    @staticmethod
    def _binding_nodes(binding, geometry, records_by_id, equivalence) -> tuple[_BandNode, _BandNode] | None:
        member_ids = tuple(str(wall_id) for wall_id in binding.member_wall_candidate_ids)
        if len(member_ids) != 4 or len(set(member_ids)) != 4:
            return None
        edge_tol = max(0.5, min(2.0, float(geometry.length) * 0.02))
        left: list[str] = []
        right: list[str] = []
        for wall_id in member_ids:
            record = records_by_id.get(wall_id)
            if record is None:
                return None
            data = host_geometry._candidate_axis_data(record, geometry)
            if data is None:
                return None
            along_min, along_max, _offset = data
            if along_min < -edge_tol and abs(along_max) <= edge_tol:
                left.append(wall_id)
            if along_max > float(geometry.length) + edge_tol and abs(
                along_min - float(geometry.length)
            ) <= edge_tol:
                right.append(wall_id)
        if len(left) != 2 or len(right) != 2:
            return None
        left_node = _band_node(tuple(sorted(left)), equivalence)
        right_node = _band_node(tuple(sorted(right)), equivalence)
        if not left_node or not right_node or left_node == right_node:
            return None
        return left_node, right_node

    def _scope_bindings(self, *, wall_scope, selected_binding, selected_geometry):
        equivalence = wall_scope.equivalence
        if equivalence is None:
            return None
        records_by_id = {record.wall_candidate_id: record for record in wall_scope.records}
        center_tol = max(0.75, float(selected_geometry.thickness) * 0.15)
        thickness_tol = max(0.75, float(selected_geometry.thickness) * 0.15)
        discovered: dict[str, object] = {}

        for observation_id in wall_scope.source_observation_ids:
            selector = ObservationSelector(
                document_id=selected_binding.document_id,
                revision_id=selected_binding.revision_id,
                source_sha256=selected_binding.source_sha256,
                snapshot_id=selected_binding.snapshot_id,
                observation_id=observation_id,
            )
            result = self._opening.prove_existence(selector)
            opening = result.existence_record
            if (
                result.status is EvidenceResolutionStatus.CORROBORATED
                and result.proposition == PHYSICAL_OPENING_EXISTS
                and opening is not None
                and opening.page_id == selected_binding.page_id
            ):
                discovered.setdefault(opening.record_id, opening)

        contexts: list[_ScopeBinding] = []
        selected_seen = False
        for opening in discovered.values():
            geometry = host_geometry._opening_geometry(self._opening, opening)
            if geometry is None:
                continue
            axis = (float(geometry.axis[0]), float(geometry.axis[1]))
            selected_axis = (
                float(selected_geometry.axis[0]),
                float(selected_geometry.axis[1]),
            )
            if abs(_cross(axis, selected_axis)) > _COORD_TOL:
                continue
            delta = (
                float(geometry.origin[0]) - float(selected_geometry.origin[0]),
                float(geometry.origin[1]) - float(selected_geometry.origin[1]),
            )
            selected_normal = (
                float(selected_geometry.normal[0]),
                float(selected_geometry.normal[1]),
            )
            if abs(_dot(delta, selected_normal)) > center_tol:
                continue
            if not math.isclose(
                float(geometry.thickness),
                float(selected_geometry.thickness),
                rel_tol=1e-6,
                abs_tol=thickness_tol,
            ):
                return None

            binding_selector = OpeningHostBindingSelector(
                document_id=selected_binding.document_id,
                revision_id=selected_binding.revision_id,
                source_sha256=selected_binding.source_sha256,
                snapshot_id=selected_binding.snapshot_id,
                page_id=selected_binding.page_id,
                decision_scope_id=selected_binding.decision_scope_id,
                opening_identity_id=opening.record_id,
            )
            binding_result = self._host.resolve(binding_selector)
            if (
                binding_result.status is not EvidenceResolutionStatus.CORROBORATED
                or binding_result.record is None
                or OPENING_HOST_BINDING_RESOLVED not in binding_result.reason_codes
            ):
                return None
            candidate_binding = binding_result.record
            nodes = self._binding_nodes(
                candidate_binding,
                geometry,
                records_by_id,
                equivalence,
            )
            if nodes is None:
                return None
            left_node, right_node = nodes
            contexts.append(
                _ScopeBinding(
                    opening=opening,
                    geometry=geometry,
                    binding=candidate_binding,
                    left_node=left_node,
                    right_node=right_node,
                )
            )
            if candidate_binding.record_id == selected_binding.record_id:
                selected_seen = True

        if not selected_seen:
            return None
        return tuple(contexts)

    @staticmethod
    def _selected_component(contexts: tuple[_ScopeBinding, ...], selected_binding):
        adjacency: dict[_BandNode, set[_BandNode]] = {}
        selected_nodes: tuple[_BandNode, _BandNode] | None = None
        for context in contexts:
            left_node, right_node = context.left_node, context.right_node
            if left_node == right_node:
                return None
            adjacency.setdefault(left_node, set()).add(right_node)
            adjacency.setdefault(right_node, set()).add(left_node)
            if context.binding.record_id == selected_binding.record_id:
                selected_nodes = (left_node, right_node)
        if selected_nodes is None:
            return None

        component: set[_BandNode] = set()
        pending = [selected_nodes[0]]
        while pending:
            node = pending.pop()
            if node in component:
                continue
            component.add(node)
            pending.extend(adjacency.get(node, ()))
        if selected_nodes[1] not in component:
            return None
        if any(len(adjacency.get(node, ())) > 2 for node in component):
            return None
        if len(component) > 1:
            endpoints = [node for node in component if len(adjacency.get(node, ())) == 1]
            if len(endpoints) != 2:
                return None
        return frozenset(component)

    @staticmethod
    def _record_projection(record, axis: _Point, normal: _Point):
        wall = record.wall_candidate
        if wall.is_curved or len(wall.centerline_pts) < 2:
            return None
        points = tuple((float(x), float(y)) for x, y in wall.centerline_pts)
        if any(not (math.isfinite(x) and math.isfinite(y)) for x, y in points):
            return None
        projected_u = tuple(_dot(point, axis) for point in points)
        projected_n = tuple(_dot(point, normal) for point in points)
        if max(projected_u) - min(projected_u) <= _COORD_TOL:
            return None
        return min(projected_u), max(projected_u), sum(projected_n) / len(projected_n)

    def _shared_host_frame(self, *, binding, geometry) -> _WholeWallFrame | None:
        wall_scope = self._walls.resolve_scope(
            PhysicalWallCandidateSelector(
                document_id=binding.document_id,
                revision_id=binding.revision_id,
                source_sha256=binding.source_sha256,
                snapshot_id=binding.snapshot_id,
                page_id=binding.page_id,
                decision_scope_id=binding.decision_scope_id,
            )
        )
        if (
            wall_scope.status is not EvidenceResolutionStatus.CORROBORATED
            or not wall_scope.scope_complete
            or wall_scope.proposition != PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED
            or wall_scope.equivalence is None
        ):
            return None

        records_by_id = {record.wall_candidate_id: record for record in wall_scope.records}
        contexts = self._scope_bindings(
            wall_scope=wall_scope,
            selected_binding=binding,
            selected_geometry=geometry,
        )
        if not contexts:
            return None
        component = self._selected_component(contexts, binding)
        if not component:
            return None

        component_ids = tuple(
            sorted(
                {
                    wall_id
                    for node in component
                    for wall_id in _node_member_ids(node)
                }
            )
        )
        if not component_ids or any(wall_id not in records_by_id for wall_id in component_ids):
            return None

        axis = (float(geometry.axis[0]), float(geometry.axis[1]))
        normal = (float(geometry.normal[0]), float(geometry.normal[1]))
        face_tol = max(0.5, float(geometry.thickness) * 0.05)
        axis_values: list[float] = []
        component_offsets: list[float] = []
        for wall_id in component_ids:
            projection = self._record_projection(records_by_id[wall_id], axis, normal)
            if projection is None:
                return None
            u_min, u_max, offset = projection
            axis_values.extend((u_min, u_max))
            component_offsets.append(offset)

        face_offsets = _cluster_offsets(component_offsets, face_tol)
        if len(face_offsets) != 2:
            return None
        wall_thickness = abs(face_offsets[1] - face_offsets[0])
        if wall_thickness <= _COORD_TOL or not math.isclose(
            wall_thickness,
            float(geometry.thickness),
            rel_tol=1e-6,
            abs_tol=max(_COORD_TOL, face_tol),
        ):
            return None

        pair_lookup = _pair_lookup(wall_scope.equivalence)
        component_set = set(component_ids)
        for record in wall_scope.records:
            wall_id = record.wall_candidate_id
            if wall_id in component_set:
                continue
            projection = self._record_projection(record, axis, normal)
            if projection is None:
                continue
            _u_min, _u_max, offset = projection
            if min(abs(offset - face) for face in face_offsets) > face_tol:
                continue
            # This is an aligned candidate on one of the selected wall faces.
            # It may be excluded only by positive DISTINCT proof against every
            # authenticated component member.  Missing/SAME/AMBIGUOUS evidence
            # means whole-wall extent is not proven complete.
            for member_id in component_ids:
                classification = pair_lookup.get(tuple(sorted((wall_id, member_id))))
                if classification is not PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS:
                    return None

        host_min_u = min(axis_values)
        host_max_u = max(axis_values)
        host_length = host_max_u - host_min_u
        if host_length <= _COORD_TOL:
            return None
        center_n = (face_offsets[0] + face_offsets[1]) / 2.0
        origin = _point_from_basis(host_min_u, center_n, axis, normal)

        opening_start = (float(geometry.origin[0]), float(geometry.origin[1]))
        opening_end = (
            opening_start[0] + axis[0] * float(geometry.length),
            opening_start[1] + axis[1] * float(geometry.length),
        )
        u0 = _dot(
            (opening_start[0] - origin[0], opening_start[1] - origin[1]),
            axis,
        )
        u1 = _dot(
            (opening_end[0] - origin[0], opening_end[1] - origin[1]),
            axis,
        )
        if (
            u0 < -_COORD_TOL
            or u1 - u0 <= _COORD_TOL
            or u1 > host_length + _COORD_TOL
        ):
            return None
        if abs(u0) <= _COORD_TOL:
            u0 = 0.0
        if abs(u1 - host_length) <= _COORD_TOL:
            u1 = host_length

        component_contexts = tuple(
            context
            for context in contexts
            if context.left_node in component and context.right_node in component
        )
        source_observation_ids = tuple(
            sorted(
                {
                    observation_id
                    for context in component_contexts
                    for observation_id in context.opening.source_observation_ids
                }
            )
        )
        frame_payload = {
            "document_id": binding.document_id,
            "revision_id": binding.revision_id,
            "source_sha256": binding.source_sha256,
            "snapshot_id": binding.snapshot_id,
            "page_id": binding.page_id,
            "decision_scope_id": binding.decision_scope_id,
            "component_nodes": tuple(sorted(component)),
            "origin_pt": tuple(round(float(value), 9) for value in origin),
            "axis_unit": tuple(round(float(value), 12) for value in axis),
            "normal_unit": tuple(round(float(value), 12) for value in normal),
            "wall_thickness_pt": round(float(wall_thickness), 9),
        }
        frame_id = stable_contract_id(
            "opening_host_whole_wall_frame_v1",
            frame_payload,
            digest_chars=32,
        )
        return _WholeWallFrame(
            origin=origin,
            axis=axis,
            normal=normal,
            u0=float(u0),
            u1=float(u1),
            wall_thickness=float(wall_thickness),
            frame_id=frame_id,
            candidate_ids=component_ids,
            source_observation_ids=source_observation_ids,
        )

    def publish(
        self,
        *,
        opening_selector: ObservationSelector,
        host_binding_selector: OpeningHostBindingSelector,
    ) -> OpeningHostFrameResult:
        if type(opening_selector) is not ObservationSelector:
            raise TypeError("opening_selector must be ObservationSelector")
        if type(host_binding_selector) is not OpeningHostBindingSelector:
            raise TypeError("host_binding_selector must be OpeningHostBindingSelector")

        opening_result = self._opening.prove_existence(opening_selector)
        if (
            opening_result.status is not EvidenceResolutionStatus.CORROBORATED
            or opening_result.proposition != PHYSICAL_OPENING_EXISTS
            or opening_result.existence_record is None
        ):
            return _blocked(
                opening_result.status
                if opening_result.status in {
                    EvidenceResolutionStatus.ABSTAINED,
                    EvidenceResolutionStatus.CONFLICT,
                }
                else EvidenceResolutionStatus.ABSTAINED,
                OPENING_HOST_FRAME_OPENING_UNAVAILABLE,
                *opening_result.reason_codes,
            )
        opening = opening_result.existence_record

        host_result = self._host.resolve(host_binding_selector)
        if (
            host_result.status is not EvidenceResolutionStatus.CORROBORATED
            or host_result.record is None
            or OPENING_HOST_BINDING_RESOLVED not in host_result.reason_codes
        ):
            return _blocked(
                host_result.status
                if host_result.status in {
                    EvidenceResolutionStatus.ABSTAINED,
                    EvidenceResolutionStatus.CONFLICT,
                }
                else EvidenceResolutionStatus.ABSTAINED,
                OPENING_HOST_FRAME_HOST_UNAVAILABLE,
                *host_result.reason_codes,
            )
        binding = host_result.record

        lineage_matches = (
            opening.document_id == binding.document_id == host_binding_selector.document_id
            and opening.revision_id == binding.revision_id == host_binding_selector.revision_id
            and opening.source_sha256 == binding.source_sha256 == host_binding_selector.source_sha256
            and opening.snapshot_id == binding.snapshot_id == host_binding_selector.snapshot_id
            and opening.page_id == binding.page_id == host_binding_selector.page_id
            and opening.record_id == binding.opening_identity_id
            == host_binding_selector.opening_identity_id
            and binding.decision_scope_id == host_binding_selector.decision_scope_id
        )
        if not lineage_matches:
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                OPENING_HOST_FRAME_SCOPE_MISMATCH,
            )

        geometry = host_geometry._opening_geometry(self._opening, opening)
        if geometry is None:
            return _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                OPENING_HOST_FRAME_GEOMETRY_UNAVAILABLE,
            )
        values = (
            *geometry.origin,
            *geometry.axis,
            *geometry.normal,
            geometry.length,
            geometry.thickness,
        )
        if (
            not all(math.isfinite(float(value)) for value in values)
            or geometry.length <= 0.0
            or geometry.thickness <= 0.0
            or not math.isclose(
                math.hypot(*geometry.axis),
                1.0,
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
            or not math.isclose(
                math.hypot(*geometry.normal),
                1.0,
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
            or abs(
                geometry.axis[0] * geometry.normal[0]
                + geometry.axis[1] * geometry.normal[1]
            ) > 1e-9
        ):
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                OPENING_HOST_FRAME_GEOMETRY_INVALID,
            )

        frame = self._shared_host_frame(binding=binding, geometry=geometry)
        if frame is None:
            return _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                OPENING_HOST_FRAME_WHOLE_WALL_UNPROVEN,
                OPENING_HOST_FRAME_WALL_UNAVAILABLE,
            )

        selector = OpeningHostFrameSelector(
            document_id=binding.document_id,
            revision_id=binding.revision_id,
            source_sha256=binding.source_sha256,
            snapshot_id=binding.snapshot_id,
            page_id=binding.page_id,
            decision_scope_id=binding.decision_scope_id,
            opening_identity_id=binding.opening_identity_id,
        )
        payload = {
            "selector": selector.key,
            "host_binding_record_id": binding.record_id,
            "host_wall_id": binding.host_wall_id,
            "whole_wall_frame_id": frame.frame_id,
            "whole_wall_candidate_ids": frame.candidate_ids,
            "source_observation_ids": frame.source_observation_ids,
            "origin_pt": tuple(round(float(value), 9) for value in frame.origin),
            "axis_unit": tuple(round(float(value), 12) for value in frame.axis),
            "normal_unit": tuple(round(float(value), 12) for value in frame.normal),
            "u0_pt": round(float(frame.u0), 9),
            "u1_pt": round(float(frame.u1), 9),
            "wall_thickness_pt": round(float(frame.wall_thickness), 9),
            "coordinate_unit": "pdf_point",
        }
        evidence = OpeningHostFrameEvidence(
            selector=selector,
            record_id=stable_contract_id("opening_host_frame_v2", payload, digest_chars=32),
            opening_identity_id=binding.opening_identity_id,
            host_binding_record_id=binding.record_id,
            host_wall_id=binding.host_wall_id,
            whole_wall_frame_id=frame.frame_id,
            whole_wall_candidate_ids=frame.candidate_ids,
            source_observation_ids=frame.source_observation_ids,
            origin_pt=(float(frame.origin[0]), float(frame.origin[1])),
            axis_unit=(float(frame.axis[0]), float(frame.axis[1])),
            normal_unit=(float(frame.normal[0]), float(frame.normal[1])),
            u0_pt=float(frame.u0),
            u1_pt=float(frame.u1),
            wall_thickness_pt=float(frame.wall_thickness),
        )
        result = OpeningHostFrameResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(OPENING_HOST_FRAME_RESOLVED,),
            evidence=evidence,
        )
        existing = self._results.get(selector.key)
        if existing is not None and existing != result:
            raise RuntimeError("opening host-frame producer equivocation")
        self._results[selector.key] = result
        return result

    def authority(self) -> OpeningHostFrameAuthority:
        return OpeningHostFrameAuthority(
            MappingProxyType(dict(self._results)),
            _seal=_AUTHORITY_SEAL,
        )


__all__ = [
    "OPENING_HOST_FRAME_GEOMETRY_INVALID",
    "OPENING_HOST_FRAME_GEOMETRY_UNAVAILABLE",
    "OPENING_HOST_FRAME_HOST_UNAVAILABLE",
    "OPENING_HOST_FRAME_OPENING_UNAVAILABLE",
    "OPENING_HOST_FRAME_RESOLVED",
    "OPENING_HOST_FRAME_SCHEMA_VERSION",
    "OPENING_HOST_FRAME_SCOPE_MISMATCH",
    "OPENING_HOST_FRAME_WALL_UNAVAILABLE",
    "OPENING_HOST_FRAME_WHOLE_WALL_UNPROVEN",
    "OpeningHostFrameAuthority",
    "OpeningHostFrameEvidence",
    "OpeningHostFrameProducer",
    "OpeningHostFrameResult",
    "OpeningHostFrameSelector",
]
