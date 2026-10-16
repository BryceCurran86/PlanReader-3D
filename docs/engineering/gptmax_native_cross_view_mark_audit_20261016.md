# GPT MAX — native cross-view opening mark census (read-only)

## Observed behavior and source

Tracking: #2396. Original 13-page Lot16 REV E architectural PDF:
SHA256 10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844.
Previous direct original native-PDF audit in #2396 observed 2127 STACKER on
PDF page-index 3 (floor plan) and page-index 5 (ELEVATION 4), plus the page-5
FSL 68560, JL 70660, 2100 and separate 2590 native words.

Files/functions studied: AGENTS.md, AI_ENGINEERING_PLAYBOOK, architecture/spec,
pb_page_title_authority (drawing numbers bind to a title block, not page name),
pb_cross_sheet_callout_evidence.find_callout_references (same label text is
not a positive source callout), pb_opening_kind_authority.resolve_opening_kind
(requires authenticated physical kind/label/schedule), 
pb_opening_host_binding_authority._resolve_raster_source_band_host_from_records
(requires original solid faces/ends AND local W4 ancestry), and
pb_source_visibility_authority._proven_raster_opening_flank_boxes (source
capture nomination alone is not host). Page-3 selected-source height first
abstains at schedule_opening_instance_binding_partial_source_coverage.

The new diagnostic reads immutable native PDF words using PyMuPDF, after a
source-SHA check, and reports every same-line consecutive mark token and
every specified datum word with original page and word bboxes. Duplicates
remain explicit. It does not guess a matching label by nearest or first.
No text source is treated as an authenticated producer observation ID.

## Inference — NOT authority

The repeated 2127 STACKER could refer to the same physical three-panel
sliding glazed opening in two views. The source-figured 2100mm FSL→JL could
be its own height. Neither claim is proved by repeated words or a coincident
datum value. The 2127 mark is not authenticated ordered 2100 x 2700.
The 5.67 m2 proposal is not part of the eight signed original areas.

The tool always emits false for physical cross-sheet identity, authenticated
viewport identity, opening kind, host, datum-to-opening alignment, ordered
width/height, count and FIRM. This is a read-only research census, NOT an
extra authority vocabulary or a production publisher.

## Proposed next producer authority gates

First: producer-issued Elevation 4 viewport rectangle and exact mark
membership; next: positively unique p3 physical-opening-to-p5 elevation
instance lineage; then: measured p5 frame top/base datum ownership and
independent source width. The old nine frames/eight signed receipts cannot
be rewritten; raw opening universe stays incomplete. No generic height
convention is implemented. In particular the separate 2590 is never
silently substituted.

## Tests and immutable original verification

The tests cover source-owned exact boxes, input-order invariance, duplicated
marks, wrong native line/block, nonconsecutive/false-role words, nonfinite
coordinates, invalid page scope, wrong source-SHA, original PDF immutability,
and a two-page datum-positive case that still grants no measurement.

The original-PDF workflow checks the SHA and inventories mark/datum text on
pages 3 and 5. Any failure is a recorded negative, not permission to use OCR,
a neighbour, a label-derived height or a benchmark expected value. It has no
access to frozen truth and does not modify production source, graph, numeric
quantity or customer output.
