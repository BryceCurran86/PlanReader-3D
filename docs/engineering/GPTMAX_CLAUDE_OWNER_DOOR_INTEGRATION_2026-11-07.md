# Owner-door review integration with source-owned height policy

Prepared as a non-force integration child of preserved Claude #4211
`9ede7e24f1919f9a135d17941e5eef572ec21834` and MAX #4227
`413c9e5d1ffa243d7e1c40fc9724949b2984ac79`. Claude continues 3Laurel;
MAX claimed these exact conflicts on #4135. The active #4227 head is unchanged.

The composer retains Claude's explicit owner-approved second-axis review path
and MAX's rejection of page-wide inferred heights. The conflicting old
uniform-height area block is removed. The handoff collector, review export
and template export all receive the same disabled inference option.
Glyph-ledger trust stays default-off. Review-required quantities remain outside
the standard source-corroborated seal and standard customer rows.

Three regressions reject the naive merge: both optional-lane option-forwarding
tests and the existing customer handoff guard fail while inference is enabled.
After resolving the policy consistently, the focused owner-door/glyph,
composer, issuer, seal and customer suites pass **683 tests**, with six
optional/original-only skips. Undefined-name and diff checks pass.

The combined owner/glyph and raster/source regression set subsequently passes
746 tests, with six optional/original-only skips. This includes a reproduced
glyph-trust defect: a second upgrade pass previously omitted already-trusted
words from its fresh ledger and could then trust an opposite mapping for the
same font-program/glyph key. The new adversarial trace regression fails on
the parent. One proof policy is now fixed per immutable revision; equivalent
repeats mint no receipts and perform no OCR, while changed page/threshold/
budget requests require a fresh producer. Existing first-pass source proofs
and default-off behavior are unchanged. New receipts are prepared together
before the producer applies them.

The independent raster-only reader candidate has published tree
`eb10fd0e3416a58fd81953585b745071820c566f` and completes the original
Maryborough three-quantity sealed/customer run in 383.656s, with both full
files equal to historical hashes, versus 659.607s on merged #4227. This is
supporting runtime proof; the full combined owner/glyph integration still
needs its own protected original acceptance and final-head dual-Python CI.

This is integration preparation, not original-source acceptance or a new
quantity. Final-head dual-Python CI, explicit-review isolation and original
signed/customer retention are still required before release. Private originals,
frozen 120, reference truth, cap and snap are unchanged.
