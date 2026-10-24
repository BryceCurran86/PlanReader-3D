"""Gold-free shadow geometry proof; original positive requires private source."""
import hashlib
import os
from pathlib import Path

import fitz
import pytest

from pb_gptmax_native_filled_scale_shadow import find_native_filled_scale_bar_shadows


def _synthetic(*, count=5, x=40, y=50, width=20, height=3, missing=None,
               colour=(0, 0, 0), opacity=1, wrong_label=None,
               extra_bar=False, stroked=False, uniform_row=False):
    doc = fitz.open()
    page = doc.new_page(width=500, height=250)

    def add_bar(x0, y0):
        for i in range(count):
            if i == missing:
                continue
            top = y0 + (0 if (i % 2 or uniform_row) else height)
            rect = fitz.Rect(x0 + i * width, top, x0 + (i + 1) * width, top + height)
            page.draw_rect(rect, fill=colour, color=(0, 0, 0) if stroked else None,
                           fill_opacity=opacity)
        for i in range(count + 1):
            label = str(i) if i < count else f'{count}m'
            if i == wrong_label:
                label = 'unknown'
            bx = x0 + i * width
            page.insert_text((bx - len(label) * 2.4, y0 + 2 * height + 10), label,
                             fontsize=8, fontname='helv')

    add_bar(x, y)
    if extra_bar:
        add_bar(x, y + 70)
    content = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return content


def _scan(data, *, page_id='1', digest=None):
    return find_native_filled_scale_bar_shadows(
        data, expected_source_sha256=digest or hashlib.sha256(data).hexdigest(), page_id=page_id)


def test_alternating_native_fill_positive_and_deterministic_replay():
    data = _synthetic()
    first = _scan(data)
    assert len(first) == 1
    assert first == _scan(data)
    assert len(first[0].drawing_indices) == 5
    assert first[0].physical_span_mm == 5000
    assert first[0].source_span_pt == pytest.approx(100)
    assert first[0].points_per_mm == pytest.approx(0.02)


@pytest.mark.parametrize('delta_x,delta_y,scale', [(12, 20, 1), (0, 0, 2), (32, 30, 0.75)])
def test_translation_and_uniform_scale_invariance(delta_x, delta_y, scale):
    data = _synthetic(x=40 + delta_x, y=50 + delta_y,
                      width=20 * scale, height=3 * scale)
    result = _scan(data)
    assert len(result) == 1
    assert result[0].points_per_mm == pytest.approx(20 * scale / 1000)


@pytest.mark.parametrize('kwargs', [
    {'missing': 2}, {'colour': (0.1, 0.1, 0.1)},
    {'opacity': 0.7}, {'wrong_label': 3}, {'stroked': True},
    {'uniform_row': True},
])
def test_source_paint_and_label_negatives(kwargs):
    assert _scan(_synthetic(**kwargs)) == ()


def test_competing_equally_scaled_bars_retained_not_elected():
    candidates = _scan(_synthetic(extra_bar=True))
    assert len(candidates) == 2
    assert candidates[0].drawing_indices != candidates[1].drawing_indices
    assert candidates[0].points_per_mm == candidates[1].points_per_mm
    # A consumer MUST abstain unless a separate authority resolves rivals.


def test_sha_and_page_scope_fail_closed():
    data = _synthetic()
    assert _scan(data, digest='0' * 64) == ()
    assert _scan(data, page_id='2') == ()
    assert _scan(data, page_id='not-a-page') == ()


def test_private_original_source_positive_if_provisioned():
    path = os.environ.get('THREELAUREL_ARCH_ORIGINAL')
    if not path:
        pytest.skip('private original source not provisioned; no source-positive claim')
    data = Path(path).read_bytes()
    expected = '014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e'
    assert hashlib.sha256(data).hexdigest() == expected
    candidates = _scan(data, page_id='3')
    assert len(candidates) == 1
    assert len(candidates[0].drawing_indices) == 10
    assert len(candidates[0].text_witnesses) == 11
    assert candidates[0].source_span_pt == pytest.approx(283.46502685546875, abs=1e-3)
    assert candidates[0].physical_span_mm == 10000
