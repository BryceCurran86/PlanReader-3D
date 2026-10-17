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
from tools.diag_gpt2_original_figured_face_rivals_shadow import (
    audit_original_figured_detail_face_rivals,
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
            type(page_1_based) is not int or page_1_based<1
        ):
            raise ValueError("source_revision_and_page_selector_required")
        published=self._source.published_snapshot_for_revision(revision_id)
        raw=_source_bytes(self._source,revision_id)
        if published is None or raw is None:
            raise ValueError("original_source_revision_sha_or_bytes_unavailable")
        decoded={int(v) for v in published.coverage.decoded_pages}
        if page_1_based not in decoded:
            raise ValueError("original_source_page_outside_producer_coverage")
        return published,raw

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
        if (finish.revision.source_sha256!=expected_root or
                any(row.get("original_source_sha256")!=expected_root
                    for row in (original_floor_doorway_ring,
                                original_finish_doorway_ring))):
            raise ValueError("original_source_doorway_handoff_revision_root_conflict")
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
