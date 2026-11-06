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
    return source,composition,producer,bound


def _evidence(producer,selected):
    return producer.source_g17_right_flank_w2_owner_shadow(
        opening_selector=selected[0],host_binding_selector=selected[2],
    )


def test_source_owned_g17_faces_are_never_copied_from_a_w2_centreline():
    source,composition,producer,bound=_source()
    baseline=tuple(_evidence(producer,b) for b in bound)
    assert all(isinstance(r,SourceG17RightFlankW2Owner) for r in baseline)
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
