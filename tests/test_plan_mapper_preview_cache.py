from __future__ import annotations

import io
import tempfile
from pathlib import Path
from unittest import mock

from PIL import Image

import pb_planreader_3d_app as app


def test_mapper_preview_cache_reuses_unchanged_source() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        path = Path(tmp) / "plan.png"
        Image.new("RGB", (1800, 1200), "white").save(path)
        app._plan_mapper_preview_cached.cache_clear()

        real_open = app.Image.open
        calls: list[str] = []

        def counted_open(*args, **kwargs):
            calls.append(str(args[0]))
            return real_open(*args, **kwargs)

        with mock.patch.object(app.Image, "open", side_effect=counted_open):
            first = app.plan_mapper_preview(str(path), 900)
            second = app.plan_mapper_preview(str(path), 900)

        assert first is not None
        assert second == first
        assert len(calls) == 1

        payload, original_w, original_h, display_w, display_h = first
        assert (original_w, original_h) == (1800, 1200)
        assert (display_w, display_h) == (900, 600)
        with Image.open(io.BytesIO(payload)) as preview:
            assert preview.size == (900, 600)


def test_mapper_preview_invalidates_when_source_changes() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        path = Path(tmp) / "plan.png"
        Image.new("RGB", (1800, 1200), "white").save(path)
        app._plan_mapper_preview_cached.cache_clear()

        first = app.plan_mapper_preview(str(path), 900)
        assert first is not None

        Image.new("RGB", (1600, 1000), "white").save(path)
        second = app.plan_mapper_preview(str(path), 900)

        assert second is not None
        assert second != first
        assert second[1:5] == (1600, 1000, 900, 562)


def test_mapper_display_scale_preserves_source_pixel_coordinates() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        path = Path(tmp) / "plan.png"
        Image.new("RGB", (1800, 1200), "white").save(path)
        app._plan_mapper_preview_cached.cache_clear()

        preview = app.plan_mapper_preview(str(path), 900)
        assert preview is not None
        _payload, original_w, original_h, display_w, display_h = preview

        display_scale = display_w / float(original_w)
        assert display_scale == 0.5
        assert display_h / float(original_h) == display_scale

        # Existing mapper conversion divides canvas coordinates by this scale.
        canvas_x, canvas_y, canvas_w, canvas_h = 225.0, 150.0, 300.0, 200.0
        assert canvas_x / display_scale == 450.0
        assert canvas_y / display_scale == 300.0
        assert canvas_w / display_scale == 600.0
        assert canvas_h / display_scale == 400.0


def test_mapper_preview_cache_is_bounded() -> None:
    assert app._plan_mapper_preview_cached.cache_info().maxsize == 8
