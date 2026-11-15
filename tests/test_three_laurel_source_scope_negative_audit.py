"""Adversarial source-scope examples for newly introduced 3Laurel finish issuers.

These deliberately synthetic pages are NOT original-source acceptance. They show
that a matching document hash plus unrelated page text/drawings must never stand
in for a room's owned physical face or a ceiling plane.
"""
from __future__ import annotations

import hashlib
from decimal import Decimal

import pytest

import pb_three_laurel_vinyl_floor_customer as vinyl
import pb_three_laurel_ceiling_customer as ceiling


class _Page:
    def __init__(self, text=""):
        self.text = text

    def get_drawings(self):
        return [{"items": [("l", "unrelated-drawing")]}]

    def get_pixmap(self, **kwargs):
        return object()

    def get_text(self, kind):
        return self.text if kind == "text" else []


class _Document:
    page_count = 18

    def __init__(self, p3_text, p7_text=""):
        self.pages = [_Page() for _ in range(18)]
        self.pages[2] = _Page(p3_text)
        self.pages[6] = _Page(p7_text)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __getitem__(self, item):
        return self.pages[item]


def _synthetic_source(monkeypatch, module, tmp_path, doc):
    path = tmp_path / "synthetic.pdf"
    payload = b"%PDF-1.4\nsynthetic-source-scope-negative\n"
    path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(module, "THREE_LAUREL_SOURCE_SHA256", digest)
    monkeypatch.setattr(module, "THREE_LAUREL_DOCUMENT_ID", f"live-source:{digest[:32]}")
    monkeypatch.setattr(module, "THREE_LAUREL_REVISION_ID", f"3laurel_sha_{digest[:20]}")
    monkeypatch.setattr(module.fitz, "open", lambda **kwargs: doc)
    return path


def test_vinyl_page_tokens_without_room_faces_must_not_publish(monkeypatch, tmp_path):
    # All token strings exist but no room-bound wall faces, dimension leaders,
    # finish ownership, or physical room geometry exists anywhere.
    doc = _Document("VINYL MEDIA BED 2 BED 3 4,200 3,130 3,000")
    path = _synthetic_source(monkeypatch, vinyl, tmp_path, doc)
    result = vinyl.issue_original_three_laurel_vinyl_floor_customer_quantities(path)
    assert result.status == "ABSTAIN"
    assert not result.customer_rows


def test_floor_area_schedule_must_not_prove_ceiling_lining(monkeypatch, tmp_path):
    doc = _Document("GROUND FLOOR PLAN AREA SCHEDULE", p7_text="GYPROCK")
    path = _synthetic_source(monkeypatch, ceiling, tmp_path, doc)
    # Even a correctly read floor-area table has no ceiling region or plane.
    monkeypatch.setattr(
        ceiling,
        "_parse_schedule_table",
        lambda page: {spec["schedule_key"]: Decimal("12.34") for spec in ceiling._CEILING_SPECS.values()},
    )
    result = ceiling.issue_original_three_laurel_ceiling_customer_quantities(path)
    assert result.status == "ABSTAIN"
    assert not result.customer_rows


import pb_three_laurel_wet_area_floor_customer as wet
import pb_three_laurel_wall_tile_customer as wall


def test_wet_area_page_tokens_without_finished_faces_must_not_publish(monkeypatch, tmp_path):
    doc = _Document("TILES")
    for spec in wet._WET_FLOOR_SPECS.values():
        doc.pages[spec["page_index"]].text += " TILES " + " ".join(spec["dim_strings"])
    path = _synthetic_source(monkeypatch, wet, tmp_path, doc)
    result = wet.issue_original_three_laurel_wet_area_floor_customer_quantities(path)
    assert result.status == "ABSTAIN"
    assert not result.customer_rows


def test_wall_tile_tokens_without_wall_faces_must_not_publish(monkeypatch, tmp_path):
    doc = _Document("NOT A WALL PLAN", p7_text="GYPROCK 2,700")
    for spec in wall._WALL_TILE_SPECS.values():
        doc.pages[spec["page_index"]].text += " " + " ".join(spec["evidence_tokens"])
    path = _synthetic_source(monkeypatch, wall, tmp_path, doc)
    result = wall.issue_original_three_laurel_wall_tile_customer_quantities(path)
    assert result.status == "ABSTAIN"
    assert not result.customer_rows

