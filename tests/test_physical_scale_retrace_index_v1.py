"""Indexed reverse-retrace lookup must preserve physical-scale semantics."""
from __future__ import annotations

from typing import Sequence

import pb_physical_scale_authority as scale_module


def _segment(
    observation_id: str,
    primitive_ref: str,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    duplicates: tuple[str, ...] = (),
):
    return scale_module._VisibleSegment(
        observation_id=observation_id,
        source_primitive_ref=primitive_ref,
        start=start,
        end=end,
        duplicate_observation_ids=duplicates,
    )


def _legacy_coalesce(
    segments: Sequence[scale_module._VisibleSegment],
) -> tuple[scale_module._VisibleSegment, ...]:
    consumed: set[str] = set()
    normalized: list[scale_module._VisibleSegment] = []
    for segment in sorted(segments, key=lambda item: item.observation_id):
        if segment.observation_id in consumed:
            continue
        position = scale_module._primitive_position(segment)
        matches = []
        if position is not None:
            drawing_index, primitive_index = position
            for other in segments:
                other_position = scale_module._primitive_position(other)
                if (
                    other.observation_id != segment.observation_id
                    and other.observation_id not in consumed
                    and other_position is not None
                    and other_position[0] == drawing_index
                    and abs(other_position[1] - primitive_index) == 1
                    and scale_module._distance(segment.start, other.end) <= 1e-6
                    and scale_module._distance(segment.end, other.start) <= 1e-6
                ):
                    matches.append(other)
        if len(matches) == 1:
            other = matches[0]
            consumed.add(other.observation_id)
            normalized.append(
                scale_module._VisibleSegment(
                    observation_id=segment.observation_id,
                    source_primitive_ref=segment.source_primitive_ref,
                    start=segment.start,
                    end=segment.end,
                    duplicate_observation_ids=tuple(
                        sorted(
                            (
                                *segment.duplicate_observation_ids,
                                *other.observation_ids,
                            )
                        )
                    ),
                )
            )
        else:
            normalized.append(segment)
        consumed.add(segment.observation_id)
    return tuple(normalized)


def test_indexed_retrace_lookup_matches_legacy_decisions() -> None:
    segments = (
        # One valid adjacent reverse retrace.
        _segment("a0", "visible:segment:d1i10", (0.0, 0.0), (10.0, 0.0)),
        _segment(
            "a1",
            "visible:segment:d1i11",
            (10.0, 0.0),
            (0.0, 0.0),
            duplicates=("existing-provenance",),
        ),
        # Same geometry but non-adjacent: must stay distinct.
        _segment("b0", "visible:segment:d2i20", (0.0, 5.0), (10.0, 5.0)),
        _segment("b1", "visible:segment:d2i22", (10.0, 5.0), (0.0, 5.0)),
        # Adjacent primitive from a different drawing path: must stay distinct.
        _segment("c0", "visible:segment:d3i30", (0.0, 10.0), (10.0, 10.0)),
        _segment("c1", "visible:segment:d4i31", (10.0, 10.0), (0.0, 10.0)),
        # Adjacent but not a reverse retrace.
        _segment("d0", "visible:segment:d5i40", (0.0, 15.0), (10.0, 15.0)),
        _segment("d1", "visible:segment:d5i41", (0.0, 15.0), (10.0, 15.0)),
        # Two valid adjacent matches make the relation ambiguous and preserve all.
        _segment("e0", "visible:segment:d6i50", (0.0, 20.0), (10.0, 20.0)),
        _segment("e1", "visible:segment:d6i49", (10.0, 20.0), (0.0, 20.0)),
        _segment("e2", "visible:segment:d6i51", (10.0, 20.0), (0.0, 20.0)),
        # Non-native source refs are untouched.
        _segment("r0", "visible:raster_segment:r1", (0.0, 25.0), (10.0, 25.0)),
        _segment("r1", "visible:raster_segment:r2", (10.0, 25.0), (0.0, 25.0)),
        # Even malformed duplicate observation IDs retain the legacy first-item
        # behavior rather than borrowing another segment's primitive position.
        _segment("zdup", "visible:segment:d7i70", (0.0, 30.0), (10.0, 30.0)),
        _segment("zmatch", "visible:segment:d7i71", (10.0, 30.0), (0.0, 30.0)),
        _segment("zdup", "visible:segment:d7i90", (0.0, 35.0), (10.0, 35.0)),
    )

    assert scale_module._coalesce_retraced_segments(segments) == _legacy_coalesce(segments)


def test_native_primitive_positions_are_parsed_once_per_visible_segment(
    monkeypatch,
) -> None:
    segments = tuple(
        _segment(
            f"obs-{index:04d}",
            f"visible:segment:d{index // 100}i{index % 100}",
            (float(index), 0.0),
            (float(index) + 0.5, 0.0),
        )
        for index in range(1200)
    )
    original = scale_module._primitive_position
    calls = 0

    def counted(segment):
        nonlocal calls
        calls += 1
        return original(segment)

    monkeypatch.setattr(scale_module, "_primitive_position", counted)

    result = scale_module._coalesce_retraced_segments(segments)

    assert result == segments
    assert calls == len(segments)
