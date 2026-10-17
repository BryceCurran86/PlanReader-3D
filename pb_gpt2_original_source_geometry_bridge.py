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
from tools.diag_gpt2_source_rcp_geometry_shadow import audit_original_rcp_ceiling_ink
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
