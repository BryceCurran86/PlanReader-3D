# Four-job official runner: correctness and elapsed time

Date: 9 November 2026, Brisbane. Owner requested a working, faster official four-job run. This report precedes the workflow change. Production source/quantity authorities and the frozen evaluator are unchanged.

## Observed

Read current `AGENTS.md`, engineering playbook and succession handover. Traced the protected four-job workflow through `tools.gpt3_owner_all_source_role_handoff.produce_all_source_roles`, `original_roster`, `source_owned_role_module`, `run_logged`, `generate_project_handoff`, `_verified_role_customer_rows`, `combine_sealed_run_files`, `verify_sealed_customer_output`, and the trusted `build_four_project_evidence_ledger`.

Protected run 42430857909 processed projects serially: Lot16 18m08s, Maryborough 44m50s, 3Laurel 11m56s, Q5446 2m32s, about 77m26s total. Every source process completed. Lot16/Q5446 supporting roles did not independently seal quantities. Maryborough lacked an independent identity map. 3Laurel's frozen source-universe gate remained incomplete. Process completion is not source/customer or official score acceptance. The four-job worker had a six-hour timeout and discarded its private results after the final failed gate, requiring expensive re-extraction for a reporting-only retry.

## Inference

Four independent workers can overlap project execution without reducing each producer's memory allowance. The prior 45-minute Maryborough execution is a planning lower bound for this workload, not a promised measured new runtime. Retaining small verified per-project result packets privately allows the final failed job to be rerun in the same Actions run without repeating successful producer jobs. Full extraction is still required when producer code, source or authority changes.

## Proposed workflow

One exact immutable candidate (`2ab5ab75b5b9fb6fcd2d7b55fed6c3e514599171`) and trusted main (`22ebd4e3c97f8efff807e9b9d84ea78837424647`). Authenticate all ten originals and unchanged frozen120, then use a four-project matrix with fail-fast disabled. Each worker builds dependencies before mounting read-only originals and runs the existing all-source-role producer offline under the existing memory/time limits. Native input receipts remain input evidence only.

Publish only allowlisted status/provenance and, when independently valid, exact aggregate sealed/customer files as one-day artifacts in the PRIVATE companion repository. Never upload source PDFs, producer logs, page images, OCR dumps, or entire output directories. Packets bind the exact producer/trusted heads, Actions run and original-role roster and carry byte digests. The final worker rejects missing/foreign/stale/tampered packets, rechecks real seal/customer bijection and original sources, and uses existing independently recorded maps and the unchanged trusted evaluator. Incomplete supporting roles never gain an empty quantity receipt or a borrowed SHA envelope. Four project outcomes and the first gate appear in one Actions summary. Publication still fails closed if any required source, customer, identity or frozen-manifest gate is unresolved.

## Validation and boundaries

Validate YAML, every embedded Python block and shell syntax; test packet transport with real archived sealed/customer data and synthetic failures, including wrong run/head/role/source, changed bytes, unexpected files, symlinks and incomplete source/customer flags. Execute the real protected four-project workflow. Record actual job durations and final publication status. Existing signed outputs, quantities, maps, truth, tolerances, 20,000 cap and 2.5pt snap remain untouched. Claude's corner-host work, AntiGravity's Maryborough authority and the separate Q5446 physical work do not overlap this workflow.

## Benchmark firewall

No expected quantity, benchmark score or item ID selects a producer algorithm or threshold. The immutable 120 denominator and four project names specify execution and reporting only. A valid blocked report is not an official accuracy result, and a candidate run is not a production merge.
