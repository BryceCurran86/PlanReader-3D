"""Test Lot 16 South Wall structural host/frame continuity across all three openings.

Under GPT MAX structural direction (SPRINT directive 2 November 2026):
- 2b2a91e8 (1215 SGW window)
- a68d0b7d (870 Door)
- 993560b2 (2127 STACKER)
all share the unified South Wall perimeter host frame and its four authenticated
solid pier/jamb members along y = 427.8 pt.
"""
import hashlib
from pathlib import Path
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_opening_host_frame_authority import OpeningHostFrameProducer
from pb_source_observation_authority import ObservationSelector


def test_lot16_south_wall_frame_continuity():
    pdf_path = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
    if not pdf_path.exists():
        pytest.skip("Private Lot 16 original PDF not available in local workspace")

    source_bytes = pdf_path.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    assert source_sha == "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"

    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version="1",
        raster_paired_outer_faces_shadow=True,
    )
    initial = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{source_sha[:32]}",
        source_bytes=source_bytes,
        source_locator="memory://pdf",
        page_ids=(3,),
    )

    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=initial.revision.revision_id,
        page_ids=("3",),
        include_unmeasured_ink_closed_flanks_shadow=True,
        source_fragment_roles_shadow=True,
    )

    published = source.published_snapshot_for_revision(initial.revision.revision_id)

    producer = OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=composition.physical_opening_authority,
        host_binding_authority=composition.opening_host_binding_authority,
        physical_wall_candidate_authority=composition.physical_wall_candidate_authority,
        supplemental_wall_candidate_authority=composition.supplemental_physical_wall_candidate_authority,
        raster_split_frame_shadow=True,
        source_fragment_roles_shadow=True,
    )

    # South Wall openings
    south_openings = {
        "1215_sgw": "2b2a91e8",
        "870_door": "a68d0b7d",
        "2127_stacker": "993560b2",
    }

    frames = {}
    for name, key in south_openings.items():
        binding = next((b for b in composition.opening_bindings if key in b.opening_identity_id), None)
        assert binding is not None, f"Binding not found for {name} ({key})"

        binding_sel = composition.binding_selectors[binding.opening_identity_id]
        obs_sel = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=binding.representative_observation_id,
        )

        res = producer.publish(opening_selector=obs_sel, host_binding_selector=binding_sel)
        assert res.status is EvidenceResolutionStatus.CORROBORATED, f"{name} failed with reasons: {res.reason_codes}"
        assert res.evidence is not None, f"{name} has no frame evidence"
        frames[name] = res.evidence

    # All three must share the identical whole-wall frame ID
    frame_ids = {f.whole_wall_frame_id for f in frames.values()}
    assert len(frame_ids) == 1, f"Expected unified frame ID, got: {frame_ids}"
    shared_frame_id = next(iter(frame_ids))
    assert shared_frame_id == "opening_host_whole_wall_frame_v1_6ffcf867640d646256337ae50c33302f"

    # Verify frame geometry
    ev = frames["1215_sgw"]
    assert pytest.approx(ev.origin_pt[1], abs=0.5) == 427.8
    assert pytest.approx(ev.axis_unit[0], abs=1e-5) == 1.0
    assert pytest.approx(ev.axis_unit[1], abs=1e-5) == 0.0

    # Verify the four solid piers/jambs are in whole_wall_candidate_ids
    expected_members = {
        "wall_2906b11862b31f7f6224",  # West jamb
        "wall_ad5e43e87149682d9900",  # Pier 1
        "wall_1bf6f00a047443a29ed6",  # Pier 2
        "wall_7037629136624408713b",  # East jamb
    }
    actual_candidates = set(ev.whole_wall_candidate_ids)
    assert expected_members.issubset(actual_candidates), (
        f"Missing expected wall members: {expected_members - actual_candidates}"
    )

    # Verify total continuous wall span
    assert pytest.approx(ev.whole_wall_length_pt, abs=0.01) == 366.72

    # Verify ordered opening aperture intervals along the host frame:
    # 1215 SGW (west) < 870 Door (middle) < 2127 STACKER (east)
    f_1215 = frames["1215_sgw"]
    f_870 = frames["870_door"]
    f_2127 = frames["2127_stacker"]

    assert 0 <= f_1215.u0_pt < f_1215.u1_pt <= f_870.u0_pt
    assert f_870.u0_pt < f_870.u1_pt <= f_2127.u0_pt
    assert f_2127.u0_pt < f_2127.u1_pt <= ev.whole_wall_length_pt
