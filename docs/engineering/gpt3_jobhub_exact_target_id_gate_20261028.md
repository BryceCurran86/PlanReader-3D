# GPT3 — Exact target JobHub row ID at final write boundary

**2026-10-28; status: proposed / source-neutral downstream consumer security**

## Observed repository behaviour

1. `pb_jobhub_publishing_pipeline.build_publishing_package_from_workspace` obtains an SQLite workspace `jobhub_job_id`, converts a nonempty value with `int(...)` and produces `ProjectIdentityPayload`.
2. Other callers can construct or deserialize `ProjectIdentityPayload` directly. Its `target_jobhub_job_id: Optional[int]` type hint is not runtime validation.
3. `pb_jobhub_publishing_contract.validate_publishing_gate` validates source, project number, quantity, pricing, seals and commercial authority but never requires an exact positive integer target ID.
4. `pb_jobhub_publishing_pipeline.execute_jobhub_publishing` checks only `if not target_job_id` before binding the value to SQLite `WHERE jobs.id=?` or PostgreSQL `WHERE jobs.id=%s FOR UPDATE`, within the write transaction. Noncanonical aliases such as Boolean `True`, float `1.0` and string `"1"` survive that truthiness gate; SQLite can coerce such bound parameters to the real job row with ID 1.

The existing atomic locked-read and job number equality check are important and remain unchanged. A job number can legitimately repeat, so matching `job_no` does not authenticate the *type* of the requested destination ID.

## Inference

A caller-supplied Boolean, fractional/numeric-string, negative or missing destination ID must not obtain write authority via database parameter coercion. A correct payload hash cannot correct an incorrectly typed destination selector; it only binds what the caller supplied.

## Proposed change and evidence

At the final production write boundary, before opening the JobHub connection, require `type(target_job_id) is int and target_job_id > 0`, retaining the existing missing-ID error. Test the *real* SQLite bridge with both ID 1 and ID 501 holding the same job number: each forged selector must fail without writing either package or line; exact positive integer ID 501 must still publish. Repeat valid draft and commercial cases and invalid parameter ordering. No SQLite/PG transaction or customer quantity computation changes.

## Authority boundaries and expected abstentions

This only rejects malformed destination selectors; it does not authenticate a construction drawing, grant estimator approval, alter a source quantity, change an existing sealed/customer receipt, promote FIRM, or reconcile the frozen 120-object scorer. The original PDF files, benchmark manifests and evaluator, GPT1/GPT2/GPT MAX/Claude/AntiGravity source/geometry modules, 20,000 primitive cap and 2.5 pt snap remain untouched. This qualifies as a source-neutral downstream customer identity safety implementation only after exact-head regression and full CI pass, review and merge.
