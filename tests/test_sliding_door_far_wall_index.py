"""The far-wall index of the sliding-door detector gives the same results as trying every wall."""

import random

import pytest

import pb_source_sliding_door_footprint_continuity as sliding

LAYER = "Enclosure_WallExternal"
DARK = (0.0, 0.0, 0.0)
WHITE = (1.0, 1.0, 1.0)


def _fill(bounds, color, layer=LAYER):
    return {"layer": layer, "rect": bounds, "fill": color, "items": ()}


def _door(rng, x, y, *, gap=None, a_post=False, b_post=False, layer=LAYER):
    """A horizontal door: two host walls (flat or upright post), two caps, two tracks and a label."""
    t = rng.choice((2.0, 2.5, 3.0, 4.0))
    gap = gap if gap is not None else rng.uniform(8.0, 120.0)
    left_end, right_start = x, x + gap
    rows = []
    if a_post:
        rows.append(_fill((left_end - t, y - rng.uniform(4, 40), left_end, y + t + rng.uniform(4, 40)), DARK, layer))
    else:
        rows.append(_fill((left_end - rng.uniform(5, 60), y, left_end, y + t), DARK, layer))
    if b_post:
        rows.append(_fill((right_start, y - rng.uniform(4, 40), right_start + t, y + t + rng.uniform(4, 40)), DARK, layer))
    else:
        rows.append(_fill((right_start, y, right_start + rng.uniform(5, 60), y + t), DARK, layer))
    rows.append(_fill((left_end, y + 0.1, left_end + 1.0, y + t - 0.1), WHITE, layer))
    rows.append(_fill((right_start - 1.0, y + 0.1, right_start, y + t - 0.1), WHITE, layer))
    half = max(5.0, 0.4 * gap)
    rows.append(_fill((left_end + 0.5, y + 0.3, left_end + 0.5 + half, y + 0.8), WHITE, layer))
    rows.append(_fill((right_start - 0.5 - half, y + 1.0, right_start - 0.5, y + 1.5), WHITE, layer))
    lx = rng.uniform(left_end, right_start)
    ly = y + rng.choice((-1, 1)) * rng.uniform(5.0, 30.0)
    word = (lx - 2.5, ly - 2.0, lx + 2.5, ly + 2.0, rng.choice(("ASD", "SGD", "ASSD")))
    return rows, word


def _transpose(rows, words):
    flipped = [{**row, "rect": (row["rect"][1], row["rect"][0], row["rect"][3], row["rect"][2])} for row in rows]
    return flipped, [(w[1], w[0], w[3], w[2], w[4]) for w in words]


def _scene(seed):
    rng = random.Random(seed)
    layer = LAYER if rng.random() < 0.7 else ""
    rows, words = [], []
    for _ in range(rng.randint(1, 4)):
        door_rows, word = _door(
            rng, rng.uniform(0, 600), rng.uniform(0, 600),
            a_post=rng.random() < 0.3, b_post=rng.random() < 0.3, layer=layer,
        )
        rows += door_rows
        words.append(word)
        if rng.random() < 0.25:  # a competing or occluding wall piece next to this door
            base = door_rows[rng.randrange(2)]["rect"]
            shift = rng.uniform(-30, 30)
            rows.append(_fill((base[0] + shift, base[1], base[2] + shift, base[3]), DARK, layer))
    for _ in range(rng.randint(0, 120)):  # unrelated wall and fill noise
        x, y = rng.uniform(0, 700), rng.uniform(0, 700)
        long_side, short_side = rng.uniform(1, 80), rng.uniform(0.3, 6)
        dx, dy = (long_side, short_side) if rng.random() < 0.5 else (short_side, long_side)
        rows.append(_fill((x, y, x + dx, y + dy), DARK if rng.random() < 0.8 else WHITE, layer))
    if rng.random() < 0.3:
        w = words[rng.randrange(len(words))]
        words.append((w[0] + 3, w[1], w[2] + 3, w[3], rng.choice(("ASW", "SD2"))))
    rng.shuffle(rows)
    if rng.random() < 0.5:
        rows, words = _transpose(rows, words)
    return rows, words


def _every_wall(window, position, a, h_first, v_first):
    return range(window.count)


def test_index_matches_trying_every_wall(monkeypatch):
    found = 0
    axes = set()
    for seed in range(600):
        rows, words = _scene(seed)
        indexed = sliding.detect_exterior_sliding_door_footprint_bridges(rows, words, page_index=1)
        with monkeypatch.context() as patch:
            patch.setattr(sliding, "_far_walls", _every_wall)
            full = sliding.detect_exterior_sliding_door_footprint_bridges(rows, words, page_index=1)
        assert indexed == full, seed
        found += len(full)
        axes.update(bridge.axis for bridge in full)
    assert found > 300  # the scenes really exercise accepted doors, on both axes
    assert axes == {"h", "v"}


@pytest.mark.parametrize("gap", [8.0, 450.0])
@pytest.mark.parametrize("flip", [False, True])
def test_gap_limits_are_kept(gap, flip):
    rows, word = _door(random.Random(3), 500.0, 300.0, gap=gap)
    words = [word]
    if flip:
        rows, words = _transpose(rows, words)
    (bridge,) = sliding.detect_exterior_sliding_door_footprint_bridges(rows, words)
    assert (bridge.first_host_path_id, bridge.second_host_path_id) == (0, 1)


def _hosted(a, b, cap_y, track_y):
    """Two host walls with the opening from x=100 to b's left edge, a cap at each end, two tracks, nothing else."""
    end = b[0]
    return [
        _fill(a, DARK), _fill(b, DARK),
        _fill((100.0, cap_y, 101.0, cap_y + 2.5), WHITE), _fill((end - 1.0, cap_y, end, cap_y + 2.5), WHITE),
        _fill((100.5, track_y, 116.5, track_y + 0.5), WHITE),
        _fill((end - 16.5, track_y + 1.0, end - 0.5, track_y + 1.5), WHITE),
    ]


@pytest.mark.parametrize("rows, label_x", [
    # Only the first host reaches the label: two upright posts, the far one short and below the label, and the
    # label near the far end so the first post is also far from it along the opening.
    (_hosted((97.5, 20.0, 100.0, 180.0), (200.0, 150.0, 202.5, 170.0), 99.0, 99.5), 170.0),
    # Neither host is within 35 pt of the label centre; only the label's half height keeps the door.
    (_hosted((40.0, 136.0, 100.0, 138.5), (140.0, 136.0, 200.0, 138.5), 136.0, 136.3), 120.0),
])
@pytest.mark.parametrize("flip", [False, True])
def test_edge_cases_match_trying_every_wall(monkeypatch, rows, label_x, flip):
    words = [(label_x - 2.5, 98.0, label_x + 2.5, 102.0, "ASD")]
    if flip:
        rows, words = _transpose(rows, words)
    indexed = sliding.detect_exterior_sliding_door_footprint_bridges(rows, words)
    monkeypatch.setattr(sliding, "_far_walls", _every_wall)
    assert indexed == sliding.detect_exterior_sliding_door_footprint_bridges(rows, words)
    assert [(bridge.first_host_path_id, bridge.second_host_path_id) for bridge in indexed] == [(0, 1)]


def test_pairs_the_gate_cannot_accept_are_skipped():
    rows, word = _door(random.Random(5), 100.0, 100.0, gap=40.0)
    walls = [(i, LAYER, row["rect"]) for i, row in enumerate(rows[:2])]
    walls.append((2, LAYER, (160.0, 600.0, 200.0, 602.5)))  # far from the label's level
    walls.append((3, LAYER, (700.0, 100.0, 740.0, 102.5)))  # more than 450 pt past the first wall
    walls.append((4, LAYER, (40.0, 600.0, walls[0][2][2], 602.5)))  # first wall also far from the level
    by_left = sliding._edge_index(walls, range(len(walls)), 0)
    by_top = sliding._edge_index(walls, range(len(walls)), 1)
    window = sliding._label_window(walls, word[:4], by_left, by_top)
    assert window.lx - 451.0 <= walls[0][2][2] <= window.lx + 1.0
    # The first wall reaches the label's level, so any far wall in the gap window stays; the 600 pt one goes.
    assert list(sliding._far_walls(window, 0, walls[0][2], True, False)) == [1, 2]
    # Neither wall reaching the level can never frame an aperture near the label.
    assert list(sliding._far_walls(window, 4, walls[4][2], True, False)) == [1]


def test_a_post_that_alone_reaches_the_label_is_kept():
    """Only the far wall reaches the label's level: an upright post well past a short first wall."""
    rows, word = _door(random.Random(7), 200.0, 200.0, gap=40.0, b_post=True)
    walls = [(0, LAYER, (150.0, 100.0, 200.0, 102.5)), (1, LAYER, rows[1]["rect"])]
    by_left = sliding._edge_index(walls, range(2), 0)
    by_top = sliding._edge_index(walls, range(2), 1)
    window = sliding._label_window(walls, word[:4], by_left, by_top)
    assert 0 not in window.level_y and 1 in window.level_y
    assert list(sliding._far_walls(window, 0, walls[0][2], True, False)) == [1]
