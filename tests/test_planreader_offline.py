"""Tests for the offline plan reader (pb_planreader_offline.py).

Validates that the offline analysis pipeline works correctly
without requiring AI APIs or real PDF files.
"""

from __future__ import annotations

import math
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure repo root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz

from pb_planreader_offline import classify_page_offline, detect_dimensions, detect_scale
from pb_planreader_shared import (
    SCALE_RE,
    classify_page,
    detect_drawing_number,
    detect_scale_from_text,
    dimension_value_m,
    extract_scale_ratio,
)


class TestDetectScaleAbstains(unittest.TestCase):
    def test_one_printed_ratio_is_kept(self):
        result = detect_scale(None, [{"text": "SCALE"}, {"text": "1:100"}])
        self.assertIsNotNone(result)
        self.assertEqual(result["ratio"], 100)

    def test_two_different_ratios_abstain(self):
        result = detect_scale(None, [{"text": "1:100"}, {"text": "1:50"}])
        self.assertIsNone(result)

    def test_one_metric_scale_is_kept(self):
        result = detect_scale(None, [{"text": "100mm = 1m"}])
        self.assertEqual(result["mm_per_m"], 100.0)

    def test_equivalent_metric_writings_stay_one_scale(self):
        result = detect_scale(None, [{"text": "100mm = 1m"}, {"text": "200mm = 2m"}])
        self.assertEqual(result["mm_per_m"], 100.0)

    def test_metric_scale_is_millimetres_per_metre(self):
        result = detect_scale(None, [{"text": "200mm = 2m"}])
        self.assertEqual(result["mm_per_m"], 100.0)

    def test_two_metric_scales_abstain(self):
        result = detect_scale(None, [{"text": "100mm = 1m"}, {"text": "50mm = 1m"}])
        self.assertIsNone(result)


def _dimension_word(text: str) -> dict:
    return {"text": text, "x0": 0, "y0": 0, "x1": 20, "y1": 8}


class TestPrintedScaleIsNotALength(unittest.TestCase):
    def test_scale_token_stays_a_scale(self):
        found = detect_dimensions(None, [_dimension_word("1:100")])
        self.assertEqual([(item["value"], item["unit"]) for item in found], [(100.0, "scale")])

    def test_bare_length_stays_millimetres(self):
        found = detect_dimensions(None, [_dimension_word("3600")])
        self.assertEqual([(item["value"], item["unit"]) for item in found], [(3600.0, "mm")])

    def test_explicit_millimetres_and_metres(self):
        millimetres = detect_dimensions(None, [_dimension_word("1200mm")])
        metres = detect_dimensions(None, [_dimension_word("3.5m")])
        self.assertEqual(millimetres[0]["value"], 1200.0)
        self.assertEqual(metres[0]["value"], 3500.0)


class TestStoreyNumberIsNotAFloorPlan(unittest.TestCase):
    def _page_type(self, text: str) -> str:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=12)
        try:
            page_type, label, _metadata = classify_page_offline(page, text, "ignored.pdf", 1)
        finally:
            doc.close()
        self.assertEqual(label, "Page 1")
        return page_type

    def test_bare_storey_is_not_a_floor_plan(self):
        self.assertEqual(self._page_type("LEVEL 1"), "Other")
        self.assertEqual(self._page_type("LEVEL 2"), "Other")
        self.assertEqual(self._page_type("LEVEL 10"), "Other")

    def test_named_plan_and_ceiling_plan_keep_their_types(self):
        self.assertEqual(self._page_type("LEVEL 1 PLAN"), "Floor Plan")
        self.assertEqual(self._page_type("GROUND FLOOR PLAN"), "Floor Plan")
        self.assertEqual(self._page_type("REFLECTED CEILING PLAN LEVEL 1"), "Reflected Ceiling Plan")


class TestDimensionValueM(unittest.TestCase):
    """Test dimension parsing from text to metres."""

    def test_millimetres(self):
        self.assertAlmostEqual(dimension_value_m("3600mm"), 3.6)
        self.assertAlmostEqual(dimension_value_m("1200mm"), 1.2)
        self.assertAlmostEqual(dimension_value_m("2400mm"), 2.4)

    def test_metres(self):
        self.assertAlmostEqual(dimension_value_m("3.6m"), 3.6)
        self.assertAlmostEqual(dimension_value_m("1.2m"), 1.2)
        self.assertAlmostEqual(dimension_value_m("0.6m"), 0.6)

    def test_bare_numbers_as_mm(self):
        self.assertAlmostEqual(dimension_value_m("3600"), 3.6)
        self.assertAlmostEqual(dimension_value_m("1200"), 1.2)
        self.assertAlmostEqual(dimension_value_m("2400"), 2.4)

    def test_small_bare_numbers_rejected(self):
        self.assertIsNone(dimension_value_m("5"))
        self.assertIsNone(dimension_value_m("50"))
        self.assertIsNone(dimension_value_m("99"))

    def test_out_of_range(self):
        self.assertIsNone(dimension_value_m("250000mm"))  # 250m - too big
        self.assertIsNone(dimension_value_m("0.01m"))     # too small

    def test_whitespace_handling(self):
        self.assertAlmostEqual(dimension_value_m("3 600mm"), 3.6)
        self.assertAlmostEqual(dimension_value_m(" 1200 mm "), 1.2)

    def test_empty_or_none(self):
        self.assertIsNone(dimension_value_m(""))
        self.assertIsNone(dimension_value_m(None))
        self.assertIsNone(dimension_value_m("no dimensions here"))


class TestExtractScaleRatio(unittest.TestCase):
    """Test scale ratio extraction."""

    def test_standard_scales(self):
        self.assertEqual(extract_scale_ratio("1:100"), 100)
        self.assertEqual(extract_scale_ratio("1:50"), 50)
        self.assertEqual(extract_scale_ratio("1:200"), 200)
        self.assertEqual(extract_scale_ratio("1:500"), 500)
        self.assertEqual(extract_scale_ratio("1:1000"), 1000)

    def test_scale_in_context(self):
        self.assertEqual(extract_scale_ratio("Scale: 1:100"), 100)
        self.assertEqual(extract_scale_ratio("Drawing at 1:200 scale"), 200)

    def test_no_scale(self):
        self.assertIsNone(extract_scale_ratio("No scale here"))
        self.assertIsNone(extract_scale_ratio(""))
        self.assertIsNone(extract_scale_ratio(None))

    def test_case_insensitive(self):
        self.assertEqual(extract_scale_ratio("1:100"), 100)


class TestClassifyPage(unittest.TestCase):
    """Test page classification."""

    def test_floor_plan(self):
        self.assertEqual(classify_page("Ground Floor Plan"), "Floor Plan")
        self.assertEqual(classify_page("First Floor Plan Layout"), "Floor Plan")
        self.assertEqual(classify_page("Site Plan and Landscape"), "Floor Plan")

    def test_elevation(self):
        self.assertEqual(classify_page("North Elevation"), "Elevation")
        self.assertEqual(classify_page("External Elevation - Front"), "Elevation")
        self.assertEqual(classify_page("East Facade"), "Elevation")

    def test_section(self):
        self.assertEqual(classify_page("Section A-A"), "Section")
        self.assertEqual(classify_page("Building Cross Section"), "Section")
        self.assertEqual(classify_page("Wall Section Detail"), "Section")

    def test_schedule(self):
        self.assertEqual(classify_page("Door Schedule"), "Schedule")
        self.assertEqual(classify_page("Window Schedule and Details"), "Schedule")
        self.assertEqual(classify_page("Finishing Schedule"), "Schedule")

    def test_title_page(self):
        self.assertEqual(classify_page("Drawing Register"), "Title / Drawing Register")
        self.assertEqual(classify_page("Project Information and Title"), "Title / Drawing Register")

    def test_other(self):
        self.assertEqual(classify_page("Random notes about construction"), "Other")
        self.assertEqual(classify_page(""), "Other")

    def test_equal_floor_and_elevation_headings_abstain(self):
        self.assertEqual(classify_page("FLOOR PLAN\nELEVATION"), "Other")
        self.assertEqual(classify_page("FLOOR PLAN\nNORTH ELEVATION"), "Other")

    def test_section_inside_another_word_is_not_a_section(self):
        self.assertEqual(classify_page("INTERSECTION DETAIL"), "Other")

    def test_bare_title_is_not_a_sheet_type(self):
        self.assertEqual(classify_page("TITLE"), "Other")
        self.assertEqual(classify_page("FLOOR PLAN\nTITLE"), "Floor Plan")
        self.assertEqual(classify_page("TITLE SHEET"), "Title / Drawing Register")
        self.assertEqual(classify_page("DRAWING INDEX"), "Title / Drawing Register")

    def test_reference_line_does_not_vote(self):
        self.assertEqual(classify_page("REFER FLOOR PLAN"), "Other")
        self.assertEqual(
            classify_page("FLOOR PLAN\nREFER TO NORTH ELEVATION"),
            "Floor Plan",
        )

    def test_reflected_ceiling_plan_is_not_a_floor_plan(self):
        self.assertEqual(classify_page("REFLECTED CEILING PLAN"), "Reflected Ceiling Plan")

    def test_keyword_order_does_not_change_a_unique_type(self):
        self.assertEqual(
            classify_page("ELEVATION\nNORTH ELEVATION"),
            classify_page("NORTH ELEVATION\nELEVATION"),
        )
        self.assertEqual(classify_page("NORTH ELEVATION"), "Elevation")


class TestDetectScaleFromText(unittest.TestCase):
    """Test scale detection with confidence."""

    def test_common_scale(self):
        result = detect_scale_from_text("Scale 1:100")
        self.assertIsNotNone(result)
        self.assertEqual(result["ratio"], 100)
        self.assertEqual(result["confidence"], "high")

    def test_uncommon_scale(self):
        result = detect_scale_from_text("Scale 1:75")
        self.assertIsNotNone(result)
        self.assertEqual(result["ratio"], 75)
        self.assertEqual(result["confidence"], "medium")

    def test_no_scale(self):
        self.assertIsNone(detect_scale_from_text("No scale here"))


class TestDetectDrawingNumber(unittest.TestCase):
    """Test drawing number extraction."""

    def test_standard_format(self):
        self.assertEqual(detect_drawing_number("Drawing A01"), "A01")
        self.assertEqual(detect_drawing_number("See DWG-A02-01"), "A02-01")
        self.assertEqual(detect_drawing_number("Ref: FP01"), "FP01")

    def test_no_drawing_number(self):
        self.assertIsNone(detect_drawing_number("No drawing number here"))
        self.assertIsNone(detect_drawing_number(""))


class TestScaleRegex(unittest.TestCase):
    """Test the shared scale regex pattern."""

    def test_matches(self):
        self.assertIsNotNone(SCALE_RE.search("1:100"))
        self.assertIsNotNone(SCALE_RE.search("1 : 200"))
        self.assertIsNotNone(SCALE_RE.search("Scale 1:50"))

    def test_no_match(self):
        self.assertIsNone(SCALE_RE.search("12345"))
        self.assertIsNone(SCALE_RE.search("no scale"))


if __name__ == "__main__":
    unittest.main()
