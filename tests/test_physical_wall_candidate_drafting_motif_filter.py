from __future__ import annotations

from pb_physical_wall_candidate_authority import (
    _filter_repeated_non_physical_drafting_primitives,
)


def _line(
    raw_id: str,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    path_index: int,
    stroke=(0.0, 0.0, 0.0),
    width: float = 0.48,
) -> dict:
    return {
        "id": raw_id,
        "kind": "line",
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "path_index": path_index,
        "stroke": stroke,
        "stroke_present": True,
        "fill": None,
        "fill_present": False,
        "width": width,
        "width_present": True,
    }


def _fill_rect_edges(path_index: int) -> list[dict]:
    result = []
    points = ((10.0, 10.0), (20.0, 10.0), (20.0, 20.0), (10.0, 20.0))
    for idx, (first, second) in enumerate(zip(points, points[1:] + points[:1])):
        result.append(
            {
                "id": f"fill-{idx}",
                "kind": "rect_edge",
                "x1": first[0],
                "y1": first[1],
                "x2": second[0],
                "y2": second[1],
                "path_index": path_index,
                "stroke": None,
                "stroke_present": False,
                "fill": (0.4, 0.4, 0.4),
                "fill_present": True,
                "width": 0.0,
                "width_present": False,
            }
        )
    return result


def _filter(segments: list[dict]) -> tuple[dict, ...]:
    return _filter_repeated_non_physical_drafting_primitives(
        segments,
        page_width=1000.0,
        page_height=1000.0,
    )


def test_unique_short_wall_return_is_preserved() -> None:
    short = _line("short", 0.0, 0.0, 1.0, 0.0, path_index=1)
    assert _filter([short]) == (short,)


def test_unique_diagonal_wall_is_preserved() -> None:
    diagonal = _line("diag", 0.0, 0.0, 20.0, 20.0, path_index=1)
    assert _filter([diagonal]) == (diagonal,)


def test_small_closed_room_under_five_square_metres_equivalent_fixture_is_preserved() -> None:
    walls = [
        _line("n", 0.0, 0.0, 12.0, 0.0, path_index=1),
        _line("e", 12.0, 0.0, 12.0, 10.0, path_index=2),
        _line("s", 12.0, 10.0, 0.0, 10.0, path_index=3),
        _line("w", 0.0, 10.0, 0.0, 0.0, path_index=4),
    ]
    assert _filter(walls) == tuple(walls)


def test_green_stroked_insulated_panel_boundaries_are_preserved() -> None:
    green = (0.0, 0.5, 0.0)
    walls = [
        _line("g1", 0.0, 0.0, 80.0, 0.0, path_index=1, stroke=green),
        _line("g2", 0.0, 8.0, 80.0, 8.0, path_index=2, stroke=green),
    ]
    assert _filter(walls) == tuple(walls)


def test_fill_only_rectangle_edges_do_not_become_wall_linework() -> None:
    fill_edges = _fill_rect_edges(path_index=1)
    assert _filter(fill_edges) == ()


def test_dense_repeated_non_orthogonal_singleton_motif_is_excluded() -> None:
    motif = [
        _line(
            f"h-{idx}",
            float(idx * 3),
            0.0,
            float(idx * 3 + 3),
            3.0,
            path_index=idx,
            stroke=(0.5, 0.5, 0.5),
            width=0.24,
        )
        for idx in range(8)
    ]
    assert _filter(motif) == ()


def test_repeated_orthogonal_short_returns_need_strong_repetition_before_exclusion() -> None:
    walls = [
        _line(
            f"r-{idx}",
            float(idx * 2),
            0.0,
            float(idx * 2 + 2),
            0.0,
            path_index=idx,
        )
        for idx in range(12)
    ]
    assert _filter(walls) == tuple(walls)
