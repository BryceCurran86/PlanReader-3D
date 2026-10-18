"""A reconstructed room does not become Level 1."""
import json
import sqlite3

from pb_wall_topology_v174 import derive_wall_topology


def test_room_storey_stays_unspecified_when_the_sheet_names_none() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE pages (id INTEGER PRIMARY KEY, workspace_id INTEGER, page_label TEXT, px_per_m REAL);
        CREATE TABLE measurement_lines (
            id INTEGER PRIMARY KEY, workspace_id INTEGER, page_id INTEGER,
            line_type TEXT, length_m REAL, area_m2 REAL, raw_points TEXT
        );
        """
    )
    conn.execute("INSERT INTO pages VALUES (10, 1, 'A-101', 100.0)")
    pts = json.dumps([(0, 0), (1000, 0), (1000, 500), (0, 500)])
    conn.execute(
        "INSERT INTO measurement_lines VALUES (100, 1, 10, 'polygon', 30.0, 50.0, ?)",
        (pts,),
    )
    registry = derive_wall_topology(conn, 1, default_wall_height=2.7)
    assert registry.rooms[0].storey_level == "Unspecified"
    assert registry.rooms[0].wall_surface_area_m2 == 81.0
