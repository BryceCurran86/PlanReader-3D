# GPT MAX — snapshot-independent source candidate membership witness

Original Lot16 PDF SHA: 10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844. The retained 23/14/9 physical/host/frame source evidence uses snapshot source_snapshot_7c0d199..., while adding genuine compact observations changes only its producer-wide snapshot address to source_snapshot_3d4583.... Existing host_wall_id, host-binding record_id and frame receipt ids include the snapshot address. Therefore an unchanged source-owned W4 candidate group changes host *receipt identity* even if its underlying candidate path/provenance is unchanged.

Original source evidence from PR #2161, run 38068100685:
- 23 physical opening identities retained
- 14 → 18 authenticated host *existence* facts, and 9 → 9 connected frames
- Zero LOST hosted opening/frame proofs at the existential level, but 11 retained openings rekey despite identical W4 candidate member IDs and corroborated physical candidate v2 ids
- Three other retained openings change W4 candidate membership; two change hybrid candidate v2 identities (source-end clipping), and MUST NOT be auto-approved as equivalent
- Four net newly hosted openings. This is a DRAFT experiment, not a production benchmark result.

## Additive candidate-membership witness

OpeningHostBindingRecord.source_candidate_membership_witness_id hashes only authenticated document/source SHA, page, physical opening existence ID and exact sorted W4 physical candidate v2 hybrid identity IDs. It does NOT include the version-specific entire SourceVisibility snapshot, revision, host address or source observation numbering. It is only an *evidence-addressing hint*.

**Critically it is NOT a physical host ID, physical equivalence proof, host retention pass, opening-count authority, sealed quantity, wall geometry correction or benchmark improvement.** A matching witness may help the auditor distinguish a snapshot-scoped rekey from an actual changed source member, but no source-owned host is published from this witness, and exact W4 equivalence groups, boundary scope, opening role and source-frame receipts must still be proved separately before publishing quantities.

No existing IDs, hashes, record payloads, field values, detector, source requirements, W2 snap tolerance or the 20,000 primitive safety cap are changed. The property is computed on request; no source scan or benchmark file is accessed. Negative tests confirm invalid, duplicated or changed hybrid identities cannot reuse a source candidate witness. Source-report retention comparator in main remains strict.

Next steps are a production source-preserving identity migration with explicit equivalence proofs and source revalidation, not silently replacing existing receipt ids. Keep compact+W2 #2161 DRAFT until that gate closes.
