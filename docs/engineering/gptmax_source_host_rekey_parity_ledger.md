# GPT MAX — original-source W4 host/frame rekey parity (read-only)

Original Lot16 source PDF SHA **10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844**. Archived real source CI run [#38068100685](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38068100685) comparing source baseline to experimental compact + W2 at PR #2161:

- 23 genuine physical opening source IDs retained. Old source: 14 host bindings and nine source frames. Experiment: 18 hosts and nine source frames. Original opening 38c03575... rehosted and reframed, but strict old receipt retention fails due to rekeys.
- Of the 14 previously hosted physical openings, **11 retain identical W4 candidate assembly members and the same positive physical candidate V2 hybrid path/primitive identities.** Their generated source split edge indexes and W2 node IDs can change when new independent source pixels are registered. Seven old source frame records retain identical source-space geometry after removing only explicitly snapshot-scoped receipt addresses.
- The other **three W4 groups change physical assembly members**: opening 2c31ccb... also changes physical hybrid identity from wall2_7d5... to wall2_544... (source x410.25, y341.5 to 342.72); 38c03575... changes an assembly address but retains hybrid wall2_a4f... with source T at (381,342.72); 661fc5e6... changes physical hybrid wall2_3eab... to wall2_87c... and a proven frame length from 170.5 to 168.6 PDF points. These cannot be treated as automatically equivalent.

## Diagnostic

`tools/gptmax_source_host_rekey_parity_ledger.py` consumes *two independently produced original-source JSON reports* from `tools/diag_opening_wall_face_preservation.py`:

    PYTHONPATH=. python tools/gptmax_source_host_rekey_parity_ledger.py --baseline original-source-before.json --candidate original-source-after.json --output host-rekey-first-failure.json

It requires identical SHA, selected page scope and unchanged 20,000 primitive bound; producer-authenticated complete W4 records and matched physical-opening/frame universes. It compares **source W4 member IDs, candidate V2 path fingerprints, authenticated parent primitive ancestry, actual positive source-edge geometry (NOT split_N indexes), wall centerline and reasons**, as well as source frame geometric fields (NOT snapshot-specific receipt IDs). Changed source members, physical walls, frame geometry, host/frame loss, changed reason codes or invalid source fail closed into `ORIGINAL_SOURCE_PROOF_CHANGED_OR_LOST`.

An unchanged W4/frame geometric source with a changed receipt is classified `UNCHANGED_W4_AND_FRAME_SOURCE_WITH_RECEIPT_REKEY`, **NOT approved**. The report explicitly sets `official_host_receipt_identity_acceptance=false`, `opening_count_or_metric_publication_allowed=false` and `benchmark_accuracy=null` for ALL cases. It is evidence triage, never a substitute for the strict upstream retention check or a source equivalence assertion.

No host IDs, source observations, wall topology, actual source geometry, W2 snap, 20k cap, quantities, source reference PDF, frozen V2 denominator, truth or evaluator is changed. Adversarial Python 3.13/3.14 tests cover source SHA/page mismatch, lost host/frame, changed physical hybrid source/path, source-edge geometry, W4 membership, frame metric extent, duplicate source identities, transient split edge number rekeys, and all source/snapshot-only receipt changes. Proceed to exact source completeness and source-proven identity migration only after individual source authority stages are fully verified.
