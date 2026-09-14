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

REVISED after an independent GPT-2 architecture review of this module found
that "2 named families" was not the same thing as "2 causally independent
observations" -- see CAUSAL-DOMAIN CONTRACT below, which is now the actual
gate. The family list itself is unchanged; what changed is that families are
no longer counted at face value.

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
   touching nothing else in the drawing) does NOT qualify at all -- there is
   no junction there to validate, only its absence.
4. ``native_layer_wall_support`` -- U1 lineage source_records whose native
   ``layer`` string(s) contain "wall" (case-insensitive substring, no
   project-specific keyword list) -- see LAYER EVIDENCE CONTRACT below for
   the plural-lineage handling GPT-2's review also required.

============================================================
CAUSAL-DOMAIN CONTRACT (the actual independence gate)
============================================================

Two "families" sharing the same underlying signal source are NOT
independent proof merely because they have different names. Every family
above is tagged with an ``EvidenceDomain`` describing WHERE its signal
physically comes from:

- ``NATIVE_METADATA``: an attribute already recorded on the native PDF
  primitive itself (stroke/dash presence, layer name). ``u2_physical_wall_
  linework`` AND ``native_layer_wall_support`` are BOTH this domain -- they
  are two different READINGS of the SAME underlying native record, not two
  independent observations. A solid stroke and a layer name that happens to
  say "Wall" can easily both be true of a single hatch tick drawn on a
  layer named "Wall Hatching"; neither one tells you anything the other
  didn't already imply.
- ``GEOMETRIC_RELATION``: a DIFFERENT edge's geometry relative to this one
  (``paired_wall_faces``). Genuinely independent of this edge's own native
  record.
- ``GRAPH_TOPOLOGY``: graph structure at this wall's own endpoints
  (``valid_junction_behavior``). Per GPT-2's review, this is CONTEXTUAL
  supporting evidence only -- it is still minted, still recorded, still
  contributes to ``supporting_evidence_ids`` and to ``physical_evidence_
  families``, but it NEVER counts toward the domain-independence tally for
  existence corroboration. A segment having "a real junction at one end"
  and "a solid native stroke" are not two independent proofs it is a wall:
  a dimension witness line, a mullion stub, or a furniture leg can show
  both. (Two deferred future families, ``explicit_figured_dimension`` and
  ``opening_interruption_continuity``, would be ``EXTERNAL_INDEPENDENT`` --
  genuinely external corroboration once wired.)

Existence corroboration now requires evidence from at least TWO DISTINCT
DOMAINS in ``_CORROBORATING_DOMAINS`` (currently ``NATIVE_METADATA`` and
``GEOMETRIC_RELATION`` -- ``GRAPH_TOPOLOGY`` is permanently excluded from
this set), with zero opposing evidence. Because this module implements only
one ``NATIVE_METADATA``-domain pairing plus one ``GEOMETRIC_RELATION``-
domain family today, existence corroboration in practice requires
``paired_wall_faces`` PLUS at least one of the two native-metadata
families -- a genuinely stricter bar than before. If a wall's only
available evidence is same-domain or contextual-only, IT STAYS CANDIDATE.
This is intentional and preferred over forcing CORROBORATED: see the FAIL
CLOSED note below.

============================================================
LAYER EVIDENCE CONTRACT (plural lineage)
============================================================

``native_layer_wall_support`` reuses U1's own already-computed
``attribute_status`` for the ``layer`` field rather than re-implementing
plural-source dedup logic:

- ``attribute_status.layer == "conflict"``: two or more of this edge's
  native source records show DIFFERENT present layer values. Layer evidence
  ABSTAINS for this edge -- a single "Wall"-named parent among genuinely
  mixed/disagreeing parents must never promote the whole candidate.
- ``attribute_status.layer == "unknown"``: no source record has a present
  layer value at all (missing layer = no layer support; a fabricated empty-
  string sentinel from a non-U1 caller is filtered the same way via the
  `layer_present` flag, never treated as evidence).
- ``attribute_status.layer == "agreed"``: exactly one distinct present
  layer value exists across every contributing native source -- safe to
  test that single value for the "wall" substring.

============================================================
PAIRED-FACE DESCENDANT-OWNERSHIP CONTRACT
============================================================

A native primitive can be split into multiple DIFFERENT descendant
``WallCandidate``s (plural lineage fan-out, or a duplicate/near-duplicate
native primitive). A ``detect_wall_pairs`` hit naming that native id is
NOT automatically proof for every descendant that happens to share it --
only for the specific descendant whose OWN geometric span the pair evidence
actually concerns. Before crediting a pair: if the matched native id also
appears in some OTHER edge that does not belong to this wall, ownership is
ambiguous UNLESS this wall's own edges can be shown to occupy a materially
different (non-overlapping) geometric region than that other edge (a
bounding-box disjointness check on whatever coordinates are available).
When the check cannot be made (missing geometry) or the regions are not
clearly disjoint, this module ABSTAINS for that pair rather than guessing
-- no nearest/first/smallest tie-break.

============================================================
FAIL CLOSED
============================================================

If the currently-implemented evidence does not contain two genuinely
independent domains, this module does NOT force CORROBORATED existence. It
is acceptable, and preferred, for a wall to remain CANDIDATE until a later,
truly independent source (explicit figured dimension, opening/schedule
evidence, a resolved measurement) exists. No confidence value or family
count is invented to preserve any particular real-drawing count.

EXPLICITLY NOT an independent domain, by design, to avoid repeating #273's
circularity:
- ROOM PARTICIPATION is never a wall-evidence input in this module at all.
  Room reconstruction in this module CONSUMES already-resolved wall
  evidence one-directionally (walls -> rooms); nothing here lets a room's
  own existence feed back into corroborating the walls that produced it.
- ONE-HOP CONNECTIVITY (an edge merely touching another edge at a node) is
  not itself a family -- it is already required just to HAVE a
  JunctionCandidate at all; the junction family requires the junction to
  resolve to a specific, unambiguous, CONNECTED type, not merely to exist,
  and even then only ever counts as GRAPH_TOPOLOGY context (see above).
- LENGTH ALONE never promotes a candidate. A long chain is not, by itself,
  one of the families above -- it can only ever gate which edges are
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

Two families are DELIBERATELY NOT implemented in this pass, with an honest
placeholder reason code rather than a shallow fake integration:
``explicit_figured_dimension`` (would need pb_figured_dimension_evidence /
pb_viewport_dimension_binding wiring) and ``opening_interruption_continuity``
(would need pb_wall_room_topology_opening_host_binding wiring). Both are
future ``EXTERNAL_INDEPENDENT`` families, not scored here.
"""
from __future__ import annotations

from dataclasses import replace
from enum import Enum
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


class EvidenceDomain(str, Enum):
    """Where a family's signal actually comes from -- see CAUSAL-DOMAIN
    CONTRACT in the module docstring. Two families in the SAME domain are
    two readings of the same underlying source, not two independent
    proofs."""

    NATIVE_METADATA = "native_metadata"
    GEOMETRIC_RELATION = "geometric_relation"
    GRAPH_TOPOLOGY = "graph_topology"
    EXTERNAL_INDEPENDENT = "external_independent"


FAMILY_DOMAIN: Dict[str, EvidenceDomain] = {
    FAMILY_U2_PHYSICAL_WALL_LINEWORK: EvidenceDomain.NATIVE_METADATA,
    FAMILY_NATIVE_LAYER_WALL_SUPPORT: EvidenceDomain.NATIVE_METADATA,
    FAMILY_PAIRED_WALL_FACES: EvidenceDomain.GEOMETRIC_RELATION,
    FAMILY_VALID_JUNCTION_BEHAVIOR: EvidenceDomain.GRAPH_TOPOLOGY,
}

# GRAPH_TOPOLOGY is deliberately absent: junction behavior is contextual
# supporting evidence only, never counted toward existence corroboration
# (Blocker 4 -- a one-end contact alone is not independent proof).
_CORROBORATING_DOMAINS = frozenset({EvidenceDomain.NATIVE_METADATA, EvidenceDomain.GEOMETRIC_RELATION, EvidenceDomain.EXTERNAL_INDEPENDENT})

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
    """See PAIRED-FACE DESCENDANT-OWNERSHIP CONTRACT in the module
    docstring.

    REVISED after a second independent GPT-2 re-review found the previous
    "credit if the sibling descendants are geometrically disjoint" rule was
    backwards: sibling disjointness proves the two descendants are
    DIFFERENT, not that either one is the pair's actual target. `detect_
    wall_pairs` records only ids + a gap/overlap scalar, never an interval
    on the native primitive's own extent, so THIS module currently has no
    way to positively localize which descendant a shared-parent pair
    belongs to. Per the fail-closed principle already used everywhere else
    in this module: when a matched native id is also carried by ANY edge
    outside this wall, ownership is ambiguous and this always abstains for
    that pair -- no bbox heuristic, no nearest/first/smallest tie-break.
    A future enhancement could resolve this properly by additionally
    passing native-segment coordinates (not just descendant/Stage-A edge
    coordinates) so the actual overlap interval on the native primitive's
    own line could be computed and compared against this specific
    descendant's own span; that is not implemented here, and no currently
    required test needs it.
    """
    wall_edge_ids = set(wall.face_a_segment_ids) | set(wall.face_b_segment_ids or ())
    wall_native_ids = _wall_native_source_ids(wall, edges_by_id)
    for pair in paired_wall_faces:
        matched_native_id: Optional[str] = None
        if str(pair.get("face_a")) in wall_native_ids:
            matched_native_id = str(pair.get("face_a"))
        elif str(pair.get("face_b")) in wall_native_ids:
            matched_native_id = str(pair.get("face_b"))
        if matched_native_id is None:
            continue

        native_id_shared_with_other_descendant = any(
            eid not in wall_edge_ids
            and matched_native_id in ((edge.get(LINEAGE_KEY) or {}).get("source_primitive_ids") or ())
            for eid, edge in edges_by_id.items()
        )
        if native_id_shared_with_other_descendant:
            continue  # ambiguous ownership across descendants sharing this native id -- always abstain for this pair

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
    the absence of the signal, not a weak instance of it. Note this is only
    ever CONTEXTUAL support (GRAPH_TOPOLOGY domain, excluded from
    _CORROBORATING_DOMAINS) -- see Blocker 4 in the module docstring: even a
    genuine one-end junction must never, by itself plus same-domain native
    metadata, reach existence corroboration.
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
    """See LAYER EVIDENCE CONTRACT in the module docstring: reuses U1's own
    already-computed ``attribute_status`` for the ``layer`` field instead of
    re-implementing plural-source dedup.

    REVISED (candidate-wide agreement) after a second independent GPT-2
    re-review found the previous per-edge early-return was itself a
    whole-wall independence violation: each contributing edge can be
    internally self-consistent (its OWN parents agree) while DIFFERENT
    edges of the SAME WallCandidate disagree with EACH OTHER (e.g. one
    edge's parents all say "A-WALL", another edge's parents all say
    "Glazing") -- returning on the first "wall"-looking edge ignored every
    other edge's own opinion entirely. This collects a representative
    present-and-agreed layer value from EVERY contributing edge first, and
    only credits when (a) at least one edge agrees layer support exists AND
    (b) no OTHER edge's own present layer value disagrees.

    REVISED AGAIN (conflicted edge must not be silently dropped) after a
    third independent GPT-2 re-review found that an edge whose OWN
    ``attribute_status.layer == "conflict"`` (this ONE edge's own native
    parents disagree with each other, e.g. "A-WALL" + "Glazing" among its
    own source records) was simply skipped -- contributing no opinion, but
    also raising no objection -- letting some OTHER, internally-clean
    "A-WALL" edge promote the whole wall regardless. A contributor whose
    own layer evidence is internally contradictory is exactly the kind of
    fact that must fail closed for the WHOLE candidate, not vanish from
    consideration: any contributing edge with an unresolved internal layer
    conflict now aborts whole-wall layer support immediately, before any
    other edge's clean value is even consulted.
    """
    wall_edge_ids = list(wall.face_a_segment_ids) + list(wall.face_b_segment_ids or ())
    per_edge_layers: List[Tuple[str, str]] = []
    for edge_id in wall_edge_ids:
        edge = edges_by_id.get(edge_id)
        if not edge:
            continue
        lineage = edge.get(LINEAGE_KEY) or {}
        attribute_status = lineage.get("attribute_status") or {}
        layer_status = attribute_status.get("layer")
        if layer_status == "conflict":
            # This edge's OWN native parents disagree with each other.
            # That is unresolved evidence, not an absent opinion -- it must
            # fail closed for the WHOLE wall, not be silently dropped while
            # some other clean edge promotes the candidate regardless.
            return None
        present_layers = [
            str(record.get("layer") or "")
            for record in (lineage.get("source_records") or ())
            if record.get("layer_present")
        ]
        if not present_layers:
            continue  # missing layer = no opinion from this edge
        # attribute_status != "conflict" guarantees every present value here
        # is identical (U1's own dedup already established that for THIS
        # edge); any one of them is representative of this edge's own view.
        per_edge_layers.append((edge_id, present_layers[0]))

    if not per_edge_layers:
        return None  # no edge on this wall has any present layer opinion at all

    wall_matches = [(eid, layer) for eid, layer in per_edge_layers if "wall" in layer.lower()]
    non_wall_matches = [(eid, layer) for eid, layer in per_edge_layers if "wall" not in layer.lower()]
    if not wall_matches:
        return None
    if non_wall_matches:
        # Candidate-wide disagreement: at least one edge says wall-ish,
        # at least one other says something else entirely -- fail closed
        # rather than letting the first wall-looking edge speak for edges
        # that plainly disagree with it.
        return None

    return _atom(
        document_id=document_id,
        page_id=page_id,
        viewport_id=wall.viewport_id,
        kind=FAMILY_NATIVE_LAYER_WALL_SUPPORT,
        wall_id=wall.candidate_id,
        reason_codes=("all_edges_with_a_present_native_layer_agree_and_contain_wall",),
        confidence=0.3,
        feature_basis={"per_edge_layers": per_edge_layers},
    )


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

        # CAUSAL-DOMAIN CONTRACT: corroboration counts DOMAINS, not family
        # names -- two families sharing one signal source (both NATIVE_
        # METADATA) are one observation, not two. GRAPH_TOPOLOGY never
        # counts here at all (contextual only). See module docstring.
        corroborating_domains_present = {
            FAMILY_DOMAIN[f] for f in families_present if FAMILY_DOMAIN[f] in _CORROBORATING_DOMAINS
        }

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
        elif len(corroborating_domains_present) >= 2:
            physical_evidence_status = "corroborated"
            confidence = max(wall.confidence, 0.75)
            reason_codes.append(
                f"corroborated_by_independent_domains:{','.join(sorted(d.value for d in corroborating_domains_present))}"
            )
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
        elif families_present:
            # Either exactly one corroborating-domain family, or only
            # GRAPH_TOPOLOGY (contextual) support -- neither is sufficient
            # for existence corroboration. Fail closed: stays CANDIDATE
            # rather than inventing a second domain.
            status = EvidenceResolutionStatus.CANDIDATE
            physical_evidence_status = "candidate"
            confidence = wall.confidence
            reason_codes.append(
                f"insufficient_independent_domains_for_corroboration:families={','.join(sorted(families_present))}"
            )
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


def wall_has_positive_uncontested_evidence(wall: WallCandidate) -> bool:
    """WEAK signal: at least one supporting evidence id and zero opposing
    evidence. NOT sufficient, on its own, for a firm/quantity-chain-eligible
    room boundary -- see ``wall_is_credible_room_boundary`` for that
    stronger contract. A wall with exactly one evidence DOMAIN (e.g. an
    ordinary solid retained line with nothing opposing it) satisfies this
    check trivially; kept only for the permissive research-visibility
    policy and for direct before/after comparison, never as the default
    "firm" claim.
    """
    return bool(wall.supporting_evidence_ids) and not bool(wall.conflicting_evidence_ids)


def wall_is_credible_room_boundary(wall: WallCandidate) -> bool:
    """FIRM BOUNDARY CONTRACT (revised after a second independent GPT-2
    re-review): a wall may bound a conservatively-reconstructed, quantity-
    chain-eligible room only when its OWN physical existence is genuinely
    CORROBORATED -- 2+ independent evidence domains, zero opposition (see
    the CAUSAL-DOMAIN CONTRACT in the module docstring) -- not merely "has
    some uncontested support".

    The previous version of this function accepted ``wall_has_positive_
    uncontested_evidence`` as sufficient. That is a real, weaker, still-
    honest claim ("nothing currently disputes this wall"), but it let a
    room close on walls the physical-existence model itself only ever
    labelled CANDIDATE (single-domain) -- confidence inflation at the room
    level, even though the wall-to-room dependency itself remained
    correctly one-directional (no room ever feeds back into wall
    corroboration). A room whose boundaries are meant to be "firm" enough
    for a later quantity chain must require the stronger claim.
    """
    return wall.metadata.get("physical_evidence_status") == "corroborated"


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
    even offered to that existing, reused function. This is a strictly
    ONE-DIRECTIONAL dependency (walls -> rooms): nothing in this function or
    in ``reconstruct_room_candidates`` feeds a room's existence back into
    wall corroboration, avoiding the circularity #273 fell into.

    ``exclude_conflict=True`` (the default, "conservative" policy) applies
    the FIRM BOUNDARY CONTRACT above (``wall_is_credible_room_boundary``):
    genuine physical-existence CORROBORATION (2+ independent domains, zero
    opposition) is required per boundary wall -- merely uncontested single-
    domain support (``wall_has_positive_uncontested_evidence``) is NOT
    enough. A resulting room's ``bounding_wall_candidate_ids`` are
    therefore, by construction, entirely walls that satisfy the stronger
    contract -- there is no separate "firm room" concept beyond this; a
    caller wanting to confirm can re-check every id in that list against
    ``wall_is_credible_room_boundary`` directly. If no boundary population
    is strong enough to close a loop, the returned list is legitimately
    empty -- this function never fabricates a closure. On real, messy
    drawings this is expected to shrink the conservative room count
    substantially relative to the weaker check, since genuine 2-domain
    corroboration is rare with the evidence families implemented so far --
    that reduction is preferred over an inflated, unearned "firm" count.

    ``exclude_conflict=False`` (the "permissive" policy) drops only
    ABSTAINED walls (no evidence at all either way), keeping CONFLICT and
    opposing-only CANDIDATE edges in the population -- exposed for
    adversarial visibility/testing of the looser policy, never used as the
    default "firm" claim.
    """
    status_by_wall_id = {w.candidate_id: w.status for w in resolved_wall_candidates}
    credible_by_wall_id = {w.candidate_id: wall_is_credible_room_boundary(w) for w in resolved_wall_candidates}

    if exclude_conflict:
        credible_edge_id_to_wall_id = {
            edge_id: wall_id
            for edge_id, wall_id in edge_id_to_wall_candidate_id.items()
            if credible_by_wall_id.get(wall_id, False)
        }
    else:
        credible_edge_id_to_wall_id = {
            edge_id: wall_id
            for edge_id, wall_id in edge_id_to_wall_candidate_id.items()
            if status_by_wall_id.get(wall_id) != EvidenceResolutionStatus.ABSTAINED
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
