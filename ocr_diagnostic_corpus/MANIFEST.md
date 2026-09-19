# Murera short-token OCR diagnostic corpus

Built without reference to any expected BOQ count. Ground truth established
by direct visual inspection of the real source page at high DPI (600-1000
DPI crops), independently of the OCR results being evaluated.

Source: `benchmarks/sources/1785347143869-bqs-drawings.pdf`, page 228
(0-indexed 227), "GENERAL LABORATORY FLOOR PLAN".

| File | Ground truth | Category | Notes |
|---|---|---|---|
| `w1_a.png` | `W-1` | positive window tag | with partial "PV" below |
| `w1_b.png` | `W-1` | positive window tag | second physical instance |
| `w1_c.png` | `W-1` | positive window tag | third physical instance, cleanly isolated |
| `w2_a.png` | `W-2` | positive window tag | with "PV" above |
| `w3_a.png` | `W-3` | positive window tag | with "PV" above |
| `w4_a.png` | `W-4` | positive window tag | with "PV" above |
| `d2_a.png` | `D-2` | positive door tag | with partial "PV" below, door-swing arc visible |
| `dim_3250.png` | `3250` (partial: "...00") | dimension figure | comparison category -- longer numeric token |

Also used as comparison/negative examples (already independently confirmed
via a real full-page `WinOCRBackend` run in a prior investigation, not
re-cropped here): title-block text ("MINISTRY OF TRANSPORT..."), room/title
labels ("GENERAL", "LABORATORY"), an area figure ("18.1"), and electrical
labels ("Cir F7"-style, recognized as "Cir F<garbled>"). All of these
WinOCR reads successfully; none are 2-3 character isolated architectural
marks.

**Not found within reasonable search effort:** a `D-1` tag (at least one
exists on the plan per earlier visual inspection, but its exact position
was not confidently relocated at crop-quality resolution). Excluded from
the corpus rather than guessed.

**Known ambiguity discovered while building this corpus:** a region
initially read as "W-6" from a lower-resolution wide crop was, on a
1000 DPI re-check, conclusively a `W-2` (the digit's flat-bottomed "2"
was misread as "6" at lower resolution). No `W-6` tag is confirmed to
exist. This is recorded as a cautionary, real example of exactly the kind
of misread this whole diagnostic effort needs to guard against -- ground
truth here was fixed by re-inspection at higher resolution before being
used in any evaluation, not asserted from a single glance.
