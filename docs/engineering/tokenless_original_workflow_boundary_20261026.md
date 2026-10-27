# Previously tokenless private-original jobs

Observed repository behavior: ten original-source jobs in nine workflows ran on public PR
events without provisioning their required private source. Several uploaded
source-derived reports. The existing dynamic credential checker correctly
enumerates token-bearing jobs, so these tokenless jobs were outside that
credential boundary. Source-absent failures are not source verification.

Inference: adding a source dependency must not expose private originals to PR
code or turn omission into acceptance. Original-source assertions must remain
separate from public synthetic coverage and must retain their failure exits.

Proposed implementation: original jobs require owner/manual/main, checkout the
triggering trusted main SHA with credentials disabled, and use the existing
manifest/SHA-backed provisioner only from that main tree. No candidate PR code
is executed with source. Existing assertions remain. Private execution uses a
separate `bash -euo pipefail` process with both output streams withheld; only
fixed pass/fail vocabulary is public. Always cleanup removes originals, private
scripts/logs, source-derived reports and the temporary baseline worktree.
Original artifact uploads are removed. Public synthetic jobs stay on PR events;
the two formerly mixed jobs gain separate source-free synthetic jobs.

The native-paint retention comparison requires an explicit full SHA that is a
proper ancestor of trusted main, authenticated before provisioning. Trusted
current code copies the verified original into that ancestor worktree. It is a
comparison between trusted main revisions, not an automatic PR-head replay.

The existing strict dynamic credential checker now discovers these provisioners
without another allowlist. New source-neutral checks execute synthetic failure
and output-leak probes against the actual wrappers, validate shell/heredoc
grammar, and exercise baseline ancestry with an isolated Git history. These
checks do not open a private PDF or execute a construction producer.

Benchmark observations that must not influence implementation: none were used.
Existing source assertions are test observations, never producer inputs. This
workflow repair changes no construction source producer, quantity issuer,
signed/customer fixture, frozen evaluator, geometry budget or snap tolerance.
Manual source-positive jobs must be reported separately; public green or an
owner-only skip does not prove an original-source replay or an accuracy gain.
