"""Shadow-only canonical physical wall + room evidence model.

    native PDF primitives
    -> U1 provenance (pb_wall_room_topology_primitive_lineage, merged to main)
    -> W2/W3 topology (pb_wall_room_topology_stage_a / _junction_classifier)
    -> U2 supporting/opposing evidence (pb_wall_room_topology_typed_negative_
       evidence, PR #283, the CANONICAL semantic-evidence contract)
    -> physical wall hypotheses            <-- THIS MODULE
    -> wall-band / wall-axis objects        (WallCandidate, reused unchanged)
    -> enclosed room/space hypotheses       <-- THIS MODULE
    -> later quantity evidence              (NOT built here)

NOT built here: primitive -> BOQ quantity directly, any commercial
publishing, DPC/plaster/paint output, opening deductions, schedule fusion.

Reuses existing contracts rather than inventing new ones:
- ``WallCandidate`` / ``RoomCandidate`` (pb_wall_room_topology_contracts) are
  the existing W1 schema, already carrying every field this phase's brief
  asked for (candidate_id, source segment ids, centerline, thickness,
  end/junction refs, status, supporting/conflicting evidence ids, reason
  codes) -- no parallel wall/room object is created.
- ``EvidenceAtom`` / ``EvidenceResolutionStatus`` / ``stable_contract_id``
  (pb_migration_contracts) are U2's own canonical evidence language, reused
  unchanged. No SemanticClass, no EvidenceStrength, no single-label
  classifier, no Otsu wall classification (all explicitly rejected per the
  U2/#282 architecture reconciliation).
- ``detect_wall_pairs`` (pb_vector_geometry_v130) is reused unmodified for
  the "paired wall faces" evidence family, not reimplemented.

Nothing in this module is imported by ``assemble_wall_candidates``,
``reconstruct_room_candidates``, ``collect_topology_from_segments``, or any
authority/publication path -- this is a pure, additive, read-only enrichment
layer over already-built WallCandidate/RoomCandidate lists, following the
same "return NEW records via dataclasses.replace, never mutate the
originals" convention pb_wall_room_topology_wall_assembly.
rekey_junctions_to_wall_candidates already established.

============================================================
INDEPENDENCE ASSUMPTIONS (read before changing any threshold below)
============================================================

CORROBORATED requires evidence from at least two of the following
INDEPENDENT FAMILIES, each backed by a genuinely different underlying
signal (different data source, different computation), with ZERO opposing
evidence present:

1. ``u2_physical_wall_linework`` -- U2's own per-edge solid-stroke atom
   (pb_wall_room_topology_typed_negative_evidence). Signal source: native
   dash/stroke metadata on the retained edge itself.
2. ``paired_wall_faces`` -- pb_vector_geometry_v130.detect_wall_pairs.
   Signal source: a SEPARATE edge's geometry (parallel line at a plausible
   offset), not this edge's own metadata.
3. ``valid_junction_behavior`` -- at least one of the wall's two end
   junctions is a REAL connection to something else (L_CORNER / T_JUNCTION /
   X_CROSSING / MULTI_WAY / COLLINEAR_CONTINUATION), and neither end is
   AMBIGUOUS / UNRESOLVED / NEAR_JUNCTION_REVIEW / REJECTED_NON_WALL_
   CROSSING. A wall with a bare ENDPOINT at BOTH ends (fully isolated,
   touching nothing else in the drawing) does NOT qualify -- there is no
   junction there to validate, only its absence. Signal source: graph
   topology at the wall's OWN two endpoints, unrelated to any other edge's
   geometry or to this edge's own metadata.
4. ``native_layer_wall_support`` -- any U1 lineage source_record whose
   native ``layer`` string contains "wall" (case-insensitive substring, no
   project-specific keyword list). Signal source: native CAD layer naming,
   unrelated to geometry entirely.

Two families are DELIBERATELY NOT implemented in this pass, with an honest
placeholder reason code rather than a shallow fake integration:
``explicit_figured_dimension`` (would need pb_figured_dimension_evidence /
pb_viewport_dimension_binding wiring) and ``opening_interruption_continuity``
(would need pb_wall_room_topology_opening_host_binding wiring). Both are
future families, not scored here.

EXPLICITLY NOT an independent family, by design, to avoid repeating #273's
circularity:
- ROOM PARTICIPATION is never a wall-evidence input in this module at all.
  Room reconstruction in this module CONSUMES already-resolved wall
  evidence one-directionally (walls -> rooms); nothing here lets a room's
  own existence feed back into corroborating the walls that produced it.
- ONE-HOP CONNECTIVITY (an edge merely touching another edge at a node) is
  not itself a family -- it is already required just to HAVE a
  JunctionCandidate at all; #3 above requires the junction to resolve to a
  specific, unambiguous TYPE, not merely to exist.
- LENGTH ALONE never promotes a candidate. A long chain is not, by itself,
  one of the four families above -- it can only ever gate which edges are
  eligible to be tested for the geometric families that use it (e.g.
  detect_wall_pairs' own 16pt minimum), never count as a family in its own
  right, per the brief's explicit "long continuous wall-band geometry" note
  being informative context rather than an independent proof.
- PAIRED FACES computed from the SAME two edges as another family's input
  are still counted as only one family each (never double-counted): each
  family above is computed once per wall from its own distinct signal
  source, not once per contributing edge -- a wall with three edges all
  showing "valid_junction_behavior" still contributes exactly one
  occurrence of that family, not three.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import EvidenceAtom, EvidenceResolutionStatus, stable_contract_id
from pb_wall_room_topology_contracts import JunctionCandidate, JunctionType, WallCandidate
from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY
from pb_wall_room_topology_room_faces import reconstruct_room_candidates
from pb_wall_room_topology_typed_negative_evidence import GRAPH_ATOMS_KEY

FAMILY_U2_PHYSICAL_WALL_LINEWORK = "u2_physical_wall_linework"
FAMILY_PAIRED_WALL_FACES = "paired_wall_faces"
FAMILY_VALID_JUNCTION_BEHAVIOR = "valid_junction_behavior"
FAMILY_NATIVE_LAYER_WALL_SUPPORT = "native_layer_wall_support"

_METHOD = "canonical_wall_room_evidence_model_shadow"

_INVALID_JUNCTION_TYPES_FOR_ENDPOINTS = frozenset(
    {
        JunctionType.AMBIGUOUS,
        JunctionType.UNRESOLVED,
        JunctionType.NEAR_JUNCTION_REVIEW,
        JunctionType.REJECTED_NON_WALL_CROSSING,
    }
)

REASON_DEFERRED_DIMENSION_EVIDENCE = "future_family_not_implemented:explicit_figured_dimension"
REASON_DEFERRED_OPENING_CONTINUITY = "future_family_not_implemented:opening_interruption_continuity"


def _atom(*, document_id: str, page_id: str, viewport_id: Optional[str], kind: str, wall_id: str, reason_codes: Tuple[str, ...], confidence: float, feature_basis: Mapping[str, Any]) -> EvidenceAtom:
    payload = {
        "kind": kind,
        "method": _METHOD,
        "wall_candidate_id": wall_id,
        "reason_codes": list(reason_codes),
        "feature_basis": dict(feature_basis),
    }
    return EvidenceAtom(
        evidence_id=stable_contract_id("wev", payload),
        document_id=document_id,
        page_id=page_id,
        kind=kind,
        method=_METHOD,
        viewport_id=viewport_id,
        confidence=confidence,
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=reason_codes,
        metadata={"wall_candidate_id": wall_id, "feature_basis": dict(feature_basis)},
    )


def _u2_atoms_for_wall(wall: WallCandidate, semantic_atoms: Sequence[Mapping[str, Any]]) -> Tuple[List[Mapping[str, Any]], List[Mapping[str, Any]]]:
    wall_edge_ids = set(wall.face_a_segment_ids) | set(wall.face_b_segment_ids or ())
    supporting: List[Mapping[str, Any]] = []
    opposing: List[Mapping[str, Any]] = []
    for atom in semantic_atoms:
        metadata = atom.get("metadata") or {}
        if str(metadata.get("target_edge_id") or "") not in wall_edge_ids:
            continue
        polarity = str(metadata.get("polarity") or "")
        if polarity == "supporting":
            supporting.append(atom)
        elif polarity == "opposing":
            opposing.append(atom)
    return supporting, opposing


def _wall_native_source_ids(wall: WallCandidate, edges_by_id: Mapping[str, Mapping[str, Any]]) -> set:
    """Native primitive ids (U1 lineage) contributing to this wall's edges.

    ``detect_wall_pairs`` runs on native/structural segments (pre-split), so
    its own "face_a"/"face_b" values are native ids -- NEVER Stage-A edge
    ids like "split_3". Matching against ``face_a_segment_ids`` directly
    would silently never match anything post-split; this is the fix.
    """
    ids: set = set()
    for edge_id in list(wall.face_a_segment_ids) + list(wall.face_b_segment_ids or ()):
        edge = edges_by_id.get(edge_id)
        if not edge:
            continue
        lineage = edge.get(LINEAGE_KEY) or {}
        ids.update(str(i) for i in (lineage.get("source_primitive_ids") or ()))
    return ids


def _paired_face_atom(
    wall: WallCandidate,
    paired_wall_faces: Sequence[Mapping[str, Any]],
    edges_by_id: Mapping[str, Mapping[str, Any]],
    *,
    document_id: str,
    page_id: str,
) -> Optional[EvidenceAtom]:
    wall_native_ids = _wall_native_source_ids(wall, edges_by_id)
    for pair in paired_wall_faces:
        if str(pair.get("face_a")) in wall_native_ids or str(pair.get("face_b")) in wall_native_ids:
            return _atom(
                document_id=document_id,
                page_id=page_id,
                viewport_id=wall.viewport_id,
                kind=FAMILY_PAIRED_WALL_FACES,
                wall_id=wall.candidate_id,
                reason_codes=("parallel_offset_face_pair",),
                confidence=0.55,
                feature_basis={"face_a": pair.get("face_a"), "face_b": pair.get("face_b"), "gap_pt": pair.get("gap_pt")},
            )
    return None


def _junction_behavior_atom(wall: WallCandidate, *, document_id: str, page_id: str) -> Optional[EvidenceAtom]:
    """A wall's endpoints show real junction behavior only when at least one
    end actually connects to something else (L_CORNER/T_JUNCTION/X_CROSSING/
    MULTI_WAY/COLLINEAR_CONTINUATION). A bare ENDPOINT at BOTH ends means the
    wall is a fully isolated, unconnected segment touching nothing else in
    the drawing at all -- there is no junction there to validate, so this is
    the absence of the signal, not a weak instance of it. Confirmed via real-
    drawing census (Lamu, KSTVET) that without this exclusion, short,
    repeated, isolated fragments (hatch-tick-scale lengths, ~3-8pt, the same
    length repeated many times in a row) trivially passed this family
    alongside U2's own near-universal solid-stroke support, reaching
    "physical_evidence_status=corroborated" for what is almost certainly
    hatch/tick geometry, not real walls -- a genuine false-strong pattern,
    not a benchmark-fitted threshold (this excludes exactly the case where
    NEITHER endpoint has any real junction to report, on first-principles
    grounds, independent of any project's specific measurements).
    """
    if wall.junction_types == (JunctionType.ENDPOINT, JunctionType.ENDPOINT):
        return None
    if all(jt not in _INVALID_JUNCTION_TYPES_FOR_ENDPOINTS for jt in wall.junction_types):
        return _atom(
            document_id=document_id,
            page_id=page_id,
            viewport_id=wall.viewport_id,
            kind=FAMILY_VALID_JUNCTION_BEHAVIOR,
            wall_id=wall.candidate_id,
            reason_codes=("at_least_one_endpoint_is_a_real_junction",),
            confidence=0.4,
            feature_basis={"junction_types": [jt.value for jt in wall.junction_types]},
        )
    return None


def _native_layer_atom(
    wall: WallCandidate, edges_by_id: Mapping[str, Mapping[str, Any]], *, document_id: str, page_id: str
) -> Optional[EvidenceAtom]:
    wall_edge_ids = list(wall.face_a_segment_ids) + list(wall.face_b_segment_ids or ())
    for edge_id in wall_edge_ids:
        edge = edges_by_id.get(edge_id)
        if not edge:
            continue
        lineage = edge.get(LINEAGE_KEY) or {}
        for record in lineage.get("source_records") or ():
            layer = str(record.get("layer") or "")
            if "wall" in layer.lower():
                return _atom(
                    document_id=document_id,
                    page_id=page_id,
                    viewport_id=wall.viewport_id,
                    kind=FAMILY_NATIVE_LAYER_WALL_SUPPORT,
                    wall_id=wall.candidate_id,
                    reason_codes=("native_layer_name_contains_wall",),
                    confidence=0.3,
                    feature_basis={"layer": layer, "source_id": record.get("id")},
                )
    return None


def resolve_wall_physical_evidence(
    wall_candidates: Sequence[WallCandidate],
    *,
    graph: Mapping[str, Any],
    document_id: str,
    page_id: str,
    paired_wall_faces: Sequence[Mapping[str, Any]] = (),
) -> Tuple[List[WallCandidate], List[EvidenceAtom]]:
    """Return NEW WallCandidate records (status/confidence/evidence ids
    resolved) plus every minted EvidenceAtom, for one viewport.

    ``graph`` must be the SAME (already ``attach_typed_semantic_evidence``-
    decorated) graph that produced ``wall_candidates`` -- U2's atoms are read
    from ``graph[GRAPH_ATOMS_KEY]`` when present; a graph with no U2 atoms
    attached (e.g. an older caller) degrades gracefully to the other three
    families rather than raising.
    """
    edges_by_id = {str(e.get("id")): e for e in graph.get("edges", []) if not e.get("_removed")}
    semantic_atoms = graph.get(GRAPH_ATOMS_KEY) or []

    resolved: List[WallCandidate] = []
    minted_atoms: List[EvidenceAtom] = []

    for wall in wall_candidates:
        u2_supporting, u2_opposing = _u2_atoms_for_wall(wall, semantic_atoms)
        # NOTE: `wall.thickness_authority` starts PROVISIONAL for every
        # candidate assemble_wall_candidates produces (no stage before this
        # one resolves real thickness -- see that module's own docstring).
        # WallCandidate.__post_init__ makes PROVISIONAL-thickness +
        # CORROBORATED-status mutually exclusive by construction (a
        # deliberate, pre-existing guard: CORROBORATED means the WHOLE
        # entity is promotion-ready, thickness included, not merely "this
        # wall exists"). This module's independent-evidence families are
        # about EXISTENCE, not thickness, so a wall whose existence is
        # doubly corroborated still cannot legitimately claim the top-level
        # CORROBORATED status while its thickness remains an unresolved
        # PROVISIONAL default -- promoting it anyway would be exactly the
        # kind of "strengthen without independent agreement on every claim
        # the status implies" shortcut this phase exists to avoid. The true
        # finding is preserved losslessly in `metadata["physical_evidence_
        # status"]` instead (see below) rather than discarded.

        supporting_ids: List[str] = []
        opposing_ids: List[str] = [str(a.get("evidence_id")) for a in u2_opposing]
        families_present: set = set()
        reason_codes: List[str] = list(wall.reason_codes)

        if u2_supporting:
            families_present.add(FAMILY_U2_PHYSICAL_WALL_LINEWORK)
            supporting_ids.extend(str(a.get("evidence_id")) for a in u2_supporting)

        paired_atom = _paired_face_atom(wall, paired_wall_faces, edges_by_id, document_id=document_id, page_id=page_id)
        if paired_atom is not None:
            families_present.add(FAMILY_PAIRED_WALL_FACES)
            supporting_ids.append(paired_atom.evidence_id)
            minted_atoms.append(paired_atom)

        junction_atom = _junction_behavior_atom(wall, document_id=document_id, page_id=page_id)
        if junction_atom is not None:
            families_present.add(FAMILY_VALID_JUNCTION_BEHAVIOR)
            supporting_ids.append(junction_atom.evidence_id)
            minted_atoms.append(junction_atom)

        layer_atom = _native_layer_atom(wall, edges_by_id, document_id=document_id, page_id=page_id)
        if layer_atom is not None:
            families_present.add(FAMILY_NATIVE_LAYER_WALL_SUPPORT)
            supporting_ids.append(layer_atom.evidence_id)
            minted_atoms.append(layer_atom)

        reason_codes.append(REASON_DEFERRED_DIMENSION_EVIDENCE)
        reason_codes.append(REASON_DEFERRED_OPENING_CONTINUITY)

        supporting_ids = sorted(set(supporting_ids))
        opposing_ids = sorted(set(opposing_ids))
        has_opposing = bool(opposing_ids)
        has_supporting = bool(supporting_ids)

        thickness_unresolved = wall.thickness_m is None and wall.thickness_authority == MeasurementAuthorityType.PROVISIONAL

        if has_opposing and has_supporting:
            status = EvidenceResolutionStatus.CONFLICT
            physical_evidence_status = "conflict"
            confidence = min(wall.confidence, 0.5)
            reason_codes.append("supporting_and_opposing_evidence_both_present")
        elif has_opposing and not has_supporting:
            status = EvidenceResolutionStatus.CANDIDATE
            physical_evidence_status = "candidate"
            confidence = min(wall.confidence, 0.2)
            reason_codes.append("opposing_evidence_without_independent_support")
        elif len(families_present) >= 2:
            physical_evidence_status = "corroborated"
            confidence = max(wall.confidence, 0.75)
            reason_codes.append(f"corroborated_by_independent_families:{','.join(sorted(families_present))}")
            if thickness_unresolved:
                # See the note above the loop: CORROBORATED is reserved for
                # a promotion-ready entity, thickness included. Existence is
                # corroborated; the top-level status is deliberately capped.
                status = EvidenceResolutionStatus.CANDIDATE
                reason_codes.append(
                    "physical_existence_corroborated_but_top_level_status_capped_by_provisional_thickness_authority"
                )
            else:
                status = EvidenceResolutionStatus.CORROBORATED
        elif len(families_present) == 1:
            status = EvidenceResolutionStatus.CANDIDATE
            physical_evidence_status = "candidate"
            confidence = wall.confidence
            reason_codes.append(f"single_family_support_insufficient_for_corroboration:{next(iter(families_present))}")
        else:
            status = EvidenceResolutionStatus.ABSTAINED
            physical_evidence_status = "abstained"
            confidence = 0.0
            reason_codes.append("no_supporting_or_opposing_evidence_found")

        metadata = dict(wall.metadata)
        metadata["physical_evidence_status"] = physical_evidence_status
        metadata["physical_evidence_families"] = sorted(families_present)

        # WallCandidate's own invariants forbid CORROBORATED with any
        # conflicting_evidence_ids and forbid CONFLICT with none, and forbid
        # CORROBORATED with a PROVISIONAL thickness_authority -- all three
        # are already satisfied by the branches above, so replace() below
        # cannot violate them.
        resolved.append(
            replace(
                wall,
                status=status,
                confidence=confidence,
                supporting_evidence_ids=tuple(supporting_ids),
                conflicting_evidence_ids=tuple(opposing_ids),
                reason_codes=tuple(reason_codes),
                metadata=metadata,
            )
        )

    return resolved, minted_atoms


def reconstruct_room_candidates_from_credible_walls(
    graph: Dict[str, Any],
    resolved_wall_candidates: Sequence[WallCandidate],
    edge_id_to_wall_candidate_id: Dict[str, str],
    *,
    document_id: str,
    viewport_id: str,
    source_page: int = 0,
    exclude_conflict: bool = True,
):
    """Room reconstruction gated on wall-evidence credibility (shadow only).

    Wraps ``pb_wall_room_topology_room_faces.reconstruct_room_candidates``
    unchanged: this function's only contribution is choosing WHICH edges are
    even offered to that existing, reused function, by dropping every edge
    whose resolved wall status is ABSTAINED (no evidence either way) and,
    by default, CONFLICT (disputed evidence) -- never CANDIDATE or
    CORROBORATED. This is a strictly ONE-DIRECTIONAL dependency (walls ->
    rooms): nothing in this function or in ``reconstruct_room_candidates``
    feeds a room's existence back into wall corroboration, avoiding the
    circularity #273 fell into.

    Setting ``exclude_conflict=False`` keeps CONFLICT-status wall edges
    in the room-boundary population (still excludes ABSTAINED) -- exposed
    for adversarial testing of both policies, not because either is
    "correct": a disputed wall's geometry is real regardless of the
    dispute, so whether it should gate room closure is a genuine open
    question this module does not resolve, only makes explicit.
    """
    status_by_wall_id = {w.candidate_id: w.status for w in resolved_wall_candidates}
    excluded_statuses = {EvidenceResolutionStatus.ABSTAINED}
    if exclude_conflict:
        excluded_statuses.add(EvidenceResolutionStatus.CONFLICT)

    credible_edge_id_to_wall_id = {
        edge_id: wall_id
        for edge_id, wall_id in edge_id_to_wall_candidate_id.items()
        if status_by_wall_id.get(wall_id) not in excluded_statuses
    }

    credible_edge_ids = set(credible_edge_id_to_wall_id.keys())
    credible_graph = dict(graph)
    credible_graph["edges"] = [
        e for e in graph.get("edges", []) if not e.get("_removed") and str(e.get("id")) in credible_edge_ids
    ]

    return reconstruct_room_candidates(
        credible_graph,
        credible_edge_id_to_wall_id,
        document_id=document_id,
        viewport_id=viewport_id,
        source_page=source_page,
    )
