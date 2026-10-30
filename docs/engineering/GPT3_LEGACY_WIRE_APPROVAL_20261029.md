# GPT3 legacy serialized customer approval Boolean integrity — 2026-10-29

## Observed
The legacy customer contract has a separate PlanReaderJobHubQuantityRow.from_dict and PlanReaderJobHubPayload.from_dict path in pb_planreader_jobhub_publish_contract.py. Both used bool(data.get(...)) for commercial permission fields. Python turns any nonempty string, including JSON "false" or "0", into True. The legacy preflight requires an explicit Boolean only for raw dictionaries, so a caller could hydrate the misleading value first and supply the resulting typed quantity row to bypass that raw-input check.

The prior #4092 upstream TakeoffOutputRow.from_dict strict flag check is independent; it does not protect these separate JobHub wire classes.

## Inference and change
Hydrating a legacy customer package must never create an approval from truthiness. Both is_publishable (line item) and is_commercial_ready (package) require exactly native Boolean true or false; an absent field defaults to False. Numeric, string, null, list and map values raise ValueError. Valid explicit flags, signed SHA fingerprints, commercial preflight, draft display and payload reconstruction retain their previous paths.

## Validation / authority limits
New parameterized adversarial wire tests use synthetic source-neutral rows and actual legacy build_jobhub_payload and run_jobhub_publish_preflight. This change does not alter original PDF extraction, issue quantities, frozen 120 evaluator/gold, provenance issuer, archived signed/customer receipts or 20,000 primitive/2.5 pt constraints. No original-source proof, extra FIRM, accuracy improvement or signed 8→9 promotion is claimed. Full exact-head Python 3.13/3.14 and relevant companions required before merge.
