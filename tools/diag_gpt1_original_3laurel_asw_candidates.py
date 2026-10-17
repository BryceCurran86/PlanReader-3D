"""Read-only original 3Laurel native ASW source candidate census.

The identified dimension pairs are not FIRM quantities without separately
authenticated physical opening identity, structural host and complete frame.
Never use frozen benchmark truth or target IDs to interpret source drawing.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import argparse
import json
import re

import fitz

ORIGINAL_SHA256 = "014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e"
PLAN_PAGE_1BASED = 3
_NUM = re.compile(r"(?:[1-9][0-9]{0,3}|[1-9][0-9]?,[0-9]{3})\Z")


def _dimension(text: str) -> int | None:
    return int(text.replace(",", "")) if _NUM.fullmatch(text) else None


def _same_line(words):
    return len({(w[5], w[6]) for w in words}) == 1 and all(
        a[7] + 1 == b[7] for a, b in zip(words, words[1:])
    )


def _bbox(words):
    return [round(float(v), 4) for v in (
        min(w[0] for w in words), min(w[1] for w in words),
        max(w[2] for w in words), max(w[3] for w in words),
    )]


def _original_token_chain(words):
    """Require a single native line or two adjacent stacked native lines.

    Some original CAD callouts wrap the final dimension or ASW type to the
    following printed line. Consecutive original tokens and intersecting native
    text columns are necessary for a candidate, never a physical host grant.
    """
    lines = []
    for word in words:
        pair = (word[5], word[6])
        if pair not in lines:
            lines.append(pair)
    if len(lines) > 2:
        return None
    if len(lines) == 1:
        return "same_native_line" if _same_line(words) else None
    if len(lines) != 2:
        return None
    sequence = [(w[5], w[6]) for w in words]
    if sum(a != b for a, b in zip(sequence, sequence[1:])) != 1:
        return None
    first = [w for w in words if (w[5], w[6]) == lines[0]]
    second = [w for w in words if (w[5], w[6]) == lines[1]]
    if (not _same_line(first) or not _same_line(second)
            or min(w[1] for w in second) - min(w[1] for w in first) > 12.5
            or min(w[1] for w in second) - min(w[1] for w in first) < 1.0):
        return None
    first_x = (min(w[0] for w in first), max(w[2] for w in first))
    second_x = (min(w[0] for w in second), max(w[2] for w in second))
    if min(first_x[1], second_x[1]) - max(first_x[0], second_x[0]) <= 0:
        return None
    return "stacked_native_lines"


def read_original_3laurel_asw_candidates(original_pdf: bytes) -> dict:
    if type(original_pdf) is not bytes or sha256(original_pdf).hexdigest() != ORIGINAL_SHA256:
        raise ValueError("SHA-verified original 3Laurel PDF required")
    doc = fitz.open(stream=original_pdf, filetype="pdf")
    try:
        if len(doc) != 18:
            raise ValueError("original 3Laurel page universe changed")
        page = doc[PLAN_PAGE_1BASED - 1]
        words = page.get_text("words", sort=False)
        if not any(w[4] == "Floor" for w in words) or not any(w[4] == "Plan" for w in words):
            raise ValueError("original floor-plan title not authenticated")
        legend = [
            words[i:i + 4] for i in range(len(words) - 3)
            if [w[4].upper() for w in words[i:i + 4]]
            == ["ASW", "-", "ALU.", "SLIDING"] and _same_line(words[i:i + 4])
        ]
        if len(legend) != 1:
            raise ValueError("source ASW window legend is ambiguous or absent")
        candidates = []
        unbound_asw = []
        occupied = set()
        claimed_asw_indices = set()
        for i in range(len(words) - 3):
            quartet = words[i:i + 4]
            left = _dimension(quartet[0][4])
            right = _dimension(quartet[2][4])
            if (left is None or right is None or quartet[1][4] != "-"
                    or quartet[3][4].lower() != "asw"):
                continue
            line_layout = _original_token_chain(quartet)
            if line_layout is None or not 300 <= left <= 6000 or not 300 <= right <= 6000:
                continue
            obscured = (i + 4 < len(words) and words[i + 4][4].lower() == "obs"
                        and _same_line(words[i + 3:i + 5]))
            native_words = words[i:i + 5] if obscured else quartet
            source = {
                "native_block": quartet[0][5], "native_line": quartet[0][6],
                "first_word": quartet[0][7], "bbox_pdf_pt": _bbox(native_words),
                "line_layout": line_layout,
            }
            address = tuple(source[k] for k in ("native_block", "native_line", "first_word"))
            if address in occupied or i + 3 in claimed_asw_indices:
                raise ValueError("duplicate source address; cannot count as distinct")
            occupied.add(address)
            claimed_asw_indices.add(i + 3)
            candidates.append({
                "source": source, "figured_axes_mm": [left, right],
                "native_mark": " ".join(w[4] for w in native_words),
                "source_label_semantic": "aluminium sliding window",
                "obscured_suffix": obscured,
                "arithmetic_product_m2": round(left * right / 1e6, 6),
                "metric_authority": "candidate_only",
                "physical_opening_identity_proven": False,
                "structural_host_proven": False,
                "signed_quantity_allowed": False,
            })
        for i, word in enumerate(words):
            if word[4].lower() != "asw" or i in claimed_asw_indices:
                continue
            if [str(w[4]).upper() for w in words[i:i + 4]] == [
                "ASW", "-", "ALU.", "SLIDING"
            ]:
                continue
            unbound_asw.append({
                "source": {"native_block": word[5], "native_line": word[6],
                           "native_word": word[7], "bbox_pdf_pt": _bbox([word])},
                "kind": "not_a_two_axis_metric_claim",
                "metric_authority": "abstain",
            })
        return {
            "schema": "gpt1.3laurel.original_native_asw_candidates.v1",
            "source_sha256": ORIGINAL_SHA256, "source_pdf_pages": len(doc),
            "page_number": PLAN_PAGE_1BASED, "legend": "ASW - ALU. SLIDING",
            "two_axis_candidates": sorted(candidates, key=lambda p: (
                p["source"]["native_block"], p["source"]["native_line"],
                p["source"]["first_word"],
            )),
            "non_metric_asw_observations": unbound_asw,
            "all_candidates_require_host_and_physical_identity": True,
            "customer_quantity_count": 0,
            "official_benchmark_match_count": None,
            "source_pdf_bytes_disclosed": False,
        }
    finally:
        doc.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.pdf.resolve() == args.output.resolve():
        raise ValueError("original PDF cannot be overwritten")
    receipt = read_original_3laurel_asw_candidates(args.pdf.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "two_axis_candidates": len(receipt["two_axis_candidates"]),
        "abstentions": len(receipt["non_metric_asw_observations"]),
        "signed_firm_quantities": 0,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
