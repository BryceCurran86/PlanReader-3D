"""Guard the explicit floor-area-only runtime switch without weakening full runs."""
from __future__ import annotations

from pathlib import Path

import pytest

import pb_live_physical_net_wall_integration as live


@pytest.mark.parametrize("selected, expected", [(True, True), (False, False)])
def test_public_collector_forwards_surface_semantic_selection(monkeypatch, selected, expected):
    marker = object()
    seen = []

    def fake_collector(path, **kwargs):
        seen.append(kwargs["include_surface_finishes"])
        return marker

    monkeypatch.setattr(live, "_collect_live_physical_net_wall_claim", fake_collector)
    assert live.collect_live_physical_net_wall_claim(
        Path("not-opened.pdf"), include_surface_finishes=selected
    ) is marker
    assert seen == [expected]


def test_default_full_surface_path_remains_enabled(monkeypatch):
    seen = []
    marker = object()

    def fake_collector(path, **kwargs):
        seen.append(kwargs["include_surface_finishes"])
        return marker

    monkeypatch.setattr(live, "_collect_live_physical_net_wall_claim", fake_collector)
    assert live.collect_live_physical_net_wall_claim(Path("not-opened.pdf")) is marker
    assert seen == [True]


@pytest.mark.parametrize("invalid", [None, 0, 1, "False"])
def test_surface_semantic_selection_rejects_non_bool(invalid):
    with pytest.raises(ValueError, match="explicit boolean"):
        live.collect_live_physical_net_wall_claim(
            Path("not-opened.pdf"), include_surface_finishes=invalid
        )
