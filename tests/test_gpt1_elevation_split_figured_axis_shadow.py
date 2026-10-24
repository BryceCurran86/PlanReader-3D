"""Original and gold-free source-figure partition negatives; no quantity grant."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import fitz
import pytest

from pb_gpt1_elevation_split_figured_axis_shadow import (
    NativeAxisLine, NativeAxisWord, audit_source_split_figured_axis_shadow,
)


def line(name, x, a, b):
    return NativeAxisLine(name, (x, a), (x, b))


def word(name, text, x, y):
    return NativeAxisWord(name, text, (x - 4, y - 3, x + 4, y + 3))


def example():
    return dict(
        overall_line=line("whole", 0, 0, 100),
        part_lines=(line("part1", 20, 0, 40), line("part2", 20, 40, 100)),
        dimension_words=(word("total-word", "1800", -4, 50),
                         word("first-word", "700", 16, 20),
                         word("second-word", "1100", 16, 70)),
        opening_mark_words=(word("window-word", "W06", 55, 20),
                            word("door-word", "D02", 55, 70)),
    )


def test_complete_source_shaped_partition_is_only_diagnostic():
    result = audit_source_split_figured_axis_shadow(**example())
    assert result["status"] == "CANDIDATE_SOURCE_SPLIT_FIGURE"
    assert [p["dimension_literal_mm_untrusted"] for p in result["partitions"]] == [700, 1100]
    assert [p["normalized_mark_candidate"] for p in result["partitions"]] == ["W6", "D2"]
    assert not any(result[k] for k in (
        "source_native_glyph_trust_proven", "complete_source_rival_universe_proven",
        "plan_to_elevation_physical_identity_bound", "physical_host_or_frame_bound",
        "metric_quantity_granted", "customer_seal_granted", "benchmark_score_granted",
    ))
    reversed_inputs = example()
    reversed_inputs["part_lines"] = tuple(reversed(reversed_inputs["part_lines"]))
    reversed_inputs["dimension_words"] = tuple(reversed(reversed_inputs["dimension_words"]))
    reversed_inputs["opening_mark_words"] = tuple(reversed(reversed_inputs["opening_mark_words"]))
    assert audit_source_split_figured_axis_shadow(**reversed_inputs) == result


def test_translation_and_axis_rotation_do_not_change_partition_evidence():
    original = example()
    def flip(p):
        return (p[1] + 800.0, p[0] - 50.0)
    def flip_line(v):
        return replace(v, start=flip(v.start), end=flip(v.end))
    def flip_word(v):
        x0, y0, x1, y1 = v.bbox
        return replace(v, bbox=(y0 + 800, x0 - 50, y1 + 800, x1 - 50))
    transformed = dict(
        overall_line=flip_line(original["overall_line"]),
        part_lines=tuple(flip_line(v) for v in original["part_lines"]),
        dimension_words=tuple(flip_word(v) for v in original["dimension_words"]),
        opening_mark_words=tuple(flip_word(v) for v in original["opening_mark_words"]),
    )
    result = audit_source_split_figured_axis_shadow(**transformed)
    assert result["status"] == "CANDIDATE_SOURCE_SPLIT_FIGURE"
    assert result["axis"] == "x"
    assert [p["dimension_literal_mm_untrusted"] for p in result["partitions"]] == [700, 1100]


@pytest.mark.parametrize("change", [
    lambda c: c.update(part_lines=(line("part1", 20, 0, 39), line("part2", 20, 40, 100))),
    lambda c: c.update(part_lines=(line("part1", 20, 0, 45), line("part2", 20, 40, 100))),
    lambda c: c.update(part_lines=(line("part1", 20, 0, 40), line("part2", 22, 40, 100))),
    lambda c: c.update(dimension_words=(c["dimension_words"][0], c["dimension_words"][1], word("second-word", "1200", 16, 70))),
    lambda c: c.update(dimension_words=(c["dimension_words"][0], c["dimension_words"][1], word("second-word", "1100", 50, 70))),
    lambda c: c.update(opening_mark_words=(c["opening_mark_words"][0], word("door-word", "W07", 55, 70))),
    lambda c: c.update(opening_mark_words=(c["opening_mark_words"][0], word("door-word", "W06", 55, 70))),
    lambda c: c.update(opening_mark_words=c["opening_mark_words"] + (word("rival", "D03", 56, 72),)),
    lambda c: c.update(part_lines=(line("whole", 20, 0, 40), c["part_lines"][1])),
])
def test_conflicting_source_partition_abstains(change):
    case = example()
    change(case)
    result = audit_source_split_figured_axis_shadow(**case)
    assert result["status"] == "ABSTAINED"
    assert not result["metric_quantity_granted"]


SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


@pytest.mark.skipif(not SOURCE.is_file(), reason="private original unavailable: trusted owner-main source replay required")
def test_original_a610_split_figures_w06_vs_d02_are_distinct_unpublished_candidates():
    raw = SOURCE.read_bytes()
    assert sha256(raw).hexdigest() == SHA
    with fitz.open(stream=raw, filetype="pdf") as doc:
        page = doc[28]
        def native_line(seq):
            path = next(x for x in page.get_drawings() if x["seqno"] == seq)
            lines = [item for item in path["items"] if item[0] == "l"]
            assert len(lines) == 1 and path["color"] == (0.0, 0.0, 0.0)
            _, a, b = lines[0]
            return NativeAxisLine(f"p29:seq{seq}", (a.x, a.y), (b.x, b.y))
        words = page.get_text("words")
        def native_word(block, line_no, value):
            matched = [w for w in words if w[5] == block and w[6] == line_no and w[4] == value]
            assert len(matched) == 1
            w = matched[0]
            return NativeAxisWord(f"p29:b{block}:l{line_no}:w{w[7]}", w[4], tuple(w[:4]))
        result = audit_source_split_figured_axis_shadow(
            overall_line=native_line(1623),
            part_lines=(native_line(1612), native_line(1607)),
            dimension_words=(native_word(50, 0, "1800"),
                             native_word(49, 0, "700"),
                             native_word(49, 1, "1100")),
            opening_mark_words=(native_word(51, 0, "W06"),
                                native_word(51, 1, "D02")),
        )
        assert result["status"] == "CANDIDATE_SOURCE_SPLIT_FIGURE"
        assert [p["dimension_literal_mm_untrusted"] for p in result["partitions"]] == [1100, 700]
        assert [p["normalized_mark_candidate"] for p in result["partitions"]] == ["D2", "W6"]
        assert result["overall_literal_mm_untrusted"] == 1800
        assert not result["source_native_glyph_trust_proven"]
        assert not result["plan_to_elevation_physical_identity_bound"]
        assert not result["metric_quantity_granted"]
    assert sha256(SOURCE.read_bytes()).hexdigest() == SHA
