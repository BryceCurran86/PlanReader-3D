"""Room label to a single inside-face ring (report only). Synthetic only."""
from __future__ import annotations

import copy

import fitz
import pytest

from pb_labelled_ring_ownership_shadow import (
    REASON_NO_RING,
    REASON_ONE_RING,
    REASON_SEVERAL_RINGS,
    REASON_SHARED_RING,
    labelled_ring_ownership,
)
from pb_migration_contracts import EvidenceResolutionStatus as Status

ROOM = ((50.0, 50.0), (164.0, 50.0), (164.0, 164.0), (50.0, 164.0))
OTHER = ((200.0, 50.0), (300.0, 50.0), (300.0, 164.0), (200.0, 164.0))


def drawings():
    document = fitz.open()
    page = document.new_page(width=600, height=600)
    for x0, y0, x1, y1 in ((44, 44, 170, 170), (50, 50, 164, 164)):
        for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            page.draw_line(a, b, color=(0, 0, 0), width=0.7)
    found = page.get_drawings()
    document.close()
    return found


def entry(polygon, status=Status.CANDIDATE, name="default"):
    return {"polygon_pdf_pts": polygon, "status": status, "record_ids": {name: f"ring-{polygon[0]}"}, "runs": (name,)}


DRAWN = drawings()


def test_one_ring_holding_one_label_is_reported_with_its_support():
    result = labelled_ring_ownership({"OFFICE": (100, 100)}, [entry(ROOM), entry(OTHER)], DRAWN)["OFFICE"]
    assert result["status"] is Status.CANDIDATE and result["reason"] == REASON_ONE_RING
    assert result["wall_support"]["unsupported_share"] < 0.01 and result["measurement_authority"] is False
    assert result["record_ids"] == {"default": f"ring-{ROOM[0]}"}


@pytest.mark.parametrize("labels,entries,expected", [
    ({"A": (500, 500)}, [entry(ROOM)], {"A": REASON_NO_RING}),
    ({"A": (100, 100)}, [entry(ROOM, status=Status.ABSTAINED)], {"A": REASON_NO_RING}),
    ({"A": (100, 100)}, [entry(ROOM), entry(((40, 40), (180, 40), (180, 180), (40, 180)))], {"A": REASON_SEVERAL_RINGS}),
    ({"LIVING": (80, 80), "KITCHEN": (140, 140)}, [entry(ROOM)], {"LIVING": REASON_SHARED_RING, "KITCHEN": REASON_SHARED_RING}),
], ids=["outside", "abstained_ring", "nested", "open_plan"])
def test_unclear_ownership_abstains(labels, entries, expected):
    result = labelled_ring_ownership(labels, entries, DRAWN)
    assert {k: v["reason"] for k, v in result.items()} == expected
    assert all(v["status"] is Status.ABSTAINED and v["wall_support"] is None for v in result.values())


def test_an_ambiguous_label_still_counts_against_its_rings():
    nested = ((60.0, 60.0), (110.0, 60.0), (110.0, 110.0), (60.0, 110.0))
    result = labelled_ring_ownership({"A": (140, 140), "B": (80, 80)}, [entry(ROOM), entry(nested)], DRAWN)
    assert result["B"]["reason"] == REASON_SEVERAL_RINGS and result["A"]["reason"] == REASON_SHARED_RING


def test_order_and_inputs():
    labels = {"B": (250, 100), "A": (100, 100)}
    entries = [entry(OTHER), entry(ROOM)]
    before = copy.deepcopy((labels, entries))
    forward = labelled_ring_ownership(labels, entries, DRAWN)
    backward = labelled_ring_ownership(dict(reversed(list(labels.items()))), list(reversed(entries)), DRAWN)
    assert forward == backward and (labels, entries) == before
    assert forward["B"]["wall_support"]["unsupported_share"] == 1.0  # a ring on no wall ink reports it
