"""Original raster source shared across G17 candidates is never a wall host."""
from copy import deepcopy

import pytest

from scripts.gptmax_full_foreground_flank_stages import cross_opening_source_usage


def _row(opening, role, source, line=(10., 20., 30., 20.)):
    return {
        "opening_identity_id": opening,
        "flanks": [{
            "role": role,
            "source_run_rows": [{
                "source_observation_id": source,
                "source_line_pt": list(line),
                "source_pixel_receipt_freshly_reauthenticated": True,
                "physical_equivalence_proven": False,
                "host_publication_allowed": False,
            }],
        }],
        "host_publication_allowed": False,
    }


def test_shared_original_source_does_not_elect_an_opening_host():
    rows = [
        _row("opening-z", "left", "pixel-42"),
        _row("opening-a", "right", "pixel-42"),
        _row("opening-other", "left", "unrelated"),
    ]
    original = deepcopy(rows)
    shared = cross_opening_source_usage(rows)
    assert rows == original
    assert shared == [{
        "source_observation_id": "pixel-42",
        "opening_identity_ids": ["opening-a", "opening-z"],
        "source_uses": [
            {"opening_identity_id": "opening-a", "flank_role": "right",
             "source_line_pt": [10., 20., 30., 20.]},
            {"opening_identity_id": "opening-z", "flank_role": "left",
             "source_line_pt": [10., 20., 30., 20.]},
        ],
        "physical_equivalence_proven": False,
        "source_parent_transfer_allowed": False,
        "host_publication_allowed": False,
        "opening_count_publication_allowed": False,
    }]
    assert cross_opening_source_usage(list(reversed(rows))) == shared


def test_original_line_orientation_does_not_invent_distinct_source():
    rows = [_row("opening-z", "left", "pixel-42"),
            _row("opening-a", "right", "pixel-42", (30., 20., 10., 20.))]
    shared = cross_opening_source_usage(rows)
    assert len(shared) == 1
    assert shared[0]["source_parent_transfer_allowed"] is False


@pytest.mark.parametrize("damage", [
    "duplicate_opening", "missing_opening", "duplicate_flank",
    "duplicate_source", "missing_source", "missing_reauthentication",
    "host_publication", "physical_equivalence", "inconsistent_geometry",
    "nonfinite_geometry", "degenerate_geometry", "missing_flanks",
])
def test_foreign_or_ambiguous_original_support_fails_closed(damage):
    rows = [_row("opening-z", "left", "pixel-42"),
            _row("opening-a", "right", "pixel-42")]
    if damage == "duplicate_opening":
        rows[1]["opening_identity_id"] = "opening-z"
    elif damage == "missing_opening":
        rows[1]["opening_identity_id"] = ""
    elif damage == "duplicate_flank":
        rows[0]["flanks"].append(deepcopy(rows[0]["flanks"][0]))
    elif damage == "duplicate_source":
        rows[0]["flanks"][0]["source_run_rows"].append(
            deepcopy(rows[0]["flanks"][0]["source_run_rows"][0])
        )
    elif damage == "missing_source":
        rows[0]["flanks"][0]["source_run_rows"][0]["source_observation_id"] = ""
    elif damage == "missing_reauthentication":
        rows[0]["flanks"][0]["source_run_rows"][0][
            "source_pixel_receipt_freshly_reauthenticated"] = False
    elif damage == "host_publication":
        rows[0]["flanks"][0]["source_run_rows"][0]["host_publication_allowed"] = True
    elif damage == "physical_equivalence":
        rows[0]["flanks"][0]["source_run_rows"][0]["physical_equivalence_proven"] = True
    elif damage == "inconsistent_geometry":
        rows[1]["flanks"][0]["source_run_rows"][0]["source_line_pt"] = [10., 21., 30., 21.]
    elif damage == "nonfinite_geometry":
        rows[0]["flanks"][0]["source_run_rows"][0]["source_line_pt"][2] = float("nan")
    elif damage == "degenerate_geometry":
        rows[0]["flanks"][0]["source_run_rows"][0]["source_line_pt"] = [1., 1., 1., 1.]
    elif damage == "missing_flanks":
        rows[0].pop("flanks")
    with pytest.raises(ValueError):
        cross_opening_source_usage(rows)


def test_unshared_source_is_not_reported_as_a_shared_host():
    assert cross_opening_source_usage([
        _row("opening-z", "left", "pixel-z"),
        _row("opening-a", "right", "pixel-a"),
    ]) == []
