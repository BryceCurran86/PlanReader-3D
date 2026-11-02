"""Real SQLite proof: original file insertion order is not drawing revision identity."""

import pytest

from pb_jobhub_publishing_contract import PublishingMode, validate_publishing_gate
from pb_jobhub_publishing_pipeline import (
    build_publishing_package_from_workspace,
    execute_jobhub_publishing,
)
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


def _package(conn):
    return build_publishing_package_from_workspace(
        conn, 1, PublishingMode.COMMERCIAL,
        preflight_fingerprint="original-source-receipt-unchanged",
        acting_user="Estimator A",
    )


def _reverse_document_ingestion_order(conn):
    original = conn.execute(
        "SELECT file_name, sha256 FROM documents WHERE workspace_id=1 ORDER BY id"
    ).fetchall()
    conn.execute("DELETE FROM documents WHERE workspace_id=1")
    conn.executemany(
        "INSERT INTO documents (workspace_id, file_name, sha256) VALUES (1, ?, ?)",
        [(row["file_name"], row["sha256"]) for row in reversed(original)],
    )
    conn.commit()


def test_reordered_original_manifest_keeps_seal_and_real_jobhub_duplicate_veto(test_dbs):
    pr, hub, bridge = test_dbs
    _firm_row(pr)
    pr.execute(
        "INSERT INTO documents (workspace_id, file_name, sha256) VALUES (1, ?, ?)",
        ("Additional_Sheets.pdf", "b" * 64),
    )
    pr.commit()

    before = _package(pr)
    assert before.drawing_revision.file_names == sorted(
        before.drawing_revision.file_names
    )
    assert len(before.drawing_revision.file_names) == 2
    assert validate_publishing_gate(before).is_publishable

    receipt = execute_jobhub_publishing(before, bridge, "Estimator A")
    assert receipt["status"] == "Published"

    _reverse_document_ingestion_order(pr)
    after = _package(pr)
    assert after.drawing_revision.file_names == before.drawing_revision.file_names
    assert after.drawing_revision.source_files_hash == before.drawing_revision.source_files_hash
    assert after.payload_hash == before.payload_hash
    assert after.payload_hash == after.compute_payload_hash()
    with pytest.raises(RuntimeError, match="Duplicate package"):
        execute_jobhub_publishing(after, bridge, "Estimator A")
    assert hub.execute("SELECT COUNT(*) FROM painting_takeoff_packages").fetchone()[0] == 1
    assert hub.execute("SELECT COUNT(*) FROM painting_takeoff_package_lines").fetchone()[0] == 1


def test_same_name_multiple_source_digests_retains_multiplicity_and_sha_identity(test_dbs):
    pr, _, _ = test_dbs
    _firm_row(pr)
    pr.execute(
        "INSERT INTO documents (workspace_id, file_name, sha256) VALUES (1, ?, ?)",
        ("26-017_BA_Drawings.pdf", "b" * 64),
    )
    pr.commit()
    first = _package(pr)
    assert first.drawing_revision.file_names == [
        "26-017_BA_Drawings.pdf", "26-017_BA_Drawings.pdf"
    ]

    _reverse_document_ingestion_order(pr)
    same = _package(pr)
    assert same.payload_hash == first.payload_hash
    pr.execute(
        "UPDATE documents SET sha256=? WHERE workspace_id=1 AND sha256=?",
        ("c" * 64, "b" * 64),
    )
    pr.commit()
    changed = _package(pr)
    assert changed.drawing_revision.file_names == first.drawing_revision.file_names
    assert changed.drawing_revision.source_files_hash != first.drawing_revision.source_files_hash
    assert changed.payload_hash != first.payload_hash


@pytest.mark.parametrize("missing_issue", [None, "", "  "])
def test_missing_issue_is_unknown_not_fabricated_ba(test_dbs, missing_issue):
    pr, _, _ = test_dbs
    _firm_row(pr)
    pr.execute("UPDATE workspaces SET drawing_issue=? WHERE id=1", (missing_issue,))
    pr.commit()
    package = _package(pr)
    assert package.drawing_revision.drawing_issue == ""
    assert package.drawing_revision.drawing_date == ""
    assert package.drawing_revision.source_files_hash
    assert package.payload_hash == package.compute_payload_hash()


def test_missing_original_digest_still_blocks_commercial_publishing(test_dbs):
    pr, hub, bridge = test_dbs
    _firm_row(pr)
    pr.execute("UPDATE documents SET sha256=NULL WHERE workspace_id=1")
    pr.commit()
    package = _package(pr)
    assert package.drawing_revision.source_files_hash == ""
    assert not validate_publishing_gate(package).is_publishable
    with pytest.raises(RuntimeError, match="Publishing blocked"):
        execute_jobhub_publishing(package, bridge, "Estimator A")
    assert hub.execute("SELECT COUNT(*) FROM painting_takeoff_packages").fetchone()[0] == 0
