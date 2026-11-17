"""Plan Mapper retains source-authenticated door + finishes behind review gates."""
import ast
from pathlib import Path


def test_plan_mapper_shows_source_matched_doors_without_any_automatic_billable_area():
    root=Path(__file__).resolve().parents[1]
    src=(root/"pb_planreader_3d_app.py").read_text(encoding="utf-8")
    tree=ast.parse(src)
    mapper=next(x for x in tree.body
                if isinstance(x,ast.FunctionDef) and x.name=="plan_mapper_page")
    body=ast.get_source_segment(src,mapper)
    assert "source_internal_door_completeness" in body
    assert "hosted_swing_count" in body
    assert "cavity_slider_geometry_authenticated_count" in body
    assert "Physical opening approved" in body
    assert "Door areas and frozen scoring are NOT authorised" in body
    assert "source_sha" in body or "_laurel_original_sha" in body


def test_independent_22_family_customer_issuance_is_explicit_opt_in():
    root=Path(__file__).resolve().parents[1]
    src=(root/"pb_planreader_3d_app.py").read_text(encoding="utf-8")
    tree=ast.parse(src)
    mapper=next(x for x in tree.body
                if isinstance(x,ast.FunctionDef) and x.name=="plan_mapper_page")
    body=ast.get_source_segment(src,mapper)
    assert "native_trace.get(\"digest\")==_laurel_original_sha" in body
    assert "Verify original and prepare 22 customer review rows" in body
    assert "issue_original_three_laurel_22_finish_customer_rows" in body
    assert "Export 22 signed source review rows (CSV)" in body
    assert "source-verified output for review" in body.lower()
    assert "all_rooms_physically_authenticated" not in body
