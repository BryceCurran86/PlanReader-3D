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

**W-6 RETRACTION (superseding the note below): a genuine, distinct `W-6`
mark exists.** This corpus originally recorded a "W-6 was actually
misread W-2" finding from an early, lower-resolution pass. A later,
independent re-investigation (this same project, subsequent session)
found the same alcove area on the source page and re-examined it at
900-1400 DPI. At that resolution the "6" is unambiguous and clearly
distinct from "2" -- this is not a rendering artifact or a close call.
The alcove in question (top wall, near the small STORE room adjacent to
the "Fan DP Switch"/"Cir F4" electrical annotations) carries **two
separate, genuinely distinct labels**: `W-2` positioned at the wall line
itself (adjacent to real orange wall-opening hatching), and `W-6`
positioned lower, next to a solid-fill orange vertical stroke inside the
room that is a duct/pipe riser symbol, not a wall-line hatch break.

What remains correctly unresolved, and is NOT settled by this
retraction: whether `W-6` denotes a physical window-type opening at all.
No `W6` type is named anywhere in this drawing package's own window
schedule or BOQ text (only W1-W4 are defined), and `W-6`'s position next
to mechanical/riser geometry rather than a wall-line opening is evidence
against it being a window instance -- but that is a physical-binding
question, not an OCR-legibility one, and this corpus makes no claim
about it either way. This note exists solely to correct the earlier,
premature "misread" conclusion: the mark is real and legible, full stop.
No production quantity has been published based on either the earlier or
the corrected version of this finding, and none is published now.
