"""Tests for green-hatch exclusion and epoxy label shadow linkage (Item 27)."""
from __future__ import annotations

from pathlib import Path
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_green_hatch_room_exclusion import SourceGreenHatchRoomWitness
import pb_source_green_exclusion_epoxy_linkage_shadow as gee
from tools.audit_no_job_specific_shared_rules import audit_shared_source

_SHA_1 = "e" * 64
_SHA_2 = "f" * 64


def _rect(x0: float, y0: float, x1: float, y1: float) -> tuple[tuple[float, float], ...]:
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _room(
    fid: str,
    poly: tuple[tuple[float, float], ...],
    *,
    page: str = "7",
    vp: str = "vp-plan",
    rev: str = "rev-1",
    sha: str = _SHA_1,
) -> gee.FloorExclusionRoomCandidate:
    return gee.FloorExclusionRoomCandidate(
        canonical_floor_id=fid,
        physical_floor_surface_id=f"surf-{fid}",
        source_room_face_record_id=f"face-{fid}",
        document_id="doc-1",
        revision_id=rev,
        source_sha256=sha,
        page_id=page,
        viewport_id=vp,
        polygon_pdf_pts=poly,
    )


def _witness(fid: str, *, wid: str = "w-1", page: str = "7", sha: str = _SHA_1) -> SourceGreenHatchRoomWitness:
    return SourceGreenHatchRoomWitness(
        witness_id=wid,
        canonical_floor_id=fid,
        physical_floor_surface_id=f"surf-{fid}",
        source_room_face_record_id=f"face-{fid}",
        source_sha256=sha,
        page_id=page,
        native_path_ids=(10, 11, 12, 13, 14, 15),
    )


def _obs(
    oid: str,
    text: str,
    pt: tuple[float, float],
    *,
    page: str = "7",
    vp: str = "vp-plan",
    rev: str = "rev-1",
    sha: str = _SHA_1,
) -> gee.FloorFinishLabelObservation:
    return gee.FloorFinishLabelObservation(
        observation_id=oid,
        document_id="doc-1",
        revision_id=rev,
        source_sha256=sha,
        page_id=page,
        viewport_id=vp,
        raw_text=text,
        anchor_pt_pdf_pts=pt,
    )


def _legend(
    did: str,
    code: str,
    desc: str,
    *,
    rev: str = "rev-1",
    sha: str = _SHA_1,
) -> gee.FinishLegendDefinitionInput:
    return gee.FinishLegendDefinitionInput(
        definition_id=did,
        document_id="doc-1",
        revision_id=rev,
        source_sha256=sha,
        legend_page_id="2",
        finish_code=code,
        description=desc,
    )


def test_links_green_hatch_coldroom_exclusion_and_epoxy_legend_codes_read_only() -> None:
    rooms = [
        _room("floor-cold", _rect(0, 0, 100, 100)),
        _room("floor-aisle", _rect(120, 0, 220, 100)),
        _room("floor-prep", _rect(240, 0, 340, 100)),
        _room("floor-office", _rect(360, 0, 460, 100)),
    ]
    witnesses = [
        _witness("floor-cold", wid="w-cold"),
        _witness("floor-aisle", wid="w-aisle"),
    ]
    labels = [
        _obs("o1", "COLD ROOM BY OTHERS", (50.0, 50.0)),
        _obs("o2", "FT2", (170.0, 50.0)),
        _obs("o3", "Non-slip epoxy floor", (290.0, 50.0)),
    ]
    legends = [_legend("def-ft2", "FT2", "Seamless epoxy resin finish")]

    report = gee.link_green_exclusions_and_epoxy_labels(
        rooms=rooms,
        green_witnesses=witnesses,
        label_observations=labels,
        finish_legend_definitions=legends,
    )
    assert report.commercial_quantity_allowed is False
    assert report.customer_write_allowed is False
    assert report.specialty_authority_granted is False
    assert report.unmatched_green_witness_ids == ()

    by_id = {r.canonical_floor_id: r for r in report.room_records}
    # Cold room: green hatch + exclusion text corroborated
    assert by_id["floor-cold"].classification == gee.CLASS_GREEN_HATCH_AND_EXCLUSION
    assert by_id["floor-cold"].ordinary_finish_exclusion_indicated is True
    assert by_id["floor-cold"].exclusion_label_observation_ids == ("o1",)

    # Hatched aisle with FT2 epoxy legend code: BOTH exclusion and epoxy candidate recorded, zero commercial write
    assert by_id["floor-aisle"].classification == gee.CLASS_GREEN_HATCH_WITH_EPOXY
    assert by_id["floor-aisle"].ordinary_finish_exclusion_indicated is True
    assert by_id["floor-aisle"].linked_finish_codes == ("FT2",)
    assert by_id["floor-aisle"].linked_legend_definition_ids == ("def-ft2",)
    assert by_id["floor-aisle"].epoxy_label_observation_ids == ("o2",)
    assert by_id["floor-aisle"].specialty_authority_granted is False
    assert by_id["floor-aisle"].customer_write_allowed is False

    # Non-hatched epoxy room: epoxy linked without inventing a green-hatch exclusion
    assert by_id["floor-prep"].classification == gee.CLASS_EPOXY_LABEL_ONLY
    assert by_id["floor-prep"].ordinary_finish_exclusion_indicated is False
    assert by_id["floor-prep"].green_hatch_witness_id is None

    # Unhatched unlabelled room abstains cleanly
    assert by_id["floor-office"].status == EvidenceResolutionStatus.ABSTAINED
    assert by_id["floor-office"].classification == gee.CLASS_UNLINKED


def test_conflicts_cross_revision_mismatches_overlapping_rooms_and_zero_literals() -> None:
    rooms = [
        _room("r-multi-code", _rect(0, 0, 100, 100)),
        _room("r-ov-1", _rect(150, 0, 270, 100)),
        _room("r-ov-2", _rect(210, 0, 330, 100)),
        _room("r-xrev", _rect(360, 0, 460, 100)),
    ]
    labels = [
        _obs("o-c1", "FT2", (30.0, 50.0)),
        _obs("o-c2", "FT3", (70.0, 50.0)),
        _obs("o-ov", "Epoxy floor", (240.0, 50.0)),
        _obs("o-xrev", "FT2", (410.0, 50.0)),
    ]
    # FT2 defined in a DIFFERENT revision/SHA must never link to rev-1 room
    legends = [
        _legend("def-wrong-rev", "FT2", "Epoxy resin", rev="rev-2", sha=_SHA_2),
    ]
    # Wrong-SHA green witness stays unmatched
    wrong_w = _witness("r-xrev", wid="w-wrong-sha", sha=_SHA_2)

    r1 = gee.link_green_exclusions_and_epoxy_labels(
        rooms=rooms,
        green_witnesses=[wrong_w],
        label_observations=labels,
        finish_legend_definitions=legends,
    )
    r2 = gee.link_green_exclusions_and_epoxy_labels(
        rooms=list(reversed(rooms)),
        green_witnesses=[wrong_w],
        label_observations=list(reversed(labels)),
        finish_legend_definitions=legends,
    )
    assert r1 == r2
    assert r1.unmatched_green_witness_ids == ("w-wrong-sha",)

    by_id = {r.canonical_floor_id: r for r in r1.room_records}
    assert by_id["r-multi-code"].status == EvidenceResolutionStatus.CONFLICT
    assert "multiple_distinct_finish_codes_in_one_room" in by_id["r-multi-code"].reason_codes
    assert by_id["r-ov-1"].status == EvidenceResolutionStatus.CONFLICT
    assert by_id["r-ov-2"].status == EvidenceResolutionStatus.CONFLICT
    assert by_id["r-xrev"].status == EvidenceResolutionStatus.ABSTAINED
    assert by_id["r-xrev"].green_hatch_witness_id is None
    assert by_id["r-xrev"].epoxy_label_observation_ids == ()

    # Duplicate conflicting legend definition fails closed
    dup_legends = [
        _legend("d1", "FT2", "Epoxy resin"),
        _legend("d2", "FT2", "Ceramic tile"),
    ]
    r_dup = gee.link_green_exclusions_and_epoxy_labels(
        rooms=[_room("r-xrev", _rect(360, 0, 460, 100))],
        green_witnesses=[],
        label_observations=[_obs("o-xrev", "FT2", (410.0, 50.0))],
        finish_legend_definitions=dup_legends,
    )
    assert r_dup.conflicting_legend_codes == ("FT2",)
    assert r_dup.room_records[0].status == EvidenceResolutionStatus.CONFLICT

    mod_path = Path(gee.__file__)
    assert audit_shared_source(mod_path.read_text(encoding="utf-8"), filename=mod_path.name) == ()
