"""Source-positive synthetic wall: calculate actual single external wall m²."""
from dataclasses import replace
import pytest

from pb_live_external_physical_net_wall_publication import (
    compose_live_external_physical_net_wall_publication,
)
from pb_live_external_wall_surface_area_quantity_publication import (
    publish_live_per_wall_surface_area_quantities,
    seal_live_per_wall_surface_area_run,
)
from tests.test_live_external_physical_net_wall_publication import _chain


def _produced():
    wall_opening,physical_void,gross,roles,void,source_wall = _chain()
    result=compose_live_external_physical_net_wall_publication(
        wall_opening_composition=wall_opening,
        physical_void_composition=physical_void,
        gross_wall_composition=gross,
        whole_wall_role_composition=roles,
    )
    assert result.quantity_evidence is not None
    return result


def test_full_original_external_wall_and_opening_universe_produces_net_m2():
    original=_produced()
    outputs=publish_live_per_wall_surface_area_quantities(original)
    assert len(outputs)==1
    q=outputs[0]
    assert q.family=="wall_net_area"
    assert q.status=="corroborated"
    assert q.value == original.canonical_walls[0].net_area_m2
    assert q.unit=="m2"
    assert q.input_entity_ids==(original.canonical_walls[0].physical_wall_id,)
    assert q.metadata["commercial_finish_permission"] is False
    assert q.metadata["face_multiplicity"]==1
    assert q.metadata["aggregate_quantity_id"]==original.quantity_evidence.quantity_id


def test_original_net_wall_area_reissues_deterministically():
    original=_produced()
    assert publish_live_per_wall_surface_area_quantities(original)==publish_live_per_wall_surface_area_quantities(original)


@pytest.mark.parametrize("field,bad",[
    ("role","internal"),
    ("net_area_m2",5000.0),
    ("source_sha256","0"*64),
    ("revision_id","stale"),
    ("physical_wall_id","different-original-wall"),
    ("physical_identity_resolved",False),
    ("gross_geometry_record_id",None),
    ("net_polygon_wkb_hex","01030000"),
])
def test_foreign_or_broken_original_wall_cannot_mint_corrupted_net_area(field,bad):
    original=_produced()
    altered=replace(original.canonical_walls[0], **{field:bad})
    assert publish_live_per_wall_surface_area_quantities(
        replace(original,canonical_walls=(altered,))
    )==()


def test_duplicate_physical_wall_cannot_mint_second_wall_surface():
    original=_produced()
    wall=original.canonical_walls[0]
    assert publish_live_per_wall_surface_area_quantities(
        replace(original,canonical_walls=(wall,wall))
    )==()


def test_source_total_must_match_exact_union_of_wall_net_m2():
    original=_produced()
    q=original.quantity_evidence
    changed=replace(q,value=q.value+1.0)
    assert publish_live_per_wall_surface_area_quantities(
        replace(original,quantity_evidence=changed)
    )==()


def test_missing_original_completeness_receipt_never_mints_per_wall_surface():
    original=_produced()
    q=original.quantity_evidence
    changed=replace(q,metadata={**q.metadata,"external_wall_ids":()})
    assert publish_live_per_wall_surface_area_quantities(
        replace(original,quantity_evidence=changed)
    )==()


def test_original_one_wall_source_quantity_seals_full_physical_m2_lineage():
    original=_produced()
    sealed=seal_live_per_wall_surface_area_run(
        original,workspace_id=7,project_id="synthetic-source-wall-project"
    )
    assert len(sealed.quantities)==1
    row=sealed.quantities[0]
    assert row.family=="wall_net_area"
    assert row.lineage_ok
    assert not row.abstained
    assert row.value==original.canonical_walls[0].net_area_m2
    assert row.object_identity_refs==(original.canonical_walls[0].canonical_wall_id,)
    assert row.source_page==original.canonical_walls[0].page_id
    assert row.source_sha256==original.canonical_walls[0].source_sha256


@pytest.mark.parametrize("original_blockers", (
    ("original_wall_identity_conflict",),
    ("opening_host_unresolved", "original_wall_identity_conflict"),
    ("stale_original_revision",),
))
def test_blocked_original_aggregate_cannot_launder_per_wall_net_m2(
    original_blockers,
):
    """A numeric corroborated aggregate with conflicts is NOT publication."""
    produced=_produced()
    original=produced.quantity_evidence
    assert original is not None
    assert not original.abstained
    assert publish_live_per_wall_surface_area_quantities(produced)
    blocked=replace(original,blocking_reasons=original_blockers)
    assert blocked.value==original.value
    assert blocked.status==original.status=="corroborated"
    rival=replace(produced,quantity_evidence=blocked)
    assert publish_live_per_wall_surface_area_quantities(rival)==()
    with pytest.raises(
        ValueError,match="no source-complete original external wall surfaces",
    ):
        seal_live_per_wall_surface_area_run(
            rival,workspace_id=7,project_id="synthetic-source-wall-project",
        )
    # An invalid retrospective claim cannot mutate the actual source result.
    assert produced.quantity_evidence.blocking_reasons==()
    assert len(publish_live_per_wall_surface_area_quantities(produced))==1
