"""Source-height-owned 3D mesh and room volume must stay CANDIDATE."""
from dataclasses import replace
from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_gpt1_figured_chain_metric_shadow import (
    FiguredPhysicalSide,measure_figured_room_edge_chain_shadow,
)
from pb_gpt1_original_figured_room_3d_shell_shadow import (
    OriginalDocumentedRoomZ,build_original_figured_room_3d_shell_shadow,
)


def parent():
    ring=((0,0),(10,0),(10,5),(0,5))
    sides=tuple(FiguredPhysicalSide(
        f"side-{i}",ring[i],ring[(i+1)%4],(f"ink-{i}",),
        {0:5000,1:2000}.get(i),
        f"figure-{i}" if i in (0,1) else None,
        (f"witness-{i}-a",f"witness-{i}-b") if i in (0,1) else (),
    ) for i in range(4))
    return measure_figured_room_edge_chain_shadow(
        sides,source_sha256="a"*64,revision_id="rev",
        page_id="7",physical_room_id="room",
    )


def elevation():
    return OriginalDocumentedRoomZ(
        "room",0,3000,"original-floor-datum","original-clear-height",
        ("original-source-section-binding",),"a"*64,"rev",
    )


def test_source_figured_3d_room_volume_walls_and_mesh_topology():
    result=build_original_figured_room_3d_shell_shadow(parent(),elevation())
    assert result.status is Status.CANDIDATE
    assert result.candidate_clear_room_volume_m3==30.
    assert result.candidate_wall_surface_m2==42.
    assert len(result.candidate_xyz_vertices_mm)==8
    assert len(result.candidate_wall_triangles)==8
    assert len(result.candidate_floor_triangles)==2
    assert len(result.candidate_ceiling_triangles)==2
    assert result.diagnostic_only and not hasattr(result,"quantity_id")


def test_missing_real_original_height_does_not_assume_2700():
    for changed in (
        replace(elevation(),clear_height_mm=0),
        replace(elevation(),revision_id="old"),
        replace(elevation(),physical_room_id="other"),
    ):
        result=build_original_figured_room_3d_shell_shadow(parent(),changed)
        assert result.status is Status.ABSTAINED
        assert result.candidate_clear_room_volume_m3 is None


def test_room_3d_floor_datum_is_explicit_not_always_zero():
    result=build_original_figured_room_3d_shell_shadow(
        parent(),replace(elevation(),lower_finished_floor_z_mm=500.)
    )
    assert result.status is Status.CANDIDATE
    assert all(z==500 for x,y,z in result.candidate_xyz_vertices_mm[:4])
    assert all(z==3500 for x,y,z in result.candidate_xyz_vertices_mm[4:])
