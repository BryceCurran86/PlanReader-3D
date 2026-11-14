# Original anonymous wall and doorway source follow-up

Base: original one-app source port d0145d05a677be4d0ee0dca813f7eef854da630c.
Read AGENTS.md/playbook/queues, source room scope, native strip/arc/leaf/gap
builders and canonical-room forwarding. This is a bounded source-selector
follow-up to the one-app owner's work, on an isolated child branch.

Observed counterexamples: an unnamed grey filled rectangular room produced
four strips/one candidate; exactly the same black filled room produced none.
An anonymous black circular door swing plus its unique leaf at a real wall
gap produced no closure; assigning only a wall layer produced one closure.
The first new regression failed before the fix with (0,0) versus (4,1).

Cause: black fills required an explicit wall layer, while the extra dark-fill
adapter excluded black. Arc/leaf extraction still enumerated named wall layers
only, even after the source-ink filter admitted anonymous black strokes.

Change: permit anonymous black narrow bars through the existing source-paint
adapter; named black polygons stay on the original route and are not doubled.
Only in explicit dark-source mode, allow opaque finite black native strokes
into the existing arc+unique-leaf detector. Retain all circularity, jamb/gap,
competing-leaf/arc and source-path checks. Keep raw path indices unchanged.
No new frame evidence from white masks, new geometry engine, guessed doorway
chord, ceiling area, quantity issuer or wall-height assumption.

Default-off source and finished-face gates, 20000 primitive cap, 2.5pt snap,
ordinary named-layer behavior, signed/customer bodies and frozen120 stay
unchanged. Source candidates remain noncommercial and nonmetric.

Validation: 13 new positive/adversarial/source-selector tests pass. Original
private drawing and existing ring/wiring/finished-face regressions are executed
separately. Expected benchmark dimensions/values never determine these rules.
Final exact-head source/CI/retention evidence is recorded in the PR comments.
