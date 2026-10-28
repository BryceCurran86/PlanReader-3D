"""Real SQLite regression: filename padding is not original revision authority.

A source SHA-256 and its canonical filename are sealed into the source
manifest. The separately sealed filename roster must use the SAME canonical
name, or an unchanged source can bypass the real JobHub duplicate lookup.
These synthetic records grant no original-source/FIRM/customer/score authority.
"""
import pytest

from pb_jobhub_publishing_contract import PublishingMode, validate_publishing_gate
from pb_jobhub_publishing_pipeline import (
    build_publishing_package_from_workspace,
    execute_jobhub_publishing,
)
from test_publishing_pipeline_e2e import test_dbs  # noqa: F401


def _firm_row(pr):
    pr.execute(
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
    pr.commit()


def _package(pr):
    return build_publishing_package_from_workspace(
        pr, 1, PublishingMode.COMMERCIAL,
        preflight_fingerprint="unchanged-original-source-receipt",
        acting_user="Estimator A",
    )


@pytest.mark.parametrize("padding", [
    "  26-017_BA_Drawings.pdf  ",
    "\t26-017_BA_Drawings.pdf\n",
    "26-017_BA_Drawings.pdf ",
])
def test_filename_padding_keeps_source_and_full_seal_and_blocks_duplicate_write(
    test_dbs, padding,
):
    pr, hub, bridge = test_dbs
    _firm_row(pr)
    before = _package(pr)
    assert validate_publishing_gate(before).is_publishable
    receipt = execute_jobhub_publishing(before, bridge, "Estimator A")
    assert receipt["status"] == "Published"

    pr.execute(
        "UPDATE documents SET file_name=? WHERE workspace_id=1",
        (padding,),
    )
    pr.commit()
    after = _package(pr)
    assert after.drawing_revision.file_names == before.drawing_revision.file_names
    assert after.drawing_revision.source_files_hash == before.drawing_revision.source_files_hash
    assert after.payload_hash == before.payload_hash
    assert after.payload_hash == after.compute_payload_hash()
    assert validate_publishing_gate(after).is_publishable

    with pytest.raises(RuntimeError, match="Duplicate package"):
        execute_jobhub_publishing(after, bridge, "Estimator A")
    assert hub.execute("SELECT COUNT(*) FROM painting_takeoff_packages").fetchone()[0] == 1
    assert hub.execute("SELECT COUNT(*) FROM painting_takeoff_package_lines").fetchone()[0] == 1


def test_reordered_padded_multiset_preserves_all_names_and_duplicate_veto(test_dbs):
    pr, hub, bridge = test_dbs
    _firm_row(pr)
    pr.execute(
        "INSERT INTO documents (workspace_id, file_name, sha256) VALUES (1, ?, ?)",
        ("  26-017_BA_Drawings.pdf  ", "b" * 64),
    )
    pr.commit()
    before = _package(pr)
    assert before.drawing_revision.file_names == [
        "26-017_BA_Drawings.pdf", "26-017_BA_Drawings.pdf"
    ]
    assert validate_publishing_gate(before).is_publishable
    assert execute_jobhub_publishing(before, bridge, "Estimator A")["status"] == "Published"

    docs = pr.execute(
        "SELECT file_name, sha256 FROM documents WHERE workspace_id=1 ORDER BY id"
    ).fetchall()
    pr.execute("DELETE FROM documents WHERE workspace_id=1")
    pr.executemany(
        "INSERT INTO documents (workspace_id, file_name, sha256) VALUES (1, ?, ?)",
        [(str(d["file_name"]).strip(), d["sha256"]) for d in reversed(docs)],
    )
    pr.commit()
    after = _package(pr)
    assert after.drawing_revision.file_names == before.drawing_revision.file_names
    assert after.drawing_revision.source_files_hash == before.drawing_revision.source_files_hash
    assert after.payload_hash == before.payload_hash
    with pytest.raises(RuntimeError, match="Duplicate package"):
        execute_jobhub_publishing(after, bridge, "Estimator A")
    assert hub.execute("SELECT COUNT(*) FROM painting_takeoff_packages").fetchone()[0] == 1
    assert hub.execute("SELECT COUNT(*) FROM painting_takeoff_package_lines").fetchone()[0] == 1


@pytest.mark.parametrize("invalid_name", [" ", "\t\n", ""])
def test_blank_canonical_filename_never_mints_commercial_source_authority(
    test_dbs, invalid_name,
):
    pr, hub, bridge = test_dbs
    _firm_row(pr)
    pr.execute(
        "UPDATE documents SET file_name=? WHERE workspace_id=1",
        (invalid_name,),
    )
    pr.commit()
    package = _package(pr)
    assert package.drawing_revision.file_names == []
    assert package.drawing_revision.source_files_hash == ""
    assert package.payload_hash == package.compute_payload_hash()
    assert not validate_publishing_gate(package).is_publishable
    with pytest.raises(RuntimeError, match="Publishing blocked"):
        execute_jobhub_publishing(package, bridge, "Estimator A")
    assert hub.execute("SELECT COUNT(*) FROM painting_takeoff_packages").fetchone()[0] == 0


@pytest.mark.parametrize("replacement", [
    "Different_Original.pdf", "26-017_ba_Drawings.pdf"
])
def test_material_filename_change_remains_distinct_source_revision(
    test_dbs, replacement,
):
    pr, _, _ = test_dbs
    _firm_row(pr)
    before = _package(pr)
    pr.execute(
        "UPDATE documents SET file_name=? WHERE workspace_id=1",
        (replacement,),
    )
    pr.commit()
    after = _package(pr)
    assert after.drawing_revision.file_names != before.drawing_revision.file_names
    assert after.drawing_revision.source_files_hash != before.drawing_revision.source_files_hash
    assert after.payload_hash != before.payload_hash
    assert after.payload_hash == after.compute_payload_hash()
