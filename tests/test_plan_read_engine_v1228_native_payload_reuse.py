from __future__ import annotations

from collections import Counter
from types import SimpleNamespace

import pb_page_title_authority as title_authority
import pb_plan_read_engine_v1228 as reading


_TEXT_PAYLOAD = {
    "blocks": [
        {
            "type": 0,
            "lines": [
                {
                    "dir": (1.0, 0.0),
                    "spans": [
                        {
                            "text": "DRAWING TITLE",
                            "bbox": (70.0, 75.0, 125.0, 84.0),
                            "size": 8.0,
                            "font": "Arial",
                            "flags": 0,
                        },
                        {
                            "text": "GROUND FLOOR PLAN",
                            "bbox": (130.0, 75.0, 195.0, 84.0),
                            "size": 8.0,
                            "font": "Arial",
                            "flags": 0,
                        },
                    ],
                },
                {
                    "dir": (1.0, 0.0),
                    "spans": [
                        {
                            "text": "SCALE 1:100",
                            "bbox": (145.0, 90.0, 195.0, 99.0),
                            "size": 7.0,
                            "font": "Arial",
                            "flags": 0,
                        }
                    ],
                },
            ],
        }
    ]
}

_WORD_PAYLOAD = [
    (70.0, 75.0, 105.0, 84.0, "DRAWING"),
    (108.0, 75.0, 125.0, 84.0, "TITLE"),
    (130.0, 75.0, 155.0, 84.0, "GROUND"),
    (158.0, 75.0, 175.0, 84.0, "FLOOR"),
    (178.0, 75.0, 195.0, 84.0, "PLAN"),
    (145.0, 90.0, 165.0, 99.0, "SCALE"),
    (168.0, 90.0, 195.0, 99.0, "1:100"),
]


class _Page:
    def __init__(self) -> None:
        self.calls = Counter()
        self.rect = SimpleNamespace(width=200.0, height=100.0)
        self.rotation = 0

    def get_text(self, mode):
        self.calls[mode] += 1
        if mode == "dict":
            return _TEXT_PAYLOAD
        if mode == "words":
            return list(_WORD_PAYLOAD)
        raise AssertionError(mode)


def test_shared_payload_reconstruction_matches_legacy_path() -> None:
    page = _Page()
    source_page = {
        "page_type": "Floor Plan",
        "page_label": "A-101",
    }

    legacy = reading.reconstruct_page_text(page, source_page)

    text_payload, word_payload = reading._native_text_payloads(page)
    shared = reading.reconstruct_page_text(
        page,
        source_page,
        text_payload=text_payload,
        word_payload=word_payload,
    )

    assert shared == legacy


def test_shared_payload_reuses_one_dict_and_one_words_read() -> None:
    page = _Page()
    source_page = {
        "page_type": "Floor Plan",
        "page_label": "A-101",
    }

    text_payload, word_payload = reading._native_text_payloads(page)
    native = reading.reconstruct_page_text(
        page,
        source_page,
        text_payload=text_payload,
        word_payload=word_payload,
    )
    spatial = reading.spatial_title_block_evidence(
        page,
        lambda _page: {},
        span_lines=native["span_lines"],
    )
    title_spans = title_authority.spans_from_text_dict(text_payload, page)
    analysis = title_authority.analyse_page(
        page,
        1,
        spans=title_spans,
        allow_ocr=False,
    )

    assert page.calls == Counter({"dict": 1, "words": 1})
    assert native["text"]
    assert spatial["spatial_title_lines"]
    assert analysis.page_no == 1


def test_precomputed_span_lines_preserve_spatial_title_result() -> None:
    page = _Page()

    legacy = reading.spatial_title_block_evidence(page, lambda _page: {})
    text_payload, _word_payload = reading._native_text_payloads(page)
    span_lines = reading._span_lines(page, text_payload)
    shared = reading.spatial_title_block_evidence(
        page,
        lambda _page: {},
        span_lines=span_lines,
    )

    assert shared == legacy
