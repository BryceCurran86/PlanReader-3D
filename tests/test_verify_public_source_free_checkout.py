"""The public code handoff must never contain private source originals."""
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from scripts.verify_public_source_free_checkout import (
    verify_source_free_public_archive,
    BENCHMARK, MASTER, PROJECTS,
)


def contents(extra=None, *, omit=None):
    suite = {"benchmark_id": "full_plan_takeoff_reconciliation_v2",
             "projects": list(PROJECTS)}
    rows = {MASTER: json.dumps(suite).encode(), "README.md": b"Public code"}
    for i, project in enumerate(PROJECTS):
        docs = [{"name": f"original-{i}-{j}.pdf",
                 "sha256": f"{i+j+1:064x}"}
                for j in range((2,1,1,6)[i])]
        rows[f"{BENCHMARK}/projects/{project}/source_manifest.json"] = (
            json.dumps({"project_id":project,"source_documents":docs}).encode())
    if extra:
        rows.update(extra)
    if omit:
        rows.pop(omit)
    return rows


def archive(tmp, rows, *, link=None):
    path=Path(tmp)/"checkout.tar.gz"
    with tarfile.open(path, "w:gz") as writer:
        for name, payload in rows.items():
            info = tarfile.TarInfo(name)
            info.size=len(payload)
            writer.addfile(info, io.BytesIO(payload))
        if link is not None:
            info=tarfile.TarInfo("source-link")
            info.type=tarfile.SYMTYPE
            info.linkname=link
            writer.addfile(info)
    return path


class PublicSourceFreeCheckoutTests(unittest.TestCase):
    def test_public_metadata_only_with_all_ten_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=verify_source_free_public_archive(archive(tmp,contents()))
        self.assertEqual(result["status"],"CODE_ONLY_SOURCE_FREE")
        self.assertEqual(result["project_count"],4)
        self.assertEqual(result["frozen_original_source_document_count"],10)
        self.assertIsNone(result["benchmark_accuracy"])

    def test_rejects_missing_frozen_suite_and_project_manifest(self):
        for missing in (MASTER, f"{BENCHMARK}/projects/{PROJECTS[0]}/source_manifest.json"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError):
                    verify_source_free_public_archive(archive(tmp,contents(omit=missing)))

    def test_rejects_private_paths_and_exact_original_basename_anywhere(self):
        for bad in (
            "documents/sources/original-0-0.pdf",
            "docs/reused-original-0-0.pdf",
            "benchmarks/sources/unlisted-client.pdf",
            ".private-sources/secret-plan.pdf",
            ".env",
            "docs/id_rsa",
            "docs/credentials.p12",
        ):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError):
                    verify_source_free_public_archive(archive(tmp,contents({bad:b"private"})))

    def test_rejects_links_and_incomplete_original_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                verify_source_free_public_archive(archive(tmp,contents(),link="../secret"))
        source=f"{BENCHMARK}/projects/{PROJECTS[-1]}/source_manifest.json"
        rows=contents()
        project=json.loads(rows[source]);project["source_documents"].pop()
        rows[source]=json.dumps(project).encode()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                verify_source_free_public_archive(archive(tmp,rows))

    def test_rejects_invalid_benchmark_or_source_hash(self):
        rows=contents()
        broken=json.loads(rows[MASTER]);broken["benchmark_id"]="wrong"
        rows[MASTER]=json.dumps(broken).encode()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                verify_source_free_public_archive(archive(tmp,rows))
        rows=contents()
        source=f"{BENCHMARK}/projects/{PROJECTS[0]}/source_manifest.json"
        broken=json.loads(rows[source])
        broken["source_documents"][0]["sha256"]="fake"
        rows[source]=json.dumps(broken).encode()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                verify_source_free_public_archive(archive(tmp,rows))


if __name__ == "__main__":
    unittest.main()
