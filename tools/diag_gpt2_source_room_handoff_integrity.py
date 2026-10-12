"""Producer-owned Maryborough source room -> floor -> quantity handoff auditor.

Read-only. No benchmark truth, name-based geometry, fallback walls, or areas.
Do not confuse an authenticated word/face receipt with a commercial floor.
"""
from __future__ import annotations
from collections import Counter
from collections.abc import Mapping
import math
import re

NAMES = ("FOOD PREP","COLD ROOM","OFFICE","FREEZER","PWD","AIRLOCK","LAUNDRY",
         "SALES","POS COUNTER","FOOD SERVICE","WASH UP","TRUCK DRIVER LOUNGE",
         "M-AMB","F-AMB","DRY STORE")


def _owned(v):
    return isinstance(v,str) and bool(v) and v==v.strip()


def _name(v):
    return " ".join(v.upper().split()) if isinstance(v,str) else ""


def _polygon(source):
    """Require valid original native geometry before reporting a floor owner.

    A positive upstream area field does not authenticate a self-intersecting
    native polygon. This diagnostic neither repairs nor measures such a face.
    """
    vertices = getattr(source, "polygon_pdf_pts", None)
    area = getattr(source, "area_page_pts2", None)
    if not (
        isinstance(vertices, (tuple, list)) and len(vertices) >= 3
        and all(
            isinstance(pt, (tuple, list)) and len(pt) == 2
            and all(type(value) in (int, float) and math.isfinite(value)
                    for value in pt)
            for pt in vertices
        )
        and type(area) in (int, float)
        and math.isfinite(area) and area > 0
    ):
        return False
    # Original-source room polygons may be open vertex rings (no repeated
    # final point); Shapely validates closure, crossings and zero area without
    # changing the vertices. Never use buffer(0) or polygon repair here.
    from shapely.errors import GEOSException
    from shapely.geometry import Polygon
    try:
        native_face = Polygon(vertices)
        return (
            not native_face.is_empty
            and native_face.is_valid
            and native_face.area > 0
            and len(native_face.interiors) == 0
        )
    except (TypeError, ValueError, OverflowError, GEOSException):
        return False

def _first_native_ring_crossing_pair_diagnostic_only(vertices):
    """Preserve two original intersecting non-neighbour source edges.

    Does not repair the source, bind edges to W4 walls, or certify a room.
    A canonical room may carry a *set* of bounding W4 IDs but not the exact
    producer edge/owner proof needed to identify a wall at this intersection.
    """
    result = {
        "first_source_crossing_gate_diagnostic_only": "source_crossing_unresolved",
        "original_ring_crossing_edge_indices": [],
        "original_ring_crossing_edge_pdf_pts": [],
        "original_ring_crossing_geometry_type": None,
        "source_edge_wall_owner_proven": False,
        "source_room_geometry_repaired": False,
    }
    if not isinstance(vertices, (tuple, list)) or not 4 <= len(vertices) <= 256:
        return result
    if any(
        not isinstance(point, (tuple, list)) or len(point) != 2
        or any(type(x) not in (float, int) or not math.isfinite(x) for x in point)
        for point in vertices
    ):
        return result
    from shapely.geometry import LineString
    from shapely.errors import GEOSException

    count = len(vertices)
    for i in range(count):
        start = vertices[i]
        end = vertices[(i + 1) % count]
        if start == end:
            continue
        for j in range(i + 2, count):
            # First/last share the original ring closure by construction.
            if i == 0 and j == count - 1:
                continue
            other_start = vertices[j]
            other_end = vertices[(j + 1) % count]
            if other_start == other_end:
                continue
            try:
                crossing = LineString((start, end)).intersection(
                    LineString((other_start, other_end))
                )
            except (GEOSException, TypeError, ValueError, OverflowError):
                continue
            if crossing.is_empty:
                continue
            result.update({
                "first_source_crossing_gate_diagnostic_only":
                    "original_nonadjacent_ring_edges_intersect_role_unproven",
                "original_ring_crossing_edge_indices": [i, j],
                "original_ring_crossing_edge_pdf_pts": [
                    [list(start), list(end)],
                    [list(other_start), list(other_end)],
                ],
                "original_ring_crossing_geometry_type": crossing.geom_type,
            })
            return result
    return result


def original_polygon_first_failure_receipt(source):
    """Explain the original ring failure without repairing or measuring it.

    Page-space source geometry is not metric authority. Positive polygon
    validity is necessary for a physical-room handoff but never sufficient
    to publish a canonical floor, floor finish, or quantity.
    """
    result = {
        "first_source_polygon_gate_diagnostic_only":
            "source_polygon_coordinates_unavailable",
        "original_native_polygon_vertex_count": 0,
        "original_native_polygon_geos_reason_diagnostic_only": None,
        "original_native_polygon_valid_diagnostic_only": False,
        "original_polygon_repaired": False,
        "metric_area_published_by_diagnostic": False,
        "original_native_source_ring_crossing_diagnostic_only": None,
    }
    vertices = getattr(source, "polygon_pdf_pts", None)
    if not isinstance(vertices, (tuple, list)):
        return result
    result["original_native_polygon_vertex_count"] = len(vertices)
    if len(vertices) < 3 or any(
        not isinstance(point, (tuple, list)) or len(point) != 2
        or any(
            type(coordinate) not in (int, float)
            or not math.isfinite(coordinate)
            for coordinate in point
        )
        for point in vertices
    ):
        return result
    native_area = getattr(source, "area_page_pts2", None)
    if (
        type(native_area) not in (int, float)
        or not math.isfinite(native_area) or native_area <= 0
    ):
        result["first_source_polygon_gate_diagnostic_only"] = (
            "source_page_area_receipt_unavailable"
        )
        return result
    from shapely.errors import GEOSException
    from shapely.geometry import Polygon
    from shapely.validation import explain_validity
    try:
        polygon = Polygon(vertices)
        if polygon.is_empty:
            gate = "source_native_polygon_empty_or_nonpositive"
        elif not polygon.is_valid:
            gate = "source_native_polygon_invalid"
        elif polygon.area <= 0:
            gate = "source_native_polygon_empty_or_nonpositive"
        elif polygon.interiors:
            gate = "source_native_polygon_has_interiors"
        else:
            gate = "source_native_polygon_valid_candidate_only"
        result["first_source_polygon_gate_diagnostic_only"] = gate
        result["original_native_polygon_valid_diagnostic_only"] = (
            gate == "source_native_polygon_valid_candidate_only"
        )
        if not result["original_native_polygon_valid_diagnostic_only"]:
            result["original_native_polygon_geos_reason_diagnostic_only"] = (
                str(explain_validity(polygon))[:180]
            )
        if gate == "source_native_polygon_invalid":
            result["original_native_source_ring_crossing_diagnostic_only"] = (
                _first_native_ring_crossing_pair_diagnostic_only(vertices)
            )
    except (GEOSException, TypeError, ValueError, OverflowError):
        result["first_source_polygon_gate_diagnostic_only"] = (
            "source_native_polygon_geos_unavailable"
        )
    return result


def _source(obj,sha):
    return getattr(obj,"source_sha256",None)==sha


def _metric_quantity(q):
    return (not getattr(q,"abstained",True)
            and str(getattr(q,"status","")).lower() in ("firm","corroborated")
            and getattr(q,"unit",None) in ("m2","m²")
            and type(getattr(q,"value",None)) in (int,float)
            and math.isfinite(q.value) and q.value>0
            and _owned(getattr(q,"quantity_id",None))
            and isinstance(getattr(q,"input_entity_ids",None),tuple)
            and bool(q.input_entity_ids)
            and all(_owned(identity) for identity in q.input_entity_ids)
            and len(set(q.input_entity_ids))==len(q.input_entity_ids)
            and isinstance(getattr(q,"evidence_ids",None),tuple)
            and bool(q.evidence_ids)
            and all(_owned(x) for x in q.evidence_ids)
            and len(q.evidence_ids)==len(set(q.evidence_ids)))


def _exact_floor_area_reissue_for_source_row(row, published, original_source_sha):
    """Observe an existing publisher result; never create or seal a quantity.

    The canonical floor commercial flag stays independent. This is useful
    when its upstream FIRM room area was reissued by the actual producer but
    the diagnostic's stricter eight-gate customer handoff still abstains.
    """
    quantity_id = row.get("documented_area_quantity_id")
    floor_id = row.get("canonical_floor_id")
    face_receipt = row.get("original_source_face_receipt_id")
    amount = row.get("source_proven_area_m2")
    if not all(_owned(value) for value in (quantity_id, floor_id, face_receipt)):
        return None
    if type(amount) not in (int, float) or not math.isfinite(amount) or amount <= 0:
        return None
    candidates = []
    for quantity in published:
        metadata = getattr(quantity, "metadata", None)
        if not isinstance(metadata, Mapping):
            continue
        if not (
            _owned(getattr(quantity, "quantity_id", None))
            and getattr(quantity, "family", None) == "floor_area"
            and str(getattr(quantity, "status", "")).lower() == "firm"
            and getattr(quantity, "abstained", True) is False
            and getattr(quantity, "unit", None) in ("m2", "m²")
            and metadata.get("upstream_room_area_quantity_id") == quantity_id
            and metadata.get("canonical_floor_id") == floor_id
            and metadata.get("source_room_face_record_id") == face_receipt
            and metadata.get("source_sha256") == original_source_sha
            and metadata.get("row_role") == "floor_area"
            and metadata.get("commercial_projection_allowed") is True
            and type(getattr(quantity, "value", None)) in (int, float)
            and math.isfinite(quantity.value)
            and math.isclose(quantity.value, amount, abs_tol=1e-9)
        ):
            continue
        candidates.append(quantity.quantity_id)
    # A duplicate producer reissue is not a uniquely attributed floor.
    return candidates[0] if len(candidates) == 1 else None


def report_source_room_handoff(claim, *, original_source_sha, targets=NAMES):
    """Report the first unproved gate for each exact producer-named room.

    A quantity is public-ready only if a UNIQUE original room, canonical
    floor, and FIRM source area all own the exact same canonical lineage.
    Finish/RCP is independently withheld until real occurrence ownership.
    """
    if not isinstance(original_source_sha,str) or not re.fullmatch(
        r"[0-9a-f]{64}",original_source_sha):
        raise ValueError("real source SHA-256 must be explicit")
    if not isinstance(targets,(list,tuple)) or not targets:
        raise ValueError("explicit report targets required")
    target_names=[_name(x) for x in targets]
    if (any(not _owned(x) for x in target_names)
            or len(set(target_names))!=len(target_names)):
        raise ValueError("ambiguous target names")
    rooms=tuple(getattr(claim,"canonical_rooms",()) or ())
    floors=tuple(getattr(claim,"canonical_floors",()) or ())
    quantities=tuple(getattr(claim,"room_area_quantity_evidence",()) or ())
    finishes=tuple(getattr(claim,"floor_finish_quantity_evidence",()) or ())
    ceilings=tuple(getattr(claim,"ceiling_lining_quantity_evidence",()) or ())
    # No foreign-source claimant can enter the report as positive evidence.
    eligible=[r for r in rooms if _name(getattr(r,"room_label",None)) in target_names]
    grouped={}
    for room in eligible:
        grouped.setdefault(_name(room.room_label),[]).append(room)
    # Index only exact source-owned typed receipt IDs. An upstream malformed
    # (possibly unhashable) ID is an unavailable owner, never a dictionary
    # address, and must not abort the diagnostic before fail-closed gates run.
    floor_ids=Counter(
        identity for f in floors
        for identity in (getattr(f,"canonical_floor_id",None),)
        if _owned(identity)
    )
    floor_by_room={}
    for floor in floors:
        owner=getattr(floor,"room_entity_id",None)
        if _owned(owner):
            floor_by_room.setdefault(owner,[]).append(floor)
    q_ids=Counter(getattr(q,"quantity_id",None) for q in quantities)
    # Room-area producer QuantityEvidence is explicitly keyed to original
    # room.face_id, NOT to a canonical floor ID. Its source receipt/evidence
    # and SHA/revision/viewport must be authenticated before the later
    # floor metric projection can be checked.
    room_ids=Counter(
        identity for r in eligible
        for identity in (getattr(r,"physical_room_id",None),)
        if _owned(identity)
    )
    face_ids=Counter(
        identity for r in eligible
        for identity in (getattr(r,"source_room_face_record_id",None),)
        if _owned(identity)
    )
    direct_labels=Counter(getattr(r,"room_label_binding_record_id",None)
                          for r in eligible if _owned(getattr(r,"room_label_binding_record_id",None)))
    text_observations=Counter(id for r in eligible
        for id in (getattr(r,"room_label_evidence_ids",()) or ())
        if _owned(id))
    rows=[]
    for name in target_names:
        owners=grouped.get(name,[])
        gate="SOURCE_PHYSICAL_FACE_UNAVAILABLE"
        room_id=face_id=floor_id=quantity_id=None
        label_binding_id=None
        original_label_evidence_ids=()
        original_metric_evidence_ids=()
        original_metric_authority=None
        amount=None
        native_ring_diagnostic=None
        if len(owners)>1:
            gate="ROOM_LABEL_MULTIPLE_SOURCE_FACES"
        elif len(owners)==1:
            r=owners[0]
            room_id=getattr(r,"physical_room_id",None)
            face_id=getattr(r,"source_room_face_record_id",None)
            label_id=getattr(r,"room_label_binding_record_id",None)
            texts=getattr(r,"room_label_evidence_ids",()) or ()
            # Inspect only uniquely named, exact-source native geometry.
            # Never use this geometric diagnostic to bypass lineage gates.
            if (_source(r,original_source_sha) and _owned(room_id)
                    and _owned(face_id) and room_ids[room_id]==1
                    and face_ids[face_id]==1):
                native_ring_diagnostic=original_polygon_first_failure_receipt(r)
            if (not _source(r,original_source_sha)
                    or not _owned(getattr(r,"document_id",None))
                    or not _owned(getattr(r,"revision_id",None))
                    or not _owned(getattr(r,"snapshot_id",None))
                    or not _owned(getattr(r,"decision_scope_id",None))
                    or not _owned(getattr(r,"viewport_id",None))
                    or not _owned(getattr(r,"canonical_room_id",None))
                    or not _owned(room_id) or not _owned(face_id)
                    or room_ids[room_id]!=1 or face_ids[face_id]!=1):
                gate="SOURCE_ROOM_FACE_IDENTITY_CONFLICT"
            elif (not _owned(label_id) or direct_labels[label_id]!=1
                    or not isinstance(texts,(tuple,list)) or not texts
                    or any(not _owned(x) or text_observations[x]!=1 for x in texts)
                    or len(set(texts))!=len(texts)):
                gate="ORIGINAL_ROOM_LABEL_RECEIPT_AMBIGUOUS"
            elif not _polygon(r) or not getattr(r,"geometry_complete",False):
                gate="SOURCE_ROOM_PHYSICAL_POLYGON_INCOMPLETE"
            else:
                label_binding_id=label_id
                original_label_evidence_ids=tuple(sorted(texts))
                matches=floor_by_room.get(getattr(r,"canonical_room_id",None),[])
                if len(matches)!=1:
                    gate="CANONICAL_FLOOR_OWNER_UNAVAILABLE"
                else:
                    f=matches[0]
                    floor_id=getattr(f,"canonical_floor_id",None)
                    if (not _source(f,original_source_sha)
                            or not _owned(floor_id) or floor_ids[floor_id]!=1
                            or f.source_room_face_record_id!=face_id
                            or f.document_id!=r.document_id
                            or f.snapshot_id!=r.snapshot_id
                            or f.page_id!=r.page_id
                            or f.viewport_id!=r.viewport_id
                            or f.polygon_pdf_pts!=r.polygon_pdf_pts
                            or not getattr(f,"geometry_complete",False)):
                        gate="FLOOR_ORIGINAL_PHYSICAL_FACE_LINEAGE_CONFLICT"
                    else:
                        # Support-only source dimensions are NOT page geometry.
                        matches=[q for q in quantities
                                 if _metric_quantity(q)
                                 and q_ids[q.quantity_id]==1
                                 and face_id in q.evidence_ids
                                 and isinstance(getattr(q,"metadata",None),dict)
                                 and q.metadata.get("source_sha256")==original_source_sha
                                 and q.metadata.get("revision_id")==r.revision_id
                                 and q.metadata.get("viewport_id")==r.viewport_id
                                 and len(q.input_entity_ids)==1
                                 and q.semantic_key=="room_area:"+q.input_entity_ids[0]]
                        if len(matches)!=1:
                            gate="FIRM_AREA_SOURCE_MEASUREMENT_UNAVAILABLE"
                        else:
                            q=matches[0]
                            quantity_id=q.quantity_id
                            original_metric_evidence_ids=tuple(sorted(q.evidence_ids))
                            original_metric_authority=(
                                q.authority if _owned(getattr(q,"authority",None)) else None
                            )
                            amount=float(q.value)
                            if (not getattr(f,"metric_geometry_complete",False)
                                or f.metric_area_quantity_id!=quantity_id
                                or not math.isfinite(getattr(f,"metric_area_m2",float("nan")) or float("nan"))
                                or not math.isclose(f.metric_area_m2,amount,abs_tol=1e-8)
                                or not getattr(f,"physical_floor_surface_identity_resolved",False)
                                or not getattr(f,"commercial_quantity_authority",False)):
                                gate="COMMERCIAL_FLOOR_AREA_AUTHORITY_UNAVAILABLE"
                            else:
                                gate="SOURCE_ROOM_AREA_READY_FOR_GPT1_GPT3_REVIEW"
        rows.append({
            "source_room_label":name,
            "first_unproved_authority":gate,
            "original_physical_room_id":room_id if _owned(room_id) else None,
            "original_source_face_receipt_id":face_id if _owned(face_id) else None,
            "original_polygon_source_validity_diagnostic_only":native_ring_diagnostic,
            "canonical_floor_id":floor_id if _owned(floor_id) else None,
            "original_label_binding_record_id":label_binding_id,
            "original_label_evidence_ids":list(original_label_evidence_ids),
            "documented_area_quantity_id":quantity_id,
            "documented_area_source_evidence_ids":list(original_metric_evidence_ids),
            "documented_area_original_authority":original_metric_authority,
            "source_proven_area_m2":amount,
            "floor_finish_publication_allowed":False,
            "ceiling_lining_publication_allowed":False,
            "source_finish_occurrence_link_unavailable":True,
            "metric_area_inferred_from_page_points":False,
            "benchmark_accuracy":None,
        })
    # The real source publisher may independently reissue a firm room area
    # despite the canonical floor's stricter commercial flag being False.
    # Report that separate observation without upgrading the eight source
    # gates or claiming a sealed customer quantity. Synthetic claims are
    # never used to call a production publisher.
    production_reissues = ()
    from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
    if type(claim) is LivePhysicalNetWallClaim:
        from pb_live_floor_area_quantity_publication import (
            publish_live_floor_area_quantities,
        )
        production_reissues = publish_live_floor_area_quantities(claim)
    for row in rows:
        receipt = _exact_floor_area_reissue_for_source_row(
            row, production_reissues, original_source_sha
        )
        row["producer_floor_area_reissue_quantity_id_observed_only"] = receipt
        row["customer_floor_area_seal_verified_by_this_report"] = False
    # Raw quantity inventories are never enough to infer source room ownership.
    return {
        "source_sha256":original_source_sha,
        "reported_source_room_count":len(rows),
        "room_handoff_first_gates":rows,
        "original_source_room_candidate_count":len(eligible),
        "original_canonical_floor_candidate_count":len(floors),
        "source_room_area_quantity_candidate_count":len(quantities),
        "independent_floor_area_reissue_observed_count":sum(
            row["producer_floor_area_reissue_quantity_id_observed_only"] is not None
            for row in rows
        ),
        "source_finish_quantity_candidate_count":len(finishes),
        "source_ceiling_lining_quantity_candidate_count":len(ceilings),
        "floor_finish_publication_allowed":False,
        "ceiling_lining_publication_allowed":False,
        "dry_store_must_abstain_without_new_proof":True,
        "diagnostic_only":True,
        "benchmark_accuracy":None,
    }
