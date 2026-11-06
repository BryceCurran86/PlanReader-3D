# GPT3 — V2 mapped floor-area source semantic / physical identity veto

2026-10-29 AEST; reviewed main `65dc4684fbcf1ce36c704457d896fc7c12a651de`.

## Observed repository behavior
`pb_live_floor_area_quantity_publication.py` emits source-owned `QuantityEvidence`: `family="floor_area"`, `semantic_key="floor_area:<physical_floor_surface_id>"`, `input_entity_ids=(physical_floor_surface_id,)`. The downstream `tools/gpt3_signed_v2_family_trade_integrity.py::require_signed_v2_family_trade_integrity`, called by the four-project evidence reporting mapping gate, verifies independently bound physical refs, quantity family/trade and units. On main it did not compare a present modern floor-area semantic source member with the exact bound physical floor identity.

## Inference / first failing boundary
A mapped `floor_area:floor-A` source semantic with `object_identity_refs=("floor-B",)` was allowed as flooring if the binding copied floor-B. The signer/customer checks remain separate, but this final negative mapping boundary should refuse that internally contradictory original-source semantic rather than permit a source identity to be traded for a different physical member. Neither a source semantic label nor an identity-map binding alone proves a floor.

## Proposed change and expected abstention
Only a mapped nonabstained `floor_area`→`flooring` quantity whose original source semantic begins with `floor_area:` is checked. Require a single physical floor member and exact `floor_area:` suffix equality to it; otherwise raise a fail-closed mapping error. The guard never discovers, infers, signs, or scores an object. Generic legacy semantics remain governed by upstream source/customer gates and are neither inferred nor converted here. An unmapped quantity remains unmapped.

The new source-neutral tests cover matching identity, repeatability, immutable inputs, foreign/blank/padded suffixes, multiple original physical floors, abstained/unmapped nonpromotion, legacy compatibility and incompatible-trade behavior.

## Unchanged authority and pending validation
No source PDFs, private credentials, source producer/issuer, customer archive, signed baseline, benchmark truth/denominator/evaluator, geometric 20k primitive cap or 2.5 pt snap changes. This disjoint guard is not a source-positive quantity or a frozen V2 score gain. Exact-head Python 3.13/3.14 public CI and original-source/signed/customer retention proof remain distinct gates. GPT3 release PR #3796 remains draft until owner-trusted original8/default and original9/explicit producer→sealed→customer whole-body replay passes both versions. No benchmark quantity or expected output drives this guard.
