"""Independent G17 ink-face to W2 centreline ancestry proof.

This intentionally does not turn a local band/host into a global W4 SAME,
DISTINCT, complete frame, quantity, sealed customer or benchmark score.
"""
from dataclasses import replace
import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_opening_host_frame_authority import SourceG17RightFlankW2Owner
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from test_gptmax_source_face_frame import _fixture


def _source():
    source,composition,producer,bound=_fixture()
    producer._raster_split_frame_shadow=True
    producer._g17_face_w2_owner_shadow=True
    return source,composition,producer,bound


def _evidence(producer,selected):
    return producer.source_g17_right_flank_w2_owner_shadow(
        opening_selector=selected[0],host_binding_selector=selected[2],
    )


def _source_neutral_gate_probe(producer, b):
    """Only tests synthetic fixtures, never emits original PDFs or coordinates."""
    import pb_opening_host_binding_authority as host
    from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
    _sel, opening, _bs, binding = b
    geometry=host._opening_geometry(producer._opening, opening)
    scoped=PhysicalWallCandidateSelector(
        document_id=binding.document_id,revision_id=binding.revision_id,
        source_sha256=binding.source_sha256,snapshot_id=binding.snapshot_id,
        page_id=binding.page_id,decision_scope_id=binding.decision_scope_id,
    )
    base=producer._walls.resolve_scope(scoped)
    supp=producer._supplemental_walls.resolve_scope(scoped)
    visibility=producer._opening.source_visibility_authority()
    from pb_source_observation_authority import ObservationSelector
    support=[]
    for oid in opening.source_observation_ids:
        rec=visibility.resolve_raster_opening_primitive(ObservationSelector(
            document_id=opening.document_id,revision_id=opening.revision_id,
            source_sha256=opening.source_sha256,snapshot_id=opening.snapshot_id,
            observation_id=oid,
        ))
        if rec.observation is not None:
            support.append(rec.observation)
    flanks=host._raster_source_band_flanks(support,geometry)
    baseline=host._resolve_raster_source_band_host(
        producer._opening, opening,base.records,geometry,base.equivalence,
        base.source_observation_ids)
    mixed=host._resolve_opening_local_mixed_scope_source_band(
        producer._opening, opening,geometry,base.records,supp.records,
        base.source_observation_ids,supp.source_observation_ids,
        source_fragment_roles_shadow=True,
    )
    originals=tuple(sorted(set(
        (*base.source_observation_ids,*supp.source_observation_ids))))
    lines=host._authenticated_raster_source_lines(
        producer._opening,opening,originals)
    records=producer._scope_records_by_id(base,binding)
    projections=[]
    from pb_raster_source_wall_frame_projection import source_edge_axis_projection
    for wall_id in binding.member_wall_candidate_ids:
        wall=records.get(wall_id)
        projections.append(wall is not None and
                           source_edge_axis_projection(wall,geometry,lines) is not None)
    return {
        "flank":flanks is not None,
        "baseline_status":baseline.status.value,
        "baseline_bands":len(baseline.bands),
        "mixed_status":mixed.status.value,
        "mixed_bands":len(mixed.bands),
        "selected_members":len(binding.member_wall_candidate_ids),
        "parent_lines":len(lines),
        "source_projection":projections,
        "supp_complete":supp.scope_complete,
    }


def test_source_owned_g17_faces_are_never_copied_from_a_w2_centreline():
    source,composition,producer,bound=_source()
    baseline=tuple(_evidence(producer,b) for b in bound)
    assert all(isinstance(r,SourceG17RightFlankW2Owner) for r in baseline), (
        _source_neutral_gate_probe(producer,bound[0])
    )
    for entry,(_,opening,_selector,binding) in zip(baseline,bound):
        assert entry.opening_identity_id==opening.record_id
        assert entry.host_binding_record_id==binding.record_id
        assert entry.right_wall_candidate_id in binding.member_wall_candidate_ids
        assert len(entry.g17_face_observation_ids)==2
        assert entry.g17_end_observation_id not in entry.g17_face_observation_ids
        assert entry.w2_edge_ids and entry.w2_source_primitive_ids
        assert entry.w2_source_observation_ids
        # Face support is separately native raster-origin ink, not W2 edges.
        assert not set(entry.g17_face_observation_ids)&set(entry.w2_source_observation_ids)
        assert not hasattr(entry,"whole_wall_frame_id")
        assert not hasattr(entry,"installed_area_m2")
    assert tuple(_evidence(producer,b) for b in reversed(bound))==tuple(reversed(baseline))
    # Still no new FIRM installed quantity from local centreline proof.
    assert all(x is None or x.right_wall_candidate_id for x in baseline)


def test_source_g17_to_w2_owner_requires_exact_original_shadow_and_selectors():
    _,comp,producer,bound=_source()
    b=bound[0]
    original=_evidence(producer,b)
    assert original is not None
    producer._source_fragment_roles_shadow=False
    assert _evidence(producer,b) is None
    producer._source_fragment_roles_shadow=True
    producer._raster_split_frame_shadow=False
    assert _evidence(producer,b) is None
    producer._raster_split_frame_shadow=True
    producer._g17_face_w2_owner_shadow=False
    assert _evidence(producer,b) is None
    producer._g17_face_w2_owner_shadow=True
    assert producer.source_g17_right_flank_w2_owner_shadow(
        opening_selector=b[0],
        host_binding_selector=replace(b[2],source_sha256="0"*64),
    ) is None
    assert producer.source_g17_right_flank_w2_owner_shadow(
        opening_selector=b[0],
        host_binding_selector=replace(b[2],opening_identity_id="foreign"),
    ) is None
    with pytest.raises(TypeError,match="exact original"):
        producer.source_g17_right_flank_w2_owner_shadow(
            opening_selector=object(),host_binding_selector=b[2],
        )


@pytest.mark.parametrize("damage",["foreign_scope","missing_w2_parent","missing_face","unknown_endcap"])
def test_source_face_or_w2_ownership_tamper_cannot_grant_local_pier(monkeypatch,damage):
    from pb_migration_contracts import EvidenceResolutionStatus as Status
    from pb_source_observation_authority import ObservationSelector
    from pb_opening_host_frame_authority import OpeningHostFrameProducer
    _,comp,producer,bound=_source()
    b=bound[0]
    assert _evidence(producer,b) is not None
    if damage=="foreign_scope":
        selector=PhysicalWallCandidateSelector(
            document_id=b[3].document_id,revision_id=b[3].revision_id,
            source_sha256=b[3].source_sha256,snapshot_id=b[3].snapshot_id,
            page_id=b[3].page_id,decision_scope_id=b[3].decision_scope_id,
        )
        original=producer._supplemental_walls.resolve_scope(selector)
        monkeypatch.setattr(producer._supplemental_walls,"resolve_scope",
            lambda _sel: replace(original,source_sha256="f"*64))
    elif damage=="missing_w2_parent":
        # All original SOURCE parent lines must be re-proved by the actual
        # producer, never supplied as caller-typed synthetic coordinates.
        import pb_opening_host_binding_authority as host
        monkeypatch.setattr(host,"_authenticated_raster_source_lines",
            lambda *_args: {})
    else:
        visibility=producer._opening.source_visibility_authority()
        old=visibility.resolve_raster_opening_primitive
        def missing(selector):
            result=old(selector)
            o=result.observation
            if (o is not None and
                    ((damage=="missing_face" and o.observation_kind=="raster_wall_band_face")
                    or (damage=="unknown_endcap" and o.observation_kind=="raster_wall_band_end"))):
                return replace(result,status=Status.ABSTAINED,observation=None)
            return result
        monkeypatch.setattr(visibility,"resolve_raster_opening_primitive",missing)
    assert _evidence(producer,b) is None


def test_new_shadow_requires_explicit_boolean_and_sealed_original_source_roles():
    from pb_opening_host_frame_authority import OpeningHostFrameProducer
    _source_visibility,comp,_producer,_bound=_source()
    base=dict(
        physical_opening_authority=comp.physical_opening_authority,
        host_binding_authority=comp.opening_host_binding_authority,
        physical_wall_candidate_authority=comp.physical_wall_candidate_authority,
        supplemental_wall_candidate_authority=comp.supplemental_physical_wall_candidate_authority,
    )
    for invalid in (None,0,1,"true",{},()):
        with pytest.raises(TypeError,match="g17_face_w2_owner_shadow must be a bool"):
            OpeningHostFrameProducer.from_authorities(
                **base,g17_face_w2_owner_shadow=invalid)
    with pytest.raises(ValueError,match="requires both original raster"):
        OpeningHostFrameProducer.from_authorities(
            **base,g17_face_w2_owner_shadow=True)
    selected=OpeningHostFrameProducer.from_authorities(
        **base,raster_split_frame_shadow=True,
        source_fragment_roles_shadow=True,g17_face_w2_owner_shadow=True)
    assert selected._g17_face_w2_owner_shadow is True
    original=OpeningHostFrameProducer.from_authorities(
        **base,raster_split_frame_shadow=True,source_fragment_roles_shadow=True)
    assert original._g17_face_w2_owner_shadow is False
