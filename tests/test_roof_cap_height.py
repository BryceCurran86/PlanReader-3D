"""A roof cap does not sit at 2.7 m when no wall height is printed."""
from pb_roof_envelope_v140 import roof_caps


class _App:
    def build_precision_prisms(self, _wid):
        return [{"points": [(0, 0), (4, 0), (4, 3)], "triangles": [], "level_name": "Level 2"}]

    def workspace_setting(self, *_args):
        return ""

    def lquery(self, *_args):
        return []


def test_printed_wall_height_stays_and_a_missing_height_makes_no_cap() -> None:
    caps = roof_caps(_App(), 1, [{"height_m": 3.2}])
    assert caps[0]["z"] == 3.2
    assert roof_caps(_App(), 1, [{"height_m": None}, {}]) == []
