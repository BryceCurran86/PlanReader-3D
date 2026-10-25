"""Real ceiling RCP marks are source-local; one original still has one owner."""
from dataclasses import replace

import pytest

from pb_live_ceiling_customer_projection import project_live_ceiling_customer_rows
from pb_live_ceiling_lining_source_closed_export import (
    build_live_ceiling_lining_source_traces,
    seal_live_ceiling_lining_run,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from pb_customer_output_verification import verify_sealed_customer_output
from test_live_ceiling_lining_source_closed_export import (
    _claim, _room, _canonical_ceiling, _quantity,
)


def _two_original_ceilings(*, same_root=False, same_mark=True, same_occurrence=True):
    first = _quantity()
    first_room = _room()
    first_ceiling = _canonical_ceiling(first)
    sha = "a" * 64 if same_root else "b" * 64
    revision = "rev-1" if same_root else "rev-2"
    document = "doc-1" if same_root else "doc-2"
    snapshot = "snap-1" if same_root else "snap-2"
    second_room = replace(
        first_room,
        canonical_room_id="canonical-room-2",
        physical_room_id="physical-room-2",
        document_id=document, revision_id=revision,
        source_sha256=sha, snapshot_id=snapshot,
        source_room_face_record_id="face-2",
        room_label="SECOND ROOM",
        room_label_binding_record_id="label-binding-2",
    )
    mark = "occ-evidence" if same_mark else "independent-mark-evidence"
    occurrence = "occ-grid" if same_occurrence else "independent-rcp-occurrence"
    second = replace(
        first, quantity_id="qty-ceiling-2",
        semantic_key="ceiling_lining:ceiling-2:GRID:ceiling_grid",
        input_entity_ids=("ceiling-2",),
        evidence_ids=(
            "room-evidence", "room-label-evidence", "area-evidence",
            mark, "def-evidence",
        ),
        metadata={
            **dict(first.metadata),
            "document_id": document,
            "snapshot_id": snapshot,
            "source_sha256": sha,
            "revision_id": revision,
            "canonical_ceiling_id": "ceiling-2",
            "physical_ceiling_surface_id": "ceiling-2",
            "canonical_room_id": "canonical-room-2",
            "physical_room_id": "physical-room-2",
            "source_room_face_record_id": "face-2",
            "source_room_index_id": "room-index-2",
            "upstream_room_area_quantity_id": "room-area-qty-2",
            "room_area_quantity_id": "room-area-qty-2",
            "finish_occurrence_record_id": occurrence,
            "finish_occurrence_evidence_id": mark,
        },
    )
    second_ceiling = replace(
        _canonical_ceiling(second),
        canonical_ceiling_id="ceiling-2",
        document_id=document,
        snapshot_id=snapshot,
        room_entity_id="canonical-room-2",
        source_sha256=sha, revision_id=revision,
        room_area_quantity_id="room-area-qty-2",
        ceiling_quantity_id="qty-ceiling-2",
        source_room_index_id="room-index-2",
        evidence_ids=tuple(second.evidence_ids),
    )
    return replace(
        _claim(first),
        canonical_rooms=(first_room, second_room),
        canonical_ceilings=(first_ceiling, second_ceiling),
        ceiling_lining_quantity_evidence=(first, second),
    )


@pytest.mark.parametrize("reverse", (False, True))
def test_two_independent_originals_reusing_pdf_local_rcp_ids_keep_both_ceilings(reverse):
    claim = _two_original_ceilings(same_root=False)
    if reverse:
        claim = replace(
            claim, canonical_rooms=tuple(reversed(claim.canonical_rooms)),
            canonical_ceilings=tuple(reversed(claim.canonical_ceilings)),
            ceiling_lining_quantity_evidence=tuple(reversed(claim.ceiling_lining_quantity_evidence)),
        )
    traces = build_live_ceiling_lining_source_traces(
        claim, workspace_id=1, project_id="project-1",
    )
    assert set(traces) == {"qty-ceiling-1", "qty-ceiling-2"}
    sealed = seal_live_ceiling_lining_run(
        claim, workspace_id=1, project_id="project-1",
    )
    rows = project_live_ceiling_customer_rows(
        claim, workspace_id=1, project_id="project-1",
    )
    assert {r["quantity_id"] for r in rows} == set(traces)
    report = verify_sealed_customer_output(sealed, rows)
    assert report.customer_row_count == 2
    assert report.valid_quantity_count == 2


@pytest.mark.parametrize("reverse", (False, True))
@pytest.mark.parametrize("same_mark,same_occurrence", (
    (True, True),
    (True, False),
    (False, True),
))
def test_same_original_rcp_mark_rivals_still_fail_closed(
    reverse, same_mark, same_occurrence,
):
    claim = _two_original_ceilings(
        same_root=True, same_mark=same_mark, same_occurrence=same_occurrence,
    )
    if reverse:
        claim = replace(
            claim, canonical_rooms=tuple(reversed(claim.canonical_rooms)),
            canonical_ceilings=tuple(reversed(claim.canonical_ceilings)),
            ceiling_lining_quantity_evidence=tuple(reversed(claim.ceiling_lining_quantity_evidence)),
        )
    for consumer in (
        build_live_ceiling_lining_source_traces,
        seal_live_ceiling_lining_run,
        project_live_ceiling_customer_rows,
    ):
        with pytest.raises(SourceClosedRunConflictError, match="original RCP material mark has competing ceilings"):
            consumer(claim, workspace_id=1, project_id="project-1")


def test_distinct_same_original_rcp_marks_can_serve_two_independent_rooms():
    claim = _two_original_ceilings(
        same_root=True, same_mark=False, same_occurrence=False,
    )
    traces = build_live_ceiling_lining_source_traces(
        claim, workspace_id=1, project_id="project-1",
    )
    assert set(traces) == {"qty-ceiling-1", "qty-ceiling-2"}
