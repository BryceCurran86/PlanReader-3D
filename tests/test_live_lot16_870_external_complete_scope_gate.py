"""Complete-scope 870 garage-personnel host stays fail-closed.

Recover mixed-scope G17 members are not ordinary W4 EXTERNAL authority.
Shared-pier openings stay demoted. The owner 2100 mm estimate does not fire
without an authenticated unique EXTERNAL whole-wall role.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from pb_live_physical_net_wall_integration import (
    LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
)
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_binding_authority import (
    OPENING_HOST_BINDING_RESOLVED,
    OPENING_LOCAL_SUPPLEMENTAL_SHARED_HOST_MEMBER,
    OPENING_LOCAL_SUPPLEMENTAL_SOURCE_BAND_HOST_RESOLVED,
    OpeningHostBindingRecord,
    OpeningHostBindingResult,
    _exclusive_mixed_scope_host_results,
)
from pb_source_visibility_authority import SourceVisibilityProducer


LOT16_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
BA7F = "physical_opening_existence_ba7f75a2e5f68bcce87cd00ac1acf90b"
INTERNAL_870 = "physical_opening_existence_8ecb81b6"
SHARED = (
    "physical_opening_existence_a68d0b7d",
    "physical_opening_existence_33d277d4",
    "physical_opening_existence_81a45c3a",
)


def _original_pdf():
    root = Path(__file__).resolve().parents[1]
    configured = os.environ.get("PLANREADER_LOT16_ORIGINAL_PDF")
    pdf = (
        Path(configured)
        if configured
        else root / "documents/sources" / "1. Construction Plans - Lot 16 Power (REV E).pdf"
    )
    if not pdf.is_file():
        if configured:
            pytest.fail("explicit owner-original PDF path is unavailable")
        pytest.skip("private original unavailable: source-positive acceptance NOT VERIFIED")
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == LOT16_SHA
    return pdf


def _mixed_record(opening, members):
    payload = OpeningHostBindingRecord(
        record_id="rec-" + opening,
        document_id="d",
        revision_id="r",
        source_sha256="s",
        snapshot_id="n",
        page_id="3",
        decision_scope_id="wall-source:page-3",
        opening_identity_id=opening,
        host_wall_id="host-" + opening,
        member_wall_candidate_ids=members,
        member_candidate_identity_ids=members,
        member_equivalence_groups=tuple((member,) for member in members),
        source_observation_ids=("obs",),
    )
    return OpeningHostBindingResult(
        EvidenceResolutionStatus.CORROBORATED,
        (OPENING_HOST_BINDING_RESOLVED, OPENING_LOCAL_SUPPLEMENTAL_SOURCE_BAND_HOST_RESOLVED),
        payload,
    )


def test_shared_pier_mixed_scope_host_stays_demoted():
    neighbour = _mixed_record("opening-neighbour", ("wall_shared_a", "wall_unique_n"))
    other = _mixed_record("opening-other", ("wall_shared_b", "wall_unique_o"))
    borrowed = _mixed_record("opening-borrowed", ("wall_shared_a", "wall_shared_b"))
    results = {
        ("d", "r", "s", "n", "3", "scope", "opening-neighbour"): neighbour,
        ("d", "r", "s", "n", "3", "scope", "opening-other"): other,
        ("d", "r", "s", "n", "3", "scope", "opening-borrowed"): borrowed,
    }
    exclusive = _exclusive_mixed_scope_host_results(results)
    demoted = exclusive[("d", "r", "s", "n", "3", "scope", "opening-borrowed")]
    assert demoted.record is None
    assert OPENING_LOCAL_SUPPLEMENTAL_SHARED_HOST_MEMBER in demoted.reason_codes
    assert exclusive[("d", "r", "s", "n", "3", "scope", "opening-neighbour")].record is neighbour.record


def test_default_off_complete_scope_ba7f_host_stays_unmapped():
    pdf = _original_pdf()
    raw = pdf.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{digest[:32]}",
        source_bytes=raw,
        source_locator="memory://lot16-870-complete-scope-gate.pdf",
        page_ids=(3,),
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("3",),
    )
    voids = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=composition,
    )
    page_scope = composition.wall_scopes[0]
    assert page_scope.scope_complete is True

    ba7f = next(
        trace
        for trace in composition.opening_bindings
        if trace.opening_identity_id == BA7F
    )
    assert ba7f.status is EvidenceResolutionStatus.ABSTAINED
    assert ba7f.host_wall_id is None
    assert ba7f.member_wall_candidate_ids == ()
    assert "raster_source_band_left_source_primitive_unmapped" in ba7f.reason_codes

    ba7f_frame = next(
        trace for trace in composition.host_frames if trace.opening_identity_id == BA7F
    )
    assert ba7f_frame.status is EvidenceResolutionStatus.ABSTAINED
    assert ba7f_frame.whole_wall_frame_id is None

    internal = next(
        opening
        for opening in voids.canonical_openings
        if INTERNAL_870 in opening.canonical_opening_id
    )
    assert internal.host_wall_id
    assert internal.host_frame_record_id
    assert internal.figured_single_axis_mm == pytest.approx(870.0)
    assert internal.area_m2 is None

    for prefix in SHARED:
        trace = next(
            item
            for item in composition.opening_bindings
            if item.opening_identity_id and prefix in item.opening_identity_id
        )
        assert trace.status is EvidenceResolutionStatus.ABSTAINED
        assert trace.host_wall_id is None
