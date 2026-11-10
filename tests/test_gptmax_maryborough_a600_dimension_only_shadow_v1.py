"""Source-neutral A600 missing-role rows remain diagnostic; no ghost doors.

The opt-in census is intentionally independent of benchmark item IDs, source
specific dimensions, original private PDFs, opening hosts, or a score.
"""
from __future__ import annotations

import fitz
import pytest

from pb_source_door_schedule_authority import (
    SourceDoorScheduleWord,
    _original_source_row_candidates,
    _dimension_only_native_rows_shadow,
    inspect_published_door_schedule,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _w(block, index, literal, x, y, *, trusted=True, page="1", part="page:1"):
    return SourceDoorScheduleWord(
        observation_id=f"word:{block}:{index}", page_id=page,
        partition_id=part, block_no=block, line_no=index, word_no=0,
        literal=literal, trusted=trusted,
        bbox_pdf_pts=(float(x), float(y), float(x) + 10.0, float(y) + 10.0),
    )


def _world():
    # Two printed DOOR SCHEDULE strings: only one is left of the
    # source-defined header. Mark and numeric columns are independently
    # evidenced, with the printed rows to their right.
    return (
        _w(1, 0, "DOOR", 10, 480), _w(1, 1, "SCHEDULE", 10, 450),
        _w(90, 0, "DOOR", 160, 500), _w(90, 1, "SCHEDULE", 160, 475),
        _w(2, 0, "WIDTH", 40, 100), _w(2, 1, "HEIGHT", 40, 65),
        _w(2, 2, "THICKNESS", 40, 30),
        _w(3, 0, "No.", 40, 230), _w(3, 1, "ROOM", 40, 190),
        _w(3, 2, "NAME", 40, 175), _w(3, 3, "TYPE", 40, 155),
        _w(4, 0, "D13", 70, 300), _w(4, 1, "SWING", 70, 220),
        _w(4, 2, "920", 70, 105), _w(4, 3, "2040", 70, 70),
        _w(5, 0, "D29", 100, 300), _w(5, 1, "UNCLASSIFIED", 100, 210),
        _w(5, 2, "930", 100, 105), _w(5, 3, "2080", 100, 70),
    )


def _shadow(words):
    established = _original_source_row_candidates(words)
    return established, _dimension_only_native_rows_shadow(words, established)


def test_opt_in_finds_native_dimension_witness_but_never_adds_an_issued_row():
    originals = _world()
    established, shadow = _shadow(originals)
    assert [r.code for r in established] == ["D13"]
    assert len(shadow) == 1
    candidate = shadow[0]
    assert candidate.code == "D29"
    assert candidate.status == "source_dimension_only_shadow_not_schedule_authority"
    assert candidate.first_unclosed_gate == "original_schedule_row_role_and_physical_instance_unproven"
    assert (candidate.original_width_literal, candidate.original_height_literal) == ("930", "2080")
    assert (candidate.original_width_word_id, candidate.original_height_word_id) == (
        "word:5:2", "word:5:3",
    )
    assert candidate.source_dimension_column_roles_authenticated is True
    assert candidate.width_height_metric_units_authenticated is False
    assert candidate.physical_host_or_frame_authenticated is False
    assert candidate.default_opening_count is None
    assert candidate.new_customer_quantity_authority is False
    assert originals == _world()  # never modify original immutable source words


def test_missing_headers_or_notes_never_grant_numeric_column_authority():
    words = tuple(w for w in _world() if w.block_no not in (1, 2, 3, 90))
    _, shadow = _shadow(words)
    assert len(shadow) == 1
    assert shadow[0].original_width_literal is None
    assert shadow[0].original_height_literal is None
    assert shadow[0].source_dimension_column_roles_authenticated is False
    assert shadow[0].new_customer_quantity_authority is False


def test_same_code_second_block_is_conflict_not_unique_shadow():
    words = _world() + (
        _w(6, 0, "D29", 140, 300),
        _w(6, 1, "NOTES", 140, 200),
        _w(6, 2, "880", 140, 105),
        _w(6, 3, "2200", 140, 70),
    )
    _, shadow = _shadow(words)
    assert shadow == ()


def test_missing_second_number_and_competing_code_refuse_shadow():
    base = _world()
    one_number = tuple(w for w in base if w.observation_id != "word:5:3")
    _, shadow = _shadow(one_number)
    assert shadow == ()
    rival = base + (_w(5, 4, "D30", 100, 170),)
    _, shadow = _shadow(rival)
    assert shadow == ()


def test_foreign_partition_or_untrusted_number_stays_out_of_source_authority():
    words = list(_world())
    tail = words[-1]
    words[-1] = _w(5, 3, "2080", 100, 70, page="2", part="page:2")
    assert _shadow(tuple(words))[1] == ()
    words[-1] = _w(5, 3, "2080", 100, 70, trusted=False)
    _, shadow = _shadow(tuple(words))
    assert len(shadow) == 1
    assert shadow[0].complete_native_row_text_trusted is False
    assert shadow[0].source_dimension_column_roles_authenticated is False
    assert shadow[0].new_customer_quantity_authority is False


def test_original_source_inspector_shadow_is_explicit_boolean_and_default_off():
    pdf = fitz.open()
    pdf.new_page(width=300, height=300)
    raw = pdf.tobytes()
    pdf.close()
    source = SourceVisibilityProducer(
        producer_method="a600-native-dimension-shadow-guard",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="synthetic-a600-shadow",
        source_bytes=raw,
        source_locator="memory://synthetic-a600.pdf",
        page_ids=("1",),
    )
    args = dict(revision_id=published.revision.revision_id, page_id="1")
    original = inspect_published_door_schedule(source, **args)
    enabled = inspect_published_door_schedule(
        source, **args, dimension_only_source_shadow=True,
    )
    assert original.dimension_only_shadow_rows == enabled.dimension_only_shadow_rows == ()
    assert original.rows == enabled.rows == ()
    assert original.new_opening_counts == enabled.new_opening_counts == 0
    assert original.new_opening_areas_m2 == enabled.new_opening_areas_m2 == 0
    assert original.complete_source_word_universe is False
    with pytest.raises(TypeError, match="dimension_only_source_shadow must be bool"):
        inspect_published_door_schedule(
            source, **args, dimension_only_source_shadow="yes",
        )


def test_sha_pinned_original_a600_shadow_cannot_change_legacy_source_or_commercial_rows():
    """Protected original-only: prove default / opt-in outputs on same immutable PDF.

    Public source-neutral CI must visibly skip without the private original.
    A new row candidate is never an issued door and cannot overwrite the
    existing 27-group source census or the historical signed takeoff.
    """
    import hashlib
    from pathlib import Path

    pdf_path = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
    if not pdf_path.is_file():
        pytest.skip("private original unavailable; original-positive NOT RUN")
    raw = pdf_path.read_bytes()
    source_digest = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
    assert hashlib.sha256(raw).hexdigest() == source_digest
    source = SourceVisibilityProducer(
        producer_method="original-a600-dimension-only-shadow-review",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="original-maryborough-source-native-shadow",
        source_bytes=raw,
        source_locator="memory://protected-original-a600.pdf",
        page_ids=("28",),
    )
    selector = dict(revision_id=published.revision.revision_id, page_id="28")
    original = inspect_published_door_schedule(source, **selector)
    reviewed = inspect_published_door_schedule(
        source, **selector, dimension_only_source_shadow=True,
    )
    assert reviewed.rows == original.rows
    assert reviewed.all_original_source_codes == original.all_original_source_codes
    assert reviewed.unparsed_original_door_codes == original.unparsed_original_door_codes
    assert reviewed.complete_source_word_universe == original.complete_source_word_universe
    assert reviewed.title_source_trusted == original.title_source_trusted
    assert not original.dimension_only_shadow_rows
    assert not reviewed.complete_source_word_universe
    assert {r.code for r in reviewed.dimension_only_shadow_rows}.issubset(
        set(original.unparsed_original_door_codes)
    )
    assert all(
        r.status == "source_dimension_only_shadow_not_schedule_authority"
        and not r.width_height_metric_units_authenticated
        and not r.physical_host_or_frame_authenticated
        and r.default_opening_count is None
        and not r.new_customer_quantity_authority
        for r in reviewed.dimension_only_shadow_rows
    )
    assert reviewed.new_opening_counts == original.new_opening_counts == 0
    assert reviewed.new_opening_areas_m2 == original.new_opening_areas_m2 == 0
    assert hashlib.sha256(pdf_path.read_bytes()).hexdigest() == source_digest
