"""No commercial quantity from source-positive Maryborough Dxx plan/schedule labels."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import hashlib

import pytest

from pb_source_door_schedule_authority import (
    SourceDoorScheduleWord as W,
    SourceDoorScheduleRow as Row,
    SourceDoorScheduleResult as Schedule,
)
from pb_source_plan_door_correspondence_authority import (
    pair_trusted_original_door_codes as pair,
    inspect_published_plan_and_schedule_door_codes as inspect,
)
from pb_source_visibility_authority import SourceVisibilityProducer


ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _word(code: str, index: int, *, trusted: bool = True):
    return W(
        observation_id=f"source:7:{index}",
        page_id="7", partition_id="page:7",
        block_no=index, line_no=0, word_no=0,
        literal=code, trusted=trusted,
        bbox_pdf_pts=(10.0 + index * 5, 10.0, 13.0 + index * 5, 18.0),
    )


def _schedule(*rows: Row, extras=()):
    return Schedule(
        source_sha256=SHA,
        revision_id="original-revision", snapshot_id="original-snapshot",
        page_id="28",
        rows=rows,
        all_original_source_codes=tuple(sorted({r.code for r in rows} | set(extras))),
        title_source_trusted=True,
        complete_source_word_universe=True,
    )


def _row(code: str, *, trusted: bool = True):
    return Row(
        code=code, source_page_id="28", native_block_no=int(code[1:]),
        observation_ids=(f"source:28:{code}",),
        original_width_literal="920", original_height_literal="2040",
        door_kind_candidate="solid_core_swing",
        source_title_observation_ids=("original:A600:DOOR", "original:A600:SCHEDULE"),
        complete_native_row_text_trusted=trusted,
        status=(
            "source_schedule_row_text_authenticated"
            if trusted else "source_schedule_row_text_unverified"
        ),
        first_unclosed_gate="source_dimension_units_and_unique_physical_opening_host",
    )


def test_exact_one_to_one_plan_and_schedule_code_pair_has_no_count_or_area_authority():
    plan = (_word("D13", 1), _word("D17", 2))
    result = pair(plan_words=plan, schedule=_schedule(_row("D13"), _row("D17")),
                  plan_page_id="7")
    assert [p.code for p in result.pairs] == ["D13", "D17"]
    assert result.eligible_printed_code_pair_count == 2
    assert not result.unresolved_codes
    assert result.source_sha256 == SHA and result.snapshot_id == "original-snapshot"
    assert all(p.source_code_correspondence_proven for p in result.pairs)
    assert all(
        p.first_unclosed_gate == "physical_door_symbol_host_and_customer_scope_unproven"
        and p.opening_count is None
        and p.installed_opening_area_m2 is None
        and not p.physical_door_symbol_bound
        and not p.structural_host_bound
        and not p.customer_quantity_authorized for p in result.pairs
    )
    assert result.new_opening_counts == result.new_opening_area_quantities == 0
    assert result.frozen_benchmark_accuracy is None


def test_missing_plan_schedule_and_repeated_plan_tag_are_preserved_as_rivals():
    words = (_word("D13", 1), _word("D13", 2), _word("D17", 3),
             _word("D99", 4))
    result = pair(plan_words=words, schedule=_schedule(
        _row("D13"), _row("D14"), _row("D17"), extras=("D18",)
    ), plan_page_id="7")
    codes = {x.code: x for x in result.pairs}
    assert codes["D13"].first_unclosed_gate == "original_plan_door_tag_ambiguous_or_repeated"
    assert codes["D14"].first_unclosed_gate == "original_plan_door_tag_missing"
    assert codes["D18"].first_unclosed_gate == "original_plan_door_tag_missing"
    assert codes["D99"].first_unclosed_gate == "original_schedule_row_missing_or_competing"
    assert codes["D17"].source_code_correspondence_proven
    assert result.eligible_printed_code_pair_count == 1
    assert result.unresolved_codes == ("D13", "D14", "D18", "D99")


def test_schedule_row_untrusted_duplicate_or_incomplete_census_must_abstain():
    source = (_word("D13", 1),)
    for schedule in (
        _schedule(_row("D13", trusted=False)),
        _schedule(_row("D13"), _row("D13")),
        replace(_schedule(_row("D13")), title_source_trusted=False),
        replace(_schedule(_row("D13")), complete_source_word_universe=False),
    ):
        result = pair(plan_words=source, schedule=schedule, plan_page_id="7")
        assert result.eligible_printed_code_pair_count == 0
        assert result.unresolved_codes == ("D13",)
        assert result.pairs[0].opening_count is None


def test_untrusted_and_duplicate_native_plan_source_address_abstain():
    source = _word("D13", 1, trusted=False)
    result = pair(plan_words=(source,), schedule=_schedule(_row("D13")),
                  plan_page_id="7")
    assert result.pairs[0].first_unclosed_gate == "original_plan_text_integrity_unverified"
    assert result.new_opening_counts == 0
    with pytest.raises(ValueError, match="duplicate"):
        pair(plan_words=(source, source), schedule=_schedule(_row("D13")),
             plan_page_id="7")
    with pytest.raises(ValueError, match="duplicate native text address"):
        pair(
            plan_words=(source, replace(source, observation_id="different-parent")),
            schedule=_schedule(_row("D13")), plan_page_id="7",
        )


def test_foreign_plan_page_partition_or_schedule_scope_fails_closed():
    source = _word("D13", 1)
    for invalid in (
        (replace(source, page_id="9"),),
        (replace(source, partition_id="page:9"),),
    ):
        with pytest.raises(ValueError):
            pair(plan_words=invalid, schedule=_schedule(_row("D13")),
                 plan_page_id="7")
    for invalid_page in ("0", "07", "28", "", "foo"):
        with pytest.raises(ValueError, match="distinct plan/schedule"):
            pair(plan_words=(source,), schedule=_schedule(_row("D13")),
                 plan_page_id=invalid_page)
    with pytest.raises(ValueError):
        pair(plan_words=(source,), schedule=object(), plan_page_id="7")


def test_source_visibility_publisher_must_own_revision_and_both_pages():
    producer = SourceVisibilityProducer(producer_method="synthetic-plan-schedule",
                                        producer_version="1")
    with pytest.raises(ValueError, match="source revision missing"):
        inspect(producer, revision_id="foreign", plan_page_id="7",
                schedule_page_id="28")
    with pytest.raises(TypeError, match="visibility issuer"):
        inspect(object(), revision_id="foreign", plan_page_id="7",
                schedule_page_id="28")


def test_original_28_plan_tags_only_if_sha_verified_private_source_present():
    if not ORIGINAL.is_file():
        pytest.skip("PRIVATE ORIGINAL NOT IN PUBLIC CI: source-positive test NOT run")
    data = ORIGINAL.read_bytes()
    assert hashlib.sha256(data).hexdigest() == SHA
    import fitz
    with fitz.open(stream=data, filetype="pdf") as doc:
        words = doc[6].get_text("words")
        schedule_words = doc[27].get_text("words")
    from collections import Counter
    import re
    code = re.compile(r"^D(?:0[1-9]|[1-9][0-9]*)$")
    plan = Counter(w[4] for w in words if code.fullmatch(str(w[4])))
    schedule = Counter(w[4] for w in schedule_words if code.fullmatch(str(w[4])))
    expected = {f"D{i:02d}" for i in range(1, 29)}
    assert set(plan) == expected
    assert all(plan[k] == 1 for k in expected)
    assert all(schedule[k] >= 1 for k in expected)
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() == SHA
    # Source-native words alone cannot issue physical door seals or counts.
