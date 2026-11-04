"""Original-page-rotation-aware schedule grouping is an opt-in source proof.

The synthetic word boxes deliberately form one printed 90-degree schedule
table; no benchmark, private drawing, opening count, unit or host is supplied.
"""
from __future__ import annotations

import fitz
import pytest

from pb_schedule_opening_instance_binding_authority import (
    _row_groups_for_page,
    _schedule_entries_for_page,
    _source_owned_page_rotation_matrices,
    ScheduleOpeningInstanceBindingProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _word(oid, text, x, y):
    return (oid, text, (float(x),float(y),float(x+8),float(y+8)))


def _vertical_native_table():
    # Applying a verified 90-degree matrix makes x'=200-y and y'=x.
    # The printed MARK, WIDTH, HEIGHT header is then a single visual row,
    # with the printed D01, 900, 2040 directly beneath it.
    return (
        _word("header-mark","MARK",20,120),
        _word("header-width","WIDTH",20,90),
        _word("header-height","HEIGHT",20,60),
        _word("row-mark","D01",50,120),
        _word("row-width","900",50,90),
        _word("row-height","2040",50,60),
    )


def test_original_90_degree_row_projection_recovers_only_source_grouped_table():
    native = _vertical_native_table()
    default = _schedule_entries_for_page(_row_groups_for_page(native),1)
    assert default == []
    rotation = (0.0,1.0,-1.0,0.0,200.0,0.0)
    rows = _row_groups_for_page(native,rotation_matrix=rotation)
    assert [ids for _row,ids in rows] == [
        ("header-mark","header-width","header-height"),
        ("row-mark","row-width","row-height"),
    ]
    matches = _schedule_entries_for_page(rows,1)
    assert len(matches)==1
    entry, ids = matches[0]
    assert (entry.type_mark,entry.width_mm,entry.height_mm)==("D01",900,2040)
    assert set(ids)=={"row-mark","row-width","row-height"}
    assert entry.dimension_basis==""
    assert entry.count_explicit is False


def test_rotated_grouping_replays_deterministically_and_rejects_fake_matrix():
    native = _vertical_native_table()
    rotation = (0.0,1.0,-1.0,0.0,200.0,0.0)
    original = _row_groups_for_page(native,rotation_matrix=rotation)
    assert _row_groups_for_page(tuple(reversed(native)),rotation_matrix=rotation)==original
    assert native==_vertical_native_table()
    for malformed in ((),(1.0,2.0), [0,1,-1,0,200,0],
                      (0,1,-1,0,float("nan"),0)):
        with pytest.raises(TypeError,match="verified six-value original page rotation"):
            _row_groups_for_page(native,rotation_matrix=malformed)


def test_exact_source_pdf_page_rotation_is_derived_and_hash_bound():
    pdf = fitz.open()
    p = pdf.new_page(width=200,height=120)
    p.insert_text((20,30),"MARK WIDTH HEIGHT")
    p.set_rotation(90)
    raw = pdf.tobytes()
    pdf.close()
    source=SourceVisibilityProducer(producer_method="source-rotation-only",
                                     producer_version="1")
    published=source.ingest_native_pdf_bytes(
        document_id="source-page-rotation-test",
        source_bytes=raw,source_locator="memory://source-rotation.pdf",
        page_ids=("1",),
    )
    matrices=_source_owned_page_rotation_matrices(source,published,("1",))
    assert matrices is not None and "1" in matrices
    assert matrices["1"]==(0.0,1.0,-1.0,0.0,120.0,0.0)
    assert _source_owned_page_rotation_matrices(source,published,("2",)) is None
    assert _source_owned_page_rotation_matrices(source,published,("01",)) is None
    source._producer._store.source_bytes_by_revision[published.revision.revision_id]=b"tampered"
    assert _source_owned_page_rotation_matrices(source,published,("1",)) is None


def test_only_boolean_opt_in_for_live_rotated_native_schedule():
    source=SourceVisibilityProducer(
        producer_method="source-rotation-type-guard",
        producer_version="1",
    )
    with pytest.raises(TypeError,match="rotated_native_schedule_shadow must be bool"):
        ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(
            source,rotated_native_schedule_shadow="true")
    normal=ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(source)
    rotated=ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(
        source,rotated_native_schedule_shadow=True)
    assert normal._rotated_native_schedule_shadow is False
    assert rotated._rotated_native_schedule_shadow is True
