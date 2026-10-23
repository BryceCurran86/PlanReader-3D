"""Integrated G17 original raster parent → flank → opening ownership → pier gates.

Source-neutral only. This is a negative downstream acceptance check, not a
replacement for SHA-pinned REV E, SourceVisibilityProducer, host/frame,
physical owner, metric dimension or archived customer replay.
"""
from dataclasses import replace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_gpt2_raster_opening_parent_source_shadow import (
    AuthenticatedRasterOpeningParentLine,
    RasterOpeningParentSourceHandoff,
)
from pb_gpt2_raster_source_flank_band_shadow import (
    reconstruct_raster_source_flank_bands_shadow,
)
from pb_gpt2_g17_opening_source_band_ownership_shadow import (
    OriginalG17OpeningFlankOwnership,
    bind_original_g17_flanks_to_physical_opening_shadow,
)
from pb_gpt2_original_g17_shared_pier_shadow import (
    audit_gpt2_original_g17_shared_piers_shadow,
)

_SHA = "e" * 64


def _line(kind, name, xy):
    return AuthenticatedRasterOpeningParentLine(
        parent_observation_id=name,
        visible_observation_id="visible:" + name,
        observation_kind=kind,
        original_source_primitive_ref="visible:raster_opening_primitive:source:" + name,
        page_id="3",
        geometry_pdf_points=xy,
    )


def _source(*, missing=False):
    lines = (
        _line("raster_wall_band_face", "left-top", (-20., 0., 0., 0.)),
        _line("raster_wall_band_face", "left-bottom", (-20., 2.4, 0., 2.4)),
        _line("raster_wall_band_end", "left-end", (0., 0., 0., 2.4)),
        _line("raster_wall_band_face", "right-top", (30., 0., 50., 0.)),
        _line("raster_wall_band_face", "right-bottom", (30., 2.4, 50., 2.4)),
        _line("raster_wall_band_end", "right-end", (30., 0., 30., 2.4)),
    )
    ids=tuple(sorted(row.parent_observation_id for row in lines))
    return RasterOpeningParentSourceHandoff(
        status="PARTIAL_ABSTAIN" if missing else "SOURCE_ONLY_CANDIDATE",
        source_sha256=_SHA,
        requested_parent_ids=ids + (("missing-owner",) if missing else ()),
        lines=lines,unresolved_parent_ids=("missing-owner",) if missing else (),
        reason_codes=("source_primitive_candidate_not_w4",),
    )


def test_complete_synthetic_ink_flanks_cannot_grant_physical_g17_host_or_customer():
    parents = _source()
    bands = reconstruct_raster_source_flank_bands_shadow(parents)
    assert bands.status=="SOURCE_BAND_GEOMETRY_CANDIDATE"
    assert len(bands.candidates)==2
    assert tuple(b.end_parent_id for b in bands.candidates)==("left-end","right-end")
    assert not bands.physical_wall_granted
    assert not bands.opening_host_granted
    assert not bands.opening_count_granted
    assert not bands.firm_quantity_granted
    owner = OriginalG17OpeningFlankOwnership(
        EvidenceResolutionStatus.ABSTAINED,
        ("original_physical_ownership_missing",),
        "physical-g17-unproved",_SHA,
    )
    result = audit_gpt2_original_g17_shared_piers_shadow({
        "physical-g17-unproved":(owner,parents),
    })
    assert result.status=="ABSTAIN"
    assert result.shadow_only
    assert not any((
        result.entire_original_opening_universe_authenticated,
        result.third_original_owner_excluded,
        result.physical_instance_conflict_exempted,
        result.w4_structural_wall_granted,
        result.opening_host_granted,
        result.opening_count_granted,
        result.metric_area_granted,
        result.customer_release_granted,
    ))


def test_missing_source_parent_propagates_abstention_to_integrated_flanks_and_pier():
    parents=_source(missing=True)
    bands=reconstruct_raster_source_flank_bands_shadow(parents)
    assert bands.status=="ABSTAIN"
    assert bands.candidates==()
    assert "missing-owner" in bands.unresolved_source_parent_ids
    owner=OriginalG17OpeningFlankOwnership(
        EvidenceResolutionStatus.ABSTAINED,("missing-original-parent",),
        "physical-g17-unproved",_SHA,
    )
    shared=audit_gpt2_original_g17_shared_piers_shadow({
        "physical-g17-unproved":(owner,parents),
    })
    assert shared.status=="ABSTAIN"
    assert not shared.w4_structural_wall_granted
    assert not shared.customer_release_granted


def test_synthetic_flanks_must_not_bypass_real_physical_opening_authority():
    parents=_source()
    bands=reconstruct_raster_source_flank_bands_shadow(parents)
    forged=replace(parents,structural_host_granted=True)
    assert reconstruct_raster_source_flank_bands_shadow(forged).status=="ABSTAIN"
    with pytest.raises(TypeError,match="PhysicalOpeningAuthority required"):
        bind_original_g17_flanks_to_physical_opening_shadow(
            object(),original_selector=object(),
            parent_source=parents,source_bands=bands,
        )
    with pytest.raises(TypeError,match="producer-authenticated parent"):
        reconstruct_raster_source_flank_bands_shadow(object())
