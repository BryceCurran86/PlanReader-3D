"""Read-only first-failure audit for original source split-label grid rooms.

Calls existing production source wall, room face, and split-label authorities;
never creates room geometry, changes candidate truth, or issues quantities.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
import math
from typing import Any
from shapely.geometry import Polygon
from shapely.ops import unary_union

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_composite_room_face_authority import (
    _fully_grid_opposed_wall_evidence,
    _grid_local_adjacency,
    _grid_connected_component,
    _component_has_conflicting_label,
    _candidate_record,
    _atomic_source_wall_edge_counts,
    _edge_key,
    _wall_edge_ids,
    SOURCE_LINEAGE_GRID_REASON,
)
from pb_wall_room_topology_typed_negative_evidence import (
    KIND_GRID, POLARITY_OPPOSING,
)
from pb_physical_wall_candidate_authority import PhysicalWallCandidateScopeResult
from pb_source_room_face_authority import SourceRoomFaceScopeResult
from pb_source_room_label_authority import SourceRoomLabelScopeResult


def _internal_grid_source_evidence_present(internal, by_wall) -> bool:
    """Mirror production: union of all exact W4 GRID receipt sets is nonempty."""
    return any(
        by_wall.get(wall_id, ())
        for wall_id, _edge in internal
    )


def _physical_union_first_unclosed_gate(
    component: tuple[str, ...],
    *,
    room_scope: SourceRoomFaceScopeResult,
    fully_grid_wall_ids: set[str],
    grid_evidence: Any,
    local_counts: Any,
) -> dict[str, Any]:
    """Read-only mirror of existing production source-boundary checks.

    No geometry is returned or published; no labels, missing source walls,
    dimension values, physical equivalences or material semantics inferred.
    """
    result = {
        "physical_union_first_unclosed_gate": "source_boundary_unverified",
        "physical_union_candidate_source_face_count": len(component),
        "physical_union_merged_geometry_type_observed_only": None,
        "physical_union_external_grid_edge_count": 0,
        "physical_union_external_grid_w4_ids_diagnostic_only": [],
        "physical_union_external_grid_atomic_subedges_diagnostic_only": [],
        "physical_union_internal_separator_edge_count": 0,
        "invalid_constituent_source_face_receipts_diagnostic_only": [],
        "first_invalid_internal_wall_receipt_diagnostic_only": None,
        "new_room_geometry_published": False,
        "new_metric_area_published": False,
    }
    # Never let a dict overwrite competing physical face or producer receipt
    # identities. This read-only gate must mirror the production fail-closed
    # source identity contract before examining any geometry.
    # A malformed upstream receipt may be an unhashable object. It must not
    # crash a source run or appear as an authentic physical room owner.
    def genuine_id(value):
        return isinstance(value, str) and bool(value) and value == value.strip()

    face_counts = Counter(
        rec.face_id for rec in room_scope.records
        if genuine_id(getattr(rec, "face_id", None))
    )
    receipt_counts = Counter(
        rec.record_id for rec in room_scope.records
        if genuine_id(getattr(rec, "record_id", None))
    )
    records = {
        rec.face_id: rec for rec in room_scope.records
        if genuine_id(getattr(rec, "face_id", None))
    }
    if any(not genuine_id(face_id) or face_id not in records for face_id in component):
        result["physical_union_first_unclosed_gate"] = "source_component_face_missing"
        return result
    if any(
        face_counts[face_id] != 1
        or not genuine_id(getattr(records[face_id], "record_id", None))
        or receipt_counts[records[face_id].record_id] != 1
        for face_id in component
    ):
        result["physical_union_first_unclosed_gate"] = "source_component_face_receipt_conflict"
        return result
    try:
        polygons = [Polygon(records[face_id].polygon_pdf_pts) for face_id in component]
        invalid_faces = [
            (face_id, poly)
            for face_id, poly in zip(component, polygons)
            if poly.is_empty or not poly.is_valid or poly.area <= 0
        ]
        if invalid_faces:
            from shapely.validation import explain_validity
            result["invalid_constituent_source_face_receipts_diagnostic_only"] = [
                {
                    "original_source_face_id": face_id,
                    "original_source_face_record_id": records[face_id].record_id,
                    "native_polygon_validity_failure": (
                        explain_validity(poly)[:180]
                        if not poly.is_valid else
                        "source_polygon_empty_or_nonpositive_area"
                    ),
                    "physical_room_polygon_published": False,
                }
                for face_id, poly in invalid_faces[:16]
            ]
            result["physical_union_invalid_constituent_face_count"] = len(invalid_faces)
            result["physical_union_first_unclosed_gate"] = "source_component_polygon_invalid"
            return result
        merged = unary_union(polygons)
        result["physical_union_merged_geometry_type_observed_only"] = merged.geom_type
        if (
            merged.geom_type != "Polygon" or merged.is_empty or not merged.is_valid
            or merged.area <= 0 or len(tuple(merged.interiors)) != 0
            or abs(sum(p.area for p in polygons) - merged.area)
            > max(1e-6, merged.length * 1e-6)
        ):
            result["physical_union_first_unclosed_gate"] = (
                "source_union_disconnected_overlapping_or_has_holes"
            )
            return result
    except Exception:
        result["physical_union_first_unclosed_gate"] = "source_polygon_union_unavailable"
        return result

    # Producer requires every constituent boundary receipt to be an
    # admissible exact wall subedge. Do not skip bad rows during noding.
    for face_id in component:
        for item in tuple(getattr(records[face_id], "boundary_wall_edges", ()) or ()):
            try:
                wall_id = item[0]
                edge = _edge_key(item[1])
            except (IndexError, TypeError, ValueError, OverflowError):
                edge = None
                wall_id = None
            if (
                not isinstance(wall_id, str) or not wall_id
                or wall_id != wall_id.strip() or edge is None
            ):
                result["physical_union_first_unclosed_gate"] = "source_boundary_receipt_invalid"
                return result

    local = local_counts
    if local is None:
        local = _atomic_source_wall_edge_counts(room_scope, fully_grid_wall_ids)
    owners = {
        key: tuple(sorted(counts))
        for key, counts in local.items()
        if all(value == 1 for value in counts.values())
    }
    component_set = set(component)
    totals = {
        key: sum(n for face, n in face_counts.items() if face in component_set)
        for key, face_counts in local.items()
    }
    totals = {key: n for key, n in totals.items() if n > 0}
    if not totals or any(n > 2 for n in totals.values()):
        result["physical_union_first_unclosed_gate"] = "source_atomic_wall_edge_multiplicity_invalid"
        return result

    internal, external = set(), set()
    for key, count in totals.items():
        wall_id, _edge = key
        global_owners = owners.get(key, ())
        if count == 2:
            if (
                wall_id not in fully_grid_wall_ids or len(global_owners) != 2
                or not set(global_owners).issubset(component_set)
            ):
                # Preserve actual atomic W4 source wall and its *global*
                # source face owners. This tells the upstream wall/face agent
                # which witness is missing, without inferring equivalence.
                result["first_invalid_internal_wall_receipt_diagnostic_only"] = {
                    "original_w4_wall_id": wall_id,
                    "original_atomic_wall_edge_pdf_pts": [
                        list(point) for point in _edge
                    ],
                    "original_global_source_face_ids": list(global_owners),
                    "source_component_face_ids": sorted(
                        component_set.intersection(global_owners)
                    ),
                    "grid_opposed_source_wall_authenticated": (
                        wall_id in fully_grid_wall_ids
                    ),
                    "no_wall_or_room_equivalence_inferred": True,
                }
                result["physical_union_first_unclosed_gate"] = (
                    "source_internal_wall_edge_not_two_sided_grid_owned"
                )
                return result
            internal.add(key)
        elif count == 1:
            external.add(key)
        else:
            result["physical_union_first_unclosed_gate"] = (
                "source_atomic_wall_edge_multiplicity_invalid"
            )
            return result
    result["physical_union_internal_separator_edge_count"] = len(internal)
    external_grid_ids=sorted({
        wall_id for wall_id, edge in external if wall_id in fully_grid_wall_ids
    })
    result["physical_union_external_grid_edge_count"] = sum(
        wall_id in fully_grid_wall_ids for wall_id, edge in external
    )
    # Record actual W4 source identities needed by the upstream wall agent;
    # they remain unowned/diagnostic and are not used as a geometry repair.
    result["physical_union_external_grid_w4_ids_diagnostic_only"] = external_grid_ids[:24]
    result["physical_union_external_grid_w4_id_count"] = len(external_grid_ids)
    # Preserve the exact *original* source W4 atomic edge and producer face
    # owner receipt behind each external GRID boundary. A W4 ID alone hides
    # which part of a long grid wall remains unclosed. These identities are
    # diagnostic only: no adjacency, wall equivalence or geometry is invented.
    grid_external_edges = sorted(
        (wall_id, edge) for wall_id, edge in external
        if wall_id in fully_grid_wall_ids
    )
    result["physical_union_external_grid_atomic_subedges_diagnostic_only"] = [
        {
            "original_w4_wall_id": wall_id,
            "original_atomic_wall_edge_pdf_pts": [list(pt) for pt in edge],
            "source_component_face_ids": sorted(
                face_id for face_id, count
                in local.get((wall_id, edge), {}).items()
                if face_id in component_set and count == 1
            ),
            "original_global_source_face_ids": list(
                owners.get((wall_id, edge), ())
            ),
            "source_edge_used_to_mint_physical_room": False,
            "new_wall_or_room_equivalence_inferred": False,
        }
        for wall_id, edge in grid_external_edges[:48]
    ]
    if not internal or not external:
        result["physical_union_first_unclosed_gate"] = (
            "source_internal_or_external_boundary_not_complete"
        )
    elif result["physical_union_external_grid_edge_count"]:
        result["physical_union_first_unclosed_gate"] = (
            "source_external_grid_owned_subedge_room_incomplete"
        )
    elif not _internal_grid_source_evidence_present(internal, grid_evidence):
        # Production collects the union of source GRID evidence receipts
        # over *all* internal separator walls, then requires that union
        # to be non-empty. Do not introduce a stricter diagnostic rule.
        result["physical_union_first_unclosed_gate"] = (
            "source_grid_separator_receipt_unavailable"
        )
    else:
        result["physical_union_first_unclosed_gate"] = (
            "source_boundary_gates_passed_candidate_only"
        )
    return result


def diagnose_original_w4_address_collisions(records):
    """Read-only unmerged source records behind colliding native W4 addresses.

    No geometry identity, physical equivalence, wall host or room closure is
    inferred. Each original record stays individually visible even when its
    candidate address was reused by the producer.
    """
    def exact(value):
        return isinstance(value, str) and bool(value) and value == value.strip()
    source = tuple(records)
    counts = Counter(
        rec.wall_candidate_id for rec in source
        if exact(getattr(rec, "wall_candidate_id", None))
    )
    collisions = {key for key, count in counts.items() if count > 1}
    evidence = []
    for index, record in enumerate(source):
        native_id = getattr(record, "wall_candidate_id", None)
        if not exact(native_id) or native_id not in collisions:
            continue
        candidate = getattr(record, "wall_candidate", None)
        points = getattr(candidate, "centerline_pts", ()) or ()
        if not isinstance(points, (tuple, list)):
            points = ()
        source_points = []
        for p in points:
            try:
                pair = tuple(float(v) for v in p)
            except (ValueError, TypeError, OverflowError):
                continue
            if len(pair) == 2 and all(math.isfinite(v) for v in pair):
                source_points.append(list(pair))
        raw_fragments = getattr(record, "source_edge_fragments", ()) or ()
        valid_fragments = isinstance(raw_fragments, (tuple, list))
        fragments = tuple(raw_fragments) if valid_fragments else ()
        physical_identity = getattr(record, "physical_identity", None)
        raw_identity_primitives = getattr(
            physical_identity, "source_primitive_ids", ()
        ) or ()
        identity_primitives_valid = isinstance(
            raw_identity_primitives, (tuple, list)
        ) and all(exact(value) for value in raw_identity_primitives)
        identity_primitives = (
            tuple(raw_identity_primitives) if identity_primitives_valid else ()
        )
        raw_identity_edges = getattr(physical_identity, "edge_ids", ()) or ()
        identity_edges_valid = isinstance(
            raw_identity_edges, (tuple, list)
        ) and all(exact(value) for value in raw_identity_edges)
        identity_edges = tuple(raw_identity_edges) if identity_edges_valid else ()
        fragment_receipts_complete = bool(fragments) and valid_fragments and all(
            exact(getattr(fragment, "edge_id", None))
            and isinstance(getattr(fragment, "source_primitive_ids", None), (tuple, list))
            and bool(fragment.source_primitive_ids)
            and all(
                exact(value) for value in fragment.source_primitive_ids
            )
            for fragment in fragments
        )
        evidence.append({
            "source_record_ordinal": index,
            "original_wall_candidate_id": native_id,
            "original_centerline_points_diagnostic_only": source_points[:16],
            "original_centerline_point_count": len(source_points),
            "source_edge_fragment_count": len(fragments),
            "source_fragment_receipts_complete": fragment_receipts_complete,
            "original_fragment_primitives_owned_by_shadow_identity": (
                fragment_receipts_complete
                and identity_primitives_valid
                and bool(identity_primitives)
                and all(
                    set(fragment.source_primitive_ids).issubset(identity_primitives)
                    for fragment in fragments
                )
            ),
            # W2 edge membership is a distinct physical ancestry test from
            # native source-primitive membership. Neither establishes
            # equivalence, but missing either must be visible as a negative
            # source diagnostic instead of silently trusting a shadow W4 ID.
            "original_fragment_edges_owned_by_shadow_identity": (
                fragment_receipts_complete
                and identity_edges_valid
                and bool(identity_edges)
                and all(fragment.edge_id in identity_edges for fragment in fragments)
            ),
            "shadow_source_geometry_and_lineage_usable_diagnostic_only": (
                bool(source_points)
                and fragment_receipts_complete
                and identity_primitives_valid
                and bool(identity_primitives)
                and identity_edges_valid
                and bool(identity_edges)
                and all(
                    set(fragment.source_primitive_ids).issubset(identity_primitives)
                    and fragment.edge_id in identity_edges
                    for fragment in fragments
                )
                and getattr(getattr(physical_identity, "status", None), "value", None)
                    == "corroborated"
            ),
            "source_fragment_edge_ids_sample": [
                frag.edge_id for frag in fragments[:8]
                if exact(getattr(frag, "edge_id", None))
            ],
            "source_fragment_primitive_ids_sample": [
                list(getattr(frag, "source_primitive_ids", ())[:16])
                for frag in fragments[:8]
                if isinstance(getattr(frag, "source_primitive_ids", None), (tuple, list))
            ],
            # An original W4 physical candidate ID is only a producer shadow
            # identifier, not same-wall proof. Keep its independent W2 lineage
            # separate from candidate-adjacent source fragment evidence.
            "shadow_physical_candidate_identity_id": (
                getattr(physical_identity, "candidate_identity_id", None)
            ),
            "shadow_physical_identity_status": (
                getattr(getattr(physical_identity, "status", None), "value", None)
            ),
            "shadow_identity_source_primitive_id_count": len(identity_primitives),
            "shadow_identity_source_primitive_ids_sample": list(identity_primitives[:16]),
            "shadow_identity_edge_ids_sample": list(identity_edges[:16]),
            "shadow_identity_lineage_valid": (
                physical_identity is not None
                and identity_primitives_valid and bool(identity_primitives)
                and identity_edges_valid and bool(identity_edges)
                and exact(getattr(physical_identity, "candidate_identity_id", None))
            ),
            "physical_wall_equivalence_proven": False,
            "source_room_boundary_published": False,
        })
    return {
        "colliding_original_w4_ids": sorted(collisions),
        "individual_original_record_count": len(evidence),
        "original_collision_records_diagnostic_only": evidence,
        "physical_wall_equivalence_proven": False,
    }


def _competing_original_label_receipts(component, candidate, label_scope):
    """Source-face overlap only, never label-string similarity or room union."""
    owned=set(component)
    direct=[]
    for record in tuple(getattr(label_scope,"records",()) or ()):
        face=getattr(record,"face_id",None)
        if isinstance(face,str) and face in owned:
            direct.append({
                "producer_receipt_id":getattr(record,"record_id",None),
                "native_room_label":getattr(record,"label",None),
                "competing_source_face_ids":[face],
                "source_direct_room_label_record_only":True,
            })
    splits=[]
    for record in tuple(getattr(label_scope,"split_face_candidates",()) or ()):
        if record is candidate:
            continue
        raw=getattr(record,"word_face_ids",()) or ()
        if not isinstance(raw,(tuple,list)):
            continue
        overlap=sorted({face for face in raw if isinstance(face,str) and face in owned})
        if overlap:
            splits.append({
                "producer_receipt_id":getattr(record,"record_id",None),
                "native_room_label":getattr(record,"label",None),
                "competing_source_face_ids":overlap,
                "source_direct_room_label_record_only":False,
            })
    return sorted(direct+splits,key=lambda row:(
        str(row["producer_receipt_id"]),str(row["native_room_label"])
    ))



def _original_w2_shadow_and_native_source_crosscheck(
    wall_scope: PhysicalWallCandidateScopeResult,
    record: Any,
    fragment: Any,
) -> dict[str, Any]:
    """Cross-check exact existing W2/W4/native receipts, never physical GRID role.

    An observed common source primitive ID is NOT an original source-parent
    membership proof. W4's identity and source-metadata descriptor are shadow
    artifacts, so even agreement across both is merely a diagnostic receipt,
    never KIND_GRID opposition, wall equivalence or a source-room boundary.
    """
    result = {
        "original_w2_w4_native_lineage_first_gate_diagnostic_only":
            "source_fragment_receipt_unavailable",
        "original_w2_w4_native_lineage_crosschecked_diagnostic_only": False,
        "source_grid_or_wall_role_authenticated_by_crosscheck": False,
    }

    def ids(value: Any) -> tuple[str, ...] | None:
        if not isinstance(value, (tuple, list)) or not value:
            return None
        if any(
            not isinstance(item, str) or not item or item != item.strip()
            for item in value
        ):
            return None
        return tuple(value)

    edge_id = getattr(fragment, "edge_id", None)
    source_ids = ids(getattr(fragment, "source_primitive_ids", None))
    if (
        not isinstance(edge_id, str) or not edge_id
        or edge_id != edge_id.strip() or source_ids is None
    ):
        return result

    identity = getattr(record, "physical_identity", None)
    native_edges = ids(getattr(identity, "edge_ids", None))
    native_sources = ids(getattr(identity, "source_primitive_ids", None))
    if (
        getattr(getattr(identity, "status", None), "value", None)
        != "corroborated"
        or native_edges is None or native_sources is None
    ):
        result["original_w2_w4_native_lineage_first_gate_diagnostic_only"] = (
            "w4_shadow_identity_unavailable"
        )
        return result
    if edge_id not in native_edges:
        result["original_w2_w4_native_lineage_first_gate_diagnostic_only"] = (
            "w2_edge_absent_from_w4_shadow_identity"
        )
        return result
    if not set(source_ids).issubset(native_sources):
        result["original_w2_w4_native_lineage_first_gate_diagnostic_only"] = (
            "source_primitive_absent_from_w4_shadow_identity"
        )
        return result

    table = getattr(wall_scope, "source_metadata_table", None)
    if (
        getattr(table, "status", None) != "described"
        or getattr(table, "page_id", None) != wall_scope.page_id
        or getattr(table, "decision_scope_id", None)
            != wall_scope.decision_scope_id
        or not isinstance(getattr(table, "descriptors", None), (tuple, list))
    ):
        result["original_w2_w4_native_lineage_first_gate_diagnostic_only"] = (
            "original_native_scope_metadata_unavailable"
        )
        return result
    original_id = getattr(record, "wall_candidate_id", None)
    descriptors = [
        row for row in table.descriptors
        if getattr(row, "wall_candidate_id", None) == original_id
    ]
    if len(descriptors) != 1:
        result["original_w2_w4_native_lineage_first_gate_diagnostic_only"] = (
            "original_native_w4_descriptor_not_unique"
        )
        return result
    descriptor = descriptors[0]
    matched = ids(getattr(descriptor, "matched_source_primitive_ids", None))
    declared = ids(getattr(descriptor, "source_primitive_ids", None))
    missing = getattr(descriptor, "missing_source_primitive_ids", None)
    if (
        matched is None or declared is None
        or not isinstance(missing, (tuple, list))
        or any(not isinstance(item, str) for item in missing)
        or tuple(sorted(set(declared))) != tuple(sorted(set(native_sources)))
        or not set(source_ids).issubset(matched)
        or any(item in missing for item in source_ids)
    ):
        result["original_w2_w4_native_lineage_first_gate_diagnostic_only"] = (
            "original_native_source_receipt_unavailable_or_conflicting"
        )
        return result
    result["original_w2_w4_native_lineage_first_gate_diagnostic_only"] = (
        "w2_w4_shadow_and_native_receipts_agree_role_still_unproven"
    )
    result["original_w2_w4_native_lineage_crosschecked_diagnostic_only"] = True
    return result


def _original_w4_native_graphic_state_first_gate(
    wall_scope: PhysicalWallCandidateScopeResult,
    record: Any,
) -> dict[str, Any]:
    """Read W4-aggregate original producer graphic-state, no per-line role.

    A joined W4 descriptor can contain multiple source primitives. Its graphic
    state is NOT per-W2 GRID opposition, exact source role or room authority.
    """
    out = {
        "first_native_graphic_state_gate_diagnostic_only":
            "original_w4_native_metadata_unavailable",
        "graphic_state_applies_to_w4_source_set_not_individual_w2": True,
        "original_w4_native_widths_pt": [],
        "original_w4_native_width_rank_ascending": [],
        "original_w4_native_stroke_values": [],
        "original_w4_native_layer_values": [],
        "original_w4_native_wall_named_layer_values": [],
        "original_w4_native_fill_values": [],
        "original_w4_native_dash_values": [],
        "original_w4_native_source_record_count": 0,
        "original_w4_graphic_state_proves_grid_role": False,
    }
    table = getattr(wall_scope, "source_metadata_table", None)
    if (
        getattr(table, "status", None) != "described"
        or getattr(table, "page_id", None) != wall_scope.page_id
        or getattr(table, "decision_scope_id", None)
            != wall_scope.decision_scope_id
        or not isinstance(getattr(table, "descriptors", None), (tuple, list))
    ):
        return out
    wall_id = getattr(record, "wall_candidate_id", None)
    matching = tuple(
        desc for desc in table.descriptors
        if getattr(desc, "wall_candidate_id", None) == wall_id
    )
    if len(matching) != 1:
        out["first_native_graphic_state_gate_diagnostic_only"] = (
            "original_w4_native_descriptor_not_unique"
        )
        return out
    native = matching[0]
    candidate_ids = getattr(native, "matched_source_primitive_ids", None)
    shadow_ids = getattr(
        getattr(record, "physical_identity", None),
        "source_primitive_ids", None
    )
    if (
        not isinstance(candidate_ids, (tuple, list)) or not candidate_ids
        or not isinstance(shadow_ids, (tuple, list)) or not shadow_ids
        or not all(isinstance(v, str) and v for v in (*candidate_ids, *shadow_ids))
        or not set(shadow_ids).issubset(candidate_ids)
    ):
        out["first_native_graphic_state_gate_diagnostic_only"] = (
            "original_w4_native_primitive_membership_unavailable"
        )
        return out
    def values(name: str) -> list[Any]:
        raw = getattr(native, name, ()) or ()
        if not isinstance(raw, (tuple, list)):
            return []
        return [item for item in raw][:24]
    out.update({
        "first_native_graphic_state_gate_diagnostic_only":
            "original_w4_native_graphic_state_observed_role_unproven",
        "original_w4_native_widths_pt": values("width_values_pt"),
        "original_w4_native_width_rank_ascending": [
            getattr(item, "rank_ascending", None)
            for item in values("drawing_relative_width_ranks")
        ],
        "original_w4_native_stroke_values": values("stroke_values"),
        "original_w4_native_layer_values": values("layer_values"),
        "original_w4_native_wall_named_layer_values": values("wall_named_layer_values"),
        "original_w4_native_fill_values": values("fill_values"),
        "original_w4_native_dash_values": values("dashes_values"),
        "original_w4_native_source_record_count":
            getattr(native, "source_record_count", 0),
    })
    return out


def inspect_original_w4_grid_opposition_first_gate(
    wall_scope: PhysicalWallCandidateScopeResult,
    original_w4_wall_id: str,
) -> dict[str, Any]:
    """Read actual original W2 opposing receipts for one W4; never mint a wall.

    A source W4 may have one positive W2 GRID semantic receipt for some edge
    fragments yet remain a physical separator where ANY original W2 edge is
    missing that authority. Never assume all edges from one textual GRID note.
    """
    output = {
        "original_w4_wall_id": original_w4_wall_id,
        "original_w4_source_candidate_count": 0,
        "original_w2_edge_ids_diagnostic_only": [],
        "source_grid_opposed_w2_edge_ids_diagnostic_only": [],
        "missing_original_grid_opposed_w2_edge_ids_diagnostic_only": [],
        "original_w2_fragment_source_receipts_diagnostic_only": [],
        "original_w4_grid_first_gate": "source_w4_identity_unavailable",
        "original_w4_grid_opposition_published": False,
        "physical_wall_equivalence_proven": False,
        "room_geometry_published": False,
    }
    if (
        not isinstance(original_w4_wall_id, str)
        or not original_w4_wall_id
        or original_w4_wall_id != original_w4_wall_id.strip()
    ):
        return output
    records = [
        rec for rec in tuple(getattr(wall_scope, "records", ()) or ())
        if getattr(rec, "wall_candidate_id", None) == original_w4_wall_id
    ]
    output["original_w4_source_candidate_count"] = len(records)
    if len(records) != 1:
        output["original_w4_grid_first_gate"] = (
            "source_w4_identity_collision" if records else "source_w4_identity_unavailable"
        )
        return output
    record = records[0]
    output["original_w4_native_graphic_state_diagnostic_only"] = (
        _original_w4_native_graphic_state_first_gate(wall_scope, record)
    )
    wall = getattr(record, "wall_candidate", None)
    # The production helper stringifies W2 keys for backward compatibility.
    # A diagnostic claiming *original native* W2 identities must inspect the
    # untouched typed source fields BEFORE any string coercion.
    raw_a = getattr(wall, "face_a_segment_ids", None)
    raw_b = getattr(wall, "face_b_segment_ids", None)
    if not isinstance(raw_a, (tuple, list)) or (
        raw_b is not None and not isinstance(raw_b, (tuple, list))
    ):
        output["original_w4_grid_first_gate"] = "source_w2_fragment_identity_unavailable"
        return output
    raw_edges = (*raw_a, *(raw_b or ()))
    if (
        not raw_edges
        or any(
            not isinstance(edge, str) or not edge
            or edge != edge.strip()
            for edge in raw_edges
        )
    ):
        output["original_w4_grid_first_gate"] = "source_w2_fragment_identity_unavailable"
        return output
    edges = tuple(sorted(set(raw_edges)))
    output["original_w2_edge_ids_diagnostic_only"] = list(edges)
    opposition: dict[str, set[str]] = {edge: set() for edge in edges}
    for atom in tuple(getattr(wall_scope, "typed_semantic_evidence_atoms", ()) or ()):
        meta = getattr(atom, "metadata", None)
        if not isinstance(meta, Mapping):
            continue
        edge = meta.get("target_edge_id")
        atom_id = getattr(atom, "evidence_id", None)
        if (
            getattr(atom, "kind", None) != KIND_GRID
            or getattr(atom, "status", None) is not EvidenceResolutionStatus.CANDIDATE
            or meta.get("polarity") != POLARITY_OPPOSING
            or SOURCE_LINEAGE_GRID_REASON
                not in tuple(getattr(atom, "reason_codes", ()) or ())
            or not isinstance(edge, str) or edge not in opposition
            or not isinstance(atom_id, str) or not atom_id
            or atom_id != atom_id.strip()
        ):
            continue
        opposition[edge].add(atom_id)
    supported = [edge for edge in edges if opposition[edge]]
    missing = [edge for edge in edges if not opposition[edge]]
    output["source_grid_opposed_w2_edge_ids_diagnostic_only"] = supported
    output["missing_original_grid_opposed_w2_edge_ids_diagnostic_only"] = missing
    output["original_w2_grid_opposition_evidence_receipts_diagnostic_only"] = {
        edge: sorted(ids) for edge, ids in opposition.items() if ids
    }
    for frag in tuple(getattr(record, "source_edge_fragments", ()) or ()):
        edge = getattr(frag, "edge_id", None)
        if edge not in edges:
            continue
        raw_sources = getattr(frag, "source_primitive_ids", ()) or ()
        parents = (
            list(raw_sources)
            if isinstance(raw_sources, (tuple, list))
            and all(isinstance(v, str) and v and v == v.strip() for v in raw_sources)
            else []
        )
        output["original_w2_fragment_source_receipts_diagnostic_only"].append({
            "original_w2_edge_id": edge,
            "native_source_primitive_ids": parents[:32],
            "source_parent_receipts_typed": bool(parents),
            "source_parent_membership_proven": False,
            "source_physical_role_inferred": False,
            **_original_w2_shadow_and_native_source_crosscheck(
                wall_scope, record, frag
            ),
        })
    if missing:
        output["original_w4_grid_first_gate"] = "source_w2_grid_opposition_missing"
    else:
        output["original_w4_grid_first_gate"] = (
            "source_w2_grid_opposition_observed_not_physical_equivalence"
        )
    return output


def inspect_external_atomic_grid_w2_source_fragments(
    wall_scope: PhysicalWallCandidateScopeResult,
    physical_union_first_gate: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Audit original W2 source fragments beneath singly owned GRID subedges.

    Geometry is checked only with the source-face producer's quantized exact
    containment contract. A source fragment says NOTHING about second-side
    physical face ownership, true GRID role or completed room geometry.
    """
    from pb_source_room_face_authority import (
        _edge_contains_edge,
        _collinear_overlap_edge,
    )

    original_rows = physical_union_first_gate.get(
        "physical_union_external_grid_atomic_subedges_diagnostic_only", ()
    )
    if not isinstance(original_rows, (tuple, list)):
        return []
    counts: Counter[str] = Counter()
    records_by_id: dict[str, Any] = {}
    for record in tuple(getattr(wall_scope, "records", ()) or ()):
        wall_id = getattr(record, "wall_candidate_id", None)
        if isinstance(wall_id, str) and wall_id and wall_id == wall_id.strip():
            counts[wall_id] += 1
            records_by_id[wall_id] = record

    output: list[dict[str, Any]] = []
    for source in original_rows[:48]:
        if not isinstance(source, Mapping):
            continue
        wall_id = source.get("original_w4_wall_id")
        raw = source.get("original_atomic_wall_edge_pdf_pts")
        atomic = _edge_key(raw)
        if (
            not isinstance(wall_id, str) or not wall_id
            or wall_id != wall_id.strip() or atomic is None
        ):
            continue
        row = {
            "original_w4_wall_id": wall_id,
            "original_atomic_wall_edge_pdf_pts": [list(pt) for pt in atomic],
            "original_global_source_face_ids_diagnostic_only": list(
                source.get("original_global_source_face_ids") or ()
            ),
            "original_w4_candidate_record_count": counts[wall_id],
            "source_w2_fragment_candidates_diagnostic_only": [],
            "source_w2_partial_overlap_candidates_diagnostic_only": [],
            "source_w2_partial_overlap_proves_second_face": False,
            "source_first_unclosed_gate":
                "original_w4_source_identity_unavailable",
            "source_second_face_owner_authenticated": False,
            "source_w2_grid_role_authenticated_by_this_diagnostic": False,
            "source_room_geometry_or_area_published": False,
        }
        if counts[wall_id] != 1:
            row["source_first_unclosed_gate"] = (
                "original_w4_identity_collision" if counts[wall_id]
                else "original_w4_source_identity_unavailable"
            )
            output.append(row)
            continue
        record = records_by_id[wall_id]
        candidates: list[dict[str, Any]] = []
        overlapping: list[dict[str, Any]] = []
        invalid_receipts = False
        for fragment in tuple(
            getattr(record, "source_edge_fragments", ()) or ()
        ):
            native_edge_id = getattr(fragment, "edge_id", None)
            source_ids = getattr(fragment, "source_primitive_ids", None)
            if (
                not isinstance(native_edge_id, str) or not native_edge_id
                or native_edge_id != native_edge_id.strip()
                or not isinstance(source_ids, (tuple, list)) or not source_ids
                or any(not isinstance(v, str) or not v or v != v.strip()
                        for v in source_ids)
            ):
                invalid_receipts = True
                continue
            native_geom = getattr(fragment, "geometry", None)
            try:
                contains = _edge_contains_edge(native_geom, atomic)
            except (TypeError, ValueError, OverflowError, IndexError):
                contains = False
            if contains:
                candidates.append({
                    "original_w2_edge_id": native_edge_id,
                    "native_source_primitive_ids": sorted(set(source_ids))[:24],
                    "exact_source_quantized_collinearity_only": True,
                    "second_face_owner_proven": False,
                })
            else:
                # Exact positive source overlap is weaker than FULL original
                # fragment containment and proves no extra face or wall role.
                # This diagnoses upstream W2 atom noding/locality failures
                # without changing physical union or first admissibility gates.
                try:
                    overlap = _collinear_overlap_edge(native_geom, atomic)
                except (TypeError, ValueError, OverflowError, IndexError):
                    overlap = None
                if overlap is not None:
                    overlapping.append({
                        "original_w2_edge_id": native_edge_id,
                        "native_source_primitive_ids": sorted(set(source_ids))[:24],
                        "original_source_overlap_edge_pdf_pts": [
                            list(point) for point in overlap
                        ],
                        "full_original_atomic_wall_edge_contained": False,
                        "source_second_face_owner_authenticated": False,
                        "source_grid_or_wall_role_authenticated": False,
                    })
        candidates.sort(key=lambda item: (
            item["original_w2_edge_id"], item["native_source_primitive_ids"]
        ))
        overlapping.sort(key=lambda item: (
            item["original_w2_edge_id"],
            item["original_source_overlap_edge_pdf_pts"],
        ))
        row["source_w2_fragment_candidates_diagnostic_only"] = candidates[:24]
        row["source_w2_partial_overlap_candidates_diagnostic_only"] = (
            overlapping[:24]
        )
        if invalid_receipts:
            row["source_first_unclosed_gate"] = (
                "original_w2_fragment_source_receipt_invalid"
            )
        elif len(candidates) == 1:
            row["source_first_unclosed_gate"] = (
                "original_w2_fragment_observed_second_face_missing"
            )
        elif not candidates:
            row["source_first_unclosed_gate"] = (
                "original_atomic_wall_subedge_w2_fragment_unavailable"
            )
        else:
            row["source_first_unclosed_gate"] = (
                "original_atomic_wall_subedge_multiple_w2_fragments"
            )
        output.append(row)
    return output


def inspect_split_grid_component_first_failure(
    candidate: Any,
    *,
    wall_scope: PhysicalWallCandidateScopeResult,
    room_scope: SourceRoomFaceScopeResult,
    label_scope: SourceRoomLabelScopeResult,
    grid_walls: set[str] | None = None,
    grid_evidence: Any = None,
    grid_adjacency: Any = None,
    local_counts: Any = None,
) -> dict[str, Any]:
    """Diagnose first missing production authority; do not promote candidates."""
    raw_seeds = getattr(candidate, "word_face_ids", ()) or ()
    seeds = tuple(raw_seeds) if isinstance(raw_seeds, (tuple, list)) else ()
    output = {
        "source_split_candidate_record_id": getattr(candidate, "record_id", None),
        "native_room_label": getattr(candidate, "label", None),
        "native_word_face_ids": list(seeds),
        "first_unclosed_gate": "source_producer_inputs_unverified",
        "connected_component_source_face_ids_diagnostic_only": [],
        "source_room_composite_published_by_diagnostic": False,
        "source_room_metric_area_published": False,
        "new_room_label_owned": False,
    }
    if (
        type(wall_scope) is not PhysicalWallCandidateScopeResult
        or type(room_scope) is not SourceRoomFaceScopeResult
        or type(label_scope) is not SourceRoomLabelScopeResult
        or wall_scope.status is not EvidenceResolutionStatus.CORROBORATED
        or room_scope.status is not EvidenceResolutionStatus.CORROBORATED
        or room_scope.scope_complete is not True
    ):
        return output
    lineage_fields = (
        "document_id", "revision_id", "source_sha256",
        "snapshot_id", "page_id", "decision_scope_id",
    )
    if any(
        getattr(wall_scope, field, None) != getattr(room_scope, field, None)
        or getattr(label_scope, field, None) != getattr(room_scope, field, None)
        or getattr(candidate, field, None) != getattr(room_scope, field, None)
        for field in lineage_fields
    ):
        output["first_unclosed_gate"] = "source_scope_lineage_conflict"
        return output
    if (
        len(seeds) < 2
        or any(
            not isinstance(face, str) or not face or face != face.strip()
            for face in seeds
        )
        or len(set(seeds)) < 2
    ):
        output["first_unclosed_gate"] = "split_source_word_face_identity_unresolved"
        return output

    face_counts = Counter(getattr(face, "face_id", None) for face in room_scope.records)
    record_counts = Counter(getattr(face, "record_id", None) for face in room_scope.records)
    faces = {
        face.face_id: face for face in room_scope.records
        if isinstance(face.face_id, str) and face.face_id
    }
    distinct = tuple(dict.fromkeys(seeds))
    expected = []
    for face_id in distinct:
        row = faces.get(face_id)
        if (
            face_counts[face_id] != 1 or row is None
            or not isinstance(row.record_id, str) or not row.record_id
            or record_counts[row.record_id] != 1
        ):
            output["first_unclosed_gate"] = "split_source_face_or_receipt_ambiguous"
            return output
        expected.append(row.record_id)
    if tuple(getattr(candidate, "source_room_face_record_ids", ()) or ()) != tuple(expected):
        output["first_unclosed_gate"] = "split_label_source_face_receipt_mismatch"
        return output

    # A scoped source run already has these producer-owned grid indexes.
    # Reuse them across candidates instead of rescanning every W4 and
    # source face separately for each native room label.
    if grid_walls is None or grid_evidence is None:
        fully_grid, grid_evidence = _fully_grid_opposed_wall_evidence(wall_scope)
    else:
        fully_grid = grid_walls
    output["fully_grid_opposed_w4_wall_count"] = len(fully_grid)
    if not fully_grid:
        output["first_unclosed_gate"] = "no_producer_authenticated_grid_opposed_w4"
        return output

    adjacency = (
        grid_adjacency if grid_adjacency is not None
        else _grid_local_adjacency(room_scope, fully_grid)
    )
    connected = _grid_connected_component(
        seeds, room_scope=room_scope, fully_grid_wall_ids=fully_grid,
        adjacency=adjacency,
    )
    if connected is None:
        output["first_unclosed_gate"] = "split_words_not_connected_by_exact_grid_owned_edges"
        return output
    output["connected_component_source_face_ids_diagnostic_only"] = list(connected)
    if _component_has_conflicting_label(
        connected, candidate, label_scope=label_scope,
    ):
        output["first_unclosed_gate"] = "grid_connected_component_has_competing_room_label"
        conflicts=_competing_original_label_receipts(
            connected,candidate,label_scope
        )
        output["competing_original_label_receipt_count"]=len(conflicts)
        output["competing_original_label_receipts_diagnostic_only"]=conflicts[:25]
        return output
    selected = _candidate_record(
        candidate, wall_scope=wall_scope, room_scope=room_scope,
        label_scope=label_scope, fully_grid_wall_ids=fully_grid,
        grid_evidence_by_wall=grid_evidence, grid_adjacency=adjacency,
        local_counts=local_counts,
    )
    if selected is None:
        output["physical_union_source_first_failure_diagnostic_only"] = (
            _physical_union_first_unclosed_gate(
                connected, room_scope=room_scope,
                fully_grid_wall_ids=fully_grid, grid_evidence=grid_evidence,
                local_counts=local_counts,
            )
        )
        original_union = output["physical_union_source_first_failure_diagnostic_only"]
        if original_union.get(
            "physical_union_external_grid_atomic_subedges_diagnostic_only"
        ):
            output["original_external_grid_atomic_w2_first_gates_diagnostic_only"] = (
                inspect_external_atomic_grid_w2_source_fragments(
                    wall_scope, original_union
                )
            )
        invalid_wall = original_union.get(
            "first_invalid_internal_wall_receipt_diagnostic_only"
        )
        if invalid_wall and isinstance(invalid_wall.get("original_w4_wall_id"), str):
            output["original_w4_grid_opposition_first_gate_diagnostic_only"] = (
                inspect_original_w4_grid_opposition_first_gate(
                    wall_scope, invalid_wall["original_w4_wall_id"]
                )
            )
        output["first_unclosed_gate"] = (
            "grid_connected_component_physical_boundary_or_union_unproven"
        )
    else:
        # This states only that the EXISTING production function could
        # return a record; the diagnostic never publishes it.
        output["first_unclosed_gate"] = "production_grid_composite_available"
        output["production_composite_record_id_observed_only"] = selected.record_id
    return output
