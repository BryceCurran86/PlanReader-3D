"""Adversarial source-scope controls for shared 3Laurel wall-face gate.

Synthetic geometry is never a signed source, but unowned annotation strokes
must not become physical wall faces inside a customer finish issuer.
"""
from __future__ import annotations
import fitz
from pb_three_laurel_wall_face_enclosure_prerequisite import (
    is_room_enclosed_by_physical_wall_faces,
)


class FakeSourcePage:
    def __init__(self, *, wall_layer: str, viewports: tuple[str, ...] | None = None):
        self._words = [(290., 295., 330., 305., "MEDIA", 0, 0, 0)]
        path = [
            ((260,270),(360,270)),
            ((260,340),(360,340)),
            ((260,270),(260,340)),
            ((360,270),(360,340)),
        ]
        self._drawings = []
        for i,(a,b) in enumerate(path):
            drawing={
                "layer":wall_layer,
                "width":0.5,
                "rect":fitz.Rect(*a,*b),
                "items":[("l",fitz.Point(*a),fitz.Point(*b))],
                "fill":None,
            }
            if viewports:
                drawing["source_viewport_id"]=viewports[i]
            self._drawings.append(drawing)
        self._drawings.append({
            # A disconnected dot from a different native family must NOT
            # authenticate an annotation rectangle as a physical room.
            "layer":"Interior_PlumbingFixture",
            "rect":fitz.Rect(335,330,340,335),
            "items":(),
            "width":0.8,
            "fill":(0.,0.,0.),
        })

    def get_text(self, mode):
        assert mode == "words"
        return self._words

    def get_drawings(self):
        return self._drawings


def test_closed_annotation_box_plus_unrelated_cad_fill_cannot_issue_room():
    page=FakeSourcePage(wall_layer="Annotation_Dimensions")
    assert is_room_enclosed_by_physical_wall_faces(page,"MEDIA") is False


def test_native_wall_layer_four_sided_candidate_is_not_annotation():
    page=FakeSourcePage(wall_layer="Enclosure_WallInternal")
    # This is an intermediate geometric gate only, not customer/source seal.
    assert is_room_enclosed_by_physical_wall_faces(page,"MEDIA") is True


def test_foreign_source_viewport_wall_sides_cannot_form_one_room():
    page=FakeSourcePage(
        wall_layer="Enclosure_WallInternal",
        viewports=("GROUND_FLOOR", "UPPER_FLOOR","GROUND_FLOOR","GROUND_FLOOR"),
    )
    assert is_room_enclosed_by_physical_wall_faces(page,"MEDIA") is False


def test_unassigned_layer_annotated_box_cannot_be_physical_wall():
    page=FakeSourcePage(wall_layer="")
    assert is_room_enclosed_by_physical_wall_faces(page,"MEDIA") is False
