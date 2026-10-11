# Maryborough physical room-face first owner: original-source audit

This is a read-only source-replay diagnostic for the original
`Arch_Combined_Maryborough_Service_Station.pdf`, source SHA
`b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`.
It reproduces production's page-selection semantics exactly:
`pages=(6,), topology_pages=(6,), room_area_support_pages=(10,)`,
meaning original PDF pages **7** and **11** (1-indexed). Only page 7
may mint physical topology. Page 11 is source-decoded support evidence,
never a new physical room boundary.

## First failing producer authority

The diagnostic composes the existing sealed SourceVisibility, W2/W4
physical wall/opening, and SourceRoomFace producers. It reports both:

- page-wide `wall-source:page-7` wall/room scopes
- each **source-authenticated** `FLOOR_PLAN` viewport scope, if any

No caller-supplied viewport rectangle, named room, wall identity, finish,
measurement, or original-source quantity enters the producer. Each wall
scope is paired with the exact room-face selector from the *same*
document/revision/SHA/snapshot/page/decision-scope lineage. Foreign,
duplicated or missing room face identities are rejected.

The diagnostic counts original producer wall candidates, published room
face receipts and **withheld** room faces by original abstention reason,
then distinguishes:

- `PHYSICAL_WALL_SCOPE_NOT_AUTHENTICATED`
- `SOURCE_ROOM_FACE_SCOPE_NOT_AUTHENTICATED`
- `PARTIAL_SOURCE_ROOM_FACE_UNIVERSE`
- `SOURCE_ROOM_FACE_SCOPE_AVAILABLE_NOT_A_METRIC_ROOM_PROOF`

These categories locate a source authority stage. Even the last category
does **not** prove room labels, physical scale, floor finishes, areas or
customer publication. All host, room, quantity, physical equivalence and
accuracy publication remain forbidden.

## Why the verification is needed

[GPT2 original-source run 38122351338](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38122351338)
previously passed the strict source controls Food Prep 13.270425 m²,
Cold Room 25.37875 m² and Office 9.05352 m² and reported 687 raw
canonical room/floor entries. This does **not** authenticate every face:
subsequent source-owner hardening can legitimately exclude unsupported
edges.

[GPT MAX W4 run 38151295279](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38151295279)
failed the original exact firm FOOD PREP receipt check, while the newer
source-room authority already recorded zero canonical rooms in an
instrumented run. The live composition modules used to orchestrate
topology are byte-identical across those two source points. Changes
to `pb_source_room_face_authority.py`,
`pb_source_room_label_authority.py`, and
`pb_source_visibility_authority.py` require this *scope-local* proof
before any substantive correction. Do not force a label, set area
constants, infer a contained owner for an explicitly indexed foreign
W4 wall, or change a benchmark expected quantity to make the old
count appear.

Run using SHA-verified source bytes:

```bash
PYTHONPATH=. python tools/diag_gptmax_maryborough_room_first_owner_gate.py \
  --pdf 'documents/sources/Arch_Combined_Maryborough_Service_Station.pdf' \
  --expected-source-sha b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007 \
  --output original-maryborough-room-first-owner.json
```

The original PDF CI source job and Python 3.13/3.14 adversarial
regressions must pass. This is diagnostic-only; the separate existing
Maryborough grid-component workflow keeps its strict three-room
QuantityEvidence controls. Frozen Full Plan V2 truth, evaluator,
denominators, tolerances and the 20,000 original primitive cap remain
unchanged.


## Second diagnostic stage — actual source-room label owners

The source-verified original run from [#2446](https://github.com/BryceCurran86/PlanReader-3D/pull/2446),
[artifact 11709139348](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38156449123/artifacts/11709139348),
determined the exact first failures on Maryborough PDF page 7:

| Producer scope | Wall candidates | Positive physical faces | Withheld faces | First gate |
| --- | ---: | ---: | ---: | --- |
| Page-wide | 3737 | 0 | 0 | source room face scope unavailable |
| Authenticated `FLOOR_PLAN` viewport `view_p7_2` | 3467 | 687 | 511 | partial physical face universe |

Of the 511 withheld faces, 505 have the original reason
`source_room_face_tiny_or_degenerate` and six have
`source_room_face_boundary_unresolved`. Their negative receipts remain
negative. The source returned 687 positive face records, but these are
**not** 687 proven labelled rooms, floor quantities or whole-page
completeness. The composer's candidate rooms cannot be assumed to be
source-complete merely because there are many raw faces.

This follow-up stage invokes the **existing production**
`SourceRoomLabelProducer.from_authorities` with the separately
source-authenticated viewport's `SourceRoomFaceAuthority`, same
SHA/revision/snapshot/decision scope. It records the exact positive
physical face receipt on every direct label and the exact original
constituent physical faces behind each unresolved split-label
`CANDIDATE`. It rejects mismatched source revision, cross-scope labels,
duplicate original text observation IDs, duplicate physical face
identities or a split label missing its authenticated source face.

This diagnoses whether Food Prep, Cold Room and Office fail at original
positive text ownership, split-face binding, incomplete physical
room-face universe or the **later** documented-area/QuantityEvidence
gate. It never infers a room from OCR, promotes a split label to
`CORROBORATED`, replaces missing W4 wall owners by proximity, publishes
an area or changes frozen benchmark truth. All floor and room quantities
continue to depend on existing production physical and metric
authority.
