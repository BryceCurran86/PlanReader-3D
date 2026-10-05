from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

import pb_material_schedule_v1222 as mat
import pb_selected_evidence_floor_v1226 as selected


class _App:
    def __init__(self, pages):
        self.pages = pages

    def lquery(self, sql, params=()):
        if "FROM pages" in sql:
            return [dict(row) for row in self.pages]
        return []


class MaterialScheduleV1222Tests(unittest.TestCase):
    def test_schedule_code_resolves_substrate(self):
        rows = mat.parse_schedule_text(
            "FINISH SCHEDULE\nEC1 - James Hardie Linea 180mm cladding\nEC2 - Textureboard cladding\nPT1 - Dulux Natural White low sheen",
            9,
            "A900",
        )
        by_code = {row["code"]: row for row in rows}
        self.assertEqual(by_code["EC1"]["substrate"], "Lineaboard Cladding")
        self.assertEqual(by_code["EC2"]["substrate"], "Textureboard Cladding")
        self.assertIn("Dulux Natural White", by_code["PT1"]["finish"])

    def test_schedule_can_define_generic_letter_number_material_codes(self):
        rows = mat.parse_schedule_text(
            "FINISH SCHEDULE\nWT1 - Porcelain wall tile\nWM1 - Liquid waterproofing membrane",
            9,
            "A900",
        )
        by_code = {row["code"]: row for row in rows}
        self.assertIn("WT1", by_code)
        self.assertIn("WM1", by_code)
        self.assertEqual(
            mat.semantic_finish_from_schedule_entry(
                {
                    **by_code["WT1"],
                    "status": "Confirmed",
                }
            ),
            "tile",
        )
        self.assertEqual(
            mat.semantic_finish_from_schedule_entry(
                {
                    **by_code["WM1"],
                    "status": "Confirmed",
                }
            ),
            "membrane",
        )

    def test_wrapped_schedule_definition_preserves_every_contributing_source_line(self):
        rows = mat.parse_schedule_text(
            "FINISH SCHEDULE\nWT1\nPorcelain wall tile\nPT1 Dulux low sheen paint",
            9,
            "A900",
        )
        by_code = {row["code"]: row for row in rows}
        self.assertEqual(
            by_code["WT1"]["source_lines"],
            ("WT1", "Porcelain wall tile"),
        )
        self.assertEqual(by_code["WT1"]["description"], "Porcelain wall tile")

    def test_generic_schedule_code_must_lead_its_definition_row(self):
        rows = mat.parse_schedule_text(
            "FINISH SCHEDULE\nRefer drawing A110 for tile details",
            9,
            "A900",
        )
        self.assertFalse(any(row["code"] == "A110" for row in rows))

    def test_explicit_finish_semantic_beats_substrate_semantic(self):
        self.assertEqual(
            mat.semantic_finish_from_schedule_entry(
                {
                    "code": "FC1",
                    "status": "Confirmed",
                    "description": "Fibre cement cladding Dulux low sheen paint",
                    "substrate": "Fibre Cement Cladding",
                    "finish": "Dulux low sheen paint",
                }
            ),
            "paint",
        )

    def test_resolved_substrates_support_schedule_defined_generic_codes(self):
        resolver = {
            "WT1": {
                "status": "Confirmed",
                "substrate": "Ceramic tile",
            }
        }
        token = mat._resolver_context.set(resolver)
        try:
            rows = mat.resolved_substrates_from_text(
                lambda _text: [],
                "Wall finish WT1",
            )
        finally:
            mat._resolver_context.reset(token)
        self.assertEqual(rows, [{"code": "WT1", "name": "Ceramic tile"}])

    def test_defined_generic_code_is_found_on_drawing_without_global_code_expansion(self):
        original = mat.auto._pdf_word_lines
        try:
            mat.auto._pdf_word_lines = lambda _app, _page: [
                {
                    "text": "Wall finish WT1",
                    "bbox": [10, 20, 60, 35],
                    "center": [35, 27],
                }
            ]
            page = {
                "id": 3,
                "page_label": "A301",
                "page_type": "Elevation",
                "extracted_text": "Wall finish WT1",
            }
            rows = mat._page_occurrences(
                object(),
                page,
                {
                    "WT1": {
                        "status": "Confirmed",
                        "substrate": "",
                        "finish": "",
                        "semantic_finish": "tile",
                        "description": "Porcelain wall tile",
                    }
                },
            )
        finally:
            mat.auto._pdf_word_lines = original
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["code"], "WT1")
        self.assertEqual(rows[0]["semantic_finish"], "tile")

    def test_authenticated_ip_schedule_normalizes_to_insulated_panel_semantic(self):
        app = _App([
            {
                "id": 9,
                "page_label": "A900",
                "page_type": "Finishes Schedule",
                "extracted_text": "FINISH SCHEDULE\nIP - 75mm Insulated Panel",
                "image_path": "",
                "document_id": 1,
                "page_no": 1,
                "render_zoom": 1,
            }
        ])
        state = mat.build_material_dictionary(app, 4)
        entry = state["dictionary"]["IP"]
        self.assertEqual(entry["status"], "Confirmed")
        self.assertEqual(entry["semantic_finish"], "insulated_panel")

    def test_selected_sheet_rebuild_preserves_authenticated_ip_semantic(self):
        entry = selected._rebuild_dictionary_item(
            "IP",
            [
                {
                    "code": "IP",
                    "description": "75mm Insulated Panel",
                    "substrate": "Insulated Panel",
                    "finish": "",
                    "page_id": 9,
                    "page_label": "A900",
                }
            ],
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry["status"], "Confirmed")
        self.assertEqual(entry["semantic_finish"], "insulated_panel")

    def test_bare_ip_has_no_finish_semantic_without_confirmed_schedule_meaning(self):
        self.assertEqual(
            mat.semantic_finish_from_schedule_entry(
                {"code": "IP", "status": "Confirmed", "description": "IP"}
            ),
            "",
        )

    def test_confirmed_schedule_normalizes_supported_trade_semantics(self):
        cases = [
            ("PT1", "Dulux low sheen paint system", "paint"),
            ("WT1", "Porcelain wall tile", "tile"),
            ("PB1", "13mm plasterboard lining", "plasterboard"),
            ("FC1", "Fibre cement sheet cladding", "fibre_cement"),
            ("RS1", "Colorbond metal roofing", "roofing"),
            ("WM1", "Liquid waterproofing membrane", "membrane"),
        ]
        for code, description, expected in cases:
            with self.subTest(code=code):
                self.assertEqual(
                    mat.semantic_finish_from_schedule_entry(
                        {
                            "code": code,
                            "status": "Confirmed",
                            "description": description,
                        }
                    ),
                    expected,
                )

    def test_trade_semantic_requires_confirmed_schedule_authority(self):
        for status in ("Conflict", "Unknown", "Abstained", ""):
            with self.subTest(status=status):
                self.assertEqual(
                    mat.semantic_finish_from_schedule_entry(
                        {
                            "code": "PT1",
                            "status": status,
                            "description": "Dulux low sheen paint system",
                        }
                    ),
                    "",
                )

    def test_conflicting_schedule_definition_is_not_silently_confirmed(self):
        app = _App([
            {"id": 1, "page_label": "A900", "page_type": "Finishes Schedule", "extracted_text": "EC1 Linea cladding", "image_path": "", "document_id": 1, "page_no": 1, "render_zoom": 1},
            {"id": 2, "page_label": "A901", "page_type": "Finishes Schedule", "extracted_text": "EC1 Rendered blockwork", "image_path": "", "document_id": 1, "page_no": 2, "render_zoom": 1},
        ])
        state = mat.build_material_dictionary(app, 4)
        self.assertEqual(state["dictionary"]["EC1"]["status"], "Conflict")
        self.assertTrue(any(issue["category"] == "Schedule conflict" for issue in state["issues"]))

    def test_resolved_code_replaces_raw_code_for_geometry(self):
        resolver = {"EC1": {"status": "Confirmed", "substrate": "Lineaboard Cladding"}}
        token = mat._resolver_context.set(resolver)
        try:
            rows = mat.resolved_substrates_from_text(lambda _text: [{"code": "EC1", "name": "EC1"}], "South elevation EC1")
        finally:
            mat._resolver_context.reset(token)
        self.assertEqual(rows, [{"code": "EC1", "name": "Lineaboard Cladding"}])

    def test_unknown_code_occurrence_becomes_review_issue(self):
        original = mat.auto._pdf_word_lines
        try:
            mat.auto._pdf_word_lines = lambda _app, _page: [{"text": "EC9", "bbox": [10, 20, 40, 35], "center": [25, 27]}]
            page = {"id": 3, "page_label": "A301", "page_type": "Elevation", "extracted_text": "EC9"}
            rows = mat._page_occurrences(object(), page, {})
        finally:
            mat.auto._pdf_word_lines = original
        self.assertEqual(rows[0]["status"], "Unknown")
        self.assertEqual(rows[0]["bbox"], [10, 20, 40, 35])

    def test_issue_preview_draws_marker_without_full_resolution_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sheet.png"
            Image.new("RGB", (2400, 1600), "white").save(path)
            payload = mat.issue_preview_bytes(
                {"image_path": str(path)},
                {"category": "Unknown material code", "bbox": [200, 300, 700, 600], "bbox_mode": "xyxy"},
            )
            self.assertTrue(payload)
            from io import BytesIO
            with Image.open(BytesIO(payload)) as image:
                self.assertLessEqual(max(image.size), 1200)


if __name__ == "__main__":
    unittest.main()
