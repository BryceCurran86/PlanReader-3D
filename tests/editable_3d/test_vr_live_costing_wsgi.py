"""Authenticated HTTP live costing: no user rate injection, no source writes."""
from __future__ import annotations

from dataclasses import replace
from io import BytesIO
import json

from pb_vr_live_costing import LiveCostBook
from pb_vr_live_costing_wsgi import make_vr_live_costing_wsgi_app
from test_vr_editor_command_preview import _fixture
from test_vr_live_costing import _book


def _app(*, authenticated=True, csrf=True, loaded=True, book=True, viewer=False):
    user, ws, ledger, command = _fixture()
    if viewer:
        user = replace(user, allowed_preview_workspace_ids=frozenset())
    def session(env):
        return user if authenticated else None
    def load_ws(principal, wid):
        return ws if loaded else None
    def load_ledger(principal, scoped):
        return ledger, ()
    def validate_csrf(env, principal):
        return csrf
    def load_book(principal, scoped):
        return _book(scoped) if book else None
    return (
        make_vr_live_costing_wsgi_app(session, load_ws, load_ledger,
                                     validate_csrf, load_book),
        command, ledger,
    )


def _request(app, command, *, method="POST",
             path="/api/editor/workspaces/w1/costing/preview", raw=None,
             content_type="application/json", declared=None):
    body = json.dumps(command).encode("utf-8") if raw is None else raw
    state = []
    def start_response(status, headers):
        state.append((status, dict(headers)))
    env = {
        "PATH_INFO": path, "REQUEST_METHOD": method,
        "CONTENT_TYPE": content_type,
        "CONTENT_LENGTH": str(len(body) if declared is None else declared),
        "wsgi.input": BytesIO(body),
    }
    payload = json.loads(b"".join(app(env, start_response)))
    return state[0][0], state[0][1], payload


def test_live_endpoint_returns_source_checked_quantity_and_cost_once_no_mutation():
    app, command, ledger = _app()
    original = ledger.get_object("wall-1").to_dict()
    status, headers, result = _request(app, command)
    assert status.startswith("200")
    assert result["accepted"] is True
    assert result["quantityPreview"]["validationState"] == "valid_preview_only"
    cost = result["costingPreview"]
    assert cost["validationState"] == "cost_preview_only"
    assert cost["totals"]["delta"]["sellIncTax"] == "78.40"
    assert not cost["quoteReady"]
    assert not cost["commercialPublicationAllowed"]
    assert headers["Cache-Control"] == "no-store, private"
    assert headers["X-Frame-Options"] == "DENY"
    assert "Access-Control-Allow-Origin" not in headers
    assert ledger.get_object("wall-1").to_dict() == original
    assert ledger.events == ()


def test_anonymous_readonly_csrf_and_nonmatching_workspace_block_before_rate_loader():
    for settings, expected in (
        (dict(authenticated=False), "401"),
        (dict(viewer=True), "403"),
        (dict(csrf=False), "403"),
        (dict(loaded=False), "404"),
    ):
        app, cmd, ledger = _app(**settings)
        status, headers, result = _request(app, cmd)
        assert status.startswith(expected), result
        assert result["accepted"] is not True if "accepted" in result else True
        assert ledger.events == ()


def test_missing_server_ratebook_is_409_never_fabricated_free_quote():
    app, cmd, ledger = _app(book=False)
    status, _, result = _request(app, cmd)
    assert status.startswith("409")
    assert result == {"error": "cost_preview_unavailable"}
    assert ledger.events == ()


def test_stale_original_revision_denies_price_before_loading_rates():
    app, cmd, ledger = _app()
    cmd["targetRevisionHash"] = "stale-revision"
    status, _, result = _request(app, cmd)
    assert status.startswith("409")
    assert result["accepted"] is False
    assert result["costingPreview"] is None
    assert result["quantityPreview"]["blockingReasons"] == ["stale_object_revision"]
    assert ledger.events == ()


def test_browser_cannot_provide_rates_tax_approvals_or_fake_quote_status():
    app, cmd, ledger = _app()
    for extra in (
        {"rates": [{"material_cost_per_unit": 0}]},
        {"taxPct": 0},
        {"approved": True},
        {"commercialPublicationAllowed": True},
    ):
        status, _, result = _request(app, {**cmd, **extra})
        assert status.startswith("422")
        assert result["accepted"] is False
        assert result["costingPreview"] is None
    assert ledger.events == ()


def test_same_origin_json_body_size_and_method_gate():
    app, cmd, ledger = _app()
    status, _, r = _request(app, cmd, method="GET")
    assert status.startswith("405")
    status, _, r = _request(app, cmd, method="PUT")
    assert status.startswith("405")
    status, _, r = _request(app, cmd, content_type="text/plain")
    assert status.startswith("415")
    status, _, r = _request(app, cmd, declared=100000)
    assert status.startswith("413")
    status, _, r = _request(app, cmd, declared=2000)
    assert status.startswith("400")
    status, _, r = _request(app, cmd, raw=b'{"duplicate":1,"duplicate":2}')
    assert status.startswith("400")
    for value in (b"NaN", b"Infinity", b"-Infinity"):
        status, _, r = _request(app, cmd, raw=b'{"value":' + value + b'}')
        assert status.startswith("400")
    assert ledger.events == ()


def test_existing_manifest_and_correction_preview_routes_still_pass_through():
    app, cmd, ledger = _app()
    status, _, scene = _request(
        app, {}, method="GET",
        path="/api/editor/workspaces/w1/manifest",
    )
    assert status.startswith("200")
    assert scene["readOnly"] is True
    status, _, result = _request(
        app, cmd, path="/api/editor/workspaces/w1/commands/preview",
    )
    assert status.startswith("200")
    assert result["accepted"] is True
    assert ledger.events == ()
