"""No source PDF needed: residual owner review remains shadow-only."""
from types import SimpleNamespace

from tools.run_source_outside_residual_owner_review import _outside_checkout, _receipt


def test_original_residual_receipt_retains_owners_and_zero_quantity(tmp_path):
    class Walk:
        status = "ABSTAINED"
        reason = "source_other_structural_walls_outside_candidate"
        enclosed_dwelling_zone_count = 2
        other_source_wall_band_count = 1

        def to_dict(self):
            return {
                "unresolved_outside_native_path_id_sample": [12],
                "unresolved_outside_band_review_sample": [{
                    "bounds_pdf_pts": [280, 20, 283, 40],
                    "source_local_native_path_ids": [12],
                    "physical_wall_authenticated": False,
                    "measurement_authorized": False,
                }],
            }

    report = _receipt(SimpleNamespace(source_outside_face_walk=Walk()), "a" * 64, 2)
    assert report["status"] == "ABSTAINED"
    assert report["unresolved_band_count"] == 1
    assert report["bands"][0]["source_local_native_path_ids"] == [12]
    assert report["all_unresolved_bands_in_sample"] is True
    assert report["enclosed_dwelling_zone_count"] == 2
    assert report["commercial_quantity_rows"] == 0
    assert not report["measurement_authorized"]
    assert not report["building_footprint_authenticated"]


def test_missing_outside_walk_retains_abstain():
    report = _receipt(SimpleNamespace(source_outside_face_walk=None), "f" * 64, 2)
    assert report["status"] == "ABSTAINED"
    assert report["bands"] == []
    assert report["measurement_authorized"] is False


def test_no_private_files_inside_checkout(tmp_path):
    repo = tmp_path / "checkout"
    repo.mkdir()
    assert not _outside_checkout(repo / "original.pdf", repo)
    assert not _outside_checkout(repo / "output" / "sample.json", repo)
    assert _outside_checkout(tmp_path / "private" / "original.pdf", repo)
    assert _outside_checkout(tmp_path / "private" / "sample.json", repo)


def test_sample_limit_does_not_pretend_to_be_exhaustive():
    class Walk:
        status = "ABSTAINED"
        reason = "source_other_structural_walls_outside_candidate"
        enclosed_dwelling_zone_count = 2
        other_source_wall_band_count = 33

        def to_dict(self):
            return {"unresolved_outside_band_review_sample": [
                {"source_local_native_path_ids": [i]} for i in range(32)
            ]}

    report = _receipt(SimpleNamespace(source_outside_face_walk=Walk()), "a" * 64, 2)
    assert report["all_unresolved_bands_in_sample"] is False
    assert not report["measurement_authorized"]
