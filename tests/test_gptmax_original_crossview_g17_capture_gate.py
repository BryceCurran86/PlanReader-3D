"""Original plan/elevation wall cross-view doesn't turn p5 into a G17 plan."""
import inspect
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer


def test_paired_plan_and_elevation_source_captures_plan_only():
    src=inspect.getsource(compose_live_wall_opening_authority)
    assert "page_ids=selected_pages," in src
    assert "source_visibility_producer.augment_with_unmeasured_g17_flanks_source_shadow(" in src
    assert "page_ids=_clean_page_ids((*selected_pages, *evidence_pages))" in src
    assert src.index("augment_with_unmeasured_g17_flanks_source_shadow(") < src.index(
        "PhysicalWallCandidateProducer.from_source_visibility_producer("
    )
    assert "include_unmeasured_ink_closed_flanks_shadow=alternate" not in src


def test_original_commercial_wall_factory_keeps_historical_public_signature():
    assert set(inspect.signature(
        PhysicalWallCandidateProducer.from_source_visibility_producer
    ).parameters) == {"source_visibility_producer","page_ids"}
