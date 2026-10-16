"""tests/test_workstream_a3_sheet_classification.py — Workstream A3 Regression Suite.

Issue #79: Multi-page plan classification & sheet role detection.
"""
from __future__ import annotations

import sqlite3
import unittest

from pb_sheet_classification_v172 import (
    SheetClassificationRecord,
    SheetClassificationRegistry,
    classify_sheet_role,
    extract_storey_level,
    derive_sheet_classifications,
)


def _create_mock_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE workspaces (
            id INTEGER PRIMARY KEY,
            job_no TEXT,
            job_name TEXT
        );

        CREATE TABLE pages (
            id INTEGER PRIMARY KEY,
            workspace_id INTEGER,
            page_label TEXT,
            page_type TEXT
        );
        """
    )
    conn.commit()
    return conn


class WorkstreamA3ClassificationTests(unittest.TestCase):

    def setUp(self):
        self.conn = _create_mock_db()
        cur = self.conn.cursor()
        cur.execute("INSERT INTO workspaces VALUES (1, 'JOB-A3', 'Classification Test')")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_01_sheet_role_classification(self):
        """Classifies canonical construction sheet roles accurately."""
        r_plan, conf1, _, t1 = classify_sheet_role("A-101 Ground Floor Plan")
        r_rcp, conf2, _, t2 = classify_sheet_role("A-201 Reflected Ceiling Plan Level 1")
        r_door, conf3, _, t3 = classify_sheet_role("A-601 Door & Window Schedule")
        r_elev, conf4, _, t4 = classify_sheet_role("A-301 North & South Elevations")

        self.assertEqual(r_plan, "FLOOR_PLAN")
        self.assertEqual(t1, "WALL_FLOOR")

        self.assertEqual(r_rcp, "REFLECTED_CEILING_PLAN")
        self.assertEqual(t2, "CEILING")

        self.assertEqual(r_door, "DOOR_WINDOW_SCHEDULE")
        self.assertEqual(t3, "OPENINGS")

        self.assertEqual(r_elev, "ELEVATION")
        self.assertEqual(t4, "ELEVATION_SURFACE")

    def test_04_two_sheet_roles_abstain_in_either_order(self):
        forward = classify_sheet_role("FLOOR PLAN\nNORTH ELEVATION")
        reverse = classify_sheet_role("NORTH ELEVATION\nFLOOR PLAN")
        self.assertEqual(forward[0], "OTHER_GENERAL")
        self.assertEqual(reverse[0], "OTHER_GENERAL")
        self.assertEqual(forward[1], 0.0)

    def test_05_a_reference_line_does_not_change_the_title_role(self):
        role, _confidence, _discipline, target = classify_sheet_role(
            "NORTH ELEVATION",
            "REFER FLOOR PLAN",
        )
        self.assertEqual(role, "ELEVATION")
        self.assertEqual(target, "ELEVATION_SURFACE")

    def test_06_a_word_inside_another_word_is_not_a_role(self):
        self.assertEqual(classify_sheet_role("RENDERED MASONRY")[0], "OTHER_GENERAL")
        self.assertEqual(classify_sheet_role("INTERSECTION DETAIL")[0], "OTHER_GENERAL")

    def test_07_door_elevations_stay_a_schedule(self):
        role, _confidence, _discipline, target = classify_sheet_role("DOOR ELEVATIONS")
        self.assertEqual(role, "DOOR_WINDOW_SCHEDULE")
        self.assertEqual(target, "OPENINGS")

    def test_08_a_storey_number_is_not_a_second_sheet_role(self):
        role = classify_sheet_role("A-201 Reflected Ceiling Plan Level 1")[0]
        self.assertEqual(role, "REFLECTED_CEILING_PLAN")

    def test_09_two_storeys_abstain_and_one_storey_is_kept(self):
        self.assertEqual(extract_storey_level("Level 1 and Level 2"), "Unspecified")
        self.assertEqual(extract_storey_level("Level 2 L02"), "Level 2")
        self.assertEqual(extract_storey_level("Level 10"), "Level 10")

    def test_02_storey_level_extraction(self):
        """Extracts storey and level identifiers correctly."""
        lvl1 = extract_storey_level("A-101 Ground Floor Plan")
        lvl2 = extract_storey_level("A-102 Level 1 Overall Layout")
        lvl3 = extract_storey_level("A-103 L02 Floor Plan")

        self.assertEqual(lvl1, "Ground Floor")
        self.assertEqual(lvl2, "Level 1")
        self.assertEqual(lvl3, "Level 2")

    def test_03_db_sheet_role_application(self):
        """apply_roles_to_db updates page_type in pages table."""
        cur = self.conn.cursor()
        cur.execute("INSERT INTO pages VALUES (10, 1, 'A-101 Floor Plan', 'Unclassified')")
        cur.execute("INSERT INTO pages VALUES (20, 1, 'A-201 RCP', 'Unclassified')")
        self.conn.commit()

        registry = derive_sheet_classifications(self.conn, 1)
        count = registry.apply_roles_to_db(self.conn, 1)
        self.assertEqual(count, 2)

        cur.execute("SELECT id, page_type FROM pages ORDER BY id")
        rows = dict(cur.fetchall())
        self.assertEqual(rows[10], "FLOOR_PLAN")
        self.assertEqual(rows[20], "REFLECTED_CEILING_PLAN")


if __name__ == "__main__":
    unittest.main()
