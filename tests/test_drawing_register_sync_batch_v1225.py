"""Regression coverage for batched Drawing Register database reads."""

from __future__ import annotations

import pb_page_registration_v1225 as registration


class _SyncApp:
    def __init__(self, pages, register_rows):
        self.pages = [dict(row) for row in pages]
        self.register_rows = [dict(row) for row in register_rows]
        self.register_selects = 0
        self.live_source_selects = 0
        self.settings_selects = 0
        self.executed = []

    def lquery(self, sql, params=()):
        if "FROM pages p JOIN documents" in sql:
            return [dict(row) for row in self.pages]
        if "FROM workspace_settings" in sql:
            self.settings_selects += 1
            return []
        if "FROM register_items" in sql:
            self.register_selects += 1
            if "source_reference=?" in sql:
                self.live_source_selects += 1
                source = str(params[1])
                return [
                    {"id": row["id"]}
                    for row in self.register_rows
                    if row["source_reference"] == source
                ]
            return [dict(row) for row in self.register_rows]
        raise AssertionError(sql)

    def workspace_setting(self, workspace_id, key, default=""):
        return default

    def lexecute(self, sql, params=()):
        self.executed.append((sql, tuple(params)))
        return 1

    def now_stamp(self):
        return "2026-09-29T19:00:00"


def _page(page_id, page_no, file_name="drawings.pdf"):
    return {
        "id": page_id,
        "page_no": page_no,
        "page_label": f"A-{page_no:03d}",
        "page_type": "Floor Plan",
        "scale_text": "1:100",
        "file_name": file_name,
    }


def test_sync_batches_existing_register_lookup_for_unique_sheet_sources():
    app = _SyncApp(
        [_page(1, 1), _page(2, 2), _page(3, 3)],
        [
            {"id": 10, "source_reference": "drawings.pdf p1"},
            {"id": 11, "source_reference": "drawings.pdf p2"},
            {"id": 12, "source_reference": "drawings.pdf p2"},
        ],
    )

    changed = registration.sync_drawing_register(app, 7)

    assert changed == 3
    assert app.register_selects == 1
    assert app.live_source_selects == 0
    assert app.settings_selects == 1
    assert any(
        sql.startswith("DELETE FROM register_items") and params == (12,)
        for sql, params in app.executed
    )
    assert any(
        sql.startswith("INSERT INTO register_items")
        for sql, _params in app.executed
    )


def test_duplicate_source_reference_falls_back_to_live_lookup():
    app = _SyncApp(
        [_page(1, 1), _page(2, 1)],
        [{"id": 10, "source_reference": "drawings.pdf p1"}],
    )

    registration.sync_drawing_register(app, 7)

    # One workspace-wide preload plus one live lookup for each ambiguous source
    # occurrence preserves the historical sequential behavior.
    assert app.register_selects == 3
    assert app.live_source_selects == 2
