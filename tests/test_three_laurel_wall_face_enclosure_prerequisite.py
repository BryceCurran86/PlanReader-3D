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
    RoomWallFaceEnclosureWitness,
    is_room_enclosed_by_physical_wall_faces,
    witness_room_wall_face_enclosure,
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


def test_closed_annotation_rectangle_and_unrelated_fill_fails_closed(monkeypatch):
    """6th-gen named negative: closed Annotation_Dimensions rectangle + unrelated filled dot fails closed."""
    doc = fitz.open()
    page = doc.new_page(width=600, height=600)
    cx, cy = 300.0, 300.0
    page.insert_text((cx - 15, cy - 5), "MEDIA", fontsize=10)

    # 4 strokes forming a closed rectangle
    page.draw_line((cx - 35, cy - 30), (cx + 35, cy - 30), width=0.2)
    page.draw_line((cx - 35, cy + 30), (cx + 35, cy + 30), width=0.2)
    page.draw_line((cx - 35, cy - 30), (cx - 35, cy + 30), width=0.2)
    page.draw_line((cx + 35, cy - 30), (cx + 35, cy + 30), width=0.2)

    # Unrelated filled dot far away from room envelope
    page.draw_circle((cx + 100, cy + 100), 5, fill=(0, 0, 0), width=0.8)

    original_drawings = page.get_drawings()
    tagged = []
    for i, d in enumerate(original_drawings):
        d_copy = dict(d)
        if i < 4:
            d_copy["layer"] = "Annotation_Dimensions"
        tagged.append(d_copy)

    monkeypatch.setattr(page, "get_drawings", lambda: tagged)

    witness = witness_room_wall_face_enclosure(page, "MEDIA")
    assert not witness.enclosed
    assert not is_room_enclosed_by_physical_wall_faces(page, "MEDIA")


def test_overlapping_rectangle_around_area_schedule_text_fails_closed():
    """Area schedule table entries with 'M2' fail closed."""
    doc = fitz.open()
    page = doc.new_page(width=600, height=600)
    cx, cy = 300.0, 300.0
    page.insert_text((cx - 15, cy - 5), "MEDIA", fontsize=10)
    page.insert_text((cx + 25, cy - 5), "13.15 M2", fontsize=10)

    # Closed rectangle
    page.draw_line((cx - 35, cy - 30), (cx + 80, cy - 30), color=(0, 0, 0), width=0.5)
    page.draw_line((cx - 35, cy + 30), (cx + 80, cy + 30), color=(0, 0, 0), width=0.5)
    page.draw_line((cx - 35, cy - 30), (cx - 35, cy + 30), color=(0, 0, 0), width=0.5)
    page.draw_line((cx + 80, cy - 30), (cx + 80, cy + 30), color=(0, 0, 0), width=0.5)

    assert not is_room_enclosed_by_physical_wall_faces(page, "MEDIA")


def test_genuine_irregular_room_with_hosted_opening_passes(monkeypatch):
    """Genuine room with thick wall strokes and door swing arc passes."""
    doc = fitz.open()
    page = doc.new_page(width=600, height=600)
    cx, cy = 300.0, 300.0
    page.insert_text((cx - 15, cy - 5), "BED 2", fontsize=10)

    # 4 walls
    page.draw_line((cx - 40, cy - 40), (cx + 40, cy - 40), width=0.5)
    page.draw_line((cx - 40, cy + 40), (cx + 40, cy + 40), width=0.5)
    page.draw_line((cx - 40, cy - 40), (cx - 40, cy + 40), width=0.5)
    page.draw_line((cx + 40, cy - 40), (cx + 40, cy + 40), width=0.5)

    # Door swing curve inside room margin
    page.draw_curve((cx + 20, cy + 40), (cx + 35, cy + 35), (cx + 40, cy + 20), width=0.2)

    original_drawings = page.get_drawings()
    tagged = []
    for i, d in enumerate(original_drawings):
        d_copy = dict(d)
        if i < 4:
            d_copy["layer"] = "Enclosure_WallInternal"
        tagged.append(d_copy)

    monkeypatch.setattr(page, "get_drawings", lambda: tagged)

    witness = witness_room_wall_face_enclosure(page, "BED 2")
    assert witness.enclosed
    assert witness.physical_wall_authenticated
    assert witness.primitives_authenticated
    assert "Enclosure_WallInternal" in witness.wall_layers
    assert not witness.measurement_authorized
