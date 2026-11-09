"""Source-neutral fail-closed tests; never commit original PDFs."""
import pytest
import fitz

import pb_gptmax_q5446_finish_support_shadow as module

BATH = "BATHROOM & ENSUITE\nCeramic floor tiles and skirting tiles throughout.\n"
LAUNDRY = "LAUNDRY\nCeramic floor tiles and skirting tiles throughout.\n"
SALE = (
    "47 - 3\n600mm x 600mm porcelain floor tiles to entry kitchen and living. "
    "Wet area ceramic floor tiles to match.\n48 - 1"
)


def test_material_scope_is_noncommercial_and_section_bounded():
    scopes = module.parse_source_material_scope(BATH + LAUNDRY + "WINDOWS & EXTERNAL DOORS", SALE)
    assert len(scopes) == 4 and "laundry_floor_tiles" in scopes


@pytest.mark.parametrize("bad", [
    (BATH + "LAUNDRY\nWINDOWS & EXTERNAL DOORS", SALE),
    ("BATHROOM & ENSUITE\nLAUNDRY\n" + LAUNDRY + "WINDOWS & EXTERNAL DOORS", SALE),
    (BATH + LAUNDRY + "WINDOWS & EXTERNAL DOORS", SALE.replace("porcelain floor tiles", "no covering")),
    (BATH + LAUNDRY + "WINDOWS & EXTERNAL DOORS", SALE.replace("entry kitchen and living", "entry kitchen")),
    (BATH + LAUNDRY + "WINDOWS & EXTERNAL DOORS", SALE.replace("Wet area ceramic floor tiles", "carpet")),
    (BATH + LAUNDRY + "WINDOWS & EXTERNAL DOORS", SALE.replace("48 - 1", "end")),
    (BATH + LAUNDRY + "WINDOWS & EXTERNAL DOORS", ""),
])
def test_missing_cross_source_material_evidence_abstains(bad):
    assert module.parse_source_material_scope(*bad) == ()


def test_invalid_input_types_abstain():
    assert module.parse_source_material_scope({}, SALE) == ()
    assert module.parse_source_material_scope(BATH, None) == ()


def _fake_roster(tmp_path):
    paths = []
    for i, role in enumerate(module.SOURCE_IDS):
        pdf = tmp_path / ("source" + str(i) + ".pdf")
        with fitz.open() as d:
            for _ in range(module.SOURCE_PAGE_COUNTS[role]):
                d.new_page().insert_text((30, 30), "synthetic source")
            d.save(pdf)
        paths.append(pdf)
    return [
        dict(role=role, path=path, sha256=source_sha,
             page_count=module.SOURCE_PAGE_COUNTS[role])
        for (role, source_sha), path in zip(module.SOURCE_IDS.items(), paths)
    ]


def test_fake_sources_cannot_borrow_real_source_sha(tmp_path):
    result = module.inspect_q5446_finish_support(_fake_roster(tmp_path))
    assert result.status == "ABSTAIN"
    assert result.reason_code == "support_source_identity_invalid"
    assert not result.authenticated_customer_quantity and not result.benchmark_score_granted


def test_duplicate_or_missing_supporting_role_blocks(tmp_path):
    roster = _fake_roster(tmp_path)
    assert module.inspect_q5446_finish_support(roster[:1]).reason_code == "supporting_role_missing"
    assert module.inspect_q5446_finish_support(roster + roster[:1]).reason_code == "duplicate_supporting_role"


def test_page_count_claim_must_match_original(tmp_path):
    roster = _fake_roster(tmp_path)
    roster[1]["page_count"] = 1
    assert module.inspect_q5446_finish_support(roster).reason_code == "support_source_identity_invalid"


def test_share_safe_summary_excludes_private_material_and_commercial_grant():
    witness = module.Q5446FinishMaterialWitness(
        status="SUPPORTING_SOURCE_CORROBORATED_NO_QUANTITY",
        source_roles=tuple(module.SOURCE_IDS),
        source_sha256s=tuple(module.SOURCE_IDS.values()),
        supporting_page_numbers=(1, 6),
        corroborated_material_scopes=("bathroom_and_ensuite_floor_tiles", "laundry_floor_tiles"),
    )
    summary = witness.public_summary()
    assert summary["material_scope_count"] == 2
    assert "corroborated_material_scopes" not in summary
    assert "source_text" not in summary and "customer_rows" not in summary
    assert not any(summary[k] for k in (
        "authentic_finished_face_area", "authenticated_customer_quantity", "benchmark_score_granted",
    ))
