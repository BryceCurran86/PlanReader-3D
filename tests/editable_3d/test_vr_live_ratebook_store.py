"""Opt-in ratebook persistence never creates public, cross-tenant prices."""
from __future__ import annotations

from dataclasses import replace
import sqlite3
import pytest

from pb_vr_live_ratebook_store import (
    install_rate_book_schema, activate_rate_book, load_authorized_cost_book,
)
from test_vr_editor_command_preview import _fixture
from test_vr_live_costing import _book, _rate
from pb_vr_live_costing import LiveRateBinding
from pb_vr_editor_readonly_wsgi import EditorPrincipal


def _db():
    connection = sqlite3.connect(":memory:")
    install_rate_book_schema(connection)
    return connection


def test_explicit_admin_rate_revision_round_trip_and_no_implicit_seed():
    user, ws, ledger, cmd = _fixture()
    with _db() as connection:
        with pytest.raises(ValueError, match="no_explicit_rate_book"):
            load_authorized_cost_book(connection, user, ws)
        book = _book(ws)
        digest = activate_rate_book(
            connection, principal=user, workspace=ws, book=book,
            authorize_rate_manager=lambda principal, scope: True,
        )
        assert len(digest) == 64
        loaded = load_authorized_cost_book(connection, user, ws)
        assert loaded == book
        assert loaded.bindings[0].rate.material_cost_per_unit == 12.0
        # An identical immutable revision can be activated again idempotently.
        assert activate_rate_book(
            connection, principal=user, workspace=ws, book=book,
            authorize_rate_manager=lambda principal, scope: True,
        ) == digest
        assert connection.execute(
            "SELECT COUNT(*) FROM vr_live_pricing_books"
        ).fetchone()[0] == 1
        assert ledger.events == ()


def test_rate_management_requires_external_role_not_merely_preview_grant():
    user, ws, _, _ = _fixture()
    connection = _db()
    with pytest.raises(PermissionError, match="management_permission_denied"):
        activate_rate_book(
            connection, principal=user, workspace=ws, book=_book(ws),
            authorize_rate_manager=lambda p, w: False,
        )
    assert connection.execute(
        "SELECT COUNT(*) FROM vr_live_pricing_books"
    ).fetchone()[0] == 0


def test_same_revision_new_prices_cannot_rewrite_history_but_new_revision_can():
    user, ws, _, _ = _fixture()
    connection = _db()
    book = _book(ws)
    admin = lambda p, w: True
    activate_rate_book(
        connection, principal=user, workspace=ws, book=book,
        authorize_rate_manager=admin,
    )
    new_rate = _rate(material_cost_per_unit=15.0)
    new_binding = replace(book.bindings[0], rate=new_rate)
    with pytest.raises(ValueError, match="immutable_rate_revision_conflict"):
        activate_rate_book(
            connection, principal=user, workspace=ws,
            book=replace(book, bindings=(new_binding,)),
            authorize_rate_manager=admin,
        )
    changed = replace(book, revision="client-rates-v2", bindings=(new_binding,))
    activate_rate_book(
        connection, principal=user, workspace=ws, book=changed,
        authorize_rate_manager=admin,
    )
    assert load_authorized_cost_book(connection, user, ws) == changed
    assert connection.execute(
        "SELECT COUNT(*) FROM vr_live_pricing_books"
    ).fetchone()[0] == 2


def test_cross_tenant_workspace_and_stale_source_never_see_rates():
    user, ws, _, _ = _fixture()
    connection = _db()
    activate_rate_book(
        connection, principal=user, workspace=ws, book=_book(ws),
        authorize_rate_manager=lambda p, w: True,
    )
    viewer = EditorPrincipal("viewer", "tenant1", frozenset({"w1"}))
    with pytest.raises(PermissionError):
        load_authorized_cost_book(connection, viewer, ws)
    outsider = EditorPrincipal("other", "tenant2",
                              frozenset({"w1"}), frozenset({"w1"}))
    with pytest.raises(PermissionError):
        load_authorized_cost_book(connection, outsider, ws)
    stale = replace(ws, scope=replace(ws.scope, snapshot_id="new-snapshot"))
    with pytest.raises(ValueError, match="no_explicit_rate_book"):
        load_authorized_cost_book(connection, user, stale)
    stale_pdf = replace(ws, scope=replace(ws.scope, source_sha256="b"*64))
    with pytest.raises(ValueError, match="no_explicit_rate_book"):
        load_authorized_cost_book(connection, user, stale_pdf)


def test_unwitnessed_target_rejected_as_rate_binding_before_storage():
    user, ws, _, _ = _fixture()
    connection = _db()
    invalid = replace(
        _book(ws),
        bindings=(LiveRateBinding(
            canonical_object_id="fabricated-canonical-wall",
            target="wall_gross_area",rate=_rate(),
            binding_evidence_ids=("untrusted-binding",),
        ),),
    )
    with pytest.raises(ValueError, match="unwitnessed"):
        activate_rate_book(
            connection, principal=user, workspace=ws, book=invalid,
            authorize_rate_manager=lambda p, w: True,
        )


def test_rate_record_hash_corruption_fails_closed():
    user, ws, _, _ = _fixture()
    connection = _db()
    activate_rate_book(
        connection, principal=user, workspace=ws, book=_book(ws),
        authorize_rate_manager=lambda p, w: True,
    )
    connection.execute(
        "UPDATE vr_live_pricing_books SET content_json=?",
        ('{"injected":"true"}',),
    )
    with pytest.raises(ValueError, match="integrity"):
        load_authorized_cost_book(connection, user, ws)
