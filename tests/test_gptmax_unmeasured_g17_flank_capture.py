"""Contract tests for opt-in source-owned G17 flank capture (never a host)."""
from __future__ import annotations

from types import SimpleNamespace as Obj

import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
import pb_opening_local_g17_wall_shadow as g17


FACES = (
    ("f1", "raster_wall_band_face", (0.0, 0.0, 5.0, 0.0)),
    ("f2", "raster_wall_band_face", (0.0, 2.0, 5.0, 2.0)),
    ("f3", "raster_wall_band_face", (10.0, 0.0, 15.0, 0.0)),
    ("f4", "raster_wall_band_face", (10.0, 2.0, 15.0, 2.0)),
)
ENDS = (
    ("e1", "raster_wall_band_end", (5.0, 0.0, 5.0, 2.0)),
    ("e2", "raster_wall_band_end", (10.0, 0.0, 10.0, 2.0)),
)


def scope(monkeypatch, *, ink=(True, True), physical_id="physical-one", observed=(*FACES, *ENDS),
          area=None, missing_area=True):
    obs = {
        oid: Obj(observation_id=oid, observation_kind=kind, geometry=geometry,
                 page_id="3")
        for oid, kind, geometry in observed
    }
    ids = tuple(sorted(obs))
    opening = Obj(record_id="physical-one", source_observation_ids=ids)
    records = tuple(obs.values())
    physical = Obj(
        _raster_primitive_snapshot_records=lambda seed: (records, ()),
        _raster_framed_candidates_for=lambda seed, all_records: (Obj(source_observation_ids=ids),),
        prove_existence=lambda selector: Obj(
            status=Status.CORROBORATED, existence_record=opening,
        ),
    )
    visibility = Obj(resolve_raster_opening_primitive=lambda selector: Obj(
        status=Status.CORROBORATED, observation=obs[selector.observation_id],
    ))
    producer = Obj(physical_opening_authority=lambda: physical, authority=lambda: visibility)
    published = Obj(
        revision=Obj(document_id="document", revision_id="revision", source_sha256="a" * 64),
        snapshot=Obj(snapshot_id="snapshot"),
        raster_opening_primitive_observation_ids=(ids[0],),
    )

    class Labels:
        @classmethod
        def from_source_visibility_producer(cls, source):
            return Obj(publish_scope=lambda selector: Obj(
                status=Status.CORROBORATED if not missing_area else Status.ABSTAINED,
                evidence=Obj(area_m2=area) if not missing_area else None,
            ))

    monkeypatch.setattr(OpeningLabelDimensionProducer, "from_source_visibility_producer",
                        Labels.from_source_visibility_producer)
    monkeypatch.setattr(g17, "build_opening_local_g17_wall_shadow", lambda src, sel, **kwargs: Obj(
        physical_opening_id=physical_id,
        flanks=tuple(Obj(
            source_ink_supported=value,
            source_observation_ids=ids,
        ) for value, ids in zip(ink, (("f1", "f2", "e1"), ("f3", "f4", "e2")))),
    ))
    return producer, published


def boxes(monkeypatch, **kwargs):
    src, published = scope(monkeypatch, **kwargs)
    return SourceVisibilityProducer._proven_raster_opening_flank_boxes(
        src, published, "3", include_unmeasured_ink_closed_flanks_shadow=True,
    )


def test_default_unmeasured_capture_stays_empty(monkeypatch):
    src, published = scope(monkeypatch)
    assert SourceVisibilityProducer._proven_raster_opening_flank_boxes(
        src, published, "3",
    ) == ()


def test_source_closed_and_both_solid_flanks_enter_candidate_capture(monkeypatch):
    assert boxes(monkeypatch) == (
        ("horizontal", (0.0, 0.0, 5.0, 2.0)),
        ("horizontal", (10.0, 0.0, 15.0, 2.0)),
    )


@pytest.mark.parametrize("ink", [(False, True), (True, False), (False, False), ()])
def test_no_single_flank_or_missing_ink_can_enter_w4(monkeypatch, ink):
    assert boxes(monkeypatch, ink=ink) == ()


def test_original_physical_id_mismatch_refuses_capture(monkeypatch):
    assert boxes(monkeypatch, physical_id="foreign-original-opening") == ()


@pytest.mark.parametrize("observed", [
    FACES, (*FACES, ENDS[0]), (*FACES[:-1], *ENDS),
    (*FACES[:2], *ENDS),
    (*FACES, *ENDS, ("fifth", "raster_wall_band_face", (0, 3, 5, 3))),
])
def test_missing_or_competing_opening_source_members_abstain(monkeypatch, observed):
    # The current opening-local producer is the authority for real source
    # closure. These mocks deliberately cannot confer source-positive ink.
    assert boxes(monkeypatch, observed=observed, ink=(False, True)) == ()


def test_historic_measured_area_path_is_not_conditional_on_new_flag(monkeypatch):
    src, published = scope(monkeypatch, area=1.8, missing_area=False, ink=())
    for flag in (False, True):
        result = SourceVisibilityProducer._proven_raster_opening_flank_boxes(
            src, published, "3",
            include_unmeasured_ink_closed_flanks_shadow=flag,
        )
        assert result == (
            ("horizontal", (0.0, 0.0, 5.0, 2.0)),
            ("horizontal", (10.0, 0.0, 15.0, 2.0)),
        )


@pytest.mark.parametrize("invalid", ["true", 1, 0, None, [], {}, object()])
def test_capture_flag_must_be_explicit_boolean(monkeypatch, invalid):
    src, published = scope(monkeypatch)
    with pytest.raises(TypeError):
        SourceVisibilityProducer._proven_raster_opening_flank_boxes(
            src, published, "3",
            include_unmeasured_ink_closed_flanks_shadow=invalid,
        )
    with pytest.raises(TypeError):
        src_real = SourceVisibilityProducer(producer_method="test", producer_version="1")
        src_real.augment_with_raster_visible_segments(
            "not-published", include_unmeasured_ink_closed_flanks_shadow=invalid,
        )
    with pytest.raises(TypeError):
        PhysicalWallCandidateProducer.from_source_visibility_producer(
            src_real, include_unmeasured_ink_closed_flanks_shadow=invalid,
        )
    with pytest.raises(TypeError):
        compose_live_wall_opening_authority(
            source_visibility_producer=src_real, revision_id="revision",
            page_ids=("3",), include_unmeasured_ink_closed_flanks_shadow=invalid,
        )


def test_first_source_support_is_not_a_valid_existence_selector(monkeypatch):
    # The original physical producer can re-prove one source observation but
    # abstain on another member of the SAME existing G17 source support set.
    # Never select the lexical first unproven observation.
    src, published = scope(monkeypatch)
    physical = src.physical_opening_authority()
    original = physical.prove_existence
    physical.prove_existence = (
        lambda selector: Obj(status=Status.ABSTAINED, existence_record=None)
        if selector.observation_id == "e1" else original(selector)
    )
    examined = []
    def authentic_ink(source, selector, **kwargs):
        examined.append(selector.observation_id)
        return Obj(physical_opening_id="physical-one",
                   flanks=(Obj(source_ink_supported=True),
                           Obj(source_ink_supported=True)))
    monkeypatch.setattr(g17, "build_opening_local_g17_wall_shadow", authentic_ink)
    result = SourceVisibilityProducer._proven_raster_opening_flank_boxes(
        src, published, "3", include_unmeasured_ink_closed_flanks_shadow=True,
    )
    assert examined == ["e2"]
    assert len(result) == 2


def test_no_own_source_positive_existence_never_nominates_a_wall(monkeypatch):
    src, published = scope(monkeypatch)
    physical=src.physical_opening_authority()
    physical.prove_existence = lambda selector: Obj(
        status=Status.ABSTAINED, existence_record=None)
    monkeypatch.setattr(g17, "build_opening_local_g17_wall_shadow",
                        lambda *args, **kwargs: pytest.fail(
                            "unproven source selectors must not enter paint check"))
    assert SourceVisibilityProducer._proven_raster_opening_flank_boxes(
        src, published, "3",
        include_unmeasured_ink_closed_flanks_shadow=True,
    ) == ()


def test_source_selector_conflict_for_same_record_fails_closed(monkeypatch):
    src, published = scope(monkeypatch)
    physical=src.physical_opening_authority()
    original=physical.prove_existence
    def contradict(selector):
        if selector.observation_id == "e2":
            return Obj(status=Status.CORROBORATED,
                       existence_record=Obj(
                           record_id="physical-one",
                           source_observation_ids=("foreign-source",)))
        return original(selector)
    physical.prove_existence=contradict
    with pytest.raises(RuntimeError):
        SourceVisibilityProducer._proven_raster_opening_flank_boxes(
            src, published, "3",
            include_unmeasured_ink_closed_flanks_shadow=True,
        )


@pytest.mark.parametrize("ink,expected_partial,expected_positive", [
    ((False,True), ("left",), ("right",)),
    ((True,False), ("right",), ("left",)),
    ((False,False), ("left","right"), ()),
    ((True,True), (), ("left","right")),
])
def test_each_independently_painted_original_flank_has_own_source_status(
        monkeypatch, ink, expected_partial, expected_positive):
    src,published=scope(monkeypatch,ink=ink)
    all_full, unclosed_ink, independently_positive = (
        SourceVisibilityProducer._proven_raster_opening_flank_boxes(
            src,published,"3",
            include_unmeasured_ink_closed_flanks_shadow=True,
            include_original_partial_jamb_receipts_shadow=True,
        )
    )
    # A strong source-ink claim never implies that the other wall flank's
    # source paint is complete, nor that a structural wall host is proved.
    left=("horizontal",(0.0,0.0,5.0,2.0))
    right=("horizontal",(10.0,0.0,15.0,2.0))
    lookup={"left":left,"right":right}
    assert set(independently_positive)=={lookup[x] for x in expected_positive}
    assert {tuple(item[:2]) for item in unclosed_ink}=={
        lookup[x] for x in expected_partial
    }
    assert set(all_full)==({left,right} if all(ink) else set())


def test_default_source_capture_stays_all_or_nothing_for_unmeasured(monkeypatch):
    src,published=scope(monkeypatch,ink=(True,False))
    # The old default and original simple shadow contract cannot quietly
    # claim the missing opposite physical flank.
    assert SourceVisibilityProducer._proven_raster_opening_flank_boxes(
        src,published,"3") == ()
    assert SourceVisibilityProducer._proven_raster_opening_flank_boxes(
        src,published,"3",include_unmeasured_ink_closed_flanks_shadow=True) == ()
