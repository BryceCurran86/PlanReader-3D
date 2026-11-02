# GPT3 — Canonical source-warning and exclusion seal ordering (2026-10-29)

## Observed production path

Current main `60234ec70a61ca319d29d335f8b0ac0ded2e18d3`. Read AGENTS.md, engineering playbook, source/frozen V2 firewall, CI and current #3462 claims. `pb_jobhub_publishing_pipeline.build_publishing_package_from_workspace` builds `PublishingPackagePayload`; `PublishingPackagePayload.compute_payload_hash` seals the source, commercial quantities, warnings and exclusions; `validate_publishing_gate` enforces warning severities, TOCTOU and approved source rows; `execute_jobhub_publishing` uses the full seal in the transactional JobHub duplicate query.

The hash sorts quantity rows by physical row ID but emits `warnings` in raw arrival order and sorts `excluded` only by item_code. When two distinct excluded records share an item code, their input order changes the hash. Reordering two informational warnings changes the hash even when all warnings and their source evidence are identical. The actual JobHub duplicate check therefore treats one unchanged physical source/customer package as two commercial packages.

## Inference

Source warnings and excluded scope are a multiset of complete records. Arrival order is not source authority or customer approval; the contents, duplicate multiplicity and every field are. Canonicalizing only the SHA payload list order must not mutate the visible order of the warnings in the source package or weaken commercial blocker severities.

## Proposed implementation

In `PublishingPackagePayload.compute_payload_hash`, sort both exclusions and warnings by the complete deterministic JSON serialization of each `to_dict()`, preserving multiplicity and all fields. Keep `hash_contract`, quantity sort, source hash, preflight, approvals, geometry, prices and created_by unchanged. Add real SQLite PlanReader builder → gate → JobHub publisher tests proving reordered informational warnings and same-code distinct exclusions cannot evade duplicate detection; changing warning severity/message or exclusion reason must change hash; blocker warnings still block; draft warnings remain visible.

## Authority / security / regression boundary

This is a source-neutral duplicate-publishing identity repair, NOT an original PDF positive replay, source/FIRM/customer promotion or frozen120 score change. No production source/geometry, signed eight/customer fixtures, frozen V2 truth, original PDFs, 20k/2.5pt limits or other agent files are changed. Historical packages with the older order-sensitive hash are NOT migrated or automatically deduplicated; their compatibility requires separate explicit review. `#3796` still needs owner-only original-eight/default and original-nine/explicit trusted positive replay.

## Required verification

Review the full patch and record technical review. Exact new-head Python3.13/3.14 full CI plus applicable signed/customer/raster/performance checks are required before merge; synthetic fixtures cannot grant original-source authority.
