# GPT2: original authentic room label present but absent from canonical output

The source-authenticated original Maryborough label replay [#2451](https://github.com/BryceCurran86/PlanReader-3D/pull/2451) produced eight independent positive source-face text bindings including **SALES**; its exact room face receipt was `source_room_face_record_42bef3e350b3cc042f17107fe610f0d8`. The later full production collector [#2467 original artifact 11715380840](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38171199754/artifacts/11715380840) listed 687 canonical physical source face candidates but only seven uniquely source-owned room **labels** (Food Prep, Cold Room, Office, Freezer, PWD, Airlock, Laundry); **SALES** was absent. Neither a matching label string nor bounding-wall proximity is enough to relabel an unrelated floor face.

The read-only `original_source_label_to_canonical_first_gates` combines a **fresh original-SHA-authenticated** positive SourceRoomFace + SourceRoomLabel replay (source wall and text provenance verified by the previously merged [#2446](https://github.com/BryceCurran86/PlanReader-3D/pull/2446) and [#2451](https://github.com/BryceCurran86/PlanReader-3D/pull/2451) diagnostics) with a separately replayed **live** `collect_live_physical_net_wall_claim` from the exact original PDF in the SAME CI run.

Every positive label is joined to canonical room candidates **only by exact original physical face RECORD receipt ID**, not by matching words or area. Once one exact room face is found, the ledger checks source PDF SHA, true page7 scope, canonical room ID, literal label, and original native-source text observation IDs. First possible failures are:

- `ORIGINAL_SOURCE_FACE_MISSING_IN_CANONICAL` (no matching source face receipt)
- `ORIGINAL_SOURCE_FACE_DUPLICATED_IN_CANONICAL`
- `CANONICAL_FACE_SOURCE_PROVENANCE_MISMATCH`
- `CANONICAL_ROOM_LABEL_BINDING_UNAVAILABLE`
- `CANONICAL_ROOM_LABEL_LITERAL_CONFLICT`
- `ORIGINAL_TEXT_RECEIPTS_NOT_RETAINED_IN_CANONICAL`
- `ORIGINAL_SOURCE_LABEL_PROJECTION_PRESENT`

The last state is a semantic source projection **only**, not an authentic metric, physical scale, finish, commercial claim, or benchmark accuracy. Original scope, positive source face IDs and native text observation IDs may not be reused to assert multiple different rooms; typed/adversarial regressions reject forged or duplicate identities. This is source first-failure engineering evidence to determine whether original **Sales** is lost by original face publication, direct label binding, or source text ancestry after source composition. It does **not** change room geometry, wall hosts, finish, quantities, evaluator or score.

Other missing rooms POS COUNTER, FOOD SERVICE, WASH UP, TRUCK DRIVER LOUNGE, M-AMB, F-AMB still require genuine original W4 physical separators and closed polygons. FREEZER metric remains unavailable. DRY STORE remains ABSTAIN. Full Plan V2 truth/24+27 denominators/tolerances and 20,000 source primitive safety cap are untouched.
