"""Phase-2b structure-adjusted graphic-state check (shadow only).

Synthetic path records test the STATISTICS with hand-computed expectations;
synthetic drawings test the wiring to the Phase-2 join rows.  Neither is
evidence about real drawings and neither chooses a rule, threshold or filter.
"""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import os
import random
import re
import subprocess
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

import fitz
import pytest

import pb_native_graphic_state_join as J
import pb_native_graphic_state_stratified as S
from pb_item35_production_authority_shadow import collect_item35_authority_shadow
from pb_native_graphic_state_join import (
    build_native_graphic_state_join,
    build_native_graphic_state_join_rows,
    collect_native_graphic_state_join,
)
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_provider_gold_isolation import (
    FORBIDDEN_MODULES,
    FORBIDDEN_NAME_FRAGMENTS,
    walk_local_import_graph,
)
from pb_semantic_conflict_diagnostic import collect_semantic_scope, diagnose_semantic_conflicts
from pb_vector_geometry_v130 import extract_native_page
from scripts import native_graphic_state_stratified_report as report_script
from tests.test_native_graphic_state_join_v1 import (
    ADJ_FACES,
    ADJ_JAMBS,
    ALL_SEGMENTS,
    DOC,
    _pdf,
    _rows,
    _scope,
    _sel,
    _separate,
    _write,
)

REPO = Path(__file__).resolve().parents[1]
MODULE = "pb_native_graphic_state_stratified"
FIXTURES = REPO / "tests" / "fixtures" / "native_graphic_state_join"
SHA = "b" * 64
LINE = "native_line"
RECT = "native_rect_edge"
BLACK = "(0.0000,0.0000,0.0000)"
GREY = "(0.5000,0.5000,0.5000)"
SUPPRESSED = S.RATIO_SUPPRESSED_LOW_N


# ------------------------------------------------- synthetic path records
_counter = {"n": 0}


def rec(page="1", klass=LINE, *, size=1, part=0, control=0, fill=False, stroke=BLACK,
        width="1.0000", layer=J.ABSENT, dash=J.ABSENT, fill_colour=GREY, index=None):
    if index is None:
        _counter["n"] += 1
        index = _counter["n"]
    paint = ("stroke_and_fill" if fill else "stroke_only") if stroke != J.ABSENT else (
        "fill_only" if fill else "neither_present"
    )
    return S.PathRecord(
        page_id=page,
        path_index=index,
        ref_class=klass,
        visible_primitives=size,
        participating_primitives=part,
        control_primitives=control,
        states={
            "stroke_state": stroke,
            "fill_state": fill_colour if fill else J.ABSENT,
            "paint_presence": paint,
            "width_state": width,
            "dash_state": dash,
            "layer_state": layer,
            "fill_presence": S.FILL_PRESENT if fill else S.FILL_ABSENT,
        },
    )


def group(page, size, count, filled, *, participating, klass=LINE, **kw):
    """``count`` paths of one size on one page, ``filled`` of them carrying a fill."""
    out = []
    for i in range(count):
        out.append(
            rec(page, klass, size=size, part=(size if participating else 0), fill=i < filled, **kw)
        )
    return out


def analyse(records):
    return S.analyse_paths(records, source_sha256=SHA)


def outcome(result, plan, field, value, klass=LINE):
    return result[klass]["plans"][plan]["fields"][field]["outcomes"][value]


def fill_outcome(result):
    return outcome(result, "lines_fill_presence", S.FILL_PRESENCE, S.FILL_PRESENT)


# ------------------------------------------- Simpson's paradox and friends
def _two_band_population(p_big, p_small, m_big=(30, 24), m_small=(60, 12), *, page="1"):
    """P and M over two size bands; each argument is (paths, filled)."""
    return [
        *group(page, 6, *p_big, participating=True),
        *group(page, 1, *p_small, participating=True),
        *group(page, 6, *m_big, participating=False),
        *group(page, 1, *m_small, participating=False),
    ]


def test_a_crude_enrichment_that_is_only_path_size_vanishes_after_stratification():
    # fill rate 0.8 in the big-path stratum and 0.2 in the small one, in BOTH groups; the
    # participating group merely sits mostly in the big-path stratum
    result = analyse(_two_band_population((60, 48), (30, 6)))
    entry = fill_outcome(result)
    crude = entry["crude"]
    assert (crude["paths_participating"], crude["k_participating"]) == (90, 54)
    assert (crude["paths_baseline"], crude["k_baseline"]) == (90, 36)
    assert (crude["share_participating"], crude["share_baseline"], crude["difference"]) == (0.6, 0.4, 0.2)
    assert entry["eligible_strata_only"]["difference"] == 0.2  # every stratum is judgeable: nothing dropped
    std = entry["standardised"]
    assert std["state"] == "ok"
    assert (std["share_participating"], std["share_baseline_standardised"], std["difference"]) == (0.6, 0.6, 0.0)
    assert entry["retained_fraction_vs_eligible_only"] == 0.0
    assert entry["sign_relation_vs_eligible_only"] == "adjusted_zero"
    assert entry["retained_fraction_vs_crude"] == 0.0 and entry["sign_relation_vs_crude"] == "adjusted_zero"
    assert entry["sign_concordance"]["zero"] == 2 and entry["sign_concordance"]["positive"] == 0
    assert entry["coverage"]["share_participating"] == 1.0


def test_a_residual_difference_inside_every_stratum_persists():
    result = analyse(_two_band_population((60, 54), (30, 9)))  # +0.1 in both strata
    entry = fill_outcome(result)
    assert entry["crude"]["difference"] == 0.3
    assert entry["standardised"]["difference"] == 0.1
    assert entry["retained_fraction_vs_eligible_only"] == 0.333333
    assert entry["sign_relation_vs_eligible_only"] == "same_sign"
    assert entry["retained_fraction_vs_crude"] == 0.333333 and entry["sign_relation_vs_crude"] == "same_sign"
    concordance = entry["sign_concordance"]
    assert (concordance["positive"], concordance["negative"], concordance["zero"]) == (2, 0, 0)
    assert concordance["dominant_sign_share"] == 1.0


def test_a_simpson_reversal_flips_the_sign_and_the_strata_show_it():
    result = analyse(_two_band_population((60, 42), (30, 3)))  # -0.1 in both strata
    entry = fill_outcome(result)
    assert entry["crude"]["difference"] == 0.1  # crude says enriched ...
    assert entry["standardised"]["difference"] == -0.1  # ... every stratum says depleted
    assert entry["retained_fraction_vs_eligible_only"] == -1.0
    assert entry["sign_relation_vs_eligible_only"] == "opposite_sign"
    assert entry["retained_fraction_vs_crude"] == -1.0 and entry["sign_relation_vs_crude"] == "opposite_sign"
    concordance = entry["sign_concordance"]
    assert concordance["negative"] == 2 and concordance["dominant_sign_share"] == 1.0
    assert concordance["dominant_sign_share_denominator"] == 2
    assert concordance["participating_paths_in_negative_strata"] == 90
    assert concordance["participating_paths_in_positive_strata"] == concordance["participating_paths_in_zero_strata"] == 0
    table = result[LINE]["plans"]["lines_fill_presence"]["strata"]["table"]
    assert [row[1]["visible_segments_band"] for row in table] == ["1", "6-10"]
    assert entry["strata_rows"] == [[0, 3, 12, -0.1], [1, 42, 24, -0.1]]  # nothing hidden


def test_strata_with_opposite_signs_are_all_listed_and_counted():
    records = [
        *group("1", 6, 30, 27, participating=True),
        *group("1", 1, 30, 3, participating=True),
        *group("1", 6, 30, 15, participating=False),
        *group("1", 1, 30, 15, participating=False),
    ]
    entry = fill_outcome(analyse(records))
    concordance = entry["sign_concordance"]
    assert (concordance["positive"], concordance["negative"], concordance["zero"]) == (1, 1, 0)
    assert concordance["dominant_sign_share"] == 0.5 and concordance["dominant_sign_share_denominator"] == 2
    assert concordance["participating_paths_in_positive_strata"] == 30
    assert concordance["participating_paths_in_negative_strata"] == 30
    assert entry["standardised"]["difference"] == 0.0
    assert sorted(row[3] for row in entry["strata_rows"]) == [-0.4, 0.4]


# ------------------------------------------------------ the floor of thirty
def test_thirty_paths_in_each_group_is_eligible_and_twenty_nine_is_not():
    records = [
        *group("1", 1, 30, 15, participating=True),
        *group("1", 1, 30, 10, participating=False),
        *group("2", 1, 30, 15, participating=True),
        *group("2", 1, 29, 10, participating=False),
    ]
    result = analyse(records)
    strata = result[LINE]["plans"]["lines_fill_presence"]["strata"]
    assert strata["total"] == 2 and strata["eligible"] == 1
    assert [row[4] for row in strata["table"]] == [True, False]
    assert [row[2:4] for row in strata["table"]] == [[30, 30], [30, 29]]  # raw counts always printed
    assert strata["participating_coverage"] == 0.5
    assert strata["baseline_paths_in_eligible_strata"] == 30 and strata["baseline_paths_total"] == 59
    entry = fill_outcome(result)
    assert entry["strata_rows"][1] == [1, 15, 10, None]  # ineligible: counts, no ratio
    assert entry["strata_rows"][0][3] == round(15 / 30 - 10 / 30, 6)
    assert entry["sign_concordance"]["eligible_strata"] == 1


def test_standardisation_uses_only_strata_where_both_groups_reach_the_floor():
    records = [
        *group("1", 1, 40, 20, participating=True),   # s1: .5 vs .25
        *group("1", 1, 80, 20, participating=False),
        *group("1", 2, 40, 10, participating=True),   # s2: .25 vs .5
        *group("1", 2, 40, 20, participating=False),
        *group("2", 1, 100, 100, participating=True),  # s3: 10 baseline paths -> ineligible
        *group("2", 1, 10, 0, participating=False),
    ]
    entry = fill_outcome(analyse(records))
    crude, eligible, std = entry["crude"], entry["eligible_strata_only"], entry["standardised"]
    assert (crude["paths_participating"], crude["k_participating"]) == (180, 130)
    assert (crude["paths_baseline"], crude["k_baseline"]) == (130, 40)
    assert crude["difference"] == round(130 / 180 - 40 / 130, 6)
    assert (eligible["paths_participating"], eligible["paths_baseline"]) == (80, 120)
    assert eligible["difference"] == round(30 / 80 - 40 / 120, 6)  # 0.041667: composition
    assert std["share_participating"] == 0.375 and std["share_baseline_standardised"] == 0.375
    assert std["difference"] == 0.0  # reweighting the baseline to P's mix removes it
    assert entry["coverage"]["share_participating"] == round(80 / 180, 6)
    assert entry["coverage"]["share_baseline"] == round(120 / 130, 6)
    assert entry["sign_concordance"]["eligible_strata"] == 2
    # the ineligible stratum still appears with its raw counts
    assert [row[1:3] for row in entry["strata_rows"]][-1] == [100, 0]


def test_no_eligible_stratum_reports_a_state_not_a_number():
    entry = fill_outcome(analyse([*group("1", 1, 40, 20, participating=True), *group("1", 1, 20, 5, participating=False)]))
    crude = entry["crude"]
    assert crude["share_participating"] == 0.5 and crude["share_baseline"] == SUPPRESSED
    assert crude["difference"] == SUPPRESSED and crude["paths_baseline"] == 20 and crude["k_baseline"] == 5
    assert entry["standardised"] == {
        "state": "no_eligible_strata",
        "share_participating": None,
        "share_baseline_standardised": None,
        "difference": None,
    }
    assert entry["retained_fraction_vs_eligible_only"] is None and entry["retained_fraction_vs_crude"] is None
    assert entry["sign_relation_vs_eligible_only"] == entry["sign_relation_vs_crude"] == "not_estimable"
    assert entry["coverage"]["share_participating"] == 0.0 and entry["coverage"]["paths_participating_in_eligible_strata"] == 0


def test_a_group_below_the_floor_never_prints_a_ratio_even_for_coverage():
    result = analyse([*group("1", 1, 29, 10, participating=True), *group("1", 1, 90, 30, participating=False)])
    entry = fill_outcome(result)
    assert entry["crude"]["share_participating"] == SUPPRESSED and entry["crude"]["paths_participating"] == 29
    assert entry["coverage"]["share_participating"] == SUPPRESSED
    assert result[LINE]["plans"]["lines_fill_presence"]["strata"]["participating_coverage"] == SUPPRESSED


def test_the_floor_is_the_approved_thirty_unique_paths():
    assert S.RATIO_MIN_UNIQUE_PATHS == 30 and SUPPRESSED == "ratio_suppressed_low_n"


# ------------------------------------------- fill presence, conditioning
def _fill_confounded_lines():
    """Participating lines are mostly fill-only (no stroke); within fill status both groups agree."""
    def mk(part, fill, count):
        return [
            rec("1", LINE, size=1, part=(1 if part else 0), fill=fill, stroke=(J.ABSENT if fill else BLACK))
            for _ in range(count)
        ]
    return [*mk(True, True, 60), *mk(True, False, 30), *mk(False, True, 30), *mk(False, False, 60)]


def test_other_outcomes_are_conditioned_on_fill_presence_but_fill_presence_is_not():
    result = analyse(_fill_confounded_lines())
    plans = result[LINE]["plans"]
    assert plans["lines_fill_presence"]["stratifiers"] == ["page_id", "visible_segments_band"]
    assert plans["lines_conditioned_on_fill"]["stratifiers"] == ["page_id", "visible_segments_band", "fill"]
    stroke_absent = outcome(result, "lines_conditioned_on_fill", "stroke_state", J.ABSENT)
    assert stroke_absent["crude"]["difference"] == round(60 / 90 - 30 / 90, 6)  # looks enriched
    assert stroke_absent["standardised"]["difference"] == 0.0  # fill status explains it
    assert stroke_absent["sign_concordance"]["eligible_strata"] == 2
    # fill presence is the outcome of its own plan: it is NOT stratified away
    fill = fill_outcome(result)
    assert fill["crude"]["difference"] == round(60 / 90 - 30 / 90, 6)
    assert fill["standardised"]["difference"] == fill["crude"]["difference"]


def test_fill_colour_of_lines_is_only_analysed_among_filled_paths():
    records = [
        *[rec("1", LINE, part=1, fill=True, fill_colour=GREY) for _ in range(40)],
        *[rec("1", LINE, part=1, fill=False) for _ in range(40)],
        *[rec("1", LINE, part=0, fill=True, fill_colour=GREY if i % 2 else "(1.0000,1.0000,1.0000)") for i in range(60)],
        *[rec("1", LINE, part=0, fill=False) for _ in range(60)],
    ]
    field = analyse(records)[LINE]["plans"]["lines_conditioned_on_fill"]["fields"]["fill_state"]
    assert field["fill_present_strata_only"] is True and J.ABSENT not in field["values_analysed"]
    grey = field["outcomes"][GREY]
    assert grey["crude"]["paths_participating"] == 40 and grey["crude"]["paths_baseline"] == 60  # filled paths only
    assert len(grey["strata_rows"]) == 1  # only the fill-present stratum is applicable
    assert (grey["crude"]["share_participating"], grey["crude"]["share_baseline"]) == (1.0, 0.5)


def test_outcome_values_are_capped_absent_is_kept_and_the_rest_is_folded():
    layers = [f"present:L{i:02d}" for i in range(14)]
    records = []
    for i, layer in enumerate(layers):  # L00 most common ... L13 least common
        records += [rec("1", LINE, part=1, layer=layer) for _ in range(20 - i)]
        records += [rec("1", LINE, part=0, layer=layer) for _ in range(20 - i)]
    records += [rec("1", LINE, part=1, layer=J.ABSENT) for _ in range(3)]
    field = analyse(records)[LINE]["plans"]["lines_conditioned_on_fill"]["fields"]["layer_state"]
    values = field["values_analysed"]
    assert values[0] == J.ABSENT and values[-1] == S.OTHER_VALUES and len(values) == S.MAX_VALUES + 1
    assert values[1:-1] == layers[: S.MAX_VALUES - 1]  # ranked by path count, ties by name
    assert field["distinct_values_folded_into_other"] == 3
    folded = field["outcomes"][S.OTHER_VALUES]["crude"]
    assert folded["paths_participating"] == sum(20 - i for i in range(14)) + 3  # every participating path
    assert folded["k_participating"] == sum(20 - i for i in range(11, 14))  # L11 + L12 + L13
    assert folded["k_baseline"] == sum(20 - i for i in range(11, 14))
    assert field["outcomes"][J.ABSENT]["crude"]["k_participating"] == 3


# ----------------------------------------------------------- the null split
def test_null_half_depends_only_on_source_owned_identity_and_is_balanced():
    a = S.null_half(SHA, "3", 17, LINE, "null_split_v1:0")
    assert all(S.null_half(SHA, "3", 17, LINE, "null_split_v1:0") == a for _ in range(50))
    halves = Counter(S.null_half(SHA, "1", i, LINE, "null_split_v1:0") for i in range(4000))
    assert 0.46 < halves[0] / 4000 < 0.54
    other_salt = [S.null_half(SHA, "1", i, LINE, "null_split_v1:1") for i in range(400)]
    same_salt = [S.null_half(SHA, "1", i, LINE, "null_split_v1:0") for i in range(400)]
    assert other_salt != same_salt
    assert [S.null_half("c" * 64, "1", i, LINE, "null_split_v1:0") for i in range(400)] != same_salt
    pages = [S.null_half(SHA, str(page), 5, LINE, "s") for page in range(1, 60)]
    assert len(set(pages)) == 2  # the page is part of the identity


def test_null_split_ignores_participation_and_replays_identically():
    base = [rec("1", LINE, index=i, part=0, fill=i % 3 == 0) for i in range(300)]
    flipped = [dataclasses.replace(r, participating_primitives=(1 if i % 5 == 0 else 0)) for i, r in enumerate(base)]
    baseline_of_flipped = [r for r in flipped if not r.participating]
    halves_a = {r.key: S.null_half(SHA, r.page_id, r.path_index, r.ref_class, "null_split_v1:0") for r in base}
    halves_b = {r.key: S.null_half(SHA, r.page_id, r.path_index, r.ref_class, "null_split_v1:0") for r in flipped}
    assert halves_a == halves_b  # which participating flags exist does not move any path
    result = analyse(flipped)
    sizes = result[LINE]["plans"]["lines_fill_presence"]["null_control"]["halves"]
    for salt, entry in zip(S.NULL_SPLIT_SALTS, sizes):
        expected = Counter(S.null_half(SHA, r.page_id, r.path_index, r.ref_class, salt) for r in baseline_of_flipped)
        assert entry == {"salt": salt, "paths_half_a": expected[0], "paths_half_b": expected[1]}
        assert entry["paths_half_a"] + entry["paths_half_b"] == len(baseline_of_flipped)
    assert json.dumps(result, sort_keys=True) == json.dumps(analyse(flipped), sort_keys=True)


def test_null_control_matches_an_independent_recomputation():
    records = [
        *[rec("1", LINE, index=i, part=1, fill=i % 2 == 0) for i in range(80)],
        *[rec("1", LINE, index=1000 + i, part=0, fill=(i * 7) % 5 < 2) for i in range(400)],
    ]
    entry = fill_outcome(analyse(records))
    baseline = [r for r in records if not r.participating]
    for i, salt in enumerate(S.NULL_SPLIT_SALTS):
        a = [r for r in baseline if S.null_half(SHA, r.page_id, r.path_index, r.ref_class, salt) == 0]
        b = [r for r in baseline if S.null_half(SHA, r.page_id, r.path_index, r.ref_class, salt) == 1]
        share = lambda group: sum(r.states[S.FILL_PRESENCE] == S.FILL_PRESENT for r in group) / len(group)
        expected = round(share(a) - share(b), 6)
        assert entry["null_control"]["difference_crude"][i] == pytest.approx(expected, abs=2e-6)
        assert entry["null_control"]["difference_adjusted"][i] == pytest.approx(expected, abs=2e-6)  # one stratum
        assert entry["null_control"]["eligible_strata"][i] == 1


def test_null_control_uses_only_the_baseline_and_never_reads_participating_paths():
    baseline = [rec("1", LINE, index=i, part=0, fill=i % 2 == 0) for i in range(200)]
    weird = [rec("1", LINE, index=5000 + i, part=1, fill=True) for i in range(100)]
    changed = [rec("1", LINE, index=5000 + i, part=1, fill=False) for i in range(100)]
    assert fill_outcome(analyse(baseline + weird))["null_control"] == fill_outcome(analyse(baseline + changed))["null_control"]


# ------------------------------------------------------ order, exactness, ids
def _mixed_population():
    rng = random.Random(7)
    out = []
    for page in ("1", "2", "10"):
        for size in (1, 2, 4, 8, 20):
            for participating in (True, False):
                for _ in range(35):
                    out.append(
                        rec(page, LINE, size=size, part=(size if participating else 0), fill=rng.random() < 0.4,
                            stroke=rng.choice([BLACK, GREY, J.ABSENT]), width=rng.choice(["1.0000", "2.0000", J.ABSENT]),
                            layer=rng.choice([J.ABSENT, "present:A", "present:B"]),
                            dash=rng.choice([J.ABSENT, "array_empty"]))
                    )
    for size in (1, 3, 4):
        for participating in (True, False):
            for _ in range(32):
                out.append(rec("1", RECT, size=size, part=(size if participating else 0), fill=rng.random() < 0.5,
                               stroke=J.ABSENT))
    return out


def test_result_is_invariant_to_input_order():
    records = _mixed_population()
    expected = json.dumps(analyse(records), sort_keys=True)
    shuffled = random.Random(3).sample(records, len(records))
    assert json.dumps(analyse(shuffled), sort_keys=True) == expected
    assert json.dumps(analyse(reversed(records)), sort_keys=True) == expected
    assert json.dumps(analyse(iter(records)), sort_keys=True) == expected


def test_arithmetic_is_exact_and_only_rounded_on_output():
    records = [*group("1", 1, 30, 10, participating=True), *group("1", 1, 30, 20, participating=False)]
    crude = fill_outcome(analyse(records))["crude"]
    assert crude["share_participating"] == 0.333333 and crude["share_baseline"] == 0.666667
    assert crude["difference"] == -0.333333  # exact 1/3 - 2/3 = -1/3, rounded once


def _snapshot(records):
    return [
        (r.page_id, r.path_index, r.ref_class, r.visible_primitives, r.participating_primitives,
         r.control_primitives, tuple(sorted(r.states.items())))
        for r in records
    ]


def test_analysis_never_mutates_its_input_and_records_are_immutable():
    records = _mixed_population()
    before = _snapshot(records)
    order = list(records)
    analyse(records)
    assert records == order
    assert _snapshot(records) == before
    with pytest.raises(dataclasses.FrozenInstanceError):
        records[0].page_id = "x"  # type: ignore[misc]
    with pytest.raises(TypeError):
        records[0].states["stroke_state"] = "x"  # type: ignore[index]


def test_native_paths_are_page_qualified_and_duplicates_are_refused():
    same_index = [rec("1", LINE, index=0), rec("2", LINE, index=0)]
    assert analyse(same_index)[LINE]["population"]["baseline_paths"] == 2  # path 0 on two pages: two paths
    with pytest.raises(ValueError, match="duplicate"):
        analyse([rec("1", LINE, index=0), rec("1", LINE, index=0)])
    assert analyse([rec("1", LINE, index=0), rec("1", RECT, index=0)])  # a class is part of the identity
    with pytest.raises(ValueError):
        S.analyse_paths([], source_sha256="")


def test_lines_and_rect_edges_are_never_pooled():
    result = analyse(_mixed_population())
    assert set(result) == {LINE, RECT}
    assert set(result[LINE]["plans"]) == {
        "lines_fill_presence",
        "lines_conditioned_on_fill",
        "lines_fill_presence_fine_bands",
        "lines_conditioned_on_fill_fine_bands",
    }
    assert set(result[RECT]["plans"]) == {
        "rect_edges_by_visible_edge_band",
        "rect_edges_by_visible_edge_count_fine",
    }
    sensitivity = {n for k in (LINE, RECT) for n, p in result[k]["plans"].items() if p["sensitivity_only"]}
    assert sensitivity == {
        "lines_fill_presence_fine_bands",
        "lines_conditioned_on_fill_fine_bands",
        "rect_edges_by_visible_edge_count_fine",
    }
    approved = {n for k in (LINE, RECT) for n, p in result[k]["plans"].items() if not p["sensitivity_only"]}
    assert approved == {"lines_fill_presence", "lines_conditioned_on_fill", "rect_edges_by_visible_edge_band"}
    lines = sum(1 for r in _mixed_population() if r.ref_class == LINE)
    assert result[LINE]["population"]["participating_paths"] + result[LINE]["population"]["baseline_paths"] == lines
    assert result[RECT]["plans"]["rect_edges_by_visible_edge_count_fine"]["sensitivity_only"] is True
    assert result[RECT]["plans"]["rect_edges_by_visible_edge_band"]["sensitivity_only"] is False
    fields = result[RECT]["plans"]["rect_edges_by_visible_edge_band"]["fields"]
    assert set(fields) == {"fill_state", "paint_presence"}  # fill colour is descriptive, never a stratifier


def test_records_reject_impossible_counts_and_missing_states():
    with pytest.raises(ValueError):
        rec("1", LINE, size=2, part=2, control=1)
    with pytest.raises(ValueError):
        rec("1", LINE, size=0)
    with pytest.raises(ValueError):
        S.PathRecord("1", 0, "unclassified", 1, 0, 0, {})
    good = rec("1", LINE)
    with pytest.raises(ValueError):
        dataclasses.replace(good, states={"stroke_state": BLACK})


def test_bands_and_strata_schemes_are_pinned():
    assert [S.line_band(n) for n in (1, 2, 3, 5, 6, 10, 11, 500)] == ["1", "2", "3-5", "3-5", "6-10", "6-10", "11+", "11+"]
    assert [S.rect_band(n) for n in (1, 2, 3, 5, 6, 40)] == ["1-2", "1-2", "3-5", "3-5", "6+", "6+"]
    assert [S.rect_fine_band(n) for n in (1, 2, 3, 4, 5, 8, 9, 40)] == ["1", "2", "3", "4", "5-8", "5-8", "9+", "9+"]
    plans = {p.name: p for p in S.PLANS}
    assert plans["lines_fill_presence"].bands == S.LINE_BANDS and not plans["lines_fill_presence"].with_fill
    assert plans["lines_conditioned_on_fill"].with_fill
    assert plans["rect_edges_by_visible_edge_band"].bands == S.RECT_BANDS
    assert not any(p.with_fill for p in S.PLANS if p.ref_class == RECT)


def test_a_plan_that_conditions_a_field_on_fill_needs_fill_as_a_stratifier():
    with pytest.raises(ValueError):
        S._Plan("x", LINE, S.line_band, S.LINE_BANDS, "b", False, (S._Field("fill_state", fill_present_only=True),))


def test_population_block_counts_paths_mixed_paths_and_control():
    records = [
        rec("1", RECT, size=4, part=3, control=0),   # mixed: one edge not participating
        rec("1", RECT, size=4, part=4),               # wholly participating
        rec("1", RECT, size=4, part=0, control=1),    # control, baseline
        rec("1", RECT, size=2, part=0),               # plain baseline
    ]
    population = analyse(records)[RECT]["population"]
    assert population["participating_paths"] == 2 and population["participating_primitives"] == 7
    assert population["baseline_paths"] == 2 and population["mixed_paths"] == 1 and population["control_paths"] == 1
    assert population["control_description"] == "counts_only"
    assert population["control_paths_at_or_above_floor"] is False
    assert population["baseline_group"] == "visible_universe_candidate_pages_minus_participating"


# ------------------------------------- path records from real join rows
def _joined(oid, page, path, item, edge, *, fill=False, klass=LINE):
    ref = f"visible:segment:d{path}i{item}" + (f"e{edge}" if edge is not None else "")
    state = J.GraphicState(
        stroke=(0.0, 0.0, 0.0), stroke_present=True,
        fill=(0.5, 0.5, 0.5) if fill else None, fill_present=fill,
        width=1.0, width_present=True, layer="", layer_present=False, dashes="", dashes_present=False,
    )
    return oid, J.JoinRow(
        observation_id=oid, page_id=page, raw_ref=ref, ref_class=klass, path_index=path, item_index=item,
        edge_index=edge, status=J.STATUS_JOINED, state=state, replay_items_in_path=2,
    )


def _unjoined(oid, page, path, item, status=J.STATUS_MISSING_IN_REPLAY):
    return oid, J.JoinRow(
        observation_id=oid, page_id=page, raw_ref=f"visible:segment:d{path}i{item}", ref_class=LINE,
        path_index=path, item_index=item, edge_index=None, status=status, state=None, replay_items_in_path=None,
    )


def _synthetic_bundle(rows, participating, control, pages=("1",)):
    from types import MappingProxyType
    return J.NativeJoinRows(
        status=J.SCOPE_STATUS_OK, record=None, published=None, computed_sha="0" * 64, semantic_result=None,
        rows=MappingProxyType(dict(rows)), candidate_pages=frozenset(pages), candidates_total=0,
        participating_candidates=0, unavailable_pages=(), participating_weight=MappingProxyType({}),
        ambiguous=frozenset(), control_members=frozenset(control), missing_rows=(),
        populations=MappingProxyType({
            J.G_PARTICIPATING: MappingProxyType({o: 1 for o in participating}),
            J.G_CONTROL: MappingProxyType({o: 1 for o in control}),
        }),
        path_sizes=MappingProxyType({}), pages_replayed=0, pages_unavailable=(), duplicate_replay_identities=0,
    )


def test_path_records_use_class_specific_counts_and_exclude_paths_with_an_unjoined_row():
    rows = dict([
        _joined("a", "1", 0, 0, None),                      # path 0: a line ...
        _joined("b", "1", 0, 1, 0, klass=RECT),             # ... and rect edges in the SAME path
        _joined("c", "1", 0, 1, 1, klass=RECT),
        _joined("d", "1", 0, 1, 2, klass=RECT),
        _joined("e", "1", 1, 0, None, fill=True),           # path 1: one filled line
        _joined("f", "1", 2, 0, None),                      # path 2: joined line ...
        _unjoined("g", "1", 2, 1),                          # ... plus a line that did not join
        _joined("i", "1", 3, 0, None),                      # path 3: a participating line ...
        _unjoined("j", "1", 3, 1),                          # ... plus a line that did not join
        _joined("h", "2", 0, 0, None),                      # page 2 has no candidates: outside the universe
    ])
    bundle = _synthetic_bundle(rows, participating={"a", "b", "c", "i"}, control={"e"}, pages=("1",))
    population = S.build_path_records(bundle)
    records = {r.key: r for r in population.records}
    assert set(records) == {("1", 0, LINE), ("1", 0, RECT), ("1", 1, LINE)}
    assert records[("1", 0, LINE)].visible_primitives == 1  # class-specific: the rect edges are not lines
    assert records[("1", 0, RECT)].visible_primitives == 3
    assert (records[("1", 0, LINE)].participating_primitives, records[("1", 0, RECT)].participating_primitives) == (1, 2)
    assert records[("1", 1, LINE)].control_primitives == 1 and not records[("1", 1, LINE)].participating
    assert records[("1", 1, LINE)].states[S.FILL_PRESENCE] == S.FILL_PRESENT
    assert dict(population.excluded_paths) == {LINE: 2}  # paths 2 and 3 are never analysed on partial information
    assert dict(population.unjoined_rows_in_excluded_paths) == {J.STATUS_MISSING_IN_REPLAY: 2}
    assert dict(population.excluded_joined_participating_primitives) == {LINE: 1}  # "i" is counted, not lost
    assert not any(k[0] == "2" for k in records)


def test_path_records_refuse_a_bundle_without_rows(tmp_path):
    source, result, reference, payload = _scope(_pdf(tmp_path, "separate", _separate()))
    mismatched = build_native_graphic_state_join_rows(
        source_visibility_producer=source, semantic_result=result, source_bytes=payload + b"\n%x"
    )
    assert not mismatched.ok
    with pytest.raises(ValueError):
        S.build_path_records(mismatched)


# ------------------------------------------------------ drawings end to end
FILL_STYLE = {"color": (0, 0, 0), "width": 1, "fill": (0.8, 0.8, 0.8)}


def _shift(segment, dy):
    return ((segment[0][0], segment[0][1] + dy), (segment[1][0], segment[1][1] + dy))


def _bulk_groups(*, copies=4, isolated=45, filled_participating=30, filled_baseline=15, fn=None):
    """40 participating single-segment lines and 45 isolated vertical lines on one page."""
    fn = fn or (lambda p: p)
    groups = []
    participating = [_shift(s, 150 * i) for i in range(copies) for s in ADJ_FACES + ADJ_JAMBS]
    for i, segment in enumerate(participating):
        groups.append(([(fn(segment[0]), fn(segment[1]))], FILL_STYLE if i < filled_participating else None))
    for j in range(isolated):
        segment = ((360 + 6 * j, 700), (360 + 6 * j, 730))
        groups.append(([(fn(segment[0]), fn(segment[1]))], FILL_STYLE if j < filled_baseline else None))
    return groups


def _stratified(pdf, **kw):
    return S.collect_stratified_graphic_state_check(pdf, document_id=DOC, **kw).to_dict()


def _oracle(pdf):
    """Independent oracle: participating / baseline line paths straight from the accessor and producer."""
    source, result, reference, payload, refs, participating, control, count_in = _rows(pdf)
    from pb_candidate_provenance_census import parse_visible_segment_ref
    keys = {}
    for oid, ref in refs.items():
        parsed = parse_visible_segment_ref(ref)
        if parsed.ref_class == LINE:
            keys[oid] = int(parsed.path_index)
    part_paths = {keys[o] for o in participating if o in keys}
    base_paths = set(keys.values()) - part_paths
    document = fitz.open(stream=payload, filetype="pdf")
    native = extract_native_page(document.load_page(0))
    document.close()
    filled = {seg["path_index"] for seg in native["segments"] if seg.get("fill_present") is True}
    return part_paths, base_paths, filled


def test_end_to_end_counts_match_an_independent_oracle(tmp_path):
    pdf = _pdf(tmp_path, "bulk", _bulk_groups(), height=1000)
    check = _stratified(pdf)
    assert check["status"] == "ok" and check["integrity"]["checks"]["all_checks_passed"] is True
    part_paths, base_paths, filled = _oracle(pdf)
    population = check["classes"][LINE]["population"]
    assert population["participating_paths"] == len(part_paths) == 40
    assert population["baseline_paths"] == len(base_paths) == 45
    entry = check["classes"][LINE]["plans"]["lines_fill_presence"]["fields"][S.FILL_PRESENCE]["outcomes"][S.FILL_PRESENT]
    crude = entry["crude"]
    assert crude["k_participating"] == len(part_paths & filled) == 30
    assert crude["k_baseline"] == len(base_paths & filled) == 15
    assert crude["difference"] == round(30 / 40 - 15 / 45, 6)
    assert entry["standardised"]["difference"] == crude["difference"]  # one stratum: nothing to adjust
    assert entry["coverage"]["share_participating"] == 1.0
    assert [row[1] for row in check["classes"][LINE]["plans"]["lines_fill_presence"]["strata"]["table"]] == [
        {"page_id": "1", "visible_segments_band": "1"}
    ]


def test_end_to_end_rows_digest_and_counts_are_the_phase_2_join_rows(tmp_path):
    pdf = _pdf(tmp_path, "bulk", _bulk_groups(), height=1000)
    join = collect_native_graphic_state_join(pdf, document_id=DOC).to_dict()
    check = _stratified(pdf)
    integrity = check["integrity"]
    assert integrity["rows_digest"] == join["rows_digest"]
    assert integrity["join_status_counts"] == join["join_status_counts"]
    assert integrity["candidates_total"] == join["scope"]["candidates_total"]
    assert integrity["participating_candidates"] == join["scope"]["participating_candidates"]
    part = join["groups"]["participating_member_incidences"]["native_line"]
    assert integrity["participating_incidences_native"][LINE] == part["incidences"]
    assert integrity["participating_primitives_native"][LINE] == part["joined_primitives"]
    assert check["binding"]["source_sha256"] == join["binding"]["source_sha256"]
    assert check["binding"]["semantic_record_id"] == join["binding"]["semantic_record_id"]
    assert check["view_id"] is None and check["view_scope_status"] == "unavailable"
    assert check["commercial_authority_granted"] is False


def test_end_to_end_rect_edges_and_mixed_paths(tmp_path):
    def draw(page, idx):
        page.draw_rect(fitz.Rect(20, 100, 100, 110), color=(0, 0, 0), width=1)
        page.draw_rect(fitz.Rect(140, 100, 220, 110), color=(0, 0, 0), width=1, fill=(0.9, 0.9, 0.9))
        page.draw_rect(fitz.Rect(260, 100, 300, 110), color=(0, 0, 0), width=1)

    check = _stratified(_write(tmp_path / "blocks.pdf", draw))
    assert check["integrity"]["checks"]["all_checks_passed"] is True
    population = check["classes"][RECT]["population"]
    assert population["participating_paths"] == 3 and population["baseline_paths"] == 0
    assert population["participating_primitives"] == 10 and population["mixed_paths"] == 2  # 10 of 12 edges
    plan = check["classes"][RECT]["plans"]["rect_edges_by_visible_edge_band"]
    assert plan["strata"]["table"][0][1] == {"page_id": "1", "visible_edges_band": "3-5"}
    assert check["classes"][LINE]["population"]["participating_paths"] == 0


def test_a_path_holding_lines_and_rect_edges_is_two_class_specific_records(tmp_path):
    def draw(page, idx):
        shape = page.new_shape()
        shape.draw_line(fitz.Point(20, 300), fitz.Point(100, 300))
        shape.draw_rect(fitz.Rect(140, 300, 220, 310))
        shape.finish(color=(0, 0, 0), width=1, closePath=False)
        shape.commit()
        page.draw_rect(fitz.Rect(20, 100, 100, 110), color=(0, 0, 0), width=1)
        page.draw_rect(fitz.Rect(140, 100, 220, 110), color=(0, 0, 0), width=1)

    pdf = _write(tmp_path / "mixedpath.pdf", draw)
    source, result, reference, payload = _scope(pdf)
    bundle = build_native_graphic_state_join_rows(
        source_visibility_producer=source, semantic_result=result, source_bytes=payload
    )
    records = {r.key: r for r in S.build_path_records(bundle).records}
    both = [k for k in records if k[2] == LINE and (k[0], k[1], RECT) in records]
    assert both, "expected one path holding both classes"
    line, rect = records[both[0]], records[(both[0][0], both[0][1], RECT)]
    assert (line.visible_primitives, rect.visible_primitives) == (1, 4)
    assert dict(line.states) == dict(rect.states)  # graphic state is constant per path


def _without_null(value):
    """The null split is keyed by the source SHA-256, so it legitimately differs per file."""
    if isinstance(value, dict):
        return {k: _without_null(v) for k, v in value.items() if k != "null_control"}
    if isinstance(value, list):
        return [_without_null(v) for v in value]
    return value


def test_invariant_under_exact_transforms_drawing_order_page_expansion_and_unrelated_pages(tmp_path):
    base = _stratified(_pdf(tmp_path, "base", _bulk_groups(), height=1000))["classes"]
    moved = _stratified(_pdf(tmp_path, "moved", _bulk_groups(fn=lambda p: (p[0] + 30.0, p[1] + 40.0)), height=1000))["classes"]
    scaled = _stratified(_pdf(tmp_path, "scaled", _bulk_groups(fn=lambda p: (p[0] * 2.0, p[1] * 2.0)), width=1400, height=2000))["classes"]
    transposed = _stratified(_pdf(tmp_path, "transposed", _bulk_groups(fn=lambda p: (p[1], p[0])), width=1000, height=700))["classes"]
    reordered = _stratified(_pdf(tmp_path, "reordered", list(reversed(_bulk_groups())), height=1000))["classes"]
    wide = _stratified(_pdf(tmp_path, "wide", _bulk_groups(), width=3000, height=3000))["classes"]
    expected = json.dumps(_without_null(base), sort_keys=True)
    for other in (moved, scaled, transposed, reordered, wide):
        assert json.dumps(_without_null(other), sort_keys=True) == expected
    groups = _bulk_groups()

    def draw(page, idx):
        from tests.test_native_graphic_state_join_v1 import _draw
        _draw(page, groups if idx == 0 else [([((500, 500), (600, 540))], {"color": (0, 1, 0), "width": 5})])

    two_pages = _stratified(_write(tmp_path / "two.pdf", draw, pages=2, height=1000))["classes"]
    assert json.dumps(_without_null(two_pages), sort_keys=True) == expected  # page 2 has no candidates


def test_the_null_split_is_source_owned_so_it_follows_the_bytes_not_the_geometry(tmp_path):
    a = _pdf(tmp_path, "a", _bulk_groups(), height=1000)
    replay_1, replay_2 = _stratified(a)["classes"], _stratified(a)["classes"]
    assert json.dumps(replay_1, sort_keys=True) == json.dumps(replay_2, sort_keys=True)  # same bytes, same split
    moved = _stratified(_pdf(tmp_path, "b", _bulk_groups(fn=lambda p: (p[0] + 30.0, p[1] + 40.0)), height=1000))["classes"]
    halves = lambda classes: classes[LINE]["plans"]["lines_fill_presence"]["null_control"]["halves"]
    assert halves(moved) != halves(replay_1)  # different bytes, a different (still participation-blind) split


def test_an_unrelated_isolated_line_on_the_candidate_page_changes_only_the_baseline(tmp_path):
    base = _stratified(_pdf(tmp_path, "base", _bulk_groups(), height=1000))["classes"][LINE]["population"]
    more = _stratified(_pdf(tmp_path, "more", _bulk_groups() + [([((10, 900), (10, 950))], None)], height=1000))["classes"][LINE]["population"]
    assert more["participating_paths"] == base["participating_paths"]
    assert more["baseline_paths"] == base["baseline_paths"] + 1


def test_splitting_a_segment_adds_one_primitive_and_keeps_the_path_state(tmp_path):
    groups = _bulk_groups()
    split = list(groups)
    (first, style) = split[-1]  # an isolated baseline line
    (a, b) = first[0]
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    split[-1] = ([(a, mid), (mid, b)], style)
    states = {}
    for name, g in (("base", groups), ("split", split)):
        pdf = _pdf(tmp_path, name, g, height=1000)
        source, result, reference, payload = _scope(pdf)
        bundle = build_native_graphic_state_join_rows(
            source_visibility_producer=source, semantic_result=result, source_bytes=payload
        )
        records = {r.key: r for r in S.build_path_records(bundle).records if r.ref_class == LINE}
        states[name] = records
    assert set(states["base"]) == set(states["split"])
    changed = [k for k in states["base"] if states["base"][k].visible_primitives != states["split"][k].visible_primitives]
    assert len(changed) == 1
    (key,) = changed
    assert states["split"][key].visible_primitives == states["base"][key].visible_primitives + 1 == 2
    assert dict(states["split"][key].states) == dict(states["base"][key].states)
    # strata depend on the visible-primitive count by design, so this move is a band change, nothing more
    assert S.line_band(1) != S.line_band(2)


# ------------------------------------------------------ fail closed / order
def test_sha_mismatch_means_no_analysis_and_no_extraction(tmp_path, monkeypatch):
    pdf = _pdf(tmp_path, "bulk", _bulk_groups(), height=1000)
    source, result, reference, payload = _scope(pdf)
    monkeypatch.setattr(J, "extract_native_page", lambda *a, **k: pytest.fail("extracted"))
    monkeypatch.setattr(J.fitz, "open", lambda *a, **k: pytest.fail("opened"))
    check = S.build_stratified_graphic_state_check(
        source_visibility_producer=source, semantic_result=result, source_bytes=payload + b"\n%tampered"
    ).to_dict()
    assert check["status"] == "no_join_sha_mismatch"
    assert check["binding"]["supplied_bytes_sha256"] != check["binding"]["source_sha256"]
    assert "classes" not in check and "integrity" not in check


def test_non_bytes_input_is_rejected(tmp_path):
    source, result, reference, payload = _scope(_pdf(tmp_path, "s", _separate()))
    with pytest.raises(TypeError):
        S.build_stratified_graphic_state_check(
            source_visibility_producer=source, semantic_result=result, source_bytes="x"  # type: ignore[arg-type]
        )


def test_a_path_with_an_unjoined_row_is_excluded_and_counted_never_guessed(tmp_path, monkeypatch):
    pdf = _pdf(tmp_path, "bulk", _bulk_groups(), height=1000)
    real = J.extract_native_page

    def dropping(page):
        native = real(page)
        segments = [s for s in native["segments"] if s["id"] != "d3i0"]
        return {**native, "segments": segments}

    monkeypatch.setattr(J, "extract_native_page", dropping)
    check = _stratified(pdf)
    integrity = check["integrity"]
    assert integrity["join_status_counts"][J.STATUS_MISSING_IN_REPLAY] == 1
    assert integrity["excluded_paths"] == {LINE: 1} and integrity["analysis_complete"] is False
    assert integrity["unjoined_rows_in_excluded_paths"] == {J.STATUS_MISSING_IN_REPLAY: 1}
    assert integrity["checks"]["no_path_excluded_for_an_unjoined_row"] is False
    assert integrity["checks"]["participating_primitives_match_join_rows"] is True  # the excluded path is counted
    assert integrity["checks"]["all_checks_passed"] is False
    population = check["classes"][LINE]["population"]
    assert population["participating_paths"] + population["baseline_paths"] == 84  # 85 lines, 1 excluded


def test_a_participating_path_with_an_unjoined_member_is_excluded_and_its_joined_members_are_counted(
    tmp_path, monkeypatch
):
    jamb = ADJ_JAMBS[0]  # a participating segment, drawn in one path with an unrelated far-away line
    far = ((600, 600), (600, 640))
    groups = [([jamb, far], None)] + [([s], None) for s in ALL_SEGMENTS if s != jamb]
    pdf = _pdf(tmp_path, "sharedpath", groups)
    clean = _stratified(pdf)
    assert clean["integrity"]["checks"]["all_checks_passed"] is True
    real = J.extract_native_page

    def dropping(page):
        native = real(page)
        return {**native, "segments": [s for s in native["segments"] if s["id"] != "d0i1"]}

    monkeypatch.setattr(J, "extract_native_page", dropping)
    check = _stratified(pdf)
    integrity = check["integrity"]
    assert integrity["excluded_paths"] == {LINE: 1}
    assert integrity["unjoined_rows_in_excluded_paths"] == {J.STATUS_MISSING_IN_REPLAY: 1}
    assert integrity["excluded_joined_participating_primitives"] == {LINE: 1}  # the jamb joined, but its path is out
    assert integrity["checks"]["participating_primitives_match_join_rows"] is True
    assert integrity["checks"]["all_checks_passed"] is False and integrity["analysis_complete"] is False
    before = clean["classes"][LINE]["population"]
    after = check["classes"][LINE]["population"]
    assert before["participating_paths"] + before["baseline_paths"] - 1 == after["participating_paths"] + after["baseline_paths"]


# ---------------------------------------------- the refactor: nothing changed
GOLDEN = json.loads((FIXTURES / "golden_1079_output.json").read_text(encoding="utf-8"))


def _with_unavailable_pages(source, result, payload):
    from types import SimpleNamespace

    from pb_migration_contracts import EvidenceResolutionStatus

    real = J.PhysicalOpeningAuthority

    class Stub(real):
        def visible_candidate_structures(self, selector):
            return SimpleNamespace(
                status=EvidenceResolutionStatus.ABSTAINED, page_id="1",
                reason_codes=("stub_reason", "another"), candidates=(),
            )

    J.PhysicalOpeningAuthority = Stub
    try:
        return build_native_graphic_state_join(
            source_visibility_producer=source, semantic_result=result, source_bytes=payload
        )
    finally:
        J.PhysicalOpeningAuthority = real


def _golden_cases():
    return sorted(GOLDEN["cases"])


def _run_case(case):
    stem, label = case.split(":")
    pdf = FIXTURES / f"{stem}.pdf"
    payload = pdf.read_bytes()
    doc_id = GOLDEN["document_id"]
    if label in {"all", "p0", "noref"}:
        kw = {"p0": {"pages": [0]}, "noref": {"with_reference": False}}.get(label, {})
        return collect_native_graphic_state_join(pdf, document_id=doc_id, source_bytes=payload, **kw)
    source, result = collect_semantic_scope(pdf, document_id=doc_id, pages=None, source_bytes=payload)
    if label == "sha_mismatch":
        return build_native_graphic_state_join(
            source_visibility_producer=source, semantic_result=result, source_bytes=payload + b"\n%x"
        )
    if label == "absent":
        return build_native_graphic_state_join(
            source_visibility_producer=source, semantic_result=dataclasses.replace(result, record=None),
            source_bytes=payload,
        )
    if label == "unavailable_pages":
        return _with_unavailable_pages(source, result, payload)
    kind = label.removeprefix("mut_")
    # the dropsecond cases were recorded without the independent structure reference
    reference = None if kind == "dropsecond" else diagnose_semantic_conflicts(
        source_visibility_producer=source, semantic_result=result
    ).candidate_structure
    real = J.extract_native_page

    def mutated(page):
        native = real(page)
        segments = list(native.get("segments") or [])
        if kind == "drop" and segments:
            segments.pop(3 if len(segments) > 3 else 0)
        if kind == "dup" and segments:
            segments.append(dict(segments[2 if len(segments) > 2 else 0]))
        if kind == "geom" and segments:
            index = 1 if len(segments) > 1 else 0
            segment = dict(segments[index])
            segment["x1"] = float(segment["x1"]) + 0.5
            segments[index] = segment
        if kind == "id" and segments:
            segment = dict(segments[0])
            segment["id"] = "d9999i9"
            segments[0] = segment
        if kind == "pathmeta" and len(segments) > 1:
            segment = dict(segments[0])
            segment["stroke"] = [0.3, 0.3, 0.3]
            segments[0] = segment
        if kind == "dropsecond" and len(segments) > 1:
            segments.pop(1)
        if kind == "unavail":
            raise RuntimeError("no replay")
        return {**native, "segments": segments}

    J.extract_native_page = mutated
    try:
        return build_native_graphic_state_join(
            source_visibility_producer=source, semantic_result=result, source_bytes=payload, reference_structure=reference
        )
    finally:
        J.extract_native_page = real


def test_golden_fixtures_are_the_committed_bytes():
    for name, digest in GOLDEN["fixtures"].items():
        assert hashlib.sha256((FIXTURES / f"{name}.pdf").read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("case", _golden_cases())
def test_phase_2_join_output_and_ids_are_byte_identical_to_the_1079_head(case):
    if fitz.VersionBind != GOLDEN["pymupdf_version"]:
        pytest.skip(f"golden recorded under PyMuPDF {GOLDEN['pymupdf_version']}, running {fitz.VersionBind}")
    join = _run_case(case)
    expected = GOLDEN["cases"][case]
    assert join.record_id == expected["record_id"]  # the record id is the content id
    assert hashlib.sha256(join.payload_json.encode("utf-8")).hexdigest() == expected["payload_sha256"]
    payload = json.loads(join.payload_json)
    assert payload["status"] == expected["status"] and payload.get("rows_digest") == expected["rows_digest"]


def test_the_golden_set_covers_every_join_status_the_join_can_report():
    seen = set()
    for expected in GOLDEN["cases"].values():
        seen.update((expected.get("join_status_counts") or {}))
    assert {
        J.STATUS_JOINED, J.STATUS_NOT_NATIVE, J.STATUS_MISSING_IN_REPLAY, J.STATUS_REPLAY_UNAVAILABLE,
        J.STATUS_CONFLICT_DUPLICATE, J.STATUS_CONFLICT_GEOMETRY, J.STATUS_CONFLICT_IDENTITY_FIELDS,
        J.STATUS_CONFLICT_PATH_METADATA,
    } <= seen
    statuses = {v["status"] for v in GOLDEN["cases"].values()}
    assert {"ok", "no_join_sha_mismatch", "semantic_record_absent"} <= statuses  # every sealed regime
    assert any(k.endswith(":unavailable_pages") for k in GOLDEN["cases"])  # candidate pages that were unavailable
    assert any(k.endswith(":mut_dropsecond") for k in GOLDEN["cases"])  # a path with a joined and an unjoined member


def test_the_golden_is_recorded_under_the_pinned_pymupdf():
    """A bumped pin must re-record the golden (the case test skips off-pin runs, so this cannot)."""
    pins = re.findall(r"^PyMuPDF==([\d.]+)\s*$", (REPO / "requirements.txt").read_text(encoding="utf-8"), re.M)
    assert pins == [GOLDEN["pymupdf_version"]]


def test_the_exposed_rows_are_exactly_what_the_join_aggregates(tmp_path):
    pdf = _pdf(tmp_path, "bulk", _bulk_groups(), height=1000)
    source, result, reference, payload = _scope(pdf)
    bundle = build_native_graphic_state_join_rows(
        source_visibility_producer=source, semantic_result=result, source_bytes=payload
    )
    join = build_native_graphic_state_join(
        source_visibility_producer=source, semantic_result=result, source_bytes=payload, reference_structure=reference
    ).to_dict()
    assert bundle.ok and J.digest_of_rows(bundle.rows) == join["rows_digest"]
    assert Counter(r.status for r in bundle.rows.values()) == Counter(join["join_status_counts"])
    assert len(bundle.rows) == join["replay"]["rows_total"]
    assert sorted(bundle.candidate_pages) == join["scope"]["candidate_pages"]
    assert bundle.candidates_total == join["scope"]["candidates_total"]
    assert bundle.participating_candidates == join["scope"]["participating_candidates"]
    universe = join["groups"]["visible_universe_candidate_pages"]["native_line"]
    assert len(bundle.populations[J.G_UNIVERSE_CAND_PAGES]) == universe["primitives"]
    part = join["groups"]["participating_member_incidences"]["native_line"]
    assert sum(bundle.populations[J.G_PARTICIPATING].values()) == part["incidences"]
    assert bundle.pages_replayed == join["replay"]["pages_replayed"]


def test_the_bundle_carries_the_control_members_the_join_aggregates(tmp_path):
    pdf = _pdf(tmp_path, "separate", _separate())  # two adjacent openings + one isolated control opening
    source, result, reference, payload, refs, participating, control, count_in = _rows(pdf)
    bundle = build_native_graphic_state_join_rows(
        source_visibility_producer=source, semantic_result=result, source_bytes=payload
    )
    assert control and bundle.control_members == frozenset(control)
    assert set(bundle.populations[J.G_CONTROL]) == set(control)
    assert set(bundle.participating_weight) == set(participating)
    assert bundle.ambiguous == frozenset(o for o, n in count_in.items() if n > 1)
    check = S.build_stratified_graphic_state_check(
        source_visibility_producer=source, semantic_result=result, source_bytes=payload
    ).to_dict()
    assert check["classes"][LINE]["population"]["control_paths"] == len(control)  # one path per segment here


def test_unavailable_candidate_pages_are_carried_and_fail_the_checks(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from pb_migration_contracts import EvidenceResolutionStatus

    pdf = _pdf(tmp_path, "separate", _separate())
    source, result, reference, payload = _scope(pdf)
    stub = SimpleNamespace(
        status=EvidenceResolutionStatus.ABSTAINED, page_id="1", reason_codes=("stub_reason",), candidates=()
    )

    class Stub(PhysicalOpeningAuthority):
        def visible_candidate_structures(self, selector):
            return stub

    monkeypatch.setattr(J, "PhysicalOpeningAuthority", Stub)
    bundle = build_native_graphic_state_join_rows(
        source_visibility_producer=source, semantic_result=result, source_bytes=payload
    )
    expected = ({"page_id": "1", "status": str(stub.status.value), "reason_codes": ["stub_reason"]},)
    (entry,) = bundle.unavailable_pages
    assert dict(entry) == {"page_id": "1", "status": str(stub.status.value), "reason_codes": ("stub_reason",)}
    with pytest.raises(TypeError):
        entry["status"] = "x"  # type: ignore[index]
    assert not bundle.candidate_pages
    join = build_native_graphic_state_join(
        source_visibility_producer=source, semantic_result=result, source_bytes=payload
    ).to_dict()
    assert join["scope"]["unavailable_pages"] == list(expected)
    assert join["consistency"]["no_unavailable_candidate_pages"] is False
    check = S.build_stratified_graphic_state_check(
        source_visibility_producer=source, semantic_result=result, source_bytes=payload
    ).to_dict()
    assert check["integrity"]["unavailable_pages"] == list(expected)
    assert check["integrity"]["analysis_complete"] is False
    assert check["integrity"]["analysis_state"] == "incomplete_unavailable_candidate_pages"
    assert check["integrity"]["checks"]["no_unavailable_candidate_pages"] is False
    assert check["integrity"]["checks"]["all_checks_passed"] is False
    assert check["classes"][LINE]["population"]["participating_paths"] == 0  # nothing is guessed for that page


def test_an_absent_semantic_record_is_reported_as_absent_everywhere(tmp_path):
    pdf = _pdf(tmp_path, "separate", _separate())
    source, result, reference, payload = _scope(pdf)
    absent = dataclasses.replace(result, record=None)
    bundle = build_native_graphic_state_join_rows(
        source_visibility_producer=source, semantic_result=absent, source_bytes=payload
    )
    assert bundle.status == J.SCOPE_STATUS_ABSENT and not bundle.ok and not bundle.rows
    join = build_native_graphic_state_join(
        source_visibility_producer=source, semantic_result=absent, source_bytes=payload
    ).to_dict()
    check = S.build_stratified_graphic_state_check(
        source_visibility_producer=source, semantic_result=absent, source_bytes=payload
    ).to_dict()
    for report in (join, check):
        assert report["status"] == "semantic_record_absent" and report["binding"] is None
        assert "groups" not in report and "classes" not in report
    assert check["semantic_reason_codes"] == join["semantic_reason_codes"]


def test_the_bundle_is_read_only(tmp_path):
    source, result, reference, payload = _scope(_pdf(tmp_path, "bulk", _bulk_groups(), height=1000))
    bundle = build_native_graphic_state_join_rows(
        source_visibility_producer=source, semantic_result=result, source_bytes=payload
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        bundle.rows = {}  # type: ignore[misc]
    oid = next(iter(bundle.rows))
    with pytest.raises(TypeError):
        bundle.rows[oid] = bundle.rows[oid]  # type: ignore[index]
    with pytest.raises(TypeError):
        bundle.populations[J.G_PARTICIPATING][oid] = 99  # type: ignore[index]
    with pytest.raises(TypeError):
        bundle.participating_weight[oid] = 99  # type: ignore[index]
    with pytest.raises(TypeError):
        bundle.path_sizes[("1", 0)] = 99  # type: ignore[index]
    with pytest.raises(dataclasses.FrozenInstanceError):
        bundle.rows[oid].status = "x"  # type: ignore[misc]
    assert isinstance(bundle.candidate_pages, frozenset) and isinstance(bundle.ambiguous, frozenset)


# ------------------------- no effect on candidates, decisions, or production
def _decisions(source, result):
    record = result.record
    authority = source.authority()
    fresh = PhysicalOpeningAuthority(authority)
    out = []
    for oid in sorted(record.visible_observation_ids):
        selector = _sel(record, oid)
        existence = fresh.prove_existence(selector)
        out.append(
            (
                fresh.classify_disposition(selector),
                (existence.status, existence.reason_codes, existence.existence_record),
                fresh.assess_visible_candidate_closure(selector),
                fresh.visible_candidate_structures(selector),
            )
        )
    return out


def test_the_check_changes_no_decision_candidate_or_shared_state(tmp_path):
    pdf = _pdf(tmp_path, "bulk", _bulk_groups(), height=1000)
    source, result, reference, payload = _scope(pdf)
    published = source.published_snapshot_for_revision(result.record.revision_id)
    before = _decisions(source, result)
    check = S.build_stratified_graphic_state_check(
        source_visibility_producer=source, semantic_result=result, source_bytes=payload
    )
    assert check.to_dict()["status"] == "ok"
    assert _decisions(source, result) == before
    assert source.published_snapshot_for_revision(result.record.revision_id) == published
    assert reference.candidates_total == diagnose_semantic_conflicts(
        source_visibility_producer=source, semantic_result=result
    ).candidate_structure.candidates_total


def test_shadow_and_commercial_output_are_identical_with_and_without_the_check(tmp_path):
    pdf = _pdf(tmp_path, "bulk", _bulk_groups(), height=1000)
    before = collect_item35_authority_shadow(pdf, document_id=DOC)
    check = _stratified(pdf)
    after = collect_item35_authority_shadow(pdf, document_id=DOC)
    assert before == after
    assert check["binding"]["semantic_record_id"] == before["semantic_record_id"]
    assert check["commercial_authority_granted"] is False


def test_a_garbage_analysis_cannot_change_the_pipeline(tmp_path, monkeypatch):
    pdf = _pdf(tmp_path, "bulk", _bulk_groups(), height=1000)
    baseline = collect_item35_authority_shadow(pdf, document_id=DOC)
    monkeypatch.setattr(S, "analyse_paths", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        S.collect_stratified_graphic_state_check(pdf, document_id=DOC)
    assert collect_item35_authority_shadow(pdf, document_id=DOC) == baseline


def test_record_id_is_deterministic_content_bound_and_tamper_evident(tmp_path):
    pdf = _pdf(tmp_path, "bulk", _bulk_groups(), height=1000)
    a = S.collect_stratified_graphic_state_check(pdf, document_id=DOC)
    b = S.collect_stratified_graphic_state_check(pdf, document_id=DOC)
    assert a.record_id == b.record_id and a.payload_json == b.payload_json
    other = _pdf(tmp_path, "other", _bulk_groups(filled_participating=10), height=1000)
    assert S.collect_stratified_graphic_state_check(other, document_id=DOC).record_id != a.record_id
    with pytest.raises(ValueError):
        dataclasses.replace(a, record_id="0" * 32)
    with pytest.raises(ValueError):
        dataclasses.replace(a, commercial_authority_granted=True)


def test_check_does_not_depend_on_filename_or_document_label(tmp_path):
    pdf = _pdf(tmp_path, "bulk", _bulk_groups(), height=1000)
    copy_path = tmp_path / "renamed_lamu_like_name.pdf"
    copy_path.write_bytes(pdf.read_bytes())
    a = _stratified(pdf)["classes"]
    b = S.collect_stratified_graphic_state_check(copy_path, document_id="other-label").to_dict()["classes"]
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_page_scope_and_document_scope_agree_for_one_page(tmp_path):
    pdf = _pdf(tmp_path, "bulk", _bulk_groups(), height=1000)
    assert json.dumps(_stratified(pdf)["classes"], sort_keys=True) == json.dumps(
        _stratified(pdf, pages=[0])["classes"], sort_keys=True
    )


# ------------------------------------------------- isolation / authority rules
def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return {name for name in found if name.startswith(("pb_", "scripts"))}


def test_module_only_uses_public_seams():
    assert _imports(REPO / f"{MODULE}.py") == {
        "pb_migration_contracts",
        "pb_native_graphic_state_join",
        "pb_semantic_conflict_diagnostic",
        "pb_semantic_opening_enumeration_authority",
        "pb_source_visibility_authority",
    }
    assert _imports(REPO / "scripts" / "native_graphic_state_stratified_report.py") == {MODULE}
    tree = ast.parse((REPO / f"{MODULE}.py").read_text(encoding="utf-8"))
    names = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("pb_")
        for alias in node.names
    ]
    assert names and not [n for n in names if n.startswith("_")]  # no private name is imported
    private = [
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr.startswith("_")
        and not (node.attr.startswith("__") and node.attr.endswith("__"))  # object.__setattr__ (frozen freeze)
        and not (isinstance(node.value, ast.Name) and node.value.id in {"self", "plan", "field"})
    ]
    assert private == []
    text = (REPO / f"{MODULE}.py").read_text(encoding="utf-8")
    for accessor in ("visible_candidate_structures", "resolve_visible", "PhysicalOpeningAuthority"):
        assert accessor not in text, accessor  # every accessor call stays inside the join
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
    }
    assert "extract_native_page" not in used and "open" not in used  # the replay stays inside the join
    assert "fitz.VersionBind" in text  # fitz is only imported to name the version in the binding


def test_module_never_touches_the_network_or_a_source_locator():
    text = (REPO / f"{MODULE}.py").read_text(encoding="utf-8")
    for fragment in ("urllib", "requests", "http", "socket", "os.environ", "glob("):
        assert fragment not in text, fragment


def test_module_and_script_are_gold_free():
    visited, findings = walk_local_import_graph(MODULE)
    assert findings == () and not set(visited) & FORBIDDEN_MODULES
    for path in (REPO / f"{MODULE}.py", REPO / "scripts" / "native_graphic_state_stratified_report.py"):
        text = path.read_text(encoding="utf-8").lower()
        for fragment in FORBIDDEN_NAME_FRAGMENTS:
            assert fragment not in text, (path.name, fragment)
        assert "benchmarks/" not in text


def test_no_production_module_imports_the_check():
    offenders = []
    for path in sorted(REPO.rglob("*.py")):
        relative = path.relative_to(REPO)
        if relative.parts[0] in {"tests", "scripts", ".git"} or path.name == f"{MODULE}.py":
            continue
        if MODULE in path.read_text(encoding="utf-8", errors="ignore"):
            offenders.append(str(relative))
    assert offenders == []


def test_importing_the_live_extractor_does_not_load_the_check():
    code = (
        "import sys\n"
        "import pb_planreader_pdf_extractor, pb_item35_production_authority_shadow\n"
        f"sys.exit(1 if {MODULE!r} in sys.modules else 0)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO,
        env={**os.environ, "PYTHONPATH": str(REPO)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr[-2000:]


def test_the_check_never_rejects_filters_or_names_a_metadata_rule():
    source = (REPO / f"{MODULE}.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            assert not re.search(r"reject|filter_|threshold|drop_|noise|is_opening|is_false", node.name), node.name
    assert "commercial_authority_granted" in source
    # the only numeric constant that gates anything is the display floor
    assert source.count("RATIO_MIN_UNIQUE_PATHS") >= 5
    doc = ast.get_docstring(tree) or ""
    assert "never that a candidate is false or real" in " ".join(doc.split()) or "never that a candidate is false or real" in source


def test_conclusion_limit_is_stated_in_the_report_itself(tmp_path):
    check = _stratified(_pdf(tmp_path, "bulk", _bulk_groups(), height=1000))
    text = check["definitions"]["conclusion_limit"]
    assert "residual association" in text and "never that a candidate is false or real" in text
    assert check["definitions"]["floor"]["is_a_production_threshold"] is False
    assert check["definitions"]["classes_pooled"] is False


# ---------------------------------------------------------------- the script
def test_script_report_is_deterministic_and_never_pools(tmp_path):
    a = _pdf(tmp_path, "a", _bulk_groups(), height=1000)
    b = _pdf(tmp_path, "b", _bulk_groups(filled_participating=12), height=1000)
    first = report_script.build_report([a, b])
    second = report_script.build_report([b, a])
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["pooled"] is False and len(first["entries"]) == 2
    assert first["coverage"]["entries_ok"] == 2 and first["coverage"]["entries_sha_mismatch"] == 0
    assert all(e["stratified"]["integrity"]["checks"]["all_checks_passed"] for e in first["entries"])


def test_script_errors_are_reported_and_cli_works(tmp_path):
    good = _pdf(tmp_path, "good", _bulk_groups(), height=1000)
    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"not a pdf")
    missing = tmp_path / "missing.pdf"
    report = report_script.build_report([bad, missing])
    assert sorted(e["status"] for e in report["entries"]) == ["error", "source_unavailable"]
    out = tmp_path / "out" / "report.json"
    assert report_script.main([str(good), "--output", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["entries"][0]["stratified"]["status"] == "ok"
    assert report_script.main([str(bad), "--output", str(tmp_path / "e.json")]) == 1
    assert report_script.main([str(tmp_path / "nope_dir")]) in (1, 2)


def test_script_uses_the_same_document_id_derivation_as_the_join_report():
    from scripts import native_graphic_state_join_report as join_report

    payload = b"%PDF-fixture"
    assert report_script.document_id_for(payload) == join_report.document_id_for(payload)


# ---------------------------------- review follow-ups: sensitivity, folded values, accounting
def test_pages_that_thin_every_stratum_give_no_adjusted_estimate_and_no_plan_recovers_one():
    records = []
    for page in ("1", "2", "3"):  # 12 vs 12 per page: no page stratum reaches the floor of 30
        records += group(page, 1, 12, 6, participating=True)
        records += group(page, 1, 12, 3, participating=False)
    result = analyse(records)
    entry = fill_outcome(result)
    assert entry["standardised"]["state"] == "no_eligible_strata" and entry["standardised"]["difference"] is None
    assert entry["coverage"]["share_participating"] == 0.0 and entry["retained_fraction_vs_crude"] is None
    assert entry["sign_relation_vs_crude"] == "not_estimable"
    assert entry["crude"]["difference"] == 0.25  # the crude number is still shown, as a crude number
    # low page-stratified coverage is the result: no plan drops page from the conditioning set
    for klass in (LINE, RECT):
        for name, plan in result[klass]["plans"].items():
            assert plan["stratifiers"][0] == "page_id", name
            assert all(row[1]["page_id"] in {"1", "2", "3"} for row in plan["strata"]["table"]), name


def test_page_composition_alone_is_removed_by_the_page_strata():
    # each page is internally null (P and M share the page's fill rate), but the pages differ and P sits on page 2
    records = [
        *group("1", 1, 30, 3, participating=True), *group("1", 1, 90, 9, participating=False),
        *group("2", 1, 90, 72, participating=True), *group("2", 1, 30, 24, participating=False),
    ]
    entry = fill_outcome(analyse(records))
    assert entry["crude"]["difference"] == 0.35  # page composition looks like an effect ...
    assert entry["standardised"]["difference"] == 0.0  # ... and vanishes once page is held fixed
    assert entry["sign_concordance"]["zero"] == 2 and entry["retained_fraction_vs_crude"] == 0.0


def test_a_crude_effect_carried_by_an_ineligible_stratum_is_not_reported_as_retained():
    records = [
        *group("1", 1, 30, 12, participating=True), *group("1", 1, 30, 15, participating=False),  # eligible, -0.1
        *group("2", 1, 100, 100, participating=True), *group("2", 1, 5, 0, participating=False),  # below the floor
    ]
    entry = fill_outcome(analyse(records))
    crude = Fraction(112, 130) - Fraction(3, 7)
    assert entry["crude"]["difference"] == round(float(crude), 6) > 0.43
    assert entry["eligible_strata_only"]["difference"] == entry["standardised"]["difference"] == -0.1
    # against the eligible strata alone nothing changed, against the crude difference the sign reversed
    assert entry["retained_fraction_vs_eligible_only"] == 1.0 and entry["sign_relation_vs_eligible_only"] == "same_sign"
    assert entry["retained_fraction_vs_crude"] == round(float(Fraction(-1, 10) / crude), 6) < 0
    assert entry["sign_relation_vs_crude"] == "opposite_sign"
    assert entry["coverage"]["share_participating"] == round(30 / 130, 6)  # the reader can see how little it covers


def test_fine_size_bands_expose_size_that_hides_inside_the_open_ended_top_band():
    records = [
        *group("1", 15, 200, 100, participating=False),
        *group("1", 15, 40, 20, participating=True),   # same fill rate as the baseline at that size
        *group("1", 800, 40, 0, participating=True),   # giant paths, never filled
    ]
    result = analyse(records)
    coarse = fill_outcome(result)
    assert coarse["standardised"]["difference"] == -0.25  # everything is in '11+': size looks like graphic state
    fine_plan = result[LINE]["plans"]["lines_fill_presence_fine_bands"]
    fine = fine_plan["fields"][S.FILL_PRESENCE]["outcomes"][S.FILL_PRESENT]
    assert fine_plan["sensitivity_only"] is True and fine_plan["band_scheme"] == list(S.LINE_FINE_BANDS)
    assert [row[1]["visible_segments_band"] for row in fine_plan["strata"]["table"]] == ["11-20", "51+"]
    assert (fine_plan["strata"]["total"], fine_plan["strata"]["eligible"]) == (2, 1)  # 51+ has no baseline path
    assert fine["standardised"]["difference"] == 0.0 and fine["coverage"]["share_participating"] == 0.5


def _layer_paths(common, rare, only_participating=0):
    records = []
    for i in range(common):
        records += [rec("1", LINE, layer=f"present:L{i:02d}") for _ in range(3)]
        records += [rec("1", LINE, layer=f"present:L{i:02d}", part=1) for _ in range(2)]
    records += [rec("1", LINE, layer=f"present:R{i:02d}") for i in range(rare)]
    records += [rec("1", LINE, layer="present:ONLY-PART", part=1) for _ in range(only_participating)]
    return records


def test_folded_values_are_listed_participating_heavy_first():
    field = analyse(_layer_paths(14, 0, only_participating=4))[LINE]["plans"]["lines_conditioned_on_fill"]["fields"]["layer_state"]
    assert len(field["values_analysed"]) == 13 and field["values_analysed"][-1] == S.OTHER_VALUES  # 12 shown + the fold
    assert field["distinct_values_folded_into_other"] == 3
    listed = field["folded_values"]
    assert field["folded_values_omitted"] == 0 and len(listed) == 3
    # a value only participating paths use is listed (and first), though it has no outcome of its own
    assert listed[0] == {"value": "present:ONLY-PART", "paths_participating": 4, "paths_baseline": 0}
    assert "present:ONLY-PART" not in field["outcomes"]
    assert sum(v["paths_participating"] + v["paths_baseline"] for v in listed) == (
        field["outcomes"][S.OTHER_VALUES]["crude"]["k_participating"] + field["outcomes"][S.OTHER_VALUES]["crude"]["k_baseline"]
    )


def test_the_folded_value_list_is_capped_and_says_how_many_were_left_out():
    field = analyse(_layer_paths(12, 60))[LINE]["plans"]["lines_conditioned_on_fill"]["fields"]["layer_state"]
    assert field["distinct_values_folded_into_other"] == 60
    assert len(field["folded_values"]) == S.MAX_FOLDED_LISTED == 50 and field["folded_values_omitted"] == 10
    fill_only = analyse([rec("1", LINE, fill=True, fill_colour=f"c{i}") for i in range(5)] + [rec("1", LINE)])
    colour = fill_only[LINE]["plans"]["lines_conditioned_on_fill"]["fields"]["fill_state"]
    assert colour["folded_values"] == [] and colour["folded_values_omitted"] == 0  # nothing folded, nothing listed


def test_folded_fill_colours_are_counted_among_filled_paths_only():
    records = [rec("1", LINE, fill=True, fill_colour=f"c{i:02d}", part=1) for i in range(14)]
    records += [rec("1", LINE, fill=False) for _ in range(5)]  # not filled: never counted as a fill colour
    colour = analyse(records)[LINE]["plans"]["lines_conditioned_on_fill"]["fields"]["fill_state"]
    assert colour["distinct_values_folded_into_other"] == 2
    assert sorted(v["value"] for v in colour["folded_values"]) == ["c12", "c13"]
    assert all(v["paths_baseline"] == 0 and v["paths_participating"] == 1 for v in colour["folded_values"])


def test_the_integrity_block_carries_the_phase_2_replay_summary(tmp_path):
    pdf = _pdf(tmp_path, "bulk", _bulk_groups(), height=1000)
    join = collect_native_graphic_state_join(pdf, document_id=DOC).to_dict()
    replay = _stratified(pdf)["integrity"]["replay"]
    assert replay == {key: join["replay"][key] for key in ("pages_replayed", "pages_unavailable", "duplicate_replay_identities")}
    assert replay["pages_replayed"] == 1 and replay["pages_unavailable"] == []


def test_the_definitions_state_how_to_read_sparse_and_sensitivity_results(tmp_path):
    definitions = _stratified(_pdf(tmp_path, "bulk", _bulk_groups(), height=1000))["definitions"]
    notes = " ".join(definitions["reading_notes"])
    for phrase in ("no plan drops page", "dominant_sign_share", "exact sign", "folded_values", "sensitivity"):
        assert phrase in notes, phrase
    assert "understates" in definitions["null_control"] and "not a significance test" in definitions["null_control"]


def test_the_runner_surfaces_an_incomplete_analysis_and_a_complete_one(tmp_path, monkeypatch, capsys):
    pdf = _pdf(tmp_path, "bulk", _bulk_groups(), height=1000)
    clean = report_script.build_report([pdf])
    assert clean["entries"][0]["analysis_state"] == "complete"
    assert clean["coverage"]["entries_analysis_incomplete"] == 0 and clean["coverage"]["analysis_incomplete_labels"] == []
    real = J.extract_native_page

    def dropping(page):
        native = real(page)
        return {**native, "segments": [s for s in native["segments"] if s["id"] != "d3i0"]}

    monkeypatch.setattr(J, "extract_native_page", dropping)
    report = report_script.build_report([pdf])
    entry = report["entries"][0]
    assert entry["status"] == "ok" and entry["analysis_state"] == "incomplete_paths_excluded"
    assert report["coverage"]["entries_ok"] == 1 and report["coverage"]["entries_analysis_incomplete"] == 1
    assert report["coverage"]["analysis_incomplete_labels"] == [pdf.name]
    assert report_script.main([str(pdf), "--output", str(tmp_path / "incomplete.json")]) == 0  # data, not a crash
    warning = capsys.readouterr().err
    assert "analysis incomplete" in warning and pdf.name in warning


def test_a_source_that_is_not_analysed_has_no_analysis_state(tmp_path):
    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"not a pdf")
    entry = report_script.build_report([bad])["entries"][0]
    assert entry["status"] == "error" and entry["analysis_state"] is None


# ------------------------- review follow-ups, batch 2: hand-derived outcomes, seams, replay
def test_width_and_dash_outcomes_are_hand_derived_and_conditioned_on_fill():
    records = [
        *[rec("1", LINE, part=1, width="2.0000", dash="array_empty") for _ in range(40)],
        *[rec("1", LINE, part=0, width="1.0000", dash=J.ABSENT) for _ in range(40)],
    ]
    plan = analyse(records)[LINE]["plans"]["lines_conditioned_on_fill"]
    assert set(plan["fields"]) == {"stroke_state", "width_state", "layer_state", "dash_state", "fill_state"}
    assert plan["stratifiers"] == ["page_id", "visible_segments_band", "fill"]
    width = plan["fields"]["width_state"]["outcomes"]
    assert (width["2.0000"]["crude"]["share_participating"], width["2.0000"]["crude"]["share_baseline"]) == (1.0, 0.0)
    assert width["2.0000"]["standardised"]["difference"] == 1.0 and width["1.0000"]["standardised"]["difference"] == -1.0
    dash = plan["fields"]["dash_state"]["outcomes"]
    assert (dash["array_empty"]["crude"]["share_participating"], dash["array_empty"]["crude"]["share_baseline"]) == (1.0, 0.0)
    assert dash[J.ABSENT]["standardised"]["difference"] == -1.0
    assert dash["array_empty"]["sign_concordance"]["dominant_sign_share"] == 1.0


def _rect_population(*, by):
    """Same shape as the line Simpson fixture: the participating group sits mostly in the high-fill stratum."""
    if by == "size":
        big, small = ("1", 4), ("1", 1)
        return [
            *group(big[0], big[1], 60, 48, participating=True, klass=RECT),
            *group(small[0], small[1], 30, 6, participating=True, klass=RECT),
            *group(big[0], big[1], 30, 24, participating=False, klass=RECT),
            *group(small[0], small[1], 60, 12, participating=False, klass=RECT),
        ]
    return [  # every path has 4 edges; only the page differs
        *group("1", 4, 60, 48, participating=True, klass=RECT),
        *group("2", 4, 30, 6, participating=True, klass=RECT),
        *group("1", 4, 30, 24, participating=False, klass=RECT),
        *group("2", 4, 60, 12, participating=False, klass=RECT),
    ]


@pytest.mark.parametrize(
    "plan,bands",
    [("rect_edges_by_visible_edge_band", ["1-2", "3-5"]), ("rect_edges_by_visible_edge_count_fine", ["1", "4"])],
)
def test_rect_edge_statistics_are_hand_derived_on_both_band_plans(plan, bands):
    result = analyse(_rect_population(by="size"))
    entry = outcome(result, plan, "fill_state", GREY, klass=RECT)
    assert (entry["crude"]["share_participating"], entry["crude"]["share_baseline"], entry["crude"]["difference"]) == (0.6, 0.4, 0.2)
    assert entry["standardised"]["difference"] == 0.0 and entry["retained_fraction_vs_crude"] == 0.0
    assert entry["sign_concordance"]["zero"] == 2
    paint = outcome(result, plan, "paint_presence", "stroke_and_fill", klass=RECT)
    assert paint["crude"]["difference"] == 0.2 and paint["standardised"]["difference"] == 0.0
    block = result[RECT]["plans"][plan]
    assert [row[1]["visible_edges_band"] for row in block["strata"]["table"]] == bands
    assert block["stratifiers"] == ["page_id", "visible_edges_band"] and set(block["fields"]) == {"fill_state", "paint_presence"}
    assert block["sensitivity_only"] is (plan != "rect_edges_by_visible_edge_band")


def test_rect_page_composition_drives_a_crude_difference_that_vanishes_by_page():
    result = analyse(_rect_population(by="page"))
    entry = outcome(result, "rect_edges_by_visible_edge_band", "fill_state", GREY, klass=RECT)
    assert entry["crude"]["difference"] == 0.2 and entry["standardised"]["difference"] == 0.0


@pytest.mark.parametrize("status", [s for s in J.JOIN_STATUSES if s != J.STATUS_JOINED])
def test_a_path_is_excluded_for_every_kind_of_unjoined_row(status):
    rows = dict([
        _joined("a", "1", 0, 0, None),
        _joined("b", "1", 1, 0, None), _unjoined("c", "1", 1, 1, status),
        _joined("d", "1", 2, 0, None), _unjoined("e", "1", 2, 1, status), _unjoined("f", "1", 2, 2, status),
    ])
    population = S.build_path_records(_synthetic_bundle(rows, participating={"b"}, control=set()))
    assert [r.key for r in population.records] == [("1", 0, LINE)]
    assert dict(population.excluded_paths) == {LINE: 2}
    assert dict(population.unjoined_rows_in_excluded_paths) == {status: 3}
    assert dict(population.excluded_joined_participating_primitives) == {LINE: 1}


def test_every_participating_member_lands_in_exactly_one_accounting_bucket():
    from types import MappingProxyType

    raster = J.JoinRow(
        observation_id="r", page_id="1", raw_ref="visible:raster:x0", ref_class="raster_region", path_index=None,
        item_index=None, edge_index=None, status=J.STATUS_NOT_NATIVE, state=None, replay_items_in_path=None,
    )
    rows = dict([
        _joined("a", "1", 0, 0, None),                       # analysed
        _joined("b", "1", 1, 0, None), _unjoined("c", "1", 1, 1),  # b: joined, in an excluded path
        _unjoined("d", "1", 2, 0),                           # d: itself unjoined
        _joined("e", "2", 0, 0, None),                       # outside the candidate pages
        ("r", raster),                                       # not a native class
    ])
    members = {"a", "b", "d", "e", "r", "ghost"}             # ghost has no join row at all
    bundle = _synthetic_bundle(rows, participating=members - {"ghost"}, control=set())
    bundle = dataclasses.replace(bundle, participating_weight=MappingProxyType({o: 1 for o in members}))
    accounting = S.participating_accounting(bundle, S.build_path_records(bundle))
    assert accounting["distinct_participating_primitives"] == 6 and accounting["without_join_row"] == 1
    assert accounting["analysed"] == {LINE: 1}
    assert accounting["in_excluded_paths_joined"] == {LINE: 1} and accounting["in_excluded_paths_unjoined"] == {LINE: 1}
    assert accounting["native_outside_candidate_pages"] == {LINE: 1}
    assert accounting["not_native_class"] == {"raster_region": 1}
    assert accounting["fully_accounted"] is True


def test_the_same_drawing_on_two_pages_gives_two_page_qualified_strata(tmp_path):
    from tests.test_native_graphic_state_join_v1 import _draw

    groups = _bulk_groups()
    one = _stratified(_write(tmp_path / "one.pdf", lambda p, i: _draw(p, groups), pages=1, height=1000))
    two = _stratified(_write(tmp_path / "two.pdf", lambda p, i: _draw(p, groups), pages=2, height=1000))
    single, double = one["classes"][LINE]["population"], two["classes"][LINE]["population"]
    assert double["participating_paths"] == 2 * single["participating_paths"] == 80
    assert double["baseline_paths"] == 2 * single["baseline_paths"] == 90
    assert two["integrity"]["candidate_pages"] == ["1", "2"] and two["integrity"]["checks"]["all_checks_passed"] is True
    plan = two["classes"][LINE]["plans"]["lines_fill_presence"]
    assert [row[1]["page_id"] for row in plan["strata"]["table"]] == ["1", "2"] and plan["strata"]["eligible"] == 2


def test_strata_are_ordered_by_page_number_then_band_then_fill():
    records = []
    for page in ("10", "2"):
        for size in (12, 8, 4, 2, 1):
            records += [rec(page, LINE, size=size, fill=f, part=p) for f in (False, True) for p in (0, 1)]
    plan = analyse(records)[LINE]["plans"]["lines_conditioned_on_fill"]
    order = [(r[1]["page_id"], r[1]["visible_segments_band"], r[1]["fill"]) for r in plan["strata"]["table"]]
    assert order == [
        (page, band, fill) for page in ("2", "10") for band in S.LINE_BANDS for fill in (S.FILL_PRESENT, S.FILL_ABSENT)
    ]
    assert [r[0] for r in plan["strata"]["table"]] == list(range(20))


def test_the_null_split_has_three_distinct_salts_and_a_pinned_known_answer_vector():
    assert len(set(S.NULL_SPLIT_SALTS)) == len(S.NULL_SPLIT_SALTS) == 3
    line = [S.null_half(SHA, "1", i, LINE, "null_split_v1:0") for i in range(24)]
    rect = [S.null_half(SHA, "1", i, RECT, "null_split_v1:0") for i in range(24)]
    other = [S.null_half(SHA, "2", i, LINE, "null_split_v1:1") for i in range(24)]
    assert line == [0, 0, 0, 1, 1, 0, 0, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 0, 1, 0, 0, 1, 0, 1]  # a deliberate change re-pins
    assert rect == [1, 1, 0, 1, 0, 0, 1, 1, 1, 1, 1, 0, 1, 1, 1, 0, 0, 0, 0, 1, 0, 1, 0, 0]
    assert other == [0, 1, 0, 0, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1]
    assert line != rect  # the primitive class is part of the identity


@pytest.mark.parametrize(
    "reference,adjusted,expected",
    [
        (None, Fraction(1, 4), (None, "not_estimable")),
        (Fraction(1, 2), None, (None, "not_estimable")),
        (Fraction(0), Fraction(0), (None, "both_zero")),
        (Fraction(0), Fraction(1, 10), (None, "reference_zero")),
        (Fraction(1, 2), Fraction(0), (0.0, "adjusted_zero")),
        (Fraction(1, 2), Fraction(1, 4), (0.5, "same_sign")),
        (Fraction(-1, 2), Fraction(-1, 4), (0.5, "same_sign")),
        (Fraction(1, 2), Fraction(-1, 4), (-0.5, "opposite_sign")),
    ],
)
def test_the_adjusted_to_reference_relation_covers_every_case(reference, adjusted, expected):
    assert S._compare_to_adjusted(reference, adjusted) == expected


def test_the_floor_is_symmetric_and_an_empty_group_is_suppressed():
    labels = ("participating", "baseline")
    for na, nb in ((29, 30), (30, 29), (0, 30), (30, 0), (0, 0)):
        pair = S._pair(labels, na // 2, na, nb // 2, nb)
        assert pair["difference"] == SUPPRESSED
        assert (pair["share_participating"] == SUPPRESSED) == (na < 30)
        assert (pair["share_baseline"] == SUPPRESSED) == (nb < 30)
    at_floor = S._pair(labels, 15, 30, 9, 30)
    assert (at_floor["difference"], at_floor["share_participating"], at_floor["share_baseline"]) == (0.2, 0.5, 0.3)


def test_outcome_values_do_not_depend_on_which_paths_participate_and_ties_break_by_name():
    def build(flip):
        records = []
        for layer in ("present:B", "present:A", "present:C"):  # equal counts everywhere
            records += [rec("1", LINE, part=int((j % 2 == 0) != flip), layer=layer) for j in range(4)]
        return records

    shown = []
    for flip in (False, True):
        field = analyse(build(flip))[LINE]["plans"]["lines_conditioned_on_fill"]["fields"]["layer_state"]
        shown.append(field["values_analysed"])
        assert S.OTHER_VALUES not in field["outcomes"] and field["folded_values"] == []  # nothing folded
    assert shown[0] == shown[1] == ["present:A", "present:B", "present:C"]


def test_invariant_under_a_true_90_degree_rotation(tmp_path):
    base = _stratified(_pdf(tmp_path, "base", _bulk_groups(), height=1000))["classes"]
    rotated = _stratified(
        _pdf(tmp_path, "rot", _bulk_groups(fn=lambda p: (1000.0 - p[1], p[0])), width=1000, height=700)
    )["classes"]
    assert json.dumps(_without_null(rotated), sort_keys=True) == json.dumps(_without_null(base), sort_keys=True)


def test_a_reference_that_disagrees_fails_the_candidate_count_check(tmp_path):
    source, result, reference, payload = _scope(_pdf(tmp_path, "bulk", _bulk_groups(), height=1000))
    agree = S.build_stratified_graphic_state_check(
        source_visibility_producer=source, semantic_result=result, source_bytes=payload, reference_structure=reference
    ).to_dict()
    assert agree["integrity"]["checks"]["candidate_total_matches_structure_reference"] is True
    assert agree["integrity"]["structure_reference"] == "supplied"
    off = dataclasses.replace(reference, candidates_total=reference.candidates_total + 1)
    check = S.build_stratified_graphic_state_check(
        source_visibility_producer=source, semantic_result=result, source_bytes=payload, reference_structure=off
    ).to_dict()
    assert check["integrity"]["checks"]["candidate_total_matches_structure_reference"] is False
    assert check["integrity"]["checks"]["all_checks_passed"] is False
    none = S.build_stratified_graphic_state_check(
        source_visibility_producer=source, semantic_result=result, source_bytes=payload
    ).to_dict()
    assert "candidate_total_matches_structure_reference" not in none["integrity"]["checks"]
    assert none["integrity"]["structure_reference"] == "not_supplied"
    with pytest.raises(TypeError):
        S.build_stratified_graphic_state_check(
            source_visibility_producer=source, semantic_result=result, source_bytes=payload,
            reference_structure=object(),  # type: ignore[arg-type]
        )


def test_duplicate_replay_identities_are_carried_into_the_integrity_replay_block(tmp_path, monkeypatch):
    pdf = _pdf(tmp_path, "bulk", _bulk_groups(), height=1000)
    real = J.extract_native_page

    def duplicating(page):
        native = real(page)
        segments = list(native["segments"])
        return {**native, "segments": [*segments, dict(segments[2])]}

    monkeypatch.setattr(J, "extract_native_page", duplicating)
    join = collect_native_graphic_state_join(pdf, document_id=DOC).to_dict()
    replay = _stratified(pdf)["integrity"]["replay"]
    assert replay["duplicate_replay_identities"] == join["replay"]["duplicate_replay_identities"] >= 1
    assert replay["pages_replayed"] == join["replay"]["pages_replayed"]


def test_the_row_digest_does_not_depend_on_row_order(tmp_path):
    source, result, reference, payload = _scope(_pdf(tmp_path, "bulk", _bulk_groups(), height=1000))
    bundle = build_native_graphic_state_join_rows(
        source_visibility_producer=source, semantic_result=result, source_bytes=payload
    )
    forward = dict(bundle.rows.items())
    backward = dict(reversed(list(bundle.rows.items())))
    assert list(forward) != list(backward) and J.digest_of_rows(forward) == J.digest_of_rows(backward)


def test_the_public_rows_seam_refuses_the_wrong_types(tmp_path):
    source, result, reference, payload = _scope(_pdf(tmp_path, "bulk", _bulk_groups(), height=1000))
    good = dict(source_visibility_producer=source, semantic_result=result, source_bytes=payload)
    assert build_native_graphic_state_join_rows(**good).ok
    for key, bad in (("source_visibility_producer", object()), ("semantic_result", object()), ("source_bytes", "text")):
        with pytest.raises(TypeError):
            build_native_graphic_state_join_rows(**{**good, key: bad})


def test_the_payload_never_states_a_forbidden_claim(tmp_path):
    check = _stratified(_pdf(tmp_path, "bulk", _bulk_groups(), height=1000))
    forbidden = re.compile(
        r"\bis noise\b|false opening|real opening|is an opening|\brejected?\b|\bfiltered\b|\bis a rule\b|\bshould be (dropped|removed)\b"
    )
    seen = []

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                seen.append(str(key))
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)
        elif isinstance(node, str):
            seen.append(node)

    walk(check)
    assert seen and not [text for text in seen if forbidden.search(text.lower())]
    assert check["definitions"]["floor"]["meaning"].startswith("group-size reporting guard")


def test_the_replay_is_identical_across_processes_and_hash_seeds(tmp_path):
    fixture = FIXTURES / "styled.pdf"
    outputs = []
    for seed in ("1", "999"):
        out = tmp_path / f"seed{seed}.json"
        run = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "native_graphic_state_stratified_report.py"), str(fixture),
             "--output", str(out)],
            cwd=REPO, env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": str(REPO)},
            capture_output=True, text=True, timeout=300,
        )
        assert run.returncode == 0, run.stderr[-2000:]
        outputs.append(out.read_bytes())
    assert outputs[0] == outputs[1]
    entry = json.loads(outputs[0])["entries"][0]
    assert entry["status"] == "ok" and entry["stratified"]["integrity"]["checks"]["all_checks_passed"] is True
