"""Fail closed when two FIRM legacy ceilings reuse one original physical face.

The canonical publisher legitimately checks room and upstream area identities.
This test exercises the first *physical source-face* ownership gate at the real
source-closed issuer and customer path. It does not create a new measurement.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_live_ceiling_area_customer_projection import (
    project_live_ceiling_area_customer_rows,
)
from pb_live_ceiling_area_quantity_publication import (
    publish_live_ceiling_area_quantities,
)
from pb_live_ceiling_area_source_closed_export import (
    build_live_ceiling_area_source_traces,
    seal_live_ceiling_area_run,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_ceiling_area_quantity_publication import (
    _ceiling,
    _result,
    _shadow_quantity,
)


def _paired_result(*, ring=None, second_page=1, second_viewport="vp-1"):
    first = _ceiling()
    second = replace(
        first,
        canonical_ceiling_id="canonical-ceiling-2",
        room_entity_id="room-2",
        room_area_quantity_id="qty-room-area-2",
        ceiling_quantity_id="qty-shadow-ceiling-2",
        source_room_index_id="room-index-2",
        source_page=second_page,
        viewport_id=second_viewport,
        polygon_pdf_pts=ring if ring is not None else first.polygon_pdf_pts,
        figured_dimension_ids=("dim2-h", "dim2-v"),
        evidence_ids=("ev2-dim-h", "ev2-dim-v", "ev2-finish"),
    )
    first_source = _shadow_quantity()
    second_source = replace(
        first_source,
        quantity_id="qty-shadow-ceiling-2",
        semantic_key="ceiling_lining:room-2",
        input_entity_ids=("room-2",),
        evidence_ids=second.evidence_ids,
        metadata={
            **dict(first_source.metadata),
            "page_no": second_page,
            "viewport_id": second_viewport,
            "upstream_area_quantity_id": "qty-room-area-2",
        },
    )
    return replace(
        _result(),
        canonical_ceilings=(first, second),
        quantity_evidence=(first_source, second_source),
    )


def _issuers():
    return (
        build_live_ceiling_area_source_traces,
        seal_live_ceiling_area_run,
        project_live_ceiling_area_customer_rows,
    )


@pytest.mark.parametrize("variant", ("same", "rotated", "reversed", "closed"))
@pytest.mark.parametrize("reverse_order", (False, True))
def test_distinct_firm_room_ids_cannot_reuse_one_original_ceiling_face(
    variant, reverse_order,
):
    original_ring = _ceiling().polygon_pdf_pts
    ring = {
        "same": original_ring,
        "rotated": original_ring[2:] + original_ring[:2],
        "reversed": tuple(reversed(original_ring)),
        "closed": original_ring + (original_ring[0],),
    }[variant]
    result = _paired_result(ring=ring)
    if reverse_order:
        result = replace(
            result,
            canonical_ceilings=tuple(reversed(result.canonical_ceilings)),
            quantity_evidence=tuple(reversed(result.quantity_evidence)),
        )
    # Both claims pass the preexisting source quantity, room ID and metric
    # gates independently. Only the actual original physical face is shared.
    assert len(publish_live_ceiling_area_quantities(result)) == 2
    before = result.canonical_ceilings
    for issuer in _issuers():
        with pytest.raises(
            SourceClosedRunConflictError, match="same original source face",
        ):
            issuer(result, workspace_id=7, project_id="source-project")
    assert result.canonical_ceilings == before


def test_distinct_source_faces_keep_two_real_sealed_and_customer_quantities():
    first_ring = _ceiling().polygon_pdf_pts
    translated = tuple((x + 20.0, y) for x, y in first_ring)
    result = _paired_result(ring=translated)
    published = publish_live_ceiling_area_quantities(result)
    assert len(published) == 2

    traces = build_live_ceiling_area_source_traces(
        result, workspace_id=7, project_id="source-project",
    )
    sealed = seal_live_ceiling_area_run(
        result, workspace_id=7, project_id="source-project",
    )
    rows = project_live_ceiling_area_customer_rows(
        result, workspace_id=7, project_id="source-project",
    )
    assert len(traces) == len(sealed.quantities) == len(rows) == 2
    assert {q.quantity_id for q in sealed.quantities} == set(traces)
    assert {row["quantity_id"] for row in rows} == set(traces)


@pytest.mark.parametrize("separate_scope", ("page", "viewport"))
def test_equal_pdf_coordinates_on_distinct_original_scopes_do_not_collide(
    separate_scope,
):
    result = _paired_result(
        second_page=2 if separate_scope == "page" else 1,
        second_viewport="vp-2" if separate_scope == "viewport" else "vp-1",
    )
    assert len(publish_live_ceiling_area_quantities(result)) == 2
    traces = build_live_ceiling_area_source_traces(
        result, workspace_id=7, project_id="source-project",
    )
    assert len(traces) == 2


def test_existing_one_ceiling_signed_and_customer_bodies_are_byte_identical():
    result = _result()
    first = seal_live_ceiling_area_run(
        result, workspace_id=7, project_id="source-project",
    )
    second = seal_live_ceiling_area_run(
        result, workspace_id=7, project_id="source-project",
    )
    rows1 = project_live_ceiling_area_customer_rows(
        result, workspace_id=7, project_id="source-project",
    )
    rows2 = project_live_ceiling_area_customer_rows(
        result, workspace_id=7, project_id="source-project",
    )
    assert first.to_json() == second.to_json()
    assert rows1 == rows2
    assert len(rows1) == len(first.quantities) == 1
