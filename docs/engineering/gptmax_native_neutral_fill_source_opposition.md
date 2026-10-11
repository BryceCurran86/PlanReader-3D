# GPT MAX — Pale neutral unstroked native fill opposition

## Original-source defect

Authenticated Lot16 Revision E page 3, original PDF SHA
`10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`,
shows the source occurrence underlying native opening
`physical_opening_existence_b222d5310a7df1d632d5daab1a676645` within
the **Area Calculations** title-block table. At this location, page-owned
PyMuPDF `get_drawings()` identifies source paint command `seqno=1682`:
two separate rectangle fills across `x=720.12..821.40`,
`y=721.56..730.80` and `740.04..749.28` PDF points. Their fill is uniform
`(0.960784,0.960784,0.960784)`, type `f`, no stroke. Source PDF native text
identifies adjacent `AREA CALCULATIONS`, `RESIDENCE`, `ALFRESCO`, and
`PORCH` cells. The original G17 physical-opening hypothesis instead uses a
line at `y=730.80` on the pale rectangle's boundary. This is a source
observation and suspected false opening, **not an input predicate**.

The already-merged `native_unstroked_fill_evidence` check authenticates
source bytes, producer snapshot, visible-segment receipts, original path
identity, edge geometry, opacity and paint order but permits only literal
white `(1,1,1)` fill. That narrowly misses neutral PDF table shading, while
correctly rejecting dark walls, chromatic shading and independent strokes.

## Proposed generic, fail-closed repair

Extend the existing **opposing candidate atom only** to exact source-owned
rectangle edges from opaque, nonstroked, very pale neutral fill (every RGB
channel ≥0.95 and ≤1, channel range ≤1/255, independently checked for *every*
G17 support edge). Preserve byte-identical metadata, stable IDs and reason
codes for the original pure-white path. Reject partial ownership, unsupported
strokes, dark/colored fills and missing/corrupt producer receipts. Retain
any opposed G17 raw candidate and explicitly keep source-enumeration
completeness **false**; a pale fill is not itself proof of nonexistence.
No "nearest" text binding, project coordinates, hardcoded opening identity,
scale or count-one is used at runtime.

This work is blocked from integration until a clean PR-base versus exact-head
original Lot16 source comparison proves that the table false positive changes
from G17 existence to authentic opposing candidate while **every original
14 host and nine frame receipt IDs remain unchanged**. The exact source job
currently requires one known problematic false occurrence and no other new
identity churn. Failing original verification is a reason to revise the
general proof, not to change the frozen V2 object universe or manually assign
an opening host. The separate native candidate near right-hand `450`
dimension marks is **still unproved as a generic dimension annotation** and
remains an independent task.

## Non-goals

No change to frozen Full Plan V2 truth, 27 denominator, evaluator,
source drawing, tolerances, W2/W3/W4 identity, opening counts, scale,
quantities, 20,000 source-primitive safety cap or customer output. No
accuracy score is claimed before production source and benchmark reconciliation.
