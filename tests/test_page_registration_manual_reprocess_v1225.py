from __future__ import annotations

import pb_page_registration_v1225 as registration


class _App:
    def __init__(self, rows, settings=None):
        self.rows = [dict(row) for row in rows]
        self.settings = dict(settings or {})

    def lquery(self, sql, params=()):
        if "FROM pages" in sql:
            document_id = int(params[0])
            return [dict(row) for row in self.rows if int(row["document_id"]) == document_id]
        return []

    def lexecute(self, sql, params=()):
        if sql.startswith("UPDATE pages SET page_label"):
            label, page_type, scale_text, page_id = params
            for row in self.rows:
                if int(row["id"]) == int(page_id):
                    row["page_label"] = str(label)
                    row["page_type"] = str(page_type)
                    row["scale_text"] = str(scale_text)
        return 1

    def workspace_setting(self, workspace_id, key, default=""):
        return self.settings.get((int(workspace_id), str(key)), default)

    def set_workspace_setting(self, workspace_id, key, value):
        self.settings[(int(workspace_id), str(key))] = str(value)


def _row(page_id=11):
    return {
        "id": page_id,
        "workspace_id": 7,
        "document_id": 1,
        "page_no": 4,
        "page_label": "A-401",
        "page_type": "Floor Plan",
        "scale_text": "1:100",
    }


def test_manual_registration_restores_same_page_row_after_rerender():
    app = _App([_row()], {
        (7, registration._manual_key(11)): "1",
        (7, registration._meta_key(11)): '{"title":"Level 1 plan","manual":true}',
    })
    snapshot = registration._snapshot_manual_registration(app, 1)
    app.rows[0].update({"page_label": "Page 4", "page_type": "Other", "scale_text": ""})
    assert registration._restore_manual_registration(app, 1, snapshot) == 1
    assert app.rows[0]["page_label"] == "A-401"
    assert app.rows[0]["page_type"] == "Floor Plan"
    assert app.rows[0]["scale_text"] == "1:100"


def test_manual_registration_transfers_to_recreated_page_id():
    app = _App([_row(11)], {
        (7, registration._manual_key(11)): "1",
        (7, registration._meta_key(11)): '{"title":"Manual title","manual":true}',
    })
    snapshot = registration._snapshot_manual_registration(app, 1)
    app.rows = [{**_row(99), "page_label": "Page 4", "page_type": "Other", "scale_text": ""}]
    assert registration._restore_manual_registration(app, 1, snapshot) == 1
    assert app.rows[0]["page_label"] == "A-401"
    assert app.rows[0]["page_type"] == "Floor Plan"
    assert app.rows[0]["scale_text"] == "1:100"
    assert app.settings[(7, registration._manual_key(99))] == "1"
    assert app.settings[(7, registration._meta_key(99))] == '{"title":"Manual title","manual":true}'


def test_non_manual_page_is_not_restored():
    app = _App([_row()], {})
    assert registration._snapshot_manual_registration(app, 1) == {}
