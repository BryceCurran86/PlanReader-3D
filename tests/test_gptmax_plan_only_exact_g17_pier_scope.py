"""An original G17 one-plan-page scope does not absorb elevation W4."""
import inspect

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer


def test_exact_plan_g17_cannot_capture_or_assemble_elevation_supplemental_walls():
    body=inspect.getsource(compose_live_wall_opening_authority)
    assert "page_ids=selected_pages" in body
    assert "if include_unmeasured_ink_closed_flanks_shadow" in body
    assert "else _clean_page_ids((*selected_pages, *evidence_pages))" in body
    assert "from_opening_local_exact_g17_source_shadow" in body


def test_original_default_ordinary_opening_local_factory_still_available():
    assert hasattr(PhysicalWallCandidateProducer,
                   "from_opening_local_supplemental_source_visibility_producer")
    assert hasattr(PhysicalWallCandidateProducer,
                   "from_opening_local_exact_g17_source_shadow")
