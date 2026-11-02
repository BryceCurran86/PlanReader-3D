"""Real SQLite regression: publish time cannot masquerade as original drawing date."""

from datetime import date
from types import SimpleNamespace

import pytest

import pb_jobhub_publishing_pipeline as pipeline
from pb_jobhub_publishing_contract import PublishingMode, validate_publishing_gate
from test_publishing_pipeline_e2e import test_dbs


def _firm_row(conn):
    conn.execute(
        """
        INSERT INTO takeoff_rows (
            id, workspace_id, section, location, substrate, finish_tag,
            element, unit, quantity, rate, total_price,
            commercial_authority_status, commercial_authority_source,
            commercial_authority_reviewed_by
        ) VALUES (
            1, 1, 'Internal walls', 'Unit 1', 'Plasterboard', 'PB01',
            'Wall', 'm2', 50.0, 20.0, 1000.0,
            'firm', 'documented_dimension', 'Estimator A'
        )
        """
    )
    conn.commit()


def _at_clock(monkeypatch, value):
    # The former implementation used datetime.date.today() to invent a
    # source drawing date. Keep an explicit clock probe even though the
    # repaired production builder no longer imports datetime.
    fake_clock = SimpleNamespace(date=SimpleNamespace(today=lambda: value))
    monkeypatch.setattr(pipeline, "datetime", fake_clock, raising=False)


def _package(conn):
    return pipeline.build_publishing_package_from_workspace(
        conn, 1, PublishingMode.COMMERCIAL,
        preflight_fingerprint="original-source-receipt-unchanged",
        acting_user="Estimator A",
    )


def test_same_source_across_calendar_days_keeps_seal_and_blocks_second_jobhub_write(
    test_dbs, monkeypatch
):
    pr, hub, bridge = test_dbs
    _firm_row(pr)
    _at_clock(monkeypatch, date(2026, 10, 28))
    first = _package(pr)

    _at_clock(monkeypatch, date(2026, 10, 29))
    second = _package(pr)

    # No source-backed date exists in this SQLite workspace. Do not invent one.
    assert first.drawing_revision.drawing_date == ""
    assert second.drawing_revision.drawing_date == ""
    assert first.drawing_revision.source_files_hash
    assert first.drawing_revision.source_files_hash == second.drawing_revision.source_files_hash
    assert first.payload_hash == second.payload_hash
    assert first.payload_hash == first.compute_payload_hash()
    assert validate_publishing_gate(first).is_publishable
    assert validate_publishing_gate(second).is_publishable

    published = pipeline.execute_jobhub_publishing(first, bridge, "Estimator A")
    assert published["status"] == "Published"
    with pytest.raises(RuntimeError, match="Duplicate package"):
        pipeline.execute_jobhub_publishing(second, bridge, "Estimator A")

    assert hub.execute("SELECT COUNT(*) FROM painting_takeoff_packages").fetchone()[0] == 1
    assert hub.execute("SELECT COUNT(*) FROM painting_takeoff_package_lines").fetchone()[0] == 1


def test_real_source_digest_change_still_changes_sealed_revision(test_dbs, monkeypatch):
    pr, _, _ = test_dbs
    _firm_row(pr)
    _at_clock(monkeypatch, date(2026, 10, 28))
    before = _package(pr)

    pr.execute("UPDATE documents SET sha256=? WHERE workspace_id=1", ("b" * 64,))
    pr.commit()
    _at_clock(monkeypatch, date(2026, 10, 29))
    after = _package(pr)

    assert before.drawing_revision.drawing_date == after.drawing_revision.drawing_date == ""
    assert before.drawing_revision.source_files_hash != after.drawing_revision.source_files_hash
    assert before.payload_hash != after.payload_hash
    assert after.payload_hash == after.compute_payload_hash()


def test_missing_original_sha_stays_commercially_blocked(test_dbs):
    pr, hub, bridge = test_dbs
    _firm_row(pr)
    pr.execute("UPDATE documents SET sha256=NULL WHERE workspace_id=1")
    pr.commit()

    package = _package(pr)
    assert package.drawing_revision.drawing_date == ""
    assert package.drawing_revision.source_files_hash == ""
    gate = validate_publishing_gate(package)
    assert not gate.is_publishable
    assert any("original document SHA-256" in reason for reason in gate.blocking_reasons)
    with pytest.raises(RuntimeError, match="Publishing blocked"):
        pipeline.execute_jobhub_publishing(package, bridge, "Estimator A")
    assert hub.execute("SELECT COUNT(*) FROM painting_takeoff_packages").fetchone()[0] == 0
