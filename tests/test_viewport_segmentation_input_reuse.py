from __future__ import annotations

from dataclasses import asdict

import pb_viewport_segmentation as module


class _Rect:
    def __init__(self, x0: float, y0: float, x1: float, y1: float) -> None:
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1
        self.width = x1 - x0
        self.height = y1 - y0


class _Page:
    def __init__(self) -> None:
        self.rect = _Rect(0.0, 0.0, 500.0, 500.0)
        self.text_calls: dict[str, int] = {}
        self.drawings_calls = 0

    def get_text(self, mode: str):
        self.text_calls[mode] = self.text_calls.get(mode, 0) + 1
        if mode == "words":
            return [(100.0, 420.0, 150.0, 432.0)]
        if mode == "dict":
            return {
                "blocks": [
                    {
                        "type": 0,
                        "lines": [
                            {
                                "bbox": (140.0, 420.0, 330.0, 434.0),
                                "spans": [
                                    {
                                        "text": "GROUND FLOOR PLAN SCALE 1:100",
                                        "bbox": (140.0, 420.0, 330.0, 434.0),
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        if mode == "blocks":
            return []
        raise AssertionError(f"unexpected get_text mode: {mode}")

    def get_drawings(self):
        self.drawings_calls += 1
        return [
            {
                "items": [
                    ("re", _Rect(50.0, 50.0, 450.0, 450.0)),
                ]
            }
        ]


def _public_rows(viewports):
    return [
        {
            "view_id": item.view_id,
            "page_number": item.page_number,
            "view_type": item.view_type,
            "label": item.label,
            "title_bbox": item.title_bbox,
            "bounding_box": item.bounding_box,
            "status": item.status,
            "boundary_source": item.boundary_source,
            "confidence": item.confidence,
            "scale_raw": item.scale_raw,
            "scale_denominator": item.scale_denominator,
            "scale_conflict": item.scale_conflict,
            "notes": list(item.notes),
            "provenance": dict(item.provenance),
        }
        for item in viewports
    ]


def test_segment_page_viewports_reads_expensive_page_inputs_once():
    page = _Page()

    result = module.segment_page_viewports(page, page_number=1)

    assert len(result) == 1
    assert result[0].status == module.ViewportSegmentationStatus.RESOLVED.value
    assert result[0].scale_denominator == 100.0
    assert page.drawings_calls == 1
    assert page.text_calls.get("dict", 0) == 1
    assert page.text_calls.get("words", 0) == 1
    assert page.text_calls.get("blocks", 0) == 0


def test_cached_page_inputs_preserve_legacy_helper_results():
    cached_page = _Page()
    cached = module.segment_page_viewports(cached_page, page_number=1)

    legacy_page = _Page()
    calibration = module.calibrate_viewport_layout(legacy_page)
    anchors = module.extract_view_title_anchors(legacy_page)
    frames = module.extract_vector_frames(legacy_page, calibration)
    framed, consumed = module._frame_resolved_viewports(
        legacy_page,
        anchors,
        frames,
        calibration,
        page_number=1,
    )
    unresolved = [i for i in range(len(anchors)) if i not in consumed]
    derived = (
        module._derived_partitions(
            legacy_page,
            anchors,
            unresolved,
            calibration,
            page_number=1,
        )
        if unresolved
        else []
    )
    legacy = sorted(
        framed + derived,
        key=lambda viewport: (
            viewport.title_bbox[1],
            viewport.title_bbox[0],
            viewport.view_id,
        ),
    )

    assert _public_rows(cached) == _public_rows(legacy)
