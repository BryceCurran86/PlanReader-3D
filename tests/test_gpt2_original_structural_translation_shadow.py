"""Source-only original stroke translations; never physical W4/FT3 or metric."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import os

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_gpt2_original_structural_translation_shadow import (
    inspect_original_structural_translation_shadow as inspect,
)

BASE_LINES = (
    ((50., 70.), (230., 70.)),
    ((50., 130.), (230., 130.)),
    ((50., 70.), (50., 260.)),
    ((230., 70.), (230., 260.)),
    ((80., 200.), (200., 200.)),
)


def _pdf(*, translations=((78., 0.),), reverse=False, color=(0, 0, 0),
         source_width=.48, duplicate_ink=False, invisible=False,
         fill_only=False, out_of_scope_extra=False, rotate=False):
    doc = fitz.open()
    for index in (0, 1):
        page = doc.new_page(width=900, height=700)
        shifts = ((0., 0.),) if index == 0 else translations
        for dx, dy in shifts:
            for pair in BASE_LINES:
                a, b = ((pair[1], pair[0]) if reverse else pair)
                a = (a[0] + dx, a[1] + dy)
                b = (b[0] + dx, b[1] + dy)
                shape = page.new_shape()
                if fill_only:
                    shape.draw_rect(fitz.Rect(a[0], a[1], b[0]+5, b[1]+5))
                    shape.finish(color=None, fill=(0, 0, 0))
                else:
                    shape.draw_line(fitz.Point(*a), fitz.Point(*b))
                    shape.finish(color=color, width=source_width,
                                 stroke_opacity=0.0 if invisible else 1.0)
                shape.commit()
                if duplicate_ink and not fill_only:
                    same = page.new_shape()
                    same.draw_line(fitz.Point(*a), fitz.Point(*b))
                    same.finish(color=color, width=source_width)
                    same.commit()
        if out_of_scope_extra:
            noise = page.new_shape()
            noise.draw_line(fitz.Point(600, 600), fitz.Point(850, 600))
            noise.finish(color=(0, 0, 0), width=.48)
            noise.commit()
        if rotate and index == 1:
            page.set_rotation(90)
    data = doc.tobytes()
    doc.close()
    return data


def _run(data=None, *, transforms=((78., 0.), (43.92, 0.)), **kwargs):
    data = data if data is not None else _pdf()
    return inspect(
        data, source_sha256=sha256(data).hexdigest(),
        first_page=1, second_page=2,
        first_bounds_pdf_pt=(35., 40., 245., 280.),
        second_bounds_pdf_pt=(35., 40., 340., 280.),
        candidate_translations_pdf_pt=transforms, **kwargs
    )


def test_unique_original_ink_translation_is_candidate_never_physical():
    source = _pdf()
    result = _run(source)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.compatible_translations_pdf_pt == ((78., 0.),)
    assert result.first_candidate_stroke_groups == len(BASE_LINES)
    assert result.second_candidate_stroke_groups == len(BASE_LINES)
    assert result.votes[1].horizontal_matches >= 2
    assert result.votes[1].vertical_matches >= 2
    assert all(not getattr(result, attribute) for attribute in (
        "complete_translation_universe_proven", "original_w4_wall_issued",
        "opening_jamb_issued", "physical_floor_issued",
        "material_finish_issued", "metric_area_issued",
        "customer_projection_allowed"
    ))
    assert result.shadow_only


@pytest.mark.parametrize("reverse,duplicated,extra", (
    (True, False, False), (False, True, False),
    (False, False, True), (True, True, True)
))
def test_path_reversal_duplicate_ink_and_outside_scope_do_not_change_votes(
    reverse, duplicated, extra
):
    source = _pdf(reverse=reverse, duplicate_ink=duplicated,
                  out_of_scope_extra=extra)
    result = _run(source)
    assert result.compatible_translations_pdf_pt == ((78., 0.),)
    assert result.votes[1].horizontal_matches >= 2
    assert result.votes[1].vertical_matches >= 2


def test_competing_source_translations_are_preserved_never_elected():
    source = _pdf(translations=((78., 0.), (110., 0.)))
    result = _run(source, transforms=((78., 0.), (110., 0.)))
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.compatible_translations_pdf_pt == ((78., 0.), (110., 0.))
    assert all(v.source_ink_candidate for v in result.votes)
    assert result.original_w4_wall_issued is False


@pytest.mark.parametrize("bad", [
    {"color": (1, 1, 1)}, {"invisible": True},
    {"source_width": 1.6}, {"fill_only": True},
])
def test_invisible_wrong_width_white_and_fill_only_are_not_stroke_evidence(bad):
    result = _run(_pdf(**bad))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.compatible_translations_pdf_pt == ()


def test_rotation_without_authenticated_registration_abstains():
    r = _run(_pdf(rotate=True))
    assert r.status is EvidenceResolutionStatus.ABSTAINED
    assert r.votes == ()
    assert not r.physical_floor_issued


def test_rival_order_is_stable_and_does_not_choose_first():
    data = _pdf(translations=((78., 0.), (110., 0.)))
    first = _run(data, transforms=((110., 0.), (78., 0.)))
    second = _run(data, transforms=((78., 0.), (110., 0.)))
    assert first == second


def test_missing_sha_invalid_tolerance_and_duplicate_votes_fail_closed():
    source = _pdf()
    args = dict(
        source_sha256="0"*64, first_page=1, second_page=2,
        first_bounds_pdf_pt=(35., 40., 245., 280.),
        second_bounds_pdf_pt=(35., 40., 340., 280.),
        candidate_translations_pdf_pt=((78., 0.),)
    )
    with pytest.raises(ValueError, match="SHA"):
        inspect(source, **args)
    with pytest.raises(ValueError, match="duplicated"):
        _run(source, transforms=((78., 0.), (78., 0.)))
    with pytest.raises(ValueError, match="bounded"):
        _run(source, coordinate_tolerance_pdf_pt=2.5)


def test_strict_original_source_read_does_not_mutate_pdf():
    source = _pdf()
    before = sha256(source).hexdigest()
    _run(source)
    assert sha256(source).hexdigest() == before


def test_private_original_office_source_stroke_registration_when_provisioned():
    path = os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not path:
        pytest.skip("protected Maryborough original not provisioned")
    source = Path(path).read_bytes()
    assert sha256(source).hexdigest() == (
        "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
    )
    result = inspect(
        source, source_sha256=sha256(source).hexdigest(),
        first_page=7, second_page=11,
        first_bounds_pdf_pt=(165., 1368., 335., 1600.),
        second_bounds_pdf_pt=(243., 1368., 413., 1600.),
        candidate_translations_pdf_pt=((78., 0.), (43.92, 0.)),
    )
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.compatible_translations_pdf_pt == ((78., 0.),)
    assert not result.original_w4_wall_issued
    assert not result.physical_floor_issued
    assert not result.metric_area_issued
