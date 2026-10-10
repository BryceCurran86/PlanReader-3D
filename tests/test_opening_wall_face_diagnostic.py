from test_opening_proven_wall_face_preservation import _source
from tools.diag_opening_wall_face_preservation import source_face_report


def test_source_face_report_retains_proven_faces_and_exact_source_identity():
    source, published, _ = _source()
    data = source._producer._store.source_bytes_by_revision[published.revision.revision_id]
    result = source_face_report(data, page_ids=("1",))
    assert result == source_face_report(data, page_ids=("1",))
    assert len(result["protected_source_wall_face_ids_by_page"]["1"]) == 4
    assert result["primitive_safety_cap"] == 20_000
    assert result["source_owned_wall_scope_results"]
    assert all(row["source_sha256"] == result["source_sha256"]
               for row in result["source_owned_wall_scope_results"])
    assert "quantities" not in result
