# GPT3 named source-estimator approval integrity — 2026-10-29

## Observed production gate
In pb_takeoff_output_authority.create_takeoff_output_row, MODEL_DERIVED, USER_CORRECTED and USER_APPROVED source paths used Python truthiness of approved_by to promote is_publishable. Whitespace-only strings, bool True, integer 1 and nonempty collections are truthy but do not identify an approving estimator. This flag feeds generate_takeoff_authority_summary and the real run_jobhub_publish_preflight consumer, where forged caller values can overstate commercial readiness before any private source authentication.

## Inference and fix
Only a native, nonblank string after whitespace stripping can represent an estimator attribution. Check type(approved_by) is str and bool(approved_by.strip()) once and use the same decision in all three factory approval paths. Preserve the exact original name string for audit, explicit warnings/blocking reasons and existing named-user positive behavior. The approve_takeoff_output_row helper delegates to this producer and therefore inherits the correction without a second approval resolver.

## Test and benchmark firewall
Adversarial source-neutral factory->summary->legacy preflight/payload negatives include whitespace, bool, numeric, container and missing names; named estimator and approval helper positive controls preserve commercial behavior. No original drawing, signed fixture, customer receipt, issuer seal, benchmark truth, denominator, 20,000 cap or 2.5pt snap edits. Synthetic safety coverage is not original FIRM evidence or a Full Plan V2 accuracy increase. Merge only with immutable head, full Python3.13/3.14 and applicable companions green.
