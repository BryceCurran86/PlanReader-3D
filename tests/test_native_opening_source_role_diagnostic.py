from tools.diag_native_opening_source_roles import source_role_report
from test_g17_visible_opening_existence_v1 import _opening_pdf_bytes
from test_native_unstroked_fill_evidence import _source


def test_source_role_report_retains_opposition_and_cannot_measure_or_close_counts():
    source, published, _, _ = _source()
    data = source._producer._store.source_bytes_by_revision[published.revision.revision_id]
    result = source_role_report(data, page_ids=("1",))
    assert result == source_role_report(data, page_ids=("1",))
    assert result["positive_existence_records"] == []
    assert result["retained_opposed_candidates"]
    assert not result["native_candidate_closures"][0]["candidate_universe_complete"]
    assert all(row["candidate"]["source_observation_ids"] for row in result["retained_opposed_candidates"])
    assert "quantities" not in result
    assert all(atom["normalized_value"] is None and atom["unit"] is None
               for row in result["retained_opposed_candidates"]
               for atom in row["opposing_evidence_atoms"])


def test_source_role_report_preserves_real_wall_opening_identity():
    data = _opening_pdf_bytes()
    result = source_role_report(data, page_ids=("1",))
    assert result["positive_existence_records"]
    assert not result["retained_opposed_candidates"]
    assert all(row["source_sha256"] == result["source_sha256"]
               for row in result["positive_existence_records"])
    assert result == source_role_report(data, page_ids=("1",))
