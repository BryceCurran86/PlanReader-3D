from __future__ import annotations

from pathlib import Path

import pb_page_registration_v1225 as registration


class _NoOpenFitz:
    def __init__(self) -> None:
        self.open_calls = 0

    def open(self, *args, **kwargs):
        self.open_calls += 1
        raise AssertionError("cached registration must not reopen the PDF")


class _FakeApp:
    def __init__(self, *, path: Path, page: dict, manual: bool = False) -> None:
        self._path = path
        self._page = dict(page)
        self._manual = bool(manual)
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
        if key == registration._manual_key(int(self._page["id"])):
            return "1" if self._manual else ""
        return default


def _page() -> dict:
    return {
        "id": 11,
        "document_id": 1,
        "page_no": 1,
        "page_label": "Page 1",
        "page_type": "Other",
        "scale_text": "",
        "extracted_text": "native text",
    }


def _signature(app: _FakeApp) -> str:
    return registration._registration_input_signature(
        app,
        workspace_id=7,
        document_id=1,
        path=app._path,
        file_name=app._path.name,
        rows=[app._page],
    )


def test_registration_signature_changes_for_relevant_inputs(tmp_path: Path) -> None:
    path = tmp_path / "drawing.pdf"
    path.write_bytes(b"pdf-v1")
    page = _page()
    app = _FakeApp(path=path, page=page)
    baseline = _signature(app)

    app._page["page_label"] = "A-101"
    assert _signature(app) != baseline
    app._page = dict(page)

    app._page["page_type"] = "Floor Plan"
    assert _signature(app) != baseline
    app._page = dict(page)

    app._page["scale_text"] = "1:100"
    assert _signature(app) != baseline
    app._page = dict(page)

    app._page["extracted_text"] = "updated spatial text"
    assert _signature(app) != baseline


def test_registration_signature_changes_for_manual_state_and_source(tmp_path: Path) -> None:
    path = tmp_path / "drawing.pdf"
    path.write_bytes(b"pdf-v1")
    app = _FakeApp(path=path, page=_page(), manual=False)
    baseline = _signature(app)

    app._manual = True
    assert _signature(app) != baseline

    app._manual = False
    path.write_bytes(b"pdf-v2-expanded")
    assert _signature(app) != baseline


def test_repair_document_registration_skips_exact_cached_input(tmp_path: Path) -> None:
    path = tmp_path / "drawing.pdf"
    path.write_bytes(b"cached-pdf")
    app = _FakeApp(path=path, page=_page())

    key = (7, 1)
    previous = registration._REGISTRATION_CACHE.get(key)
    registration._REGISTRATION_CACHE[key] = _signature(app)
    try:
        result = registration.repair_document_registration(app, 1)
    finally:
        if previous is None:
            registration._REGISTRATION_CACHE.pop(key, None)
        else:
            registration._REGISTRATION_CACHE[key] = previous

    assert result == {
        "updated": 0,
        "pages": [],
        "workspace_id": 7,
        "cached": 1,
    }
    assert app.fitz.open_calls == 0


def test_registration_cache_is_process_local_dictionary() -> None:
    # The cache intentionally is not written to workspace settings. A process
    # restart/deployment therefore forces a fresh title-registration pass.
    assert isinstance(registration._REGISTRATION_CACHE, dict)
