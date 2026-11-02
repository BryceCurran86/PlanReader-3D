"""GPT2 original-source compiler seam for downstream measurement lanes.

This bridge can only consume a SourceVisibilityProducer's immutable revision
and its original PDF bytes. It exposes diagnostic geometry and material
hand-offs without altering W2/W3/W4, awarding physical wall authority, or
publishing a customer quantity. GPT1 can explicitly consume these receipts
rather than reproduce a list of page-local source coordinates.
"""
from __future__ import annotations

from pb_source_visibility_authority import SourceVisibilityProducer
from pb_cross_view_ceiling_finish_authority import _source_bytes
from tools.diag_gpt2_source_room_graph_shadow import audit_original_room_edge_graph
from tools.diag_gpt2_original_figured_detail_plan_shadow import (
    audit_original_figured_detail_plan_pair,
)
from tools.diag_gpt2_original_native_dimension_chain_shadow import (
    audit_original_native_orthogonal_dimension_chains,
)
from tools.diag_gpt2_original_figured_face_rivals_shadow import (
    audit_original_figured_detail_face_rivals,
    audit_original_figured_wall_note_alignment,
    audit_original_ft2_internal_wall_face_basis,
)
from tools.diag_gpt2_original_detail_floor_same_room_shadow import (
    audit_original_detail_vs_main_source_room_candidate,
)
from tools.diag_gpt2_original_room_doorway_ancestry_shadow import (
    audit_gpt2_original_room_doorway_ancestry_pair,
)
from tools.diag_gpt2_source_rcp_geometry_shadow import (
    audit_original_rcp_ceiling_ink,
    audit_original_rcp_source_finish_occurrence,
)
from pb_gpt2_w4_rcp_source_handoff import (
    audit_gpt2_w4_original_rcp_ceiling_handoff,
)
from pb_gpt2_w4_original_floor_handoff import (
    audit_gpt2_w4_bound_original_floor,
    audit_gpt2_w4_material_to_gpt1,
)
from tools.diag_gpt2_source_finish_floor_handoff_shadow import (
    audit_gpt2_original_cross_sheet_ring_correspondence,
    audit_gpt2_original_doorway_bound_floor_finish_correspondence,
    audit_gpt2_source_material_floor_handoff,
)



def _original_doorway_ring_matches_reissued_native_graph(ring: dict, graph: dict) -> bool:
    """Prove a caller's perimeter vertices/IDs against SHA-page-native strokes.

    This is a negative-only source integrity gate. The jamb receipt and W4
    physical wall/room authority remain separate, never inferred here.
    """
    import math
    import re

    def point(value):
        if type(value) not in (tuple, list) or len(value) != 2:
            return None
        out = []
        for coordinate in value:
            if type(coordinate) not in (int, float):
                return None
            # Native PDF endpoints above the binary64 exact integer range
            # cannot retain distinct physical point identity as floats.
            if abs(coordinate) > 2**53:
                return None
            try:
                number = float(coordinate)
            except (ValueError, OverflowError):
                return None
            if not math.isfinite(number):
                return None
            out.append(number)
        return tuple(out)

    if type(ring) is not dict or type(graph) is not dict:
        return False
    # Equality of two absent roots (None == None), or numeric page aliases
    # (7.0 == 7, True == 1), is NOT original-source authentication. Require
    # complete typed source roots on BOTH independently supplied witnesses
    # before comparing their values or accepting any native edge geometry.
    ring_sha = ring.get("original_source_sha256")
    graph_sha = graph.get("source_sha256")
    ring_page = ring.get("original_page_1_based")
    graph_page = graph.get("page_1_based")
    if (any(type(sha) is not str
            or re.fullmatch(r"[0-9a-f]{64}", sha) is None
            for sha in (ring_sha, graph_sha))
            or any(type(page) is not int or not 1 <= page <= 2**53
                   for page in (ring_page, graph_page))):
        return False
    if (ring.get("source_jamb_roles_same_sha_rechecked") is not True
            or ring.get("source_wall_and_jamb_geometry_independently_recomputed") is not True
            or graph_sha != ring_sha
            or graph_page != ring_page):
        return False
    ids = ring.get("original_source_perimeter_side_ids")
    if (type(ids) is not tuple or not 2 <= len(ids) <= 120000
            or any(type(ident) is not str
                   or re.fullmatch(r"d(0|[1-9][0-9]*)i(0|[1-9][0-9]*)", ident) is None
                   for ident in ids)
            or len(set(ids)) != len(ids)
            or tuple(sorted(ids)) != graph.get("original_native_edge_ids")):
        return False
    components = graph.get("native_components")
    intersections = graph.get("interior_stroke_intersections_and_overlaps")
    # The native producer explicitly emits a tuple of every intersecting or
    # overlapping stroke. Missing/None/False is NOT proof of zero conflicts.
    # Likewise, the component must explicitly report whether it has a closed
    # simple ring; an omitted field cannot stand in for an open doorway.
    if (type(components) not in (tuple, list) or len(components) != 1
            or type(components[0]) is not dict
            or "source_simple_ring_candidate" not in components[0]
            or type(intersections) is not tuple or intersections
            or components[0]["source_simple_ring_candidate"] is not None):
        return False
    edges = graph.get("original_native_edges")
    if type(edges) not in (tuple, list) or len(edges) != len(ids):
        return False
    # The sealed source can expose many native strokes. Tuple membership for
    # each stroke is quadratic and can stall a source replay on large rooms.
    # This set changes lookup complexity only; it does not elect any edge.
    id_set = set(ids)
    native = {}
    for row in edges:
        if type(row) is not dict:
            return False
        source_id = row.get("source_id")
        if type(source_id) is not str or source_id not in id_set:
            return False
        ends = row.get("endpoints_pdf_pts")
        if type(ends) not in (tuple, list) or len(ends) != 2:
            return False
        a, b = point(ends[0]), point(ends[1])
        if a is None or b is None or a == b or row["source_id"] in native:
            return False
        native[row["source_id"]] = frozenset((a, b))
    if len(native) != len(ids):
        return False
    vertices = ring.get("source_ink_ring_with_explicit_virtual_door_gap_pdf_pts")
    if type(vertices) not in (tuple, list) or len(vertices) != len(ids) + 1:
        return False
    chain = [point(vertex) for vertex in vertices]
    if any(vertex is None for vertex in chain) or len(set(chain)) != len(chain):
        return False
    actual_edges = [frozenset((a, b)) for a, b in zip(chain, chain[1:])]
    if any(len(edge) != 2 for edge in actual_edges):
        return False
    if sorted(actual_edges, key=lambda x: sorted(x)) != sorted(native.values(), key=lambda x: sorted(x)):
        return False
    gap = ring.get("source_virtual_door_connector_pdf_pts")
    if type(gap) not in (tuple, list) or len(gap) != 2:
        return False
    if point(gap[0]) != chain[-1] or point(gap[1]) != chain[0]:
        return False
    # The connector is VIRTUAL, so the original native-stroke intersection
    # census cannot prove that it avoids the other room walls. A crossing,
    # nonadjacent touch, or overlap would close a self-intersecting room ring.
    # This is only a veto: an unblocked connector still has no W4, jamb,
    # physical-room, finish or measurement authority.
    connector_a, connector_b = chain[-1], chain[0]

    def orient(a, b, c):
        return ((b[0] - a[0]) * (c[1] - a[1])
                - (b[1] - a[1]) * (c[0] - a[0]))

    def on_segment(a, b, c):
        return (min(a[0], b[0]) <= c[0] <= max(a[0], b[0])
                and min(a[1], b[1]) <= c[1] <= max(a[1], b[1]))

    def intersects(a, b, c, d):
        ab_c, ab_d = orient(a, b, c), orient(a, b, d)
        cd_a, cd_b = orient(c, d, a), orient(c, d, b)
        return (ab_c == 0 and on_segment(a, b, c)
                or ab_d == 0 and on_segment(a, b, d)
                or cd_a == 0 and on_segment(c, d, a)
                or cd_b == 0 and on_segment(c, d, b)
                or ab_c * ab_d < 0 and cd_a * cd_b < 0)

    # Independently veto backtracking between adjacent native strokes.
    # An empty producer intersection census is not enough: two distinct
    # collinear edges sharing a vertex can overlap along a nonzero ink span.
    # A legitimate straight-through split has an opposite-ray direction and
    # remains valid. This O(N) check is source-only, not W4 wall authority.
    for i in range(1, len(chain) - 1):
        shared, previous, following = chain[i], chain[i - 1], chain[i + 1]
        if orient(shared, previous, following) == 0 and (
            (previous[0] - shared[0]) * (following[0] - shared[0])
            + (previous[1] - shared[1]) * (following[1] - shared[1])
        ) > 0:
            return False

    for index, (a, b) in enumerate(zip(chain, chain[1:])):
        if index in (0, len(chain) - 2):
            # The first and last native strokes are permitted to meet the
            # virtual connector at their own single doorway endpoint only.
            # Collinear same-ray segments instead share a nonzero span.
            shared = connector_b if index == 0 else connector_a
            other_connector = connector_a if index == 0 else connector_b
            other_native = b if index == 0 else a
            if orient(shared, other_connector, other_native) == 0 and (
                (other_connector[0] - shared[0])
                * (other_native[0] - shared[0])
                + (other_connector[1] - shared[1])
                * (other_native[1] - shared[1])
            ) > 0:
                return False
        elif intersects(connector_a, connector_b, a, b):
            return False
    # Reissued endpoint degrees are evidence only when they account for
    # EVERY native vertex and the exact source IDs incident on that vertex.
    # Two reported open endpoints alone could hide a missing interior node,
    # a duplicate degree row, or an unrelated source-edge owner.
    native_incidence = {}
    for source_id, endpoints in native.items():
        for vertex in endpoints:
            native_incidence.setdefault(vertex, set()).add(source_id)
    degrees = components[0].get("native_endpoint_degrees")
    if type(degrees) not in (tuple, list):
        return False
    reported_incidence = {}
    for row in degrees:
        if type(row) is not dict or type(row.get("degree")) is not int:
            return False
        coordinate = point(row.get("point_pdf_pt"))
        owners = row.get("original_source_edge_ids")
        if (coordinate is None or coordinate in reported_incidence
                or row["degree"] not in (1, 2)
                or type(owners) not in (tuple, list)
                or len(owners) != row["degree"]
                or any(type(owner) is not str for owner in owners)
                or len(set(owners)) != len(owners)):
            return False
        reported_incidence[coordinate] = set(owners)
    if reported_incidence != native_incidence:
        return False
    open_ends = {vertex for vertex, owners in reported_incidence.items()
                 if len(owners) == 1}
    if len(open_ends) != 2 or open_ends != {chain[0], chain[-1]}:
        return False
    area = ring.get("source_only_native_polygon_area_pdf_pt2_not_m2")
    if type(area) not in (int, float):
        return False
    try:
        expected_area = float(area)
    except (OverflowError, ValueError):
        return False
    shoelace = abs(sum(
        a[0] * b[1] - b[0] * a[1]
        for a, b in zip(chain, chain[1:] + chain[:1])
    )) / 2.0
    return (math.isfinite(expected_area) and expected_area > 0
            and math.isfinite(shoelace)
            and math.isclose(expected_area, shoelace, rel_tol=1e-12, abs_tol=1e-8))




class GPT2OriginalSourceGeometryBridge:
    """Read-only source publisher, bound to an existing visibility producer."""

    def __init__(self, source: SourceVisibilityProducer):
        if type(source) is not SourceVisibilityProducer:
            raise TypeError("existing_source_visibility_producer_required")
        self._source=source

    @classmethod
    def from_source_visibility_producer(
        cls, source: SourceVisibilityProducer,
    ) -> "GPT2OriginalSourceGeometryBridge":
        return cls(source)

    def _source_revision(self, revision_id: str, *, page_1_based: int):
        if type(revision_id) is not str or not revision_id or (
            type(page_1_based) is not int or not 1 <= page_1_based <= 2**53
        ):
            raise ValueError("source_revision_and_page_selector_required")
        published=self._source.published_snapshot_for_revision(revision_id)
        raw=_source_bytes(self._source,revision_id)
        if published is None or raw is None:
            raise ValueError("original_source_revision_sha_or_bytes_unavailable")
        # Coverage, immutable revision and published snapshot must all belong
        # to the SAME source root. A copied page-coverage receipt cannot
        # authorize a foreign source snapshot for later original-page joins.
        snapshot = getattr(published, "snapshot", None)
        snapshot_id = getattr(snapshot, "snapshot_id", None)
        if (
            published.revision.revision_id != revision_id
            or type(published.revision.document_id) is not str
            or not published.revision.document_id
            or getattr(snapshot, "document_id", None) != published.revision.document_id
            or getattr(snapshot, "revision_id", None) != revision_id
            or getattr(snapshot, "source_sha256", None) != published.revision.source_sha256
            or type(snapshot_id) is not str
            or not snapshot_id
            or snapshot_id != snapshot_id.strip()
        ):
            raise ValueError("original_source_snapshot_lineage_conflict")
        # Original-page identity is producer-owned. int(v) silently turns
        # True, 7.0 and "7" into the same page; malformed values may raise.
        # A page listed as both decoded and failed is never authenticated.
        coverage = published.coverage
        total = coverage.total_pages
        decoded = coverage.decoded_pages
        failed = coverage.failed_pages
        if (
            type(total) is not int or not 1 <= total <= 2**53
            or type(decoded) is not tuple or type(failed) is not tuple
            or any(type(v) is not int or not 1 <= v <= total
                   for v in (*decoded, *failed))
            or len(set(decoded)) != len(decoded)
            or len(set(failed)) != len(failed)
            or not set(decoded).isdisjoint(failed)
            or coverage.document_id != published.revision.document_id
            or coverage.revision_id != revision_id
            or coverage.state not in ("complete", "partial")
            # A producer's COMPLETE decode receipt must cover the whole
            # original PDF. A subset marked complete can falsely certify
            # source-page universe completeness even if the requested page
            # itself was decoded. PARTIAL retains its separate valid scope.
            or (coverage.state == "complete" and (
                bool(failed) or len(decoded) != total
                or decoded != tuple(range(1, total + 1))
            ))
            or page_1_based > total or page_1_based not in decoded
        ):
            raise ValueError("original_source_page_outside_producer_coverage")
        return published,raw

    def original_native_amenity_dimension_chains(
        self, *, revision_id: str, detail_page_1_based: int,
        source_vertical_dimension_segments: dict,
        source_horizontal_dimension_segments: dict,
    ) -> dict:
        """Reissue native arrowhead-to-arrowhead figured chains from source.

        Unlike copying a '92 mm wall thickness' nominal text, this reads
        the two actual short-figure arrow intervals surrounding each main
        figured span directly from the sealed SourceVisibilityProducer.
        The result intentionally cannot pick an internal finished wall or
        promote a floor/ceiling m² quantity.
        """
        published,raw=self._source_revision(
            revision_id,page_1_based=detail_page_1_based)
        out=audit_original_native_orthogonal_dimension_chains(
            raw,expected_sha256=published.revision.source_sha256,
            page_1_based=detail_page_1_based,
            vertical=source_vertical_dimension_segments,
            horizontal=source_horizontal_dimension_segments,
        )
        return {
            **out,
            "source_document_id":published.revision.document_id,
            "source_revision_id":revision_id,
            "source_snapshot_id":published.snapshot.snapshot_id,
            "source_figured_chain_material_or_finished_face_issuer":False,
            "new_firm_quantities":0,
        }

    def original_figured_detail_plan_candidate(
        self, *, revision_id: str, detail_page_1_based: int,
        first_dimension: dict, second_dimension: dict,
        original_room_word_address: tuple[int,int,int],
        original_finish_word_address: tuple[int,int,int],
        plan_enclosure_bbox_pdf_pts: tuple[float,float,float,float],
    ) -> dict:
        """Independently printed figured mm plus native arrowhead witnesses.

        A diagnostic area is genuine arithmetic derived from original
        figured source text, but can NEVER be used to identify a room or
        finish without existing W4 source-face and physical-room proof.
        """
        published,raw=self._source_revision(
            revision_id,page_1_based=detail_page_1_based)
        result=audit_original_figured_detail_plan_pair(
            raw,expected_sha256=published.revision.source_sha256,
            page_1_based=detail_page_1_based,
            first_dimension=first_dimension,second_dimension=second_dimension,
            original_room_word_address=original_room_word_address,
            original_finish_word_address=original_finish_word_address,
            plan_enclosure_bbox_pdf_pts=plan_enclosure_bbox_pdf_pts,
        )
        return {
            **result,
            "source_document_id":published.revision.document_id,
            "source_revision_id":revision_id,
            "source_snapshot_id":published.snapshot.snapshot_id,
            "metric_figured_area_candidate_only":True,
            "original_detail_to_main_floor_W4_binding_granted":False,
            "new_firm_quantities":0,
        }

    def original_figured_detail_face_rival_census(
        self, *, revision_id: str,
        detail_page_1_based: int,
        first_dimension: dict, second_dimension: dict,
        original_room_word_address: tuple[int,int,int],
        original_finish_word_address: tuple[int,int,int],
        plan_enclosure_bbox_pdf_pts: tuple[float,float,float,float],
        competing_original_wall_face_families: tuple[dict,...],
    ) -> dict:
        """Reissue original figured dimensions and all real face rivals.

        This method deliberately has NO input for a caller-passed "verified"
        figure receipt, family winner, room area, wall snap or answer. Both
        independent dimension and original path-item provenance are decoded
        fresh from the same sealed SourceVisibilityProducer original revision.
        """
        published,raw=self._source_revision(
            revision_id,page_1_based=detail_page_1_based)
        figure=self.original_figured_detail_plan_candidate(
            revision_id=revision_id,detail_page_1_based=detail_page_1_based,
            first_dimension=first_dimension,second_dimension=second_dimension,
            original_room_word_address=original_room_word_address,
            original_finish_word_address=original_finish_word_address,
            plan_enclosure_bbox_pdf_pts=plan_enclosure_bbox_pdf_pts,
        )
        result=audit_original_figured_detail_face_rivals(
            raw,source_sha256=published.revision.source_sha256,
            original_figure_receipt=figure,page_1_based=detail_page_1_based,
            competing_original_wall_face_families=
                competing_original_wall_face_families,
        )
        return {
            **result,
            "source_document_id":published.revision.document_id,
            "source_revision_id":revision_id,
            "source_snapshot_id":published.snapshot.snapshot_id,
            "source_original_detail_figure_receipt":figure,
            "source_finished_net_area_m2":None,
            "source_canonical_room_same_identity_issued":False,
            "new_firm_quantities":0,
        }

    def original_amenity_figured_wall_note_face_handoff(
        self, *, revision_id: str, detail_page_1_based: int,
        first_dimension: dict, second_dimension: dict,
        original_room_word_address: tuple[int,int,int],
        original_finish_word_address: tuple[int,int,int],
        plan_enclosure_bbox_pdf_pts: tuple[float,float,float,float],
        competing_original_wall_face_families: tuple[dict,...],
        original_vertical_dimension_chain: dict,
        original_horizontal_dimension_chain: dict,
    ) -> dict:
        """Return all original wall-finish rivals plus TRUE arrow-tip chain.

        This is a source-only constraint set for GPT1: no unit calibration,
        guessed 92mm stud wall, automatic inner/outer election or published
        customer finish area. Re-reads original bytes and both independent
        source diagnostic issuers from the same immutable revision.
        """
        published,_=self._source_revision(
            revision_id,page_1_based=detail_page_1_based)
        faces=self.original_figured_detail_face_rival_census(
            revision_id=revision_id,detail_page_1_based=detail_page_1_based,
            first_dimension=first_dimension,second_dimension=second_dimension,
            original_room_word_address=original_room_word_address,
            original_finish_word_address=original_finish_word_address,
            plan_enclosure_bbox_pdf_pts=plan_enclosure_bbox_pdf_pts,
            competing_original_wall_face_families=
                competing_original_wall_face_families,
        )
        notes=self.original_native_amenity_dimension_chains(
            revision_id=revision_id,detail_page_1_based=detail_page_1_based,
            source_vertical_dimension_segments=
                original_vertical_dimension_chain,
            source_horizontal_dimension_segments=
                original_horizontal_dimension_chain,
        )
        result=audit_original_figured_wall_note_alignment(faces,notes)
        ft2_inside_face=audit_original_ft2_internal_wall_face_basis(faces,notes)
        return {
            **result,
            "source_FT2_inside_finished_wall_face_takeoff_basis":ft2_inside_face,
            "original_source_sha256":published.revision.source_sha256,
            "source_document_id":published.revision.document_id,
            "source_revision_id":revision_id,
            "source_snapshot_id":published.snapshot.snapshot_id,
            "original_dimension_and_face_rivals":faces,
            "original_true_arrow_tip_dimension_chains":notes,
            "source_finished_net_floor_m2_issued":None,
            "physical_room_same_identity_issued":False,
            "new_firm_quantities":0,
        }

    def original_amenity_detail_vs_floor_source_candidates(
        self, *, revision_id: str,
        detail_page_1_based: int,
        floor_page_1_based: int,
        first_dimension: dict, second_dimension: dict,
        detail_room_word_address: tuple[int,int,int],
        detail_finish_word_address: tuple[int,int,int],
        detail_plan_enclosure_bbox_pdf_pts: tuple[float,float,float,float],
        detail_wall_face_family_candidates: tuple[dict,...],
        original_floor_wall_path_ids: tuple[str,...],
        original_floor_room_word_address: tuple[int,int,int],
        original_floor_door_word_address: tuple[int,int,int],
        original_detail_door_word_address: tuple[int,int,int],
        room_literal: str, door_literal: str,
        original_detail_finish_code_literal: str,
    ) -> dict:
        """Original figure + true source face families + named plan caption.

        This replays the original producer's bytes and revision twice; it
        takes no caller-prepared "proven" material or physical-room receipt.
        Similar geometry/room labels never bypass W4 face membership.
        """
        published,raw=self._source_revision(
            revision_id,page_1_based=floor_page_1_based)
        other,_=self._source_revision(
            revision_id,page_1_based=detail_page_1_based)
        if published.revision.source_sha256!=other.revision.source_sha256:
            raise ValueError("independent_source_amenity_detail_root_conflict")
        rivals=self.original_figured_detail_face_rival_census(
            revision_id=revision_id,detail_page_1_based=detail_page_1_based,
            first_dimension=first_dimension,second_dimension=second_dimension,
            original_room_word_address=detail_room_word_address,
            original_finish_word_address=detail_finish_word_address,
            plan_enclosure_bbox_pdf_pts=detail_plan_enclosure_bbox_pdf_pts,
            competing_original_wall_face_families=
                detail_wall_face_family_candidates,
        )
        result=audit_original_detail_vs_main_source_room_candidate(
            raw,source_sha256=published.revision.source_sha256,
            original_floor_page=floor_page_1_based,
            original_detail_page=detail_page_1_based,
            floor_source_edge_ids=original_floor_wall_path_ids,
            original_floor_room_word_address=original_floor_room_word_address,
            original_detail_room_word_address=detail_room_word_address,
            original_floor_door_word_address=original_floor_door_word_address,
            original_detail_door_word_address=original_detail_door_word_address,
            original_detail_figure_face_receipt=rivals,
            source_room_literal=room_literal,
            original_door_code_literal=door_literal,
            original_detail_finish_code_literal=
                original_detail_finish_code_literal,
        )
        return {
            **result,
            "source_document_id":published.revision.document_id,
            "source_revision_id":revision_id,
            "source_snapshot_id":published.snapshot.snapshot_id,
            "source_original_figure_and_face_ancestry":rivals,
            "source_main_floor_room_W4_issuer_granted":False,
            "source_detail_to_physical_room_identity_issued":False,
            "new_firm_quantities":0,
        }

    def original_room_ink_graph(
        self, *, revision_id: str, page_1_based: int,
        original_source_edge_ids: tuple[str,...],
    ) -> dict:
        published,raw=self._source_revision(revision_id,page_1_based=page_1_based)
        graph=audit_original_room_edge_graph(
            raw,source_sha256=published.revision.source_sha256,
            page_1_based=page_1_based,source_edge_ids=original_source_edge_ids)
        return {
            **graph,
            "source_document_id":published.revision.document_id,
            "source_revision_id":revision_id,
            "source_snapshot_id":published.snapshot.snapshot_id,
            "source_native_pdf_graph_is_not_measurement_authority":True,
        }

    def original_room_doorway_source_ancestry(
        self, *, revision_id: str, original_floor_page_1_based: int,
        original_second_page_1_based: int,
        original_floor_source_edge_ids: tuple[str,...],
        original_second_source_edge_ids: tuple[str,...],
        original_translation_pdf_pts: tuple[float,float],
    ) -> dict:
        """Retain real five-stroke doorway evidence, including the p11 rival.

        Never silently elect the geometrically nearest printed wall segment.
        The public GitHub checkout cannot invoke this without original bytes,
        and this producer verifies those bytes before inspecting either page.
        """
        published,raw=self._source_revision(
            revision_id,page_1_based=original_floor_page_1_based)
        other,_=self._source_revision(
            revision_id,page_1_based=original_second_page_1_based)
        if other.revision.source_sha256!=published.revision.source_sha256:
            raise ValueError("original_source_doorway_page_root_disagreement")
        result=audit_gpt2_original_room_doorway_ancestry_pair(
            raw,expected_sha256=published.revision.source_sha256,
            floor_page_1_based=original_floor_page_1_based,
            second_page_1_based=original_second_page_1_based,
            original_floor_source_edge_ids=original_floor_source_edge_ids,
            original_second_source_edge_ids=original_second_source_edge_ids,
            original_translation_pdf_pts=original_translation_pdf_pts,
        )
        return {
            **result,
            "source_document_id":published.revision.document_id,
            "source_revision_id":revision_id,
            "source_snapshot_id":published.snapshot.snapshot_id,
        }

    def original_rcp_ink_graph(
        self, *, revision_id: str, page_1_based: int,
        viewport_id: str, source_boundary_edge_ids: tuple[str,...],
        original_source_grid_edge_ids: tuple[str,...]=(),
    ) -> dict:
        self._source_revision(revision_id,page_1_based=page_1_based)
        return audit_original_rcp_ceiling_ink(
            self._source,revision_id=revision_id,
            original_rcp_page=page_1_based,
            original_rcp_viewport_id=viewport_id,
            boundary_source_ids=source_boundary_edge_ids,
            grid_source_ids=original_source_grid_edge_ids,
        )

    def original_floor_finish_ink_handoff(
        self, *, revision_id: str,
        floor_page_1_based: int, finish_page_1_based: int,
        source_floor_wall_ids: tuple[str,...],
        source_finish_wall_ids: tuple[str,...],
        independent_cross_sheet_registration: dict,
        source_translation_pdf_pts: tuple[float,float],
        material_authority,
        source_definition_selector,
        source_occurrence_selector,
        source_finish_code: str,
    ) -> dict:
        # A cross-sheet floor/finish receipt must actually involve two
        # distinct original pages. Re-reading one native page twice can
        # never independently authenticate a physical room correspondence.
        # Keep this fail-closed check before either source graph is issued.
        if floor_page_1_based == finish_page_1_based:
            raise ValueError("original_source_floor_finish_distinct_pages_required")
        floor=self.original_room_ink_graph(
            revision_id=revision_id,page_1_based=floor_page_1_based,
            original_source_edge_ids=source_floor_wall_ids)
        finish=self.original_room_ink_graph(
            revision_id=revision_id,page_1_based=finish_page_1_based,
            original_source_edge_ids=source_finish_wall_ids)
        registration=audit_gpt2_original_cross_sheet_ring_correspondence(
            floor,finish,
            original_source_registration=independent_cross_sheet_registration,
            translation_pdf_pts=source_translation_pdf_pts,
        )
        return {
            "status":"original_source_floor_finish_compilation_shadow_only",
            "floor_original_source_graph":floor,
            "finish_original_source_graph":finish,
            "original_registration_evidence":registration,
            "source_material_handoff":audit_gpt2_source_material_floor_handoff(
                registration,material_authority=material_authority,
                definition_selector=source_definition_selector,
                occurrence_selector=source_occurrence_selector,
                original_finish_code=source_finish_code,
            ),
            "new_firm_quantities":0,
            "physical_floor_or_ceiling_issued":False,
            "source_verified_not_customer_verified":True,
        }


    def original_doorway_bound_floor_finish_handoff(
        self, *, revision_id: str,
        floor_page_1_based: int, finish_page_1_based: int,
        original_floor_doorway_ring: dict,
        original_finish_doorway_ring: dict,
        independent_cross_sheet_registration: dict,
        original_translation_pdf_pts: tuple[float,float],
        material_authority,
        source_definition_selector,
        source_occurrence_selector,
        source_finish_code: str,
    ) -> dict:
        # Reconfirm the producer's source root/page coverage before
        # examining separately SHA-authenticated doorway receipts.
        floor,_=self._source_revision(
            revision_id,page_1_based=floor_page_1_based)
        finish,_=self._source_revision(
            revision_id,page_1_based=finish_page_1_based)
        expected_root=floor.revision.source_sha256
        if floor_page_1_based==finish_page_1_based:
            raise ValueError("original_source_doorway_distinct_pages_required")
        # The original jamb-bound ring producer emits a typed native page.
        # A matching SHA alone cannot authorize a ring from a DIFFERENT
        # floor/finish sheet in this sealed source-visibility compilation.
        if any(
            type(row) is not dict
            or row.get("status")!="source_jamb_bound_open_door_perimeter_candidate_only"
            or type(row.get("original_page_1_based")) is not int
            or row["original_page_1_based"]!=page
            for row,page in (
                (original_floor_doorway_ring,floor_page_1_based),
                (original_finish_doorway_ring,finish_page_1_based),
            )
        ):
            raise ValueError("original_source_doorway_compiler_page_receipt_conflict")
        if (finish.revision.source_sha256!=expected_root or
                any(row.get("original_source_sha256")!=expected_root
                    for row in (original_floor_doorway_ring,
                                original_finish_doorway_ring))):
            raise ValueError("original_source_doorway_handoff_revision_root_conflict")
        # A page number and SHA copied into a caller dictionary are not
        # proof that its side IDs and polygon are the original printed ink.
        # Reissue BOTH open perimeters from the sealed original PDF, then
        # require exact native side/vertex/gap correspondence before joining.
        for candidate, page in (
            (original_floor_doorway_ring, floor_page_1_based),
            (original_finish_doorway_ring, finish_page_1_based),
        ):
            ids = candidate.get("original_source_perimeter_side_ids")
            if (type(ids) is not tuple or len(ids) < 2
                    or len(ids) > 120000 or any(type(v) is not str for v in ids)):
                raise ValueError("original_source_doorway_compiler_native_perimeter_receipt_conflict")
            try:
                graph = self.original_room_ink_graph(
                    revision_id=revision_id, page_1_based=page,
                    original_source_edge_ids=ids,
                )
            except (ValueError, TypeError, KeyError, IndexError, OverflowError, AttributeError):
                raise ValueError(
                    "original_source_doorway_compiler_native_perimeter_receipt_conflict"
                ) from None
            if not _original_doorway_ring_matches_reissued_native_graph(candidate, graph):
                raise ValueError("original_source_doorway_compiler_native_perimeter_receipt_conflict")
        joining=audit_gpt2_original_doorway_bound_floor_finish_correspondence(
            original_floor_doorway_ring,original_finish_doorway_ring,
            source_registration=independent_cross_sheet_registration,
            translation_pdf_pts=original_translation_pdf_pts,
        )
        return {
            "status":"original_source_doorway_bound_floor_finish_shadow_only",
            "source_geometry_correspondence":joining,
            "source_material_handoff":audit_gpt2_source_material_floor_handoff(
                joining,
                material_authority=material_authority,
                definition_selector=source_definition_selector,
                occurrence_selector=source_occurrence_selector,
                original_finish_code=source_finish_code,
            ),
            "original_source_sha256":expected_root,
            "new_firm_quantities":0,
            "source_virtual_door_connectors_are_structural":False,
            "customer_floor_finish_area_issued":False,
        }


    def source_closed_original_ft_handoff_for_gpt1(
        self, *, revision_id: str,
        original_floor_page_1_based: int,
        source_cross_sheet_receipt: dict,
        source_material_receipt: dict,
        source_material_authority,
        source_definition_selector,
        source_occurrence_selector,
        original_finish_code: str,
        canonical_rooms,
        physical_room_id: str,
        original_doorway_source_ancestry: dict | None = None,
    ) -> dict:
        """One actual published W4 face + one original FT occurrence.

        Unlike native path proximity, this requires the sealed original
        source-face authority retained by the canonical room composition.
        No caller-provided area, copied wall ID, screenshot, or label can
        mint room ownership or floor-finish quantity authority.
        """
        published,_=self._source_revision(
            revision_id,page_1_based=original_floor_page_1_based)
        if (type(source_cross_sheet_receipt) is not dict or
                source_cross_sheet_receipt.get("original_source_sha256")!=
                    published.revision.source_sha256):
            raise ValueError("source_cross_sheet_root_does_not_match_active_revision")
        if source_cross_sheet_receipt.get(
                "source_real_door_ink_gap_virtual_closure_only") is True:
            rival=original_doorway_source_ancestry
            if (type(rival) is not dict
                    or rival.get("status")!=
                        "original_doorway_all_printed_wall_strokes_match_candidate"
                    or rival.get("original_source_sha256")!=
                        published.revision.source_sha256
                    or rival.get("source_revision_id")!=revision_id
                    or rival.get("source_snapshot_id")!=
                        published.snapshot.snapshot_id
                    or rival.get("original_floor_page")!=original_floor_page_1_based
                    or rival.get("original_other_plan_page")!=
                        source_cross_sheet_receipt.get("original_finish_page")):
                return {
                    "status":"source_original_doorway_ancestry_conflict",
                    "first_failure":"real_original_doorway_stub_disagrees_across_sheets",
                    "original_doorway_source_ancestry":rival,
                    "floor_finish_quantity_granted":False,
                    "new_firm_quantities":0,
                }
        # Independently resolve through the exact producer-owned source
        # material authority. A copied dict that merely says "authenticated"
        # is not an FT2/FT3 mark or material-definition issuer.
        actual_material=audit_gpt2_source_material_floor_handoff(
            source_cross_sheet_receipt,
            material_authority=source_material_authority,
            definition_selector=source_definition_selector,
            occurrence_selector=source_occurrence_selector,
            original_finish_code=original_finish_code,
        )
        if (type(source_material_receipt) is not dict
                or source_material_receipt!=actual_material
                or actual_material.get("status")!=
                    "source_owned_material_on_original_ink_ring_candidate"):
            return {
                "status":"source_material_issuer_not_replayable",
                "first_failure":"original_FT_mark_or_schedule_source_lineage_unresolved",
                "source_material_first_failure":actual_material.get("first_failure"),
                "floor_finish_quantity_granted":False,
                "new_firm_quantities":0,
            }
        w4=audit_gpt2_w4_bound_original_floor(
            source_cross_sheet_receipt,canonical_rooms=canonical_rooms,
            physical_room_id=physical_room_id)
        if (w4.get("original_revision_id") and
                w4["original_revision_id"]!=revision_id):
            return {"status":"source_W4_revision_mismatch",
                    "source_w4_room_face_claim":w4,
                    "new_firm_quantities":0}
        return {
            "status":"source_W4_FT_handoff_shadow_only",
            "source_w4_room_face_claim":w4,
            "source_gpt1_floor_finish_input":
                audit_gpt2_w4_material_to_gpt1(w4,actual_material),
            "source_original_document_id":published.revision.document_id,
            "source_original_revision_id":revision_id,
            "source_original_snapshot_id":published.snapshot.snapshot_id,
            "new_firm_quantities":0,
            "floor_finish_quantity_granted":False,
        }


    def original_rcp_ceiling_source_handoff_for_gpt1(
        self, *, revision_id: str,
        original_floor_page_1_based: int,
        source_floor_rcp_correspondence: dict,
        original_rcp_ink: dict,
        original_rcp_material: dict,
        source_material_authority,
        source_definition_selector,
        source_occurrence_selector,
        original_ceiling_finish_code: str,
        canonical_rooms,
        physical_room_id: str,
    ) -> dict:
        """Bind original A120-only ceiling geometry to one sealed W4 room.

        The A120 perimeter/m² is independent of p7 floor m². The source
        ceiling area is ALWAYS absent until GPT1 uses independently measured
        physical ceiling zones. No source-pdf scale is guessed.
        """
        published,_=self._source_revision(
            revision_id,page_1_based=original_floor_page_1_based)
        if (type(source_floor_rcp_correspondence) is not dict
                or source_floor_rcp_correspondence.get("original_source_sha256")!=
                    published.revision.source_sha256):
            raise ValueError("source_floor_to_RCP_original_root_mismatch")
        # Source issue is independently repeated from the original,
        # producer-sealed A120 RCP mark and material definition. A copied
        # dict cannot supply source-verified ceiling material ownership.
        actual_rcp_material=audit_original_rcp_source_finish_occurrence(
            original_rcp_ink,authority=source_material_authority,
            definition_selector=source_definition_selector,
            occurrence_selector=source_occurrence_selector,
            original_finish_code=original_ceiling_finish_code,
        )
        if (type(original_rcp_material) is not dict
                or original_rcp_material!=actual_rcp_material
                or actual_rcp_material.get("status")!=
                    "original_rcp_material_in_ceiling_ink_candidate"):
            return {
                "status":"source_RCP_material_issuer_not_replayable",
                "first_failure":"original_A120_schedule_or_mark_source_lineage_unresolved",
                "source_ceiling_area_m2":None,
                "new_firm_quantities":0,
            }
        w4=audit_gpt2_w4_bound_original_floor(
            source_floor_rcp_correspondence,canonical_rooms=canonical_rooms,
            physical_room_id=physical_room_id)
        result=audit_gpt2_w4_original_rcp_ceiling_handoff(
            independently_registered_rcp=source_floor_rcp_correspondence,
            original_rcp_ink=original_rcp_ink,
            original_rcp_material=actual_rcp_material,
            canonical_rooms=canonical_rooms,
            physical_room_id=physical_room_id,
        )
        return {
            "status":"source_W4_original_A120_ceiling_compilation_shadow_only",
            "source_w4_room_face_claim":w4,
            "source_original_rcp_ceiling_input_for_gpt1":result,
            "source_original_document_id":published.revision.document_id,
            "source_original_revision_id":revision_id,
            "source_original_snapshot_id":published.snapshot.snapshot_id,
            "source_ceiling_area_m2":None,
            "new_firm_quantities":0,
        }
