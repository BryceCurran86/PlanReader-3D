"""Q02 cross-view ceiling source receipt, metric and geometry sealing safety."""
from dataclasses import replace

import pytest

from pb_live_ceiling_lining_source_closed_export import build_live_ceiling_lining_source_traces
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_ceiling_lining_source_closed_export import _claim, _quantity, _canonical_ceiling


def _valid():
    return _claim(_quantity())


def _build(claim, workspace=5):
    return build_live_ceiling_lining_source_traces(
        claim, workspace_id=workspace, project_id="project-5"
    )


def test_original_cross_view_ceiling_positive_metric_source_receipts():
    trace = _build(_valid())["qty-ceiling-1"]
    assert trace.workspace_id == 5
    assert trace.source_bbox == (10.0, 20.0, 110.0, 100.0)
    assert {"room-evidence", "area-evidence", "occ-evidence"}.issubset(trace.evidence_ids)
    assert {"ceiling-1", "canonical-room-1", "physical-room-1"} <= set(trace.canonical_entity_ids)


@pytest.mark.parametrize("bad", [True, False, "5", 5.1, 5.0, 0, -1])
def test_ceiling_cannot_coerce_workspace(bad):
    with pytest.raises(SourceClosedRunConflictError, match="workspace_id"):
        _build(_valid(), workspace=bad)


@pytest.mark.parametrize("dimension_ids", [
    [" dim-h", "dim-v"], ["dim-h", "dim-v "],
    ["dim-h", "dim-h"], ["dim-h", True], "dim-h,dim-v",
])
def test_original_ceilings_cannot_launder_figure_pair(dimension_ids):
    q = _quantity()
    bad = replace(q, metadata={**q.metadata, "figured_dimension_ids": dimension_ids})
    with pytest.raises(SourceClosedRunConflictError, match="figured dimension"):
        _build(_claim(bad, canonical_ceiling=_canonical_ceiling(q)))


@pytest.mark.parametrize("receipts", [
    ("room-evidence", " area-evidence"),
    ("room-evidence", "room-evidence"),
    ("room-evidence", True),
])
def test_original_ceiling_evidence_receipts_must_remain_exact(receipts):
    q = _quantity()
    ceiling = replace(_canonical_ceiling(q), evidence_ids=receipts)
    with pytest.raises(SourceClosedRunConflictError, match="trace receipts"):
        _build(_claim(q, canonical_ceiling=ceiling))


@pytest.mark.parametrize("polygon", [
    ((10.,20.), (110.,20.), (True,100.), (10.,100.)),
    ((10.,20.), (110.,20.), (110.,float("nan")), (10.,100.)),
    ((10.,20.), (110.,20.), (110.,10**400), (10.,100.)),
    ((0.,0.), (10.,10.), (0.,10.), (10.,0.)),
])
def test_ceiling_nonphysical_page_polygon_cannot_seal_m2(polygon):
    q = _quantity()
    ceiling = replace(_canonical_ceiling(q), polygon_pdf_pts=polygon)
    with pytest.raises(SourceClosedRunConflictError, match="polygon"):
        _build(_claim(q, canonical_ceiling=ceiling))


@pytest.mark.parametrize("bad,expected", [
    (True, "typed metric"), ("9.05352", "typed metric"),
    (10**400, "not metric"),
])
def test_ceiling_quantity_requires_typed_metric_not_coerced(bad, expected):
    # QuantityEvidence's constructor normalizes some numeric-like values.
    # Recreate an imported/replayed wire value AFTER construction to test the
    # actual final export boundary, without accidentally sanitizing the input.
    from copy import copy
    q = copy(_quantity())
    object.__setattr__(q, "value", bad)
    with pytest.raises(SourceClosedRunConflictError, match=expected):
        _build(_claim(q, canonical_ceiling=_canonical_ceiling(_quantity())))
