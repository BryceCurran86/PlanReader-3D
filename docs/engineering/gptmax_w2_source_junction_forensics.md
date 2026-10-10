# GPT MAX — W2 source/junction forensic guard

This is a read-only companion to the exact opening-host retention audit (PR #2136).
It cannot prove wall continuity or publish openings, wall hosts, frames,
physical counts, quantities or frozen benchmark accuracy. It never modifies W2,
W4, source capture, snapping, source projection, scale, or the 20,000 primitive cap.

## Reproducible source failure

The original Lot16 experiment is archived in branch
experiment/gptmax-compact-pixel-footprint-blocked-20261010,
at docs/engineering/gptmax_compact_capture_failed_retention.json.
The source SHA in that record is
10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844.
This is source evidence only, never a frozen denominator comparison.

The shared genuine original raster source primitive ending :1567 supports
the original W4 wall candidate and the added-capture W4 wall candidate.
The original wall consists of two source edge fragments;
the new candidate has three, with an additional snapped near-junction at
(380.64, 342.72) in PDF page-points. In both cases the local source edge
fragments still omit the interval 336.75..338.75 along the wall axis.
The full original parent line does not prove the local W2 gap.
The experiment therefore loses the existing authenticated host and frame for
physical opening 38c03575cd66ed19cae7f9e4489f1609.
The resulting 23 physical identities / 17 hosts / 8 frames cannot replace
the existing retained 23 / 14 / 9, because it regresses a proven identity.

## How to use

Run this audit on the existing archived diagnostic (no new source extraction):

    PYTHONPATH=. python -m pytest -q tests/test_gptmax_w2_source_junction_forensics.py
    PYTHONPATH=. python tools/gptmax_w2_source_junction_forensics.py --input /path/to/gptmax_compact_capture_failed_retention.json --output /tmp/gptmax_w2_source_gap_forensics.json

The output groups wall records only by unique exact source ancestry. Multiple
walls from the same source ancestry remain explicitly ambiguous. Each paired
record preserves its own aligned source intervals, unproven interior gaps,
off-axis source fragments and snapped centerline offsets in PDF page points.
Input damage (missing/duplicate parent, nonfinite or malformed geometry) is an
error, not zero or a host fallback. The float comparison epsilon only controls
diagnostic coordinate stability; it is not a geometric authority tolerance.

## Acceptance gate for a future production change

Before considering a #2032 successor, prove the W2 junction belongs to its
exact local source edge and physical wall rather than a compact raster neighbor.
Show uninterrupted same-source continuous local coverage of the currently
unproven 336.75..338.75 interval, or keep its host/frame ABSTAIN in the
experiment. No invented interpolation or remote parent extent. Run the existing
real Lot16 and Maryborough source parity workflows, exact physical-opening
host/frame retention, both Python matrix checks, and frozen integrity checks.
Keep #2032 and #2078 draft while their original regression gates fail.
