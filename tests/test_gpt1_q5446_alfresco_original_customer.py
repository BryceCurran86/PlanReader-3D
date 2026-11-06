"""Source-neutral witness tests plus optional SHA-original Q5446 private replay.

A synthetic drawing list only tests rejection/geometry invariants. It never
establishes real source authority or an accuracy gain.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import os

import fitz
import pytest

from pb_gpt1_q5446_alfresco_figure_authority import (
    FIGURE_HORIZONTAL_PATHS, FIGURE_VERTICAL_PATHS,
    FIGURE_HORIZONTAL_LINE, FIGURE_VERTICAL_LINE,
    PLAN_ALFRESCO_LABEL_PATHS, SOURCE_PRIMITIVE_CAP,
    original_alfresco_figure_witness,
)
from pb_gpt1_q5446_alfresco_original_customer import (
    issue_original_q5446_alfresco_customer_area,
)


def _ink(bounds, *, count=1, width=.72, first=None):
    x0,y0,x1,y1 = bounds
    first = first if first is not None else (x0,y0)
    return {
        "rect": fitz.Rect(*bounds), "type": "s",
        "width": width, "color": (0.,0.,0.),
        "items": [("l", fitz.Point(*first), fitz.Point(x1,y1))] * count,
    }


def _source_neutral_native_fixture():
    rows = [{} for _ in range(10686)]
    boxes_h = (
        (831.12,654.6,834.48,660.36),
        (835.92,654.6,839.28,660.36),
        (840.72,654.6,844.08,660.36),
        (845.52,654.6,849.12,660.36),
    )
    for pos,(i,rect) in enumerate(zip(FIGURE_HORIZONTAL_PATHS,boxes_h)):
        first = (rect[0]+.48,rect[1]) if pos == 0 else (rect[0]+1.44,rect[1])
        rows[i] = _ink(rect,count=14 if pos == 0 else 16,first=first)
    boxes_v = (
        (1054.08,412.56,1059.84,416.16),
        (1054.08,408.0,1059.84,411.36),
        (1054.08,403.2,1059.84,406.56),
        (1054.08,398.4,1059.84,401.76),
    )
    for pos,(i,rect) in enumerate(zip(FIGURE_VERTICAL_PATHS,boxes_v)):
        first = ((rect[2],rect[1]+1.2) if pos == 0
                 else (rect[0],rect[1]+1.92))
        rows[i] = _ink(rect,count=3 if pos == 0 else 16,first=first)
    rows[FIGURE_HORIZONTAL_LINE] = _ink(
        (799.68,661.8,880.32,661.8),width=.48)
    rows[FIGURE_VERTICAL_LINE] = _ink(
        (1061.28,352.8,1061.28,461.64),width=.48)
    for i in PLAN_ALFRESCO_LABEL_PATHS:
        rows[i] = _ink((820.,396.,824.,400.),width=.96)
    rows[PLAN_ALFRESCO_LABEL_PATHS[0]] = _ink(
        (813.84,395.28,817.,399.),width=.96)
    rows[PLAN_ALFRESCO_LABEL_PATHS[-1]] = _ink(
        (863.,398.,867.84,402.24),width=.96)
    return rows


def test_native_figures_are_source_area_not_a_benchmark_value():
    original = _source_neutral_native_fixture()
    witness = original_alfresco_figure_witness(original)
    assert witness is not None
    assert witness.horizontal_mm == 3000
    assert witness.vertical_mm == 4000
    assert witness.area_m2 == Decimal("12")
    assert witness.diagnostic_only is True
    assert len(witness.source_vector_path_ids) == len(set(witness.source_vector_path_ids))


@pytest.mark.parametrize("change", [
    "missing_digit", "wrong_digit_strokes", "wall_side_figure",
    "shift_horizontal_dimension", "shift_vertical_dimension",
    "foreign_label", "missing_label", "oversized_source",
])
def test_native_figured_source_conflicts_abstain(change):
    rows = _source_neutral_native_fixture()
    if change == "missing_digit":
        rows[FIGURE_HORIZONTAL_PATHS[0]] = {}
    elif change == "wrong_digit_strokes":
        rows[FIGURE_HORIZONTAL_PATHS[0]]["items"] = rows[FIGURE_HORIZONTAL_PATHS[0]]["items"][:5]
    elif change == "wall_side_figure":
        rows[FIGURE_VERTICAL_PATHS[0]]["items"] = rows[FIGURE_VERTICAL_PATHS[0]]["items"] * 2
    elif change == "shift_horizontal_dimension":
        rows[FIGURE_HORIZONTAL_LINE]["rect"] = fitz.Rect(799.68,663,880.32,663)
    elif change == "shift_vertical_dimension":
        rows[FIGURE_VERTICAL_LINE]["rect"] = fitz.Rect(1062.8,352.8,1062.8,461.64)
    elif change == "foreign_label":
        rows[PLAN_ALFRESCO_LABEL_PATHS[-1]]["rect"] = fitz.Rect(900,398,905,402.24)
    elif change == "missing_label":
        rows[PLAN_ALFRESCO_LABEL_PATHS[-1]] = {}
    elif change == "oversized_source":
        rows += [{} for _ in range(SOURCE_PRIMITIVE_CAP)]
    assert original_alfresco_figure_witness(rows) is None


def test_no_original_alfresco_cannot_mint_customer_area(tmp_path):
    missing = issue_original_q5446_alfresco_customer_area(
        str(tmp_path / "missing.pdf"), workspace_id=12)
    assert missing.status == "ABSTAIN"
    assert missing.quantity is None and missing.customer_rows == ()
    false_pdf = tmp_path / "lookalike.pdf"
    false_pdf.write_bytes(b"%PDF-1.7 fake")
    false = issue_original_q5446_alfresco_customer_area(
        str(false_pdf), workspace_id=12)
    assert false.status == "ABSTAIN"
    assert false.quantity is None and false.sealed_run is None


@pytest.mark.parametrize("workspace", [None, True, 0, -1, "1", 1.5])
def test_bad_workspace_never_issues_original_customer_area(workspace):
    r = issue_original_q5446_alfresco_customer_area("private.pdf",workspace_id=workspace)
    assert r.status == "ABSTAIN" and r.customer_rows == ()


def test_original_sha_alfresco_has_independent_physical_owner_and_customer():
    private = os.getenv("PLANREADER_ORIGINAL_Q5446_STANDARD_PLANS")
    if not private:
        pytest.skip("private source not in public checkout: no original-positive claim")
    import hashlib
    from pathlib import Path
    from pb_gpt1_q5446_original_area_schedule_shadow import SOURCE_SHA256
    from pb_customer_output_verification import verify_sealed_customer_output

    assert hashlib.sha256(Path(private).read_bytes()).hexdigest() == SOURCE_SHA256
    result = issue_original_q5446_alfresco_customer_area(private, workspace_id=14)
    assert result.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW", result.reason_codes
    assert result.quantity is not None
    assert result.trace is not None and result.sealed_run is not None
    assert len(result.sealed_run.quantities) == len(result.customer_rows) == 1
    assert result.quantity.family == "floor_area"
    assert result.quantity.metadata["canonical_physical_floor_owner_authenticated"] is True
    assert result.quantity.metadata["source_schedule_commercial_permission"] is False
    assert result.quantity.metadata["tiled_floor_finish_authorized"] is False
    assert result.quantity.metadata["net_internal_finished_face_authorized"] is False
    assert result.quantity.metadata["physical_boundary_model"] == "source_post_bounded_open_bay"
    connector_ids = result.quantity.metadata["physical_connector_source_path_ids"]
    assert type(connector_ids) is list and len(connector_ids) == 4
    assert len(connector_ids) == len(set(connector_ids))
    # The signed physical lineage must include independently witnessed native
    # wall continuations and corner-post quads, NOT disconnected four ink edges.
    assert all(
        any(
            evidence_id.endswith(f"_p1_path_{path_id}")
            for evidence_id in result.quantity.evidence_ids
        )
        for path_id in connector_ids
    )
    assert result.customer_rows[0]["quantity_status"] == "To review"
    assert result.customer_rows[0]["quantity_family"] == "floor_area"
    verification = verify_sealed_customer_output(result.sealed_run, result.customer_rows)
    assert verification.valid_quantity_count == verification.customer_row_count == 1


def test_original_sha_open_bay_primitive_mutations_must_abstain():
    private = os.getenv("PLANREADER_ORIGINAL_Q5446_STANDARD_PLANS")
    if not private:
        pytest.skip("private original source unavailable; cannot claim source positivity")
    from pb_source_native_rectangular_footprint_authority import (
        corroborate_source_labeled_rectangular_footprint as binder,
    )
    from pathlib import Path
    import hashlib
    from pb_gpt1_q5446_original_area_schedule_shadow import SOURCE_SHA256

    assert hashlib.sha256(Path(private).read_bytes()).hexdigest() == SOURCE_SHA256
    with fitz.open(private) as pdf:
        drawings = pdf[0].get_drawings()
    figure = original_alfresco_figure_witness(drawings)
    assert figure is not None
    def source_proof(rows):
        return binder(
            rows, source_label_path_ids=PLAN_ALFRESCO_LABEL_PATHS,
            figured_width_mm=figure.horizontal_mm,
            figured_depth_mm=figure.vertical_mm,
            excluded_source_path_ids=figure.source_vector_path_ids,
        )
    original = source_proof(drawings)
    assert original is not None
    assert original.boundary_model == "source_post_bounded_open_bay"
    assert len(original.connector_source_path_ids) == 4
    for connector_id in original.connector_source_path_ids:
        changed = drawings.copy()
        changed[connector_id] = {}
        assert source_proof(changed) is None
    # Two visually identical post strokes must not silently select one.
    duplicate = drawings.copy()
    duplicate.append(drawings[original.connector_source_path_ids[2]])
    assert len(duplicate) <= SOURCE_PRIMITIVE_CAP
    assert source_proof(duplicate) is None
