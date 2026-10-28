# GPT3 — Unknown legacy JobHub publish modes must fail closed (2026-10-29)

## Actual production boundary

Read AGENTS, engineering playbook, coordination hub, the source/frozen V2 firewall, CI, actual `pb_planreader_jobhub_publish_contract.py`, and legacy draft/commercial tests. On base `f64d1617cad9ff45de4a39b9c386aa4513e361d2`, `run_jobhub_publish_preflight` considered only exact `"commercial_publish"` to be commercial; every other mode (including `"commercial_publish "`, `"published"`, `None`, booleans and unknown strings) took draft logic. It could report `is_valid=True` on provisional PDF/AI measurements and emit non-commercial warning as if explicitly requested. `build_jobhub_payload` repeated the same test; it raised on blocked preflight only for recognised commercial and would issue a SHA-fingerprinted payload with an unrecognised mode. This creates a real incorrectly classified publishing payload even though no explicitly authorised draft or commercial mode was requested.

## Inference and production change

A requested mode controls whether unverified quantities may appear in a JobHub payload; unknown values cannot be mapped to draft merely by inequality. Retain existing mode enums, lowercase/uppercase string support, genuine `draft_publish` provisional warnings and `commercial_publish` measured-authority gates. Reject all unsupported modes in preflight via explicit blocking reason; builder rejects unsupported modes with a `ValueError` before row conversion or final recipient seal. Avoid lossy stripping that could incorrectly treat padded commercial mode as equivalent.

## Real downstream tests and limits

New tests exercise preflight **and** actual `build_jobhub_payload` for invalid/ambiguous mode strings and nonstring aliases, positive existing enum/strings, valid commercial FIRM contract and genuine draft provisional warnings. Synthetic row tests are only gate mechanics; no source signed quantity, customer release, V2 scorer/tolerance, original PDF, credentials, 20k or 2.5pt changes. Independent #4080 JobHub writer, #4082 final quantity row-ID gate, GPT1/2/MAX/AntiGravity/Claude and signed archives remain untouched.

## Required release

Exact-head full Python 3.13 and 3.14 CI and applicable signed/customer/raster/performance checks plus full patch technical review before merging. No claim of original source-positive or official frozen120 score increase.
