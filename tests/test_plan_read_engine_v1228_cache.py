from __future__ import annotations

import json
from pathlib import Path

import pb_plan_read_engine_v1228 as reading


class _NoOpenFitz:
    def __init__(self) -> None:
        self.open_calls = 0

    def open(self, *args, **kwargs):
        self.open_calls += 1
        raise AssertionError("unchanged cached document must not reopen the PDF")


class _FakeApp:
    def __init__(self, *, path: Path, page: dict, cached: dict) -> None:
        self._path = path
        self._page = dict(page)
        self._cached = dict(cached)
        self.fitz = _NoOpenFitz()

    def lquery(self, sql, params=()):
        if "FROM documents" in sql:
            return [{
                "id": 1,
                "workspace_id": 7,
                "path": str(self._path),
                "file_name": self._path.name,
            }]
        if "FROM pages" in sql:
            return [dict(self._page)]
        raise AssertionError(sql)

    def workspace_setting(self, workspace_id, key, default=""):
        if key == reading._page_read_key(int(self._page["id"])):
            return json.dumps(self._cached)
        return default


def _page() -> dict:
    return {
        "id": 11,
        "document_id": 1,
        "page_no": 1,
        "page_label": "Page 1",
        "page_type": "Other",
        "selected": 1,
        "image_path": "",
        "extracted_text": "existing text",
    }


def test_native_read_signature_changes_for_reconstruction_inputs(tmp_path: Path) -> None:
    path = tmp_path / "drawing.pdf"
    path.write_bytes(b"first")
    page = _page()

    baseline = reading._native_read_signature(path, page)

    changed_type = dict(page, page_type="Floor Plan")
    assert reading._native_read_signature(path, changed_type) != baseline

    changed_label = dict(page, page_label="A-101")
    assert reading._native_read_signature(path, changed_label) != baseline

    changed_selected = dict(page, selected=0)
    assert reading._native_read_signature(path, changed_selected) != baseline

    path.write_bytes(b"first-but-now-different")
    assert reading._native_read_signature(path, page) != baseline


def test_native_read_signature_tracks_rendered_image_state(tmp_path: Path) -> None:
    path = tmp_path / "drawing.pdf"
    path.write_bytes(b"pdf")
    image = tmp_path / "page.png"
    image.write_bytes(b"image-v1")
    page = dict(_page(), image_path=str(image))

    baseline = reading._native_read_signature(path, page)
    image.write_bytes(b"image-v2-expanded")
    assert reading._native_read_signature(path, page) != baseline


def test_enhance_document_pages_skips_exact_unchanged_cached_input(
    tmp_path: Path,
) -> None:
    path = tmp_path / "drawing.pdf"
    path.write_bytes(b"not-opened-by-fast-path")
    page = _page()
    signature = reading._native_read_signature(path, page)
    app = _FakeApp(
        path=path,
        page=page,
        cached={
            "version": reading.VERSION,
            "native_signature": signature,
            "word_count": 20,
            "char_count": 120,
            "table_mode": False,
            "visual_fallback": False,
        },
    )

    result = reading.enhance_document_pages(app, 1)

    assert result == {
        "updated": 0,
        "visual": 0,
        "workspace_id": 7,
        "cached": 1,
    }
    assert app.fitz.open_calls == 0


def test_cache_rejects_old_records_without_native_signature(tmp_path: Path) -> None:
    path = tmp_path / "drawing.pdf"
    path.write_bytes(b"pdf")
    page = _page()
    app = _FakeApp(
        path=path,
        page=page,
        cached={
            "version": reading.VERSION,
            "word_count": 20,
            "char_count": 120,
        },
    )

    assert reading._cached_native_read_matches(app, 7, path, page) is False
