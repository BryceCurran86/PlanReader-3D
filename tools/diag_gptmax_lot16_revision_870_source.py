"""Nonpublishing Lot16 original source census for revision and 870 labels.

Structural S10 title is outlined/rasterized, not native PDF text. Its
visual transcription is deliberately NOT promoted into machine source truth.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

import fitz

ARCH_SHA = '10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844'
STRUCT_SHA = 'b40259589dd39a46e45d25e145cfa789d9a9415b50613ebc4fee01dceab6b3d6'
TITLE_CROP = (560, 690, 1191, 842)


def _hash_file(path: Path, expected: str) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise ValueError('immutable original source SHA-256 mismatch')
    return digest


def _native_spans(page, needle: str, *, exact=True):
    rows = []
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines', ()):
            for span in line.get('spans', ()):
                s = span['text'].strip()
                if (s == needle if exact else needle in s):
                    rows.append({'text': s,
                                 'bbox': [round(float(x), 4) for x in span['bbox']],
                                 'direction': [float(x) for x in line['dir']]})
    return rows


def _require_single(page, text: str, *, region=None):
    rows = _native_spans(page, text)
    if region is not None:
        x0, y0, x1, y1 = region
        rows = [r for r in rows if x0 <= r["bbox"][0] and y0 <= r["bbox"][1]
                and r["bbox"][2] <= x1 and r["bbox"][3] <= y1]
    if len(rows) != 1:
        raise ValueError(f'original native source text not unique: {text}')
    return rows[0]


def source_census(architectural: Path, structural: Path) -> dict:
    """Authenticate immutable originals, emit no physical host or quantity."""
    architectural, structural = Path(architectural), Path(structural)
    a_sha = _hash_file(architectural, ARCH_SHA)
    s_sha = _hash_file(structural, STRUCT_SHA)
    with fitz.open(architectural) as a, fitz.open(structural) as s:
        if len(a) != 13 or len(s) != 11:
            raise ValueError('original source page-count mismatch')
        plan, elev, struct_page = a[2], a[4], s[9]
        arch_date = _require_single(plan, '28/07/26', region=(1000, 765, 1080, 790))
        arch_revision = _require_single(plan, 'E', region=(1125, 780, 1170, 810))
        plan_title = _require_single(plan, 'FLOOR PLAN')
        plan_stacker = _require_single(plan, '2127 STACKER')
        elev_stacker = _require_single(elev, '2127 STACKER')
        exact_870 = _native_spans(plan, '870')
        csd_870 = _native_spans(plan, '870 CSD')
        elev_2100 = _native_spans(elev, '2100')
        if len(exact_870) != 10 or len(csd_870) != 1:
            raise ValueError('original 870 label population changed')
        # Structural title has no native text; hash original render, not a guess.
        crop = struct_page.get_pixmap(matrix=fitz.Matrix(2, 2),
                    clip=fitz.Rect(*TITLE_CROP), alpha=False)
        title_hash = hashlib.sha256(crop.samples).hexdigest()
        return {
            'architectural_sha256': a_sha,
            'structural_sha256': s_sha,
            'architectural_plan_page_1based': 3,
            'structural_bracing_page_1based': 10,
            'architectural_title': plan_title,
            'architectural_native_date': arch_date,
            'architectural_native_revision': arch_revision,
            'stacker_native_plan': plan_stacker,
            'stacker_native_elevation': elev_stacker,
            'plan_exact_870_occurrences': exact_870,
            'plan_870_csd_occurrences': csd_870,
            'elevation_2100_occurrences_unbound': elev_2100,
            'stacker_instance_height_mm': 'ABSTAIN',
            'structural_title_visual_review_crop': list(TITLE_CROP),
            'structural_title_render_samples_sha256': title_hash,
            'structural_title_native_text': 'UNAVAILABLE',
            'structural_issue_date': 'REQUIRES_SOURCE_IMAGE_REVIEW',
            'source_revision_applicability': 'ABSTAIN',
            'cross_document_same_physical_wall': 'ABSTAIN',
            'canonical_w4_host': 'ABSTAIN',
            'opening_frame': 'ABSTAIN',
            'opening_area': 'ABSTAIN',
            'opening_count': 'ABSTAIN',
            'new_firm_quantity': False,
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--architectural', type=Path, required=True)
    parser.add_argument('--structural', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = source_census(args.architectural, args.structural)
    body = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(body + '\n')
    else:
        print(body)


if __name__ == '__main__':
    main()
