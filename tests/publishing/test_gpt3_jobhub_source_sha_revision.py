"""Source PDF byte identity must drive JobHub commercial revision fingerprints."""
from __future__ import annotations

import re
import pytest

from pb_jobhub_publishing_contract import PublishingMode, validate_publishing_gate
from pb_jobhub_publishing_pipeline import build_publishing_package_from_workspace
from test_publishing_pipeline_e2e import test_dbs


def _package(conn, mode=PublishingMode.COMMERCIAL):
    return build_publishing_package_from_workspace(
        conn, 1, mode, acting_user="Source Estimator",
    )


def test_one_pdf_same_filename_changed_sha_changes_revision_fingerprint(test_dbs):
    local, _, _ = test_dbs
    first = _package(local)
    assert re.fullmatch("[a-f0-9]{64}", first.drawing_revision.source_files_hash)
    local.execute("UPDATE documents SET sha256=? WHERE workspace_id=1", ("b" * 64,))
    second = _package(local)
    assert first.drawing_revision.file_names == second.drawing_revision.file_names
    assert first.drawing_revision.source_files_hash != second.drawing_revision.source_files_hash
    assert first.payload_hash != second.payload_hash


def test_missing_sha_column_does_not_forge_commercial_drawing_source(test_dbs):
    local, _, _ = test_dbs
    local.executescript("""
        DROP TABLE documents;
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY, workspace_id INTEGER, file_name TEXT
        );
        INSERT INTO documents (workspace_id,file_name) VALUES
            (1,'26-017_BA_Drawings.pdf');
    """)
    commercial = _package(local)
    assert commercial.drawing_revision.source_files_hash == ""
    assert not validate_publishing_gate(commercial).is_publishable
    assert any("original document SHA-256" in r
               for r in validate_publishing_gate(commercial).blocking_reasons)
    draft = _package(local, PublishingMode.DRAFT)
    assert draft.drawing_revision.source_files_hash == ""


@pytest.mark.parametrize("digest", [None, "", "not-an-original", "A" * 64,
                                     "z" * 64, "deadbeef"])
def test_unverified_or_malformed_source_sha_never_authorises_sale(digest, test_dbs):
    local, _, _ = test_dbs
    local.execute("UPDATE documents SET sha256=? WHERE workspace_id=1", (digest,))
    commercial = _package(local)
    assert commercial.drawing_revision.source_files_hash == ""
    assert not validate_publishing_gate(commercial).is_publishable


def test_two_source_files_have_deterministic_revision_independent_of_insert_order(test_dbs):
    local, _, _ = test_dbs
    local.execute(
        "INSERT INTO documents (workspace_id,file_name,sha256) VALUES (1,?,?)",
        ("26-017_Structure.pdf", "b" * 64),
    )
    first = _package(local)
    assert first.drawing_revision.source_files_hash
    local.execute("UPDATE documents SET id=100 WHERE sha256=?", ("a" * 64,))
    second = _package(local)
    assert first.drawing_revision.source_files_hash == second.drawing_revision.source_files_hash


def test_one_incomplete_document_invalidates_entire_multi_pdf_revision(test_dbs):
    local, _, _ = test_dbs
    local.execute(
        "INSERT INTO documents (workspace_id,file_name,sha256) VALUES (1,?,?)",
        ("26-017_Structure.pdf", None),
    )
    commercial = _package(local)
    assert commercial.drawing_revision.source_files_hash == ""
    assert not validate_publishing_gate(commercial).is_publishable


def test_source_sha_is_not_a_proof_of_original_pdf_bytes(test_dbs):
    local, _, _ = test_dbs
    report = _package(local)
    assert report.drawing_revision.source_files_hash != "a" * 64
    # The SHA is derived from document ingestion metadata, not a reread of
    # the original drawing bytes. Owner-local original SHA replays remain required.
