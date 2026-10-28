"""Original whole-room ceiling source geometry must match its canonical room.

These are negative issuer-to-seal/customer source-identity checks. They neither
measure ceilings nor grant RCP finish or physical-room authority.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_customer_output_verification import verify_sealed_customer_output
from pb_live_ceiling_customer_projection import project_live_ceiling_customer_rows
from pb_live_ceiling_lining_source_closed_export import (
    build_live_ceiling_lining_source_traces,
    seal_live_ceiling_lining_run,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_ceiling_lining_source_closed_export import (
    _canonical_ceiling,
    _claim,
    _quantity,
)

CONSUMERS = (
    build_live_ceiling_lining_source_traces,
    seal_live_ceiling_lining_run,
    project_live_ceiling_customer_rows,
)


def _room_changed(claim, **changes):
    return replace(
        claim, canonical_rooms=(replace(claim.canonical_rooms[0], **changes),),
    )


def _must_abstain_at_every_customer_boundary(claim):
    original_rooms = claim.canonical_rooms
    original_ceilings = claim.canonical_ceilings
    original_quantities = claim.ceiling_lining_quantity_evidence
    for consumer in CONSUMERS:
        with pytest.raises(SourceClosedRunConflictError):
            consumer(claim, workspace_id=1, project_id="project-1")
    assert claim.canonical_rooms == original_rooms
    assert claim.canonical_ceilings == original_ceilings
    assert claim.ceiling_lining_quantity_evidence == original_quantities


@pytest.mark.parametrize(("field", "foreign"), (
    ("document_id", "foreign-document"),
    ("revision_id", "foreign-revision"),
    ("source_sha256", "b" * 64),
    ("snapshot_id", "foreign-snapshot"),
    ("page_id", "8"),
    ("viewport_id", "foreign-floor-viewport"),
))
def test_foreign_original_room_source_cannot_authorize_ceiling(field, foreign):
    _must_abstain_at_every_customer_boundary(
        _room_changed(_claim(_quantity()), **{field: foreign}),
    )


@pytest.mark.parametrize("foreign_ring", (
    ((20.0, 20.0), (120.0, 20.0), (120.0, 100.0), (20.0, 100.0)),
    ((10.0, 20.0), (110.0, 20.0), (110.0, 110.0), (10.0, 110.0)),
))
def test_different_simple_original_room_ring_cannot_lend_ceiling_area(foreign_ring):
    _must_abstain_at_every_customer_boundary(
        _room_changed(_claim(_quantity()), polygon_pdf_pts=foreign_ring),
    )


def test_rekeyed_ceiling_polygon_with_unchanged_firm_area_cannot_seal():
    source = _quantity()
    ceiling = replace(
        _canonical_ceiling(source),
        polygon_pdf_pts=((20.0, 20.0), (120.0, 20.0),
                         (120.0, 100.0), (20.0, 100.0)),
    )
    _must_abstain_at_every_customer_boundary(
        _claim(source, canonical_ceiling=ceiling),
    )


def test_rekeyed_ceiling_root_and_quantity_receipt_cannot_borrow_room():
    source = _quantity()
    changed = replace(source, metadata={
        **source.metadata, "document_id": "foreign-document",
    })
    ceiling = replace(
        _canonical_ceiling(changed), document_id="foreign-document",
    )
    _must_abstain_at_every_customer_boundary(
        _claim(changed, canonical_ceiling=ceiling),
    )


@pytest.mark.parametrize("ring_transform", (
    lambda p: p[1:] + p[:1],
    lambda p: tuple(reversed(p)),
    lambda p: p + (p[0],),
))
def test_exact_original_room_ring_permutations_preserve_customer_body(ring_transform):
    source = _quantity()
    baseline_claim = _claim(source)
    baseline = project_live_ceiling_customer_rows(
        baseline_claim, workspace_id=1, project_id="project-1",
    )
    ceiling = replace(
        _canonical_ceiling(source),
        polygon_pdf_pts=ring_transform(_canonical_ceiling(source).polygon_pdf_pts),
    )
    claim = _claim(source, canonical_ceiling=ceiling)
    rows = project_live_ceiling_customer_rows(
        claim, workspace_id=1, project_id="project-1",
    )
    run = seal_live_ceiling_lining_run(
        claim, workspace_id=1, project_id="project-1",
    )
    assert rows == baseline
    assert len(run.quantities) == len(rows) == 1
    assert verify_sealed_customer_output(run, rows).valid_quantity_count == 1
    assert rows == project_live_ceiling_customer_rows(
        claim, workspace_id=1, project_id="project-1",
    )


def test_room_without_explicit_viewport_keeps_original_source_ownership():
    # The original room producer may have a page-owned, unbound viewport.
    # Do not invent a viewport ID or reject the valid source-owned ring.
    source = _quantity()
    claim = _room_changed(_claim(source), viewport_id=None)
    rows = project_live_ceiling_customer_rows(
        claim, workspace_id=1, project_id="project-1",
    )
    assert len(rows) == 1
    assert verify_sealed_customer_output(
        seal_live_ceiling_lining_run(
            claim, workspace_id=1, project_id="project-1",
        ),
        rows,
    ).valid_quantity_count == 1


def test_invalid_original_room_ring_fails_closed_without_mutation():
    _must_abstain_at_every_customer_boundary(
        _room_changed(
            _claim(_quantity()),
            polygon_pdf_pts=((10.0, 20.0), (110.0, 100.0),
                             (110.0, 20.0), (10.0, 100.0)),
        ),
    )
