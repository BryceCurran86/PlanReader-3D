"""Adversarial tests for source-owned Item19B callout->wall binding."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_finish_callout_wall_authority import (
    WallFinishCalloutWallProducer,
    _local_owner_universe_safe,
    _target_provenance,
)
from pb_wall_finish_face_binding_authority import _Line, _Terminator


def _line(obs: str, raw: str, x1: float, y1: float, x2: float, y2: float) -> _Line:
    return _Line(observation_id=obs, raw_id=raw, geometry=(x1, y1, x2, y2))


def _term(x: float, y: float, size: float = 2.0) -> _Terminator:
    return _Terminator(
        primitive_id=f"term-{x}-{y}",
        bbox=(x - size, y - size, x + size, y + size),
        center=(x, y),
    )


def test_boundary_primitive_far_from_terminator_does_not_poison_local_owner() -> None:
    scope = SimpleNamespace(
        scope_boundary_observation_ids=("boundary",),
        ambiguous_source_observation_ids=(),
    )
    assert _local_owner_universe_safe(
        terminator=_term(5.0, 10.0),
        page_lines=(_line("boundary", "raw-boundary", 80.0, 0.0, 80.0, 20.0),),
        wall_scope=scope,
    )


def test_boundary_primitive_intersecting_terminator_blocks_local_owner() -> None:
    scope = SimpleNamespace(
        scope_boundary_observation_ids=("boundary",),
        ambiguous_source_observation_ids=(),
    )
    assert not _local_owner_universe_safe(
        terminator=_term(5.0, 10.0),
        page_lines=(_line("boundary", "raw-boundary", 5.0, 0.0, 5.0, 20.0),),
        wall_scope=scope,
    )


def test_unreplayable_withheld_structural_primitive_blocks_local_owner() -> None:
    scope = SimpleNamespace(
        scope_boundary_observation_ids=("missing-boundary",),
        ambiguous_source_observation_ids=(),
    )
    assert not _local_owner_universe_safe(
        terminator=_term(5.0, 10.0),
        page_lines=(),
        wall_scope=scope,
    )


def test_target_provenance_retains_raw_owners_and_positive_same_group() -> None:
    lines = (
        _line("w1", "raw-w1", 4.0, 0.0, 4.0, 20.0),
        _line("w2", "raw-w2", 6.0, 0.0, 6.0, 20.0),
    )
    rec1 = SimpleNamespace(
        wall_candidate_id="wall-1",
        physical_identity=SimpleNamespace(source_primitive_ids=("raw-w1",)),
    )
    rec2 = SimpleNamespace(
        wall_candidate_id="wall-2",
        physical_identity=SimpleNamespace(source_primitive_ids=("raw-w2",)),
    )
    scope = SimpleNamespace(
        records=(rec1, rec2),
        equivalence=SimpleNamespace(
            equivalence_groups=(("wall-1", "wall-2"),),
            pair_classifications=(("wall-1", "wall-2", "same_physical_wall"),),
        ),
    )

    owners, group, pairs = _target_provenance(
        terminator=_term(5.0, 10.0),
        wall_lines=lines,
        wall_scope=scope,
        target=rec1,
    )
    assert owners == ("wall-1", "wall-2")
    assert group == ("wall-1", "wall-2")
    assert pairs == (("wall-1", "wall-2", "same_physical_wall"),)


def _write_finish_source(
    path: Path,
    *,
    unrelated_boundary_crossing: bool = False,
    target_boundary_crossing: bool = False,
    note_gap: float = 0.0,
    wall_gap: float = 0.0,
) -> None:
    doc = fitz.open()
    page = doc.new_page(width=300.0, height=200.0)
    page.draw_rect(fitz.Rect(20.0, 15.0, 280.0, 185.0), color=(0, 0, 0), width=1)
    page.insert_text((120.0, 178.0), "GROUND FLOOR PLAN", fontsize=9)

    # Two-room wall topology.
    for first, second in (
        ((50.0, 50.0), (250.0, 50.0)),
        ((250.0, 50.0), (250.0, 150.0)),
        ((250.0, 150.0), (50.0, 150.0)),
        ((50.0, 150.0), (50.0, 50.0)),
        ((150.0, 50.0), (150.0, 150.0)),
    ):
        page.draw_line(first, second, color=(0, 0, 0), width=1)

    page.insert_text(
        fitz.Point(80.0, 100.0),
        "wall key to finish externally",
        fontsize=8,
        color=(0, 0, 0),
    )
    terminator_x = 50.0 + wall_gap
    radius = 2.0
    page.draw_line(
        fitz.Point(80.0 - note_gap, 100.0),
        fitz.Point(terminator_x + radius, 100.0),
        color=(0, 0, 0),
        dashes="[3 2] 0",
        width=0.5,
    )
    page.draw_circle(
        fitz.Point(terminator_x, 100.0),
        radius,
        color=(0, 0, 0),
        fill=(0, 0, 0),
        width=0.5,
    )

    if unrelated_boundary_crossing:
        # Structural source line crosses the viewport boundary far from the
        # terminator. Global scope must remain incomplete, but this local
        # target universe is still exact.
        page.draw_line((260.0, 35.0), (295.0, 35.0), color=(0, 0, 0), width=1)

    if target_boundary_crossing:
        # Omitted structural primitive crosses the authenticated viewport and
        # the callout terminator. Local target uniqueness is therefore unknown.
        page.draw_line((0.0, 100.0), (100.0, 100.0), color=(0, 0, 0), width=1)

    doc.save(path)
    doc.close()


def _run(path: Path) -> WallFinishCalloutWallProducer:
    source = SourceVisibilityProducer(
        producer_method="item19b-callout-wall-test",
        producer_version="1.0",
    )
    source.ingest_native_pdf_bytes(
        document_id=f"test:{path.name}",
        source_bytes=path.read_bytes(),
        source_locator=str(path),
    )
    return WallFinishCalloutWallProducer.from_source_visibility_producer(
        source,
        page_ids=("1",),
    )


def _bindings(producer: WallFinishCalloutWallProducer):
    return [
        binding
        for result in producer.published_results()
        for binding in result.bindings
    ]


def test_end_to_end_publishes_exact_callout_wall_before_face_role(tmp_path: Path) -> None:
    path = tmp_path / "positive.pdf"
    _write_finish_source(path)
    bindings = _bindings(_run(path))
    assert len(bindings) == 1
    binding = bindings[0]
    assert binding.status is EvidenceResolutionStatus.CORROBORATED
    assert binding.trade_scope_id == "external_key_pointing"
    assert binding.finish_material == "key_pointing"
    assert binding.semantic_direction == "externally"
    assert binding.physical_wall_id in binding.equivalence_group_wall_ids
    assert binding.source_wall_primitive_ids


def test_unrelated_cropped_geometry_does_not_block_exact_local_callout(tmp_path: Path) -> None:
    path = tmp_path / "unrelated-crop.pdf"
    _write_finish_source(path, unrelated_boundary_crossing=True)
    bindings = _bindings(_run(path))
    assert len(bindings) == 1


def test_boundary_primitive_at_terminator_forces_abstention(tmp_path: Path) -> None:
    path = tmp_path / "target-crop.pdf"
    _write_finish_source(path, target_boundary_crossing=True)
    assert _bindings(_run(path)) == []


def test_near_note_without_native_contact_does_not_bind(tmp_path: Path) -> None:
    path = tmp_path / "note-gap.pdf"
    _write_finish_source(path, note_gap=0.005)
    assert _bindings(_run(path)) == []


def test_terminator_near_but_not_intersecting_wall_does_not_bind(tmp_path: Path) -> None:
    path = tmp_path / "wall-gap.pdf"
    _write_finish_source(path, wall_gap=0.01)
    assert _bindings(_run(path)) == []
