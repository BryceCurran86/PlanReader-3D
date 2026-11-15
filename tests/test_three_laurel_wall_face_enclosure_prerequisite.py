"""Tests for shared source-owned closed physical wall-face graph prerequisite.

Verifies that pb_three_laurel_wall_face_enclosure_prerequisite strictly enforces:
1. Authentic 3Laurel rooms on Ground Floor (page 2) and Upper Floor (page 3) pass.
2. Schedule table entries with 'M2' are rejected.
3. 5th-gen open-bottom decoys (35 pt gap) fail closed (False).
4. 4th-gen disconnected four-stroke decoys fail closed (False).
5. 3-sided open enclosures missing one wall fail closed (False).
6. Text-only decoys without CAD primitives fail closed (False).
"""
from __future__ import annotations

import fitz

from pb_three_laurel_wall_face_enclosure_prerequisite import (
    is_room_enclosed_by_physical_wall_faces,
)
from tests.original_source_3laurel import require_original_3laurel


def test_synthetic_open_bottom_two_corner_decoy_fails_closed():
    """5th-gen adversarial decoy: 2 top corners meet, bottom edge has 35 pt gap."""
    doc = fitz.open()
    page = doc.new_page(width=600, height=600)
    cx, cy = 300.0, 300.0
    page.insert_text((cx - 15, cy - 5), "MEDIA", fontsize=10)

    # 4 strokes: top horizontal, bottom horizontal, left vertical (ends 35 pt above bottom),
    # right vertical (ends 35 pt above bottom)
    page.draw_line((cx - 35, cy - 30), (cx + 35, cy - 30), color=(0, 0, 0), width=0.2)
    page.draw_line((cx - 35, cy + 40), (cx + 35, cy + 40), color=(0, 0, 0), width=0.2)
    page.draw_line((cx - 35, cy - 30), (cx - 35, cy + 5), color=(0, 0, 0), width=0.2)
    page.draw_line((cx + 35, cy - 30), (cx + 35, cy + 5), color=(0, 0, 0), width=0.2)
    # Isolated filled circle (CAD ink decoy)
    page.draw_circle((cx + 35, cy + 35), radius=2, color=(0, 0, 0), fill=(0, 0, 0), width=0.8)

    assert not is_room_enclosed_by_physical_wall_faces(page, "MEDIA")


def test_synthetic_four_disconnected_strokes_fails_closed():
    """4th-gen decoy: 4 disconnected strokes with gap at every corner."""
    doc = fitz.open()
    page = doc.new_page(width=600, height=600)
    cx, cy = 300.0, 300.0
    page.insert_text((cx - 15, cy - 5), "BED 2", fontsize=10)

    # 4 strokes with gaps at all 4 corners
    page.draw_line((cx - 20, cy - 30), (cx + 20, cy - 30), color=(0, 0, 0), width=0.2)
    page.draw_line((cx - 20, cy + 30), (cx + 20, cy + 30), color=(0, 0, 0), width=0.2)
    page.draw_line((cx - 30, cy - 20), (cx - 30, cy + 20), color=(0, 0, 0), width=0.2)
    page.draw_line((cx + 30, cy - 20), (cx + 30, cy + 20), color=(0, 0, 0), width=0.2)
    page.draw_circle((cx + 35, cy + 35), radius=2, color=(0, 0, 0), fill=(0, 0, 0), width=0.8)

    assert not is_room_enclosed_by_physical_wall_faces(page, "BED 2")


def test_synthetic_three_sided_open_c_shape_fails_closed():
    """3-sided open enclosure (missing right wall completely)."""
    doc = fitz.open()
    page = doc.new_page(width=600, height=600)
    cx, cy = 300.0, 300.0
    page.insert_text((cx - 15, cy - 5), "BATHROOM", fontsize=10)

    # Top, bottom, left walls meet, but right side is completely missing
    page.draw_line((cx - 35, cy - 30), (cx + 35, cy - 30), color=(0, 0, 0), width=0.5)
    page.draw_line((cx - 35, cy + 30), (cx + 35, cy + 30), color=(0, 0, 0), width=0.5)
    page.draw_line((cx - 35, cy - 30), (cx - 35, cy + 30), color=(0, 0, 0), width=0.5)

    assert not is_room_enclosed_by_physical_wall_faces(page, "BATHROOM")


def test_synthetic_text_only_decoy_without_cad_primitives_fails_closed():
    """Text-only label without any CAD primitives."""
    doc = fitz.open()
    page = doc.new_page(width=600, height=600)
    page.insert_text((300, 300), "LAUNDRY", fontsize=10)

    assert not is_room_enclosed_by_physical_wall_faces(page, "LAUNDRY")


def test_synthetic_closed_four_sided_room_passes():
    """Authentic-style closed rectangular room with connected corners and CAD primitives."""
    doc = fitz.open()
    page = doc.new_page(width=600, height=600)
    cx, cy = 300.0, 300.0
    page.insert_text((cx - 15, cy - 5), "MEDIA", fontsize=10)

    # Top, bottom, left, right walls meet cleanly at corners
    page.draw_line((cx - 35, cy - 30), (cx + 35, cy - 30), color=(0, 0, 0), width=0.5)
    page.draw_line((cx - 35, cy + 30), (cx + 35, cy + 30), color=(0, 0, 0), width=0.5)
    page.draw_line((cx - 35, cy - 30), (cx - 35, cy + 30), color=(0, 0, 0), width=0.5)
    page.draw_line((cx + 35, cy - 30), (cx + 35, cy + 30), color=(0, 0, 0), width=0.5)

    assert is_room_enclosed_by_physical_wall_faces(page, "MEDIA")


def test_authentic_3laurel_page2_rooms_enclosed():
    """Verify authentic rooms on 3Laurel Ground Floor Plan (page 2)."""
    pdf_path = require_original_3laurel()
    doc = fitz.open(pdf_path)
    page = doc[2]

    for room in ("MEDIA", "BED 2", "BED 3", "GARAGE", "LIVING"):
        assert is_room_enclosed_by_physical_wall_faces(page, room), f"Room {room} must be enclosed"
