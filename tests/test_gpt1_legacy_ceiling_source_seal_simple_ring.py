"""Legacy ceiling FIRM source seal refuses crossed or repeated physical rings.

The upstream canonical ceiling may already have FIRM documented metric area;
this tests the first independent source-geometry veto at the actual seal and
customer paths, not a new geometry/metric/material measurement authority.
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
from tests.test_live_ceiling_area_quantity_publication import _ceiling, _result


@pytest.mark.parametrize("bad_ring", [
    # Crossed edges with a positive shoelace area (not the old zero-area bowtie).
    ((0., 0.), (4., 0.), (0., 4.), (4., 4.), (2., 6.)),
    ((0., 0.), (4., 0.), (4., 4.), (0., 4.), (2., -1.)),
    # Repeated nonclosing vertex/backtrack, still positive shoelace and bbox.
    ((0., 0.), (10., 0.), (10., 10.), (0., 10.), (10., 0.)),
    ((0., 0.), (4., 0.), (4., 4.), (0., 4.), (4., 0.), (0., 0.)),
])
def test_non_simple_source_ring_cannot_reach_ceiling_seal_or_customer(bad_ring):
    original = _result(ceiling=replace(_ceiling(), polygon_pdf_pts=bad_ring))
    # Proves this is the real FIRST failing source-seal geometry gate, not an
    # upstream absence of a numeric canonical FIRM ceiling.
    published = publish_live_ceiling_area_quantities(original)
    assert len(published) == 1
    assert published[0].value == 13.270425

    for issuer in (
        build_live_ceiling_area_source_traces,
        seal_live_ceiling_area_run,
        project_live_ceiling_area_customer_rows,
    ):
        with pytest.raises(SourceClosedRunConflictError, match="source polygon is invalid"):
            issuer(original, workspace_id=7, project_id="source-project")

    # Neither abstention nor failed sealing mutates the original producer fact.
    assert original.canonical_ceilings[0].polygon_pdf_pts == bad_ring
    assert publish_live_ceiling_area_quantities(original) == published


@pytest.mark.parametrize("closed", [False, True])
def test_authentic_simple_ceiling_ring_preserves_sealed_and_customer_bodies(closed):
    baseline = _result()
    polygon = _ceiling().polygon_pdf_pts
    ceiling = replace(
        _ceiling(),
        polygon_pdf_pts=polygon + (polygon[0],) if closed else polygon,
    )
    candidate = _result(ceiling=ceiling)
    base_run = seal_live_ceiling_area_run(
        baseline, workspace_id=7, project_id="source-project",
    )
    candidate_run = seal_live_ceiling_area_run(
        candidate, workspace_id=7, project_id="source-project",
    )
    base_rows = project_live_ceiling_area_customer_rows(
        baseline, workspace_id=7, project_id="source-project",
    )
    candidate_rows = project_live_ceiling_area_customer_rows(
        candidate, workspace_id=7, project_id="source-project",
    )
    assert len(candidate_run.quantities) == len(candidate_rows) == 1
    assert candidate_run.to_json() == base_run.to_json()
    assert candidate_rows == base_rows
    assert candidate_run.fingerprint == seal_live_ceiling_area_run(
        candidate, workspace_id=7, project_id="source-project",
    ).fingerprint
