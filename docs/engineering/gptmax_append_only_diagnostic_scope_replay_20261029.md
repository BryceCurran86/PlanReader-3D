# Append-only source/customer diagnostic scope replay

## Observed

An actual SHA-authenticated Lot16 original run passed the default eight path, then failed the existing whole-body eight-to-nine acceptance test. run_original_lot16_sealed_handoff's source callback explicitly forwards source_reproved_append_only to both seal_live_opening_area_claim_run and project_live_opening_customer_rows, receiving one independently verified source/customer seal. The independent _opening_sealing_diagnostic in tools/diag_lot16_room_face_scope.py forwards the same existing explicit opt-in only to its seal, while its customer projection silently uses the default legacy scope. Its verification therefore compares different explicitly selected source scopes.

## Inference and proposed correction

The independent diagnostic must replay the same caller-selected source scope through both existing consumers. Forward source_reproved_append_only to its customer projection, preserving the False default. This does not grant the opt-in automatically, infer an opening, change a source/measurement issuer, add benchmark inputs, or relax customer verification. The existing actual-original acceptance test remains unchanged and must independently reproduce eight plus nine with every archived signed/customer body retained.

## Validation

Run the unchanged original eight-to-nine whole-body acceptance test using the SHA-authenticated private PDF, existing source/customer/activation synthetic suites, final diff and full exact-head Python3.13/3.14 checks. Original files, archived signed rows and frozen truth remain unchanged. No frozen accuracy claim follows from this diagnostic correction.
