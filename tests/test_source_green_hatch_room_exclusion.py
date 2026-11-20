"""Original source green-hatch exclusion works for any physical floor."""
from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace
import os

import fitz

from pb_source_green_hatch_room_exclusion import (
    collect_native_green_hatch_exclusions,
    quarantine_ordinary_hatched_floor_quantities,
)
from tests.test_live_floor_finish_area_source_closed_export import _quantity


def _pdf(*, green=True, full=True):
    pdf = fitz.open()
    page = pdf.new_page(width=200, height=200)
    color = (0, .5, 0) if green else (0, 0, 1)
    for i in range(12 if full else 2):
        a = (43 + i * 7, 43 + i * 5)
        page.draw_line(a, (a[0] + 28, a[1] + 28), color=color, width=.7)
    data = pdf.tobytes()
    pdf.close()
    return data


def _floor(data, **kwargs):
    values = dict(page_id="1", source_sha256=sha256(data).hexdigest(),
                  canonical_floor_id="unseen-f1",
                  source_room_face_record_id="unseen-face-1",
                  physical_floor_surface_id="physical-floor-1",
                  polygon_pdf_pts=((30.,30.),(170.,30.),(170.,170.),(30.,170.)),
                  geometry_complete=True, physical_floor_surface_identity_resolved=True)
    values.update(kwargs)
    return SimpleNamespace(**values)


def test_source_native_parallel_hatch_crosses_unseen_physical_room():
    data = _pdf()
    (witness,) = collect_native_green_hatch_exclusions(data, (_floor(data),))
    assert witness.canonical_floor_id == "unseen-f1"
    assert witness.source_sha256 == sha256(data).hexdigest()
    assert len(witness.native_path_ids) >= 5
    assert not witness.commercial_quantity_allowed
    assert (witness,) == collect_native_green_hatch_exclusions(data, (_floor(data),))


def test_not_blue_not_two_green_strokes_not_false_source_or_missing_room():
    for source in (_pdf(green=False), _pdf(full=False)):
        assert collect_native_green_hatch_exclusions(source, (_floor(source),)) == ()
    data = _pdf()
    assert collect_native_green_hatch_exclusions(data, (_floor(data, source_sha256="a"*64),)) == ()
    assert collect_native_green_hatch_exclusions(data, (_floor(data, geometry_complete=False),)) == ()
    assert collect_native_green_hatch_exclusions(data, (_floor(data, page_id="99"),)) == ()
    floor = _floor(data)
    assert collect_native_green_hatch_exclusions(data, (floor, floor)) == ()


def test_hatched_floor_ordinary_finish_abstains_but_independent_specialty_survives():
    data = _pdf()
    (witness,) = collect_native_green_hatch_exclusions(data, (_floor(data),))
    original = _quantity()
    original = replace(original, input_entity_ids=(witness.canonical_floor_id,),
                       metadata={**dict(original.metadata),
                                 "source_sha256":witness.source_sha256})
    (excluded,) = quarantine_ordinary_hatched_floor_quantities((original,), (witness,))
    assert excluded.abstained and excluded.value is None
    assert excluded.metadata["inclusion_status"] == "EXCLUSION"
    assert witness.witness_id in excluded.evidence_ids
    assert original.value is not None and not original.abstained
    specialty = replace(original, metadata={
        **original.metadata, "specialty_finish_independent_source_authority":True,
        "specialty_finish_source_evidence_id":"original_schedule_specialty_finish",
    })
    (preserved,) = quarantine_ordinary_hatched_floor_quantities((specialty,), (witness,))
    assert preserved is specialty


def test_source_belongs_to_own_room_and_cannot_quarantine_a_different_room():
    data = _pdf()
    (witness,) = collect_native_green_hatch_exclusions(data, (_floor(data),))
    quantity = replace(_quantity(), input_entity_ids=("other-room",))
    assert quarantine_ordinary_hatched_floor_quantities((quantity,), (witness,)) == (quantity,)
    bad_sha = replace(quantity, input_entity_ids=(witness.canonical_floor_id,),
                      metadata={"source_sha256":"f"*64})
    assert quarantine_ordinary_hatched_floor_quantities((bad_sha,), (witness,)) == (bad_sha,)


def test_owner_uploaded_original_hatch_proof_if_provisioned():
    path = os.environ.get("PLANREADER_ORIGINAL_MARYBOROUGH")
    if not path:
        return
    data = open(path, "rb").read()
    assert sha256(data).hexdigest() == (
        "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
    )
    # Source-positive viewport witness only, NOT a commercial floor polygon;
    # production source must supply the independently proven physical room.
    floor = _floor(
        data, page_id="7",
        polygon_pdf_pts=((350.,855.),(525.,855.),(525.,1080.),(350.,1080.)),
    )
    (witness,) = collect_native_green_hatch_exclusions(data, (floor,))
    assert len(witness.native_path_ids) >= 10
