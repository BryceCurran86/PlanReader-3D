"""The physical opening closure must use the parity-tested indexed broad phase."""
from __future__ import annotations

import pb_physical_opening_authority as opening
from tests import test_physical_opening_candidate_structure_v1 as fixture


def test_candidate_closure_uses_indexed_door_and_gap_detectors(monkeypatch):
    # Long structural wall strokes ensure the detector scope is nonempty.
    source, published = fixture._publish(
        fixture._wall([(20, 330), (360, 600)]) + fixture._jambs([330, 360])
    )
    physical = opening.PhysicalOpeningAuthority(source.authority())
    selector = fixture._selector(
        published, sorted(published.visible_observation_ids)[0]
    )

    def forbidden_legacy(*args, **kwargs):
        raise AssertionError("page-wide legacy detector must not be invoked")

    original_door = opening.detect_door_candidates_indexed
    original_gap = opening.detect_gap_candidates_indexed
    indexed_calls = []

    def door(*args, **kwargs):
        indexed_calls.append("door")
        return original_door(*args, **kwargs)

    def gap(*args, **kwargs):
        indexed_calls.append("gap")
        return original_gap(*args, **kwargs)

    monkeypatch.setattr(opening, "detect_door_candidates", forbidden_legacy)
    monkeypatch.setattr(opening, "detect_gap_candidates", forbidden_legacy)
    monkeypatch.setattr(opening, "detect_door_candidates_indexed", door)
    monkeypatch.setattr(opening, "detect_gap_candidates_indexed", gap)

    outcome = physical.assess_visible_candidate_closure(selector)
    assert outcome.page_id == "1"
    # Candidate-source inventory and final closure each use the same indexed
    # detector pair, never the older page-wide nested scan.
    assert indexed_calls == ["door", "gap", "door", "gap"]
