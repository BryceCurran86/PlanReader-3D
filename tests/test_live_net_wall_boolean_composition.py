from __future__ import annotations

import inspect

from pb_live_gross_wall_geometry_composition import (
    compose_live_gross_wall_geometry,
)
from pb_live_net_wall_boolean_composition import (
    LIVE_NET_WALL_PARTIAL,
    compose_live_net_wall_boolean_union,
)
from pb_live_opening_deduction_composition import (
    compose_live_opening_deductions,
)
from pb_live_physical_opening_void_composition import (
    compose_live_physical_opening_voids,
)
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_net_wall_boolean_union_authority import NET_WALL_GROSS_UNRESOLVED
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.test_live_opening_deduction_composition import (
    TARGET_ID,
    _deduction_pdf,
)


def _chain():
    source = SourceVisibilityProducer(
        producer_method="live-net-wall-boolean-composition-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="live-net-wall-boolean",
        source_bytes=_deduction_pdf(),
        source_locator="memory://live-net-wall-boolean.pdf",
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    assert wall_opening.status is EvidenceResolutionStatus.CORROBORATED

    physical_void = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    assert physical_void.status is EvidenceResolutionStatus.CORROBORATED

    deductions = compose_live_opening_deductions(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
        physical_void_composition=physical_void,
        target_scope_ids=(TARGET_ID,),
    )
    assert deductions.status is EvidenceResolutionStatus.CORROBORATED

    gross = compose_live_gross_wall_geometry(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
        physical_void_composition=physical_void,
    )
    assert gross.status is EvidenceResolutionStatus.ABSTAINED

    return wall_opening, physical_void, deductions, gross


def test_net_wall_never_relabels_unresolved_gross_geometry_as_net() -> None:
    wall_opening, physical_void, deductions, gross = _chain()

    composition = compose_live_net_wall_boolean_union(
        wall_opening_composition=wall_opening,
        physical_void_composition=physical_void,
        opening_deduction_composition=deductions,
        gross_wall_composition=gross,
    )

    assert composition.status is EvidenceResolutionStatus.ABSTAINED
    assert LIVE_NET_WALL_PARTIAL in composition.reason_codes
    assert len(composition.traces) == 1

    trace = composition.traces[0]
    assert trace.target_scope_id == TARGET_ID
    assert trace.status is EvidenceResolutionStatus.ABSTAINED
    assert NET_WALL_GROSS_UNRESOLVED in trace.reason_codes
    assert trace.record_id is None
    assert trace.gross_area_m2 is None
    assert trace.void_union_area_m2 is None
    assert trace.net_area_m2 is None

    selector = composition.net_wall_selectors[
        (trace.physical_wall_id, TARGET_ID)
    ]
    authority = composition.net_wall_authorities[trace.page_id]
    replay = authority.resolve(selector)
    assert replay.status is EvidenceResolutionStatus.ABSTAINED
    assert replay.record is None


def test_net_wall_composer_accepts_no_geometry_or_quantity_truth_inputs() -> None:
    parameters = set(
        inspect.signature(compose_live_net_wall_boolean_union).parameters
    )
    forbidden = {
        "gross_area",
        "gross_area_m2",
        "net_area",
        "net_area_m2",
        "opening_area",
        "opening_area_m2",
        "void_area",
        "void_polygons",
        "opening_count",
        "opening_ids",
        "deduct",
        "complete",
        "physical_wall_id",
        "trade_scope_id",
    }
    assert not (parameters & forbidden)
