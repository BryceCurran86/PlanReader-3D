"""``attach_lineage_to_split_fragments`` throughput change must be output-identical to the implementation it replaced.

``_reference_attach`` is the previous implementation, verbatim, built from the module's own unchanged helpers.  The tests compare the
two on synthetic positives, look-alike negatives, borderline-tolerance geometry, non-finite input, duplicate/overlapping sources,
input-order and unrelated-content changes, and check that no mutable container is shared between emitted fragments or with the
input.  Nothing here uses a benchmark value, a source PDF or a project name.
"""
from __future__ import annotations

import copy
import math
import random

import pytest

import pb_wall_room_topology_primitive_lineage as lin

TOL = lin._CONTAINMENT_TOL_PT


def _reference_attach(split_pairs, source_segments, *, id_prefix="split", source_parent_indexes=None):
    """The implementation that was on main before the change (unchanged logic)."""
    if source_parent_indexes is not None and (
        not isinstance(source_parent_indexes, (list, tuple))
        or len(source_parent_indexes) != len(split_pairs)
        or any(type(i) is not int or not 0 <= i < len(source_segments) for i in source_parent_indexes)
    ):
        raise ValueError("exact split source parent inventory invalid")
    buckets = {}
    for segment in source_segments:
        buckets.setdefault(lin.source_line_bucket(segment), []).append(segment)
    containment_grid, global_containment_indexes = lin._build_source_containment_grid(source_segments)
    out = []
    for idx, pair in enumerate(split_pairs):
        p1, p2 = pair
        seen_candidates = set()
        candidates = []
        for neighbor_key in lin.fragment_line_bucket_neighbors(pair):
            for candidate in buckets.get(neighbor_key, ()):
                marker = id(candidate)
                if marker in seen_candidates:
                    continue
                seen_candidates.add(marker)
                candidates.append(candidate)
        for candidate in lin._containment_grid_candidates(pair, source_segments, containment_grid, global_containment_indexes):
            marker = id(candidate)
            if marker in seen_candidates:
                continue
            seen_candidates.add(marker)
            candidates.append(candidate)
        parents = lin.sources_for_fragment(pair, candidates)
        if source_parent_indexes is not None:
            origin = source_segments[source_parent_indexes[idx]]
            coords = (*p1, *p2)
            if (not all(math.isfinite(float(v)) for v in coords) or p1 == p2
                    or not all(lin._point_on_segment(*point, *(float(origin[k]) for k in lin._PAGE_COORD_FIELDS))
                               for point in pair)):
                raise ValueError("exact split origin contradicts fragment geometry")
            if all(origin is not parent for parent in parents):
                parents.append(origin)
        fragment = {
            "id": f"{id_prefix}_{idx}",
            "x1": p1[0], "y1": p1[1], "x2": p2[0], "y2": p2[1],
            **lin.fabricated_live_fields(),
            lin.LINEAGE_KEY: lin.isolated_lineage(lin.lineage_from_source_segments(parents)),
        }
        out.append(fragment)
    return out


def _source(i, x1, y1, x2, y2, **extra):
    return {"id": f"src_{i}", "x1": x1, "y1": y1, "x2": x2, "y2": y2, "kind": "line", "width": 0.5,
            "stroke": (0.0, 0.0, 0.0), "layer": "L", "dashes": "", "path_index": i, "item_index": 0, **extra}


def _random_sources(rng, count, *, collinear_share=0.6):
    """Dense collinear dashes, overlapping duplicates, diagonals and clutter, with varied style/clip attributes."""
    sources = []
    for i in range(count):
        roll = rng.random()
        if roll < collinear_share:  # many dashes on a handful of shared horizontal/vertical/diagonal lines
            line = rng.randrange(4)
            if line == 0:
                y = 100.0 + rng.choice((0.0, 0.004, -0.004, 0.011))
                x1 = rng.uniform(0, 300); x2 = x1 + rng.uniform(0.5, 60)
                sources.append(_source(i, x1, y, x2, y))
            elif line == 1:
                x = 50.0 + rng.choice((0.0, 0.003, -0.009))
                y1 = rng.uniform(0, 300); y2 = y1 + rng.uniform(0.5, 60)
                sources.append(_source(i, x, y1, x, y2))
            elif line == 2:
                t1 = rng.uniform(0, 200); t2 = t1 + rng.uniform(0.5, 80)
                sources.append(_source(i, 10 + t1, 10 + t1, 10 + t2, 10 + t2))
            else:
                t1 = rng.uniform(0, 200); t2 = t1 + rng.uniform(0.5, 80)
                sources.append(_source(i, 10 + t1, 400 - t1, 10 + t2, 400 - t2))
        else:
            x1, y1 = rng.uniform(0, 400), rng.uniform(0, 400)
            sources.append(_source(i, x1, y1, x1 + rng.uniform(-90, 90), y1 + rng.uniform(-90, 90)))
        extra = rng.random()
        if extra < 0.2:
            sources[-1]["stroke"] = (1.0, 0.0, 0.0)
        elif extra < 0.3:
            sources[-1]["clip"] = (0.0, 0.0, 500.0, 500.0)
            sources[-1]["clip_known"] = True
        elif extra < 0.35:
            sources[-1]["fill"] = (0.5, 0.5, 0.5)
    for _ in range(count // 10):  # exact duplicates and shared-geometry twins
        sources.append(copy.deepcopy(rng.choice(sources)))
    return sources


def _fragments_for(rng, sources, count, *, jitter):
    pairs = []
    for _ in range(count):
        s = rng.choice(sources)
        x1, y1, x2, y2 = float(s["x1"]), float(s["y1"]), float(s["x2"]), float(s["y2"])
        a, b = sorted((rng.random(), rng.random()))
        p1 = (x1 + (x2 - x1) * a, y1 + (y2 - y1) * a)
        p2 = (x1 + (x2 - x1) * b, y1 + (y2 - y1) * b)
        if rng.random() < 0.15:  # leave the source
            p2 = (p2[0] + rng.uniform(-3, 3), p2[1] + rng.uniform(-3, 3))
        # endpoint noise from well inside to well outside the containment tolerance
        p1 = (p1[0] + rng.uniform(-jitter, jitter), p1[1] + rng.uniform(-jitter, jitter))
        p2 = (p2[0] + rng.uniform(-jitter, jitter), p2[1] + rng.uniform(-jitter, jitter))
        pairs.append((p1, p2))
    return pairs


@pytest.mark.parametrize("seed", range(24))
@pytest.mark.parametrize("jitter", [0.0, TOL * 0.5, TOL * 1.3, TOL * 3.0])
def test_randomised_outputs_equal_the_previous_implementation(seed, jitter):
    rng = random.Random(seed * 1000 + int(jitter * 1e7))
    sources = _random_sources(rng, rng.choice((12, 40, 160)))
    pairs = _fragments_for(rng, sources, 60, jitter=jitter)
    before_sources, before_pairs = copy.deepcopy(sources), copy.deepcopy(pairs)
    expected = _reference_attach(pairs, sources)
    actual = lin.attach_lineage_to_split_fragments(pairs, sources)
    assert actual == expected
    assert [list(f) for f in actual] == [list(f) for f in expected]  # same key order
    assert sources == before_sources and pairs == before_pairs  # no input mutation


def test_worst_case_diagonal_corner_offsets_at_and_around_the_tolerance():
    """The oriented-rectangle corner is the farthest the exact predicate can reach beyond a source's own box."""
    s = _source(0, 0.0, 0.0, 100.0, 100.0)
    fillers = [_source(i, 0.0, 0.0, 100.0, 100.0) for i in range(1, 40)]  # one shared bucket, above the prefilter size
    sources = [s] + fillers
    u = 1 / math.sqrt(2)
    for scale in (0.5, 0.9, 0.99, 0.999, 1.0, 1.001, 1.01, 1.5, 3.0):
        t = TOL * scale
        # beyond the end by t along the axis and t off the line: the box corner direction
        p_end = (100.0 + t * u + t * u, 100.0 + t * u - t * u)
        p_start = (-t * u - t * u, -t * u + t * u)
        for pair in (((10.0, 10.0), p_end), (p_start, (20.0, 20.0)), (p_start, p_end)):
            assert lin.attach_lineage_to_split_fragments([pair], sources) == _reference_attach([pair], sources), (scale, pair)


@pytest.mark.parametrize("count", [1, 5, 15, 16, 17, 200])
def test_bucket_sizes_around_the_prefilter_threshold(count):
    rng = random.Random(count)
    sources = [_source(i, 10.0 + 5 * i, 100.0, 12.0 + 5 * i, 100.0) for i in range(count)]
    pairs = [((10.0 + 5 * i + 0.5, 100.0), (11.5 + 5 * i, 100.0)) for i in range(count)]
    pairs += [((rng.uniform(0, 300), 100.0), (rng.uniform(0, 300), 100.0)) for _ in range(20)]
    assert lin.attach_lineage_to_split_fragments(pairs, sources) == _reference_attach(pairs, sources)


def test_non_finite_and_degenerate_geometry_matches_previous_behaviour():
    sources = [_source(i, 10.0 * i, 5.0, 10.0 * i + 8.0, 5.0) for i in range(30)]
    pairs = [
        ((1.0, 5.0), (7.0, 5.0)),
        ((float("nan"), 5.0), (7.0, 5.0)),
        ((1.0, 5.0), (float("inf"), 5.0)),
        ((12.0, 5.0), (12.0, 5.0)),  # zero length
        ((12.0, 5.0), (12.0 + TOL / 2, 5.0)),  # shorter than the tolerance
        ((31.0, 5.0 + TOL / 2), (37.0, 5.0 - TOL / 2)),
    ]
    def outcome(fn, chunk):
        try:
            return ("ok", repr(fn(chunk, sources)))  # repr: NaN never compares equal to itself
        except Exception as exc:  # noqa: BLE001 - the contract is "same failure as before"
            return ("raised", type(exc).__name__, str(exc))

    for pair in pairs:  # one fragment at a time: a non-finite fragment must not change the answer for any other
        assert outcome(lin.attach_lineage_to_split_fragments, [pair]) == outcome(_reference_attach, [pair]), pair
    assert outcome(lin.attach_lineage_to_split_fragments, pairs) == outcome(_reference_attach, pairs)
    finite = [pair for pair in pairs if all(math.isfinite(v) for point in pair for v in point)]
    assert outcome(lin.attach_lineage_to_split_fragments, finite)[0] == "ok"
    assert outcome(lin.attach_lineage_to_split_fragments, finite) == outcome(_reference_attach, finite)


@pytest.mark.parametrize("field,value", [("x2", float("inf")), ("y1", float("nan")), ("x1", float("-inf"))])
def test_non_finite_source_coordinates_fail_exactly_as_before(field, value):
    sources = [_source(i, 10.0 * i, 5.0, 10.0 * i + 8.0, 5.0) for i in range(30)]
    sources[3][field] = value
    pairs = [((1.0, 5.0), (7.0, 5.0))]
    with pytest.raises(Exception) as ref:
        _reference_attach(pairs, sources)
    with pytest.raises(type(ref.value)) as mine:
        lin.attach_lineage_to_split_fragments(pairs, sources)
    assert str(mine.value) == str(ref.value)


def test_malformed_input_raises_what_the_previous_implementation_raised():
    good = _source(0, 0.0, 0.0, 10.0, 0.0)
    bad = {"id": "bad", "x1": 0.0, "y1": 0.0, "x2": 1.0}  # missing y2
    for sources in ([good, bad], [good, dict(good, x1="oops")]):
        with pytest.raises(Exception) as ref:
            _reference_attach([((1.0, 0.0), (2.0, 0.0))], sources)
        with pytest.raises(type(ref.value)):
            lin.attach_lineage_to_split_fragments([((1.0, 0.0), (2.0, 0.0))], sources)


def test_exact_split_parent_indexes_match_and_invalid_inventories_are_rejected_alike():
    rng = random.Random(5)
    sources = _random_sources(rng, 50)
    pairs, indexes = [], []
    for _ in range(40):
        i = rng.randrange(len(sources))
        s = sources[i]
        a, b = sorted((rng.random(), rng.random()))
        if abs(a - b) < 1e-6:
            continue
        pairs.append(((s["x1"] + (s["x2"] - s["x1"]) * a, s["y1"] + (s["y2"] - s["y1"]) * a),
                      (s["x1"] + (s["x2"] - s["x1"]) * b, s["y1"] + (s["y2"] - s["y1"]) * b)))
        indexes.append(i)
    assert (lin.attach_lineage_to_split_fragments(pairs, sources, source_parent_indexes=indexes)
            == _reference_attach(pairs, sources, source_parent_indexes=indexes))
    for bad in (indexes[:-1], [-1] + indexes[1:], [True] + indexes[1:], "nope"):
        with pytest.raises(ValueError):
            lin.attach_lineage_to_split_fragments(pairs, sources, source_parent_indexes=bad)
    wrong = [(0.0, 0.0), (500.0, 500.0)]
    with pytest.raises(ValueError):
        lin.attach_lineage_to_split_fragments([tuple(wrong)], sources[:1], source_parent_indexes=[0])


def test_emitted_fragments_share_no_mutable_container_with_each_other_or_the_input():
    s = _source(0, 0.0, 0.0, 100.0, 0.0, stroke=[0.1, 0.2], clip=[1, 2, 3, 4])
    sources = [s] + [_source(i, 0.0, 0.0, 100.0, 0.0) for i in range(1, 20)]
    pairs = [((1.0, 0.0), (2.0, 0.0)), ((3.0, 0.0), (4.0, 0.0)), ((1.0, 0.0), (2.0, 0.0))]
    out = lin.attach_lineage_to_split_fragments(pairs, sources)
    first, second, third = (f[lin.LINEAGE_KEY] for f in out)
    assert first == third  # identical parent sets, identical payload ...
    assert first is not third and first["source_records"] is not third["source_records"]  # ... but separate containers
    assert first["source_records"][0] is not third["source_records"][0]
    first["source_records"][0]["stroke"].append("poison") if isinstance(first["source_records"][0]["stroke"], list) else None
    first["source_primitive_ids"].append("poison")
    first["attribute_status"]["width"] = "poison"
    assert "poison" not in third["source_primitive_ids"] and third["attribute_status"]["width"] != "poison"
    again = lin.attach_lineage_to_split_fragments(pairs, sources)
    assert again[2][lin.LINEAGE_KEY] == out[2][lin.LINEAGE_KEY]
    assert sources[0]["stroke"] == [0.1, 0.2]  # input untouched by the poisoning above


def test_input_order_and_unrelated_content_do_not_change_each_fragments_lineage():
    rng = random.Random(11)
    sources = _random_sources(rng, 120)
    pairs = _fragments_for(rng, sources, 50, jitter=TOL * 0.5)
    base = lin.attach_lineage_to_split_fragments(pairs, sources)

    shuffled = sources[:]
    rng.shuffle(shuffled)
    permuted = lin.attach_lineage_to_split_fragments(pairs, shuffled)
    assert [f[lin.LINEAGE_KEY] for f in permuted] == [f[lin.LINEAGE_KEY] for f in base]

    far = [_source(10_000 + i, 5000.0 + i, 5000.0, 5004.0 + i, 5000.0) for i in range(40)]
    expanded = lin.attach_lineage_to_split_fragments(pairs, sources + far)
    assert [f[lin.LINEAGE_KEY] for f in expanded] == [f[lin.LINEAGE_KEY] for f in base]


def test_repeated_calls_are_deterministic():
    rng = random.Random(3)
    sources = _random_sources(rng, 90)
    pairs = _fragments_for(rng, sources, 40, jitter=TOL)
    runs = [lin.attach_lineage_to_split_fragments(pairs, sources) for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]


def test_prefilter_removes_most_exact_checks_in_a_dense_collinear_bucket(monkeypatch):
    """Deterministic work count (not wall time): 2,000 dashes on one line, fragments inside a few of them."""
    sources = [_source(i, 4.0 * i, 100.0, 4.0 * i + 3.0, 100.0) for i in range(2000)]
    pairs = [((4.0 * i + 0.5, 100.0), (4.0 * i + 2.5, 100.0)) for i in range(0, 2000, 40)]
    calls = {"n": 0}
    original = lin.fragment_contained_in_segment

    def counting(fragment, segment, **kw):
        calls["n"] += 1
        return original(fragment, segment, **kw)

    monkeypatch.setattr(lin, "fragment_contained_in_segment", counting)
    actual = lin.attach_lineage_to_split_fragments(pairs, sources)
    new_calls = calls["n"]
    calls["n"] = 0
    expected = _reference_attach(pairs, sources)
    ref_calls = calls["n"]
    assert actual == expected
    assert all(len(f[lin.LINEAGE_KEY]["source_primitive_ids"]) == 1 for f in actual)
    assert new_calls * 20 < ref_calls, (new_calls, ref_calls)


def test_copy_json_like_matches_deepcopy_for_payload_shapes_and_falls_back_for_others():
    nan = float("nan")
    payload = {"a": [1, 2.5, "x", None, True, (1, (2, 3), [4, {"k": ()}])], "b": {"n": nan, "t": (1.0, 2.0)}}
    mine, theirs = lin._copy_json_like(payload), copy.deepcopy(payload)
    assert repr(mine) == repr(theirs)
    assert mine["a"][5][2] is not payload["a"][5][2] and mine["a"] is not payload["a"]

    class Odd:
        def __init__(self):
            self.items = [1, 2]

    odd = {"o": Odd()}
    copied = lin._copy_json_like(odd)
    assert copied["o"] is not odd["o"] and copied["o"].items == [1, 2] and copied["o"].items is not odd["o"].items


def test_dense_hatch_inside_one_grid_cell_is_pruned_and_output_is_identical(monkeypatch):
    """Real drawings put hundreds of short hatch strokes into one 64 pt containment-grid cell; the grid candidates must be
    pruned by position too, not only the line buckets (a first version pruned buckets only and gained 1.1x)."""
    rng = random.Random(21)
    sources = []
    for i in range(1500):  # a 50 x 50 pt hatch patch, strokes at assorted angles
        x, y = rng.uniform(5, 55), rng.uniform(5, 55)
        sources.append(_source(i, x, y, x + rng.uniform(-4, 4), y + rng.uniform(-4, 4)))
    sources.append(_source(1500, 10.0, 30.0, 50.0, 30.0))  # a long wall line crossing the patch
    pairs = [((12.0, 30.0), (18.0, 30.0)), ((20.0, 30.0), (45.0, 30.0))]
    pairs += [((s["x1"], s["y1"]), (s["x2"], s["y2"])) for s in sources[:40]]  # fragments equal to hatch strokes
    calls = {"n": 0}
    original = lin.fragment_contained_in_segment

    def counting(fragment, segment, **kw):
        calls["n"] += 1
        return original(fragment, segment, **kw)

    monkeypatch.setattr(lin, "fragment_contained_in_segment", counting)
    actual = lin.attach_lineage_to_split_fragments(pairs, sources)
    new_calls = calls["n"]
    calls["n"] = 0
    expected = _reference_attach(pairs, sources)
    ref_calls = calls["n"]
    assert actual == expected
    assert any(len(f[lin.LINEAGE_KEY]["source_primitive_ids"]) >= 1 for f in actual)
    assert new_calls * 20 < ref_calls, (new_calls, ref_calls)
