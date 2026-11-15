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


def test_valid_native_vector_decoy_without_wall_geometry_abstains(monkeypatch, tmp_path):
    """Adversarial regression: real native PDF with 610 valid vector strokes but no walls.

    Verifies that real vector strokes without orthogonal wall geometry or closed room
    perimeters strictly abstain and emit zero customer rows across all four issuers.
    """
    import fitz

    path = tmp_path / "native_decoy.pdf"
    doc = fitz.open()
    terms = [
        "GROUND FLOOR PLAN AREA SCHEDULE VINYL TILES MEDIA BED 2 BED 3",
        "SECTION A-A 2,700 GYPROCK",
    ]
    for spec in wet._WET_FLOOR_SPECS.values():
        terms.extend(["TILES", *map(str, spec["dim_strings"])])
    for spec in vinyl._VINYL_FLOOR_SPECS.values():
        terms.extend(["VINYL", str(spec["room_label"]), *map(str, spec["dim_strings"])])
    for spec in wall._WALL_TILE_SPECS.values():
        terms.extend(map(str, spec["evidence_tokens"]))

    for page_i in range(18):
        page = doc.new_page(width=1400, height=950)
        for i in range(610):
            x = 40 + (i % 100) * 7
            y = 380 + (i // 100) * 17
            page.draw_line((x, y), (x + 2.1, y + 1.6), color=(0, 0, 0), width=0.2)
        words = (" ".join(terms)).split()
        for j in range(0, len(words), 10):
            row = " ".join(words[j : j + 10])
            page.insert_text((30, 36 + 14 * (j // 10)), row, fontsize=7.4)
        if page_i == 2:
            vals = [
                "MAIN LIVING 12.34 m2",
                "GARAGE 12.34 m2",
                "MAIN PORCH 12.34 m2",
                "MAIN ALFRESCO 12.34 m2",
                "GF LIVING 12.34 m2",
                "GF ALFRESCO 12.34 m2",
                "GF PORCH 12.34 m2",
            ]
            for k, row in enumerate(vals):
                page.insert_text((961, 632 + 13 * k), row, fontsize=8)
    doc.save(path)
    doc.close()

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    for mod, fn in (
        (vinyl, vinyl.issue_original_three_laurel_vinyl_floor_customer_quantities),
        (wet, wet.issue_original_three_laurel_wet_area_floor_customer_quantities),
        (wall, wall.issue_original_three_laurel_wall_tile_customer_quantities),
        (ceiling, ceiling.issue_original_three_laurel_ceiling_customer_quantities),
    ):
        monkeypatch.setattr(mod, "THREE_LAUREL_SOURCE_SHA256", digest)
        monkeypatch.setattr(mod, "THREE_LAUREL_DOCUMENT_ID", f"live-source:{digest[:32]}")
        monkeypatch.setattr(mod, "THREE_LAUREL_REVISION_ID", f"3laurel_sha_{digest[:20]}")
        res = fn(path)
        assert res.status == "ABSTAIN"
        assert len(res.quantities) == 0
        assert len(res.customer_rows) == 0
        assert "source_owned_physical_quantity_authority_unavailable" in res.reason_codes
def test_orthogonal_native_vector_decoy_without_room_wall_enclosures_abstains(tmp_path, monkeypatch):
    """Adversarial decoy with 1220 native vectors (including 60 H and 60 V lines) must abstain."""
    import fitz

    terms = [
        "GROUND FLOOR PLAN AREA SCHEDULE VINYL TILES MEDIA BED 2 BED 3",
        "SECTION A-A 2,700 GYPROCK",
    ]
    for spec in wet._WET_FLOOR_SPECS.values():
        terms.extend(["TILES", *map(str, spec["dim_strings"])])
    for spec in vinyl._VINYL_FLOOR_SPECS.values():
        terms.extend(["VINYL", str(spec["room_label"]), *map(str, spec["dim_strings"])])
    for spec in wall._WALL_TILE_SPECS.values():
        terms.extend(map(str, spec["evidence_tokens"]))

    path = tmp_path / "native_orthogonal_decoy.pdf"
    doc = fitz.open()
    for page_i in range(18):
        page = doc.new_page(width=1400, height=950)
        # 1100 tiny diagonal lines
        for i in range(1100):
            x = 40 + (i % 100) * 7
            y = 380 + (i // 100) * 17
            page.draw_line((x, y), (x + 2.1, y + 1.6), color=(0, 0, 0), width=0.2)
        # 60 horizontal and 60 vertical lines
        for i in range(60):
            page.draw_line((900, 80 + 8 * i), (924, 80 + 8 * i), color=(0, 0, 0), width=0.2)
            page.draw_line((1100 + 2 * i, 80), (1100 + 2 * i, 104), color=(0, 0, 0), width=0.2)
        text = " ".join(terms)
        words = text.split()
        for j in range(0, len(words), 10):
            row = " ".join(words[j : j + 10])
            page.insert_text((30, 36 + 14 * (j // 10)), row, fontsize=7.4)
        page.insert_text((1000, 750), "FLOOR PLAN", fontsize=8)
        if page_i == 2:
            vals = [
                "MAIN LIVING 12.34 m2",
                "GARAGE 12.34 m2",
                "MAIN PORCH 12.34 m2",
                "MAIN ALFRESTO 12.34 m2",
                "GF LIVING 12.34 m2",
                "GF ALFRESCO 12.34 m2",
                "GF PORCH 12.34 m2",
            ]
            for k, row in enumerate(vals):
                page.insert_text((961, 632 + 13 * k), row, fontsize=8)
    doc.save(path)
    doc.close()

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    for mod, fn in (
        (vinyl, vinyl.issue_original_three_laurel_vinyl_floor_customer_quantities),
        (wet, wet.issue_original_three_laurel_wet_area_floor_customer_quantities),
        (wall, wall.issue_original_three_laurel_wall_tile_customer_quantities),
        (ceiling, ceiling.issue_original_three_laurel_ceiling_customer_quantities),
    ):
        monkeypatch.setattr(mod, "THREE_LAUREL_SOURCE_SHA256", digest)
        monkeypatch.setattr(mod, "THREE_LAUREL_DOCUMENT_ID", f"live-source:{digest[:32]}")
        monkeypatch.setattr(mod, "THREE_LAUREL_REVISION_ID", f"3laurel_sha_{digest[:20]}")
        res = fn(path)
        assert res.status == "ABSTAIN"
        assert len(res.quantities) == 0
        assert len(res.customer_rows) == 0
        assert "source_owned_physical_quantity_authority_unavailable" in res.reason_codes
def test_disconnected_four_quadrant_decoy_without_room_cad_primitives_abstains(tmp_path, monkeypatch):
    """3rd-generation adversarial decoy with disconnected quadrant strokes around room labels
    and an unrelated thick stroke at (1290, 850) must strictly return ABSTAIN across all 4 finish issuers.
    """
    import fitz

    terms = [
        "GROUND FLOOR PLAN AREA SCHEDULE VINYL TILES MEDIA BED 2 BED 3",
        "SECTION A-A 2,700 GYPROCK",
    ]
    for spec in wet._WET_FLOOR_SPECS.values():
        terms.extend(["TILES", *map(str, spec["dim_strings"])])
    for spec in vinyl._VINYL_FLOOR_SPECS.values():
        terms.extend(["VINYL", str(spec["room_label"]), *map(str, spec["dim_strings"])])
    for spec in wall._WALL_TILE_SPECS.values():
        terms.extend(map(str, spec["evidence_tokens"]))

    path = tmp_path / "native_disconnected_quadrant_decoy.pdf"
    doc = fitz.open()
    for page_i in range(18):
        page = doc.new_page(width=1400, height=950)
        for i in range(1100):
            x = 40 + (i % 100) * 7
            y = 380 + (i // 100) * 17
            page.draw_line((x, y), (x + 2.1, y + 1.6), color=(0, 0, 0), width=0.2)
        for i in range(60):
            page.draw_line((900, 80 + 8 * i), (924, 80 + 8 * i), color=(0, 0, 0), width=0.2)
            page.draw_line((1100 + 2 * i, 80), (1100 + 2 * i, 104), color=(0, 0, 0), width=0.2)
        text = " ".join(terms)
        words = text.split()
        for j in range(0, len(words), 10):
            row = " ".join(words[j : j + 10])
            page.insert_text((30, 36 + 14 * (j // 10)), row, fontsize=7.4)
        page.insert_text((1000, 750), "FLOOR PLAN", fontsize=8)
        page.draw_line((1290, 850), (1320, 850), color=(0, 0, 0), width=0.8)
        if page_i == 2:
            vals = [
                "MAIN LIVING 12.34 m2",
                "GARAGE 12.34 m2",
                "MAIN PORCH 12.34 m2",
                "MAIN ALFRESCO 12.34 m2",
                "GF LIVING 12.34 m2",
                "GF ALFRESCO 12.34 m2",
                "GF PORCH 12.34 m2",
            ]
            for k, row in enumerate(vals):
                page.insert_text((961, 632 + 13 * k), row, fontsize=8)
    page = doc[2]
    for i, label in enumerate(("BATH", "BATHROOM", "LAUNDRY", "ENSUITE", "WC")):
        page.insert_text((480, 195 + 47 * i), label, fontsize=8)
    words = page.get_text("words")
    labels = (
        "MEDIA", "BED 2", "BED 3", "BATH", "BATHROOM", "LAUNDRY", "ENSUITE", "LIVING", "GARAGE", "WC",
    )
    for label in labels:
        toks = label.split()
        matches = [
            words[i : i + len(toks)]
            for i in range(len(words) - len(toks) + 1)
            if all(toks[k].upper() == words[i + k][4].upper() for k in range(len(toks)))
        ]
        if not matches:
            continue
        tw = matches[0]
        cx = (min(w[0] for w in tw) + max(w[2] for w in tw)) / 2.0
        cy = (min(w[1] for w in tw) + max(w[3] for w in tw)) / 2.0
        lines = (
            ((cx - 9, cy - 20), (cx + 9, cy - 20)),
            ((cx - 9, cy + 20), (cx + 9, cy + 20)),
            ((cx - 20, cy - 9), (cx - 20, cy + 9)),
            ((cx + 20, cy - 9), (cx + 20, cy + 9)),
        )
        for a, b in lines:
            page.draw_line(a, b, color=(0, 0, 0), width=0.2)
    doc.save(path)
    doc.close()

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    for mod, fn in (
        (vinyl, vinyl.issue_original_three_laurel_vinyl_floor_customer_quantities),
        (wet, wet.issue_original_three_laurel_wet_area_floor_customer_quantities),
        (wall, wall.issue_original_three_laurel_wall_tile_customer_quantities),
        (ceiling, ceiling.issue_original_three_laurel_ceiling_customer_quantities),
    ):
        monkeypatch.setattr(mod, "THREE_LAUREL_SOURCE_SHA256", digest)
        monkeypatch.setattr(mod, "THREE_LAUREL_DOCUMENT_ID", f"live-source:{digest[:32]}")
        monkeypatch.setattr(mod, "THREE_LAUREL_REVISION_ID", f"3laurel_sha_{digest[:20]}")
        res = fn(path)
        assert res.status == "ABSTAIN"
        assert len(res.quantities) == 0
        assert len(res.customer_rows) == 0
        assert "source_owned_physical_quantity_authority_unavailable" in res.reason_codes
def test_local_fill_disconnected_four_quadrant_decoy_without_room_wall_enclosures_abstains(tmp_path, monkeypatch):
    """4th-generation adversarial decoy with disconnected quadrant strokes around room labels
    plus a nearby filled CAD circle within 250 pt of each label must strictly return ABSTAIN.
    """
    import fitz

    terms = [
        "GROUND FLOOR PLAN AREA SCHEDULE VINYL TILES MEDIA BED 2 BED 3",
        "SECTION A-A 2,700 GYPROCK",
    ]
    for spec in wet._WET_FLOOR_SPECS.values():
        terms.extend(["TILES", *map(str, spec["dim_strings"])])
    for spec in vinyl._VINYL_FLOOR_SPECS.values():
        terms.extend(["VINYL", str(spec["room_label"]), *map(str, spec["dim_strings"])])
    for spec in wall._WALL_TILE_SPECS.values():
        terms.extend(map(str, spec["evidence_tokens"]))

    path = tmp_path / "native_local_fill_disconnected_quadrant_decoy.pdf"
    doc = fitz.open()
    for page_i in range(18):
        page = doc.new_page(width=1400, height=950)
        for i in range(1100):
            x = 40 + (i % 100) * 7
            y = 380 + (i // 100) * 17
            page.draw_line((x, y), (x + 2.1, y + 1.6), color=(0, 0, 0), width=0.2)
        for i in range(60):
            page.draw_line((900, 80 + 8 * i), (924, 80 + 8 * i), color=(0, 0, 0), width=0.2)
            page.draw_line((1100 + 2 * i, 80), (1100 + 2 * i, 104), color=(0, 0, 0), width=0.2)
        text = " ".join(terms)
        words = text.split()
        for j in range(0, len(words), 10):
            row = " ".join(words[j : j + 10])
            page.insert_text((30, 36 + 14 * (j // 10)), row, fontsize=7.4)
        page.insert_text((1000, 750), "FLOOR PLAN", fontsize=8)
        page.draw_line((1290, 850), (1320, 850), color=(0, 0, 0), width=0.8)
        if page_i == 2:
            vals = [
                "MAIN LIVING 12.34 m2",
                "GARAGE 12.34 m2",
                "MAIN PORCH 12.34 m2",
                "MAIN ALFRESCO 12.34 m2",
                "GF LIVING 12.34 m2",
                "GF ALFRESCO 12.34 m2",
                "GF PORCH 12.34 m2",
            ]
            for k, row in enumerate(vals):
                page.insert_text((961, 632 + 13 * k), row, fontsize=8)
    page = doc[2]
    for i, label in enumerate(("BATH", "BATHROOM", "LAUNDRY", "ENSUITE", "WC")):
        page.insert_text((480, 195 + 47 * i), label, fontsize=8)
    words = page.get_text("words")
    labels = (
        "MEDIA", "BED 2", "BED 3", "BATH", "BATHROOM", "LAUNDRY", "ENSUITE", "LIVING", "GARAGE", "WC",
    )
    for label in labels:
        toks = label.split()
        matches = [
            words[i : i + len(toks)]
            for i in range(len(words) - len(toks) + 1)
            if all(toks[k].upper() == words[i + k][4].upper() for k in range(len(toks)))
        ]
        if not matches:
            continue
        tw = matches[0]
        cx = (min(w[0] for w in tw) + max(w[2] for w in tw)) / 2.0
        cy = (min(w[1] for w in tw) + max(w[3] for w in tw)) / 2.0
        lines = (
            ((cx - 9, cy - 20), (cx + 9, cy - 20)),
            ((cx - 9, cy + 20), (cx + 9, cy + 20)),
            ((cx - 20, cy - 9), (cx - 20, cy + 9)),
            ((cx + 20, cy - 9), (cx + 20, cy + 9)),
        )
        for a, b in lines:
            page.draw_line(a, b, color=(0, 0, 0), width=0.2)
        page.draw_circle((cx + 35, cy + 35), radius=2, color=(0, 0, 0), fill=(0, 0, 0), width=0.8)
    doc.save(path)
    doc.close()

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    for mod, fn in (
        (vinyl, vinyl.issue_original_three_laurel_vinyl_floor_customer_quantities),
        (wet, wet.issue_original_three_laurel_wet_area_floor_customer_quantities),
        (wall, wall.issue_original_three_laurel_wall_tile_customer_quantities),
        (ceiling, ceiling.issue_original_three_laurel_ceiling_customer_quantities),
    ):
        monkeypatch.setattr(mod, "THREE_LAUREL_SOURCE_SHA256", digest)
        monkeypatch.setattr(mod, "THREE_LAUREL_DOCUMENT_ID", f"live-source:{digest[:32]}")
        monkeypatch.setattr(mod, "THREE_LAUREL_REVISION_ID", f"3laurel_sha_{digest[:20]}")
        res = fn(path)
        assert res.status == "ABSTAIN"
        assert len(res.quantities) == 0
        assert len(res.customer_rows) == 0
        assert "source_owned_physical_quantity_authority_unavailable" in res.reason_codes

def test_open_bottom_two_corner_decoy_without_room_wall_enclosures_abstains(tmp_path, monkeypatch):
    """5th-generation adversarial decoy: exactly TWO top corners touch; both bottom corners
    have a 35 pt gap to verticals, so no closed physical room perimeter exists.
    Must strictly return ABSTAIN across all 4 finish issuers.
    """
    import fitz

    terms = [
        "GROUND FLOOR PLAN AREA SCHEDULE VINYL TILES MEDIA BED 2 BED 3",
        "SECTION A-A 2,700 GYPROCK",
    ]
    for spec in wet._WET_FLOOR_SPECS.values():
        terms.extend(["TILES", *map(str, spec["dim_strings"])])
    for spec in vinyl._VINYL_FLOOR_SPECS.values():
        terms.extend(["VINYL", str(spec["room_label"]), *map(str, spec["dim_strings"])])
    for spec in wall._WALL_TILE_SPECS.values():
        terms.extend(map(str, spec["evidence_tokens"]))

    path = tmp_path / "native_open_bottom_two_corner_decoy.pdf"
    doc = fitz.open()
    for page_i in range(18):
        page = doc.new_page(width=1400, height=950)
        for i in range(1100):
            x = 40 + (i % 100) * 7
            y = 380 + (i // 100) * 17
            page.draw_line((x, y), (x + 2.1, y + 1.6), color=(0, 0, 0), width=0.2)
        for i in range(60):
            page.draw_line((900, 80 + 8 * i), (924, 80 + 8 * i), color=(0, 0, 0), width=0.2)
            page.draw_line((1100 + 2 * i, 80), (1100 + 2 * i, 104), color=(0, 0, 0), width=0.2)
        text = " ".join(terms)
        words = text.split()
        for j in range(0, len(words), 10):
            row = " ".join(words[j : j + 10])
            page.insert_text((30, 36 + 14 * (j // 10)), row, fontsize=7.4)
        page.insert_text((1000, 750), "FLOOR PLAN", fontsize=8)
        page.draw_line((1290, 850), (1320, 850), color=(0, 0, 0), width=0.8)
        if page_i == 2:
            vals = [
                "MAIN LIVING 12.34 m2",
                "GARAGE 12.34 m2",
                "MAIN PORCH 12.34 m2",
                "MAIN ALFRESCO 12.34 m2",
                "GF LIVING 12.34 m2",
                "GF ALFRESCO 12.34 m2",
                "GF PORCH 12.34 m2",
            ]
            for k, row in enumerate(vals):
                page.insert_text((961, 632 + 13 * k), row, fontsize=8)
    page = doc[2]
    for i, label in enumerate(("BATH", "BATHROOM", "LAUNDRY", "ENSUITE", "WC")):
        page.insert_text((480, 195 + 47 * i), label, fontsize=8)
    words = page.get_text("words")
    labels = (
        "MEDIA", "BED 2", "BED 3", "BATH", "BATHROOM", "LAUNDRY", "ENSUITE", "LIVING", "GARAGE", "WC",
    )
    for label in labels:
        toks = label.split()
        matches = [
            words[i : i + len(toks)]
            for i in range(len(words) - len(toks) + 1)
            if all(toks[k].upper() == words[i + k][4].upper() for k in range(len(toks)))
        ]
        if not matches:
            continue
        tw = matches[0]
        cx = (min(w[0] for w in tw) + max(w[2] for w in tw)) / 2.0
        cy = (min(w[1] for w in tw) + max(w[3] for w in tw)) / 2.0
        lines = (
            ((cx - 35, cy - 30), (cx + 35, cy - 30)),
            ((cx - 35, cy + 40), (cx + 35, cy + 40)),
            ((cx - 35, cy - 30), (cx - 35, cy + 5)),
            ((cx + 35, cy - 30), (cx + 35, cy + 5)),
        )
        for a, b in lines:
            page.draw_line(a, b, color=(0, 0, 0), width=0.2)
        page.draw_circle((cx + 35, cy + 35), radius=2, color=(0, 0, 0), fill=(0, 0, 0), width=0.8)
    doc.save(path)
    doc.close()

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    for mod, fn in (
        (vinyl, vinyl.issue_original_three_laurel_vinyl_floor_customer_quantities),
        (wet, wet.issue_original_three_laurel_wet_area_floor_customer_quantities),
        (wall, wall.issue_original_three_laurel_wall_tile_customer_quantities),
        (ceiling, ceiling.issue_original_three_laurel_ceiling_customer_quantities),
    ):
        monkeypatch.setattr(mod, "THREE_LAUREL_SOURCE_SHA256", digest)
        monkeypatch.setattr(mod, "THREE_LAUREL_DOCUMENT_ID", f"live-source:{digest[:32]}")
        monkeypatch.setattr(mod, "THREE_LAUREL_REVISION_ID", f"3laurel_sha_{digest[:20]}")
        res = fn(path)
        assert res.status == "ABSTAIN"
        assert len(res.quantities) == 0
        assert len(res.customer_rows) == 0
        assert "source_owned_physical_quantity_authority_unavailable" in res.reason_codes

