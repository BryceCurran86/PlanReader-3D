# GPT3 typed takeoff authority wire missing-source quarantine — 2026-10-29

## Observed actual customer path
TakeoffOutputRow.from_dict in pb_takeoff_output_authority.py treats omitted or blank source_type as documented_dimension, and omitted or blank authority_status as FIRM. A wire message with is_publishable True plus source page and figured dimension trace can then become a typed TakeoffOutputRow. The downstream run_jobhub_publish_preflight checks explicit source field presence only for raw mappings, whereas hydrated typed rows are accepted from their newly defaulted values. #4092 separately fixed non-Boolean publishability but did not fix authority field omission.

## Production change
Missing, blank or non-native-text source_type or authority_status MUST NOT generate commercial FIRM. Reject publishable wire hydration when either metadata field is invalid. Preserve unapproved legacy messages for draft inspection by hydrating them with explicit blocked source and authority and False publishability; never manufacture documented source evidence. Legitimate complete named-approved source row roundtrips and commercial legacy consumer stay intact.

## Verification and boundary
Adversarial omission/blank/number/collection wire permutations via real TakeoffOutputRow.from_dict and downstream legacy preflight/build_jobhub_payload, blocked draft positives and full explicit commercial positive. No private original PDFs, signed issuer/customer archive, frozen evaluator/denominators, 20,000 cap or 2.5pt snap modifications. Safety only, no newly authenticated FIRM or frozen120 score gain. Exact-head dual Python3.13/3.14 and all applicable companions required before merge.
