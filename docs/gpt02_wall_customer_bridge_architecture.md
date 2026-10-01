# GPT-02: selected-source wall publication repair

Current main was fetched again at task start: e95ef8489f3a0b7c024fb99dc5e48fed887ee40b.
This isolated branch is stacked on GPT-01 draft PR #1195, a5b529fbbb321ad5dcc237493177b3820ba5a9df.

## Observed authority and consumers

`collect_live_physical_net_wall_claim` derives the document identity from source
bytes and replays source visibility, physical wall/opening identity, whole-wall
roles, authenticated gross geometry, physical void union and the original net
wall QuantityEvidence. The customer bridge returns a canonical 21-field row.
`analyse_workspace` publishes those rows, model and report in one transaction;
AG-09 reads the actual transaction's takeoff rows.

The bridge currently returns after its first positive PDF, calls the authority
with `pages=None` for documents having no selected pages, rounds the already
verified six-decimal quantity to two decimals, and assigns material labels from
all workspace facades. Its caller then suppresses every facade, including those
from unrelated unresolved sources. Coverage can also consume stale unscoped
extractor attachments. These are customer bridge defects, not missing geometry.

## Proposed repair and limits

Enumerate selected pages per source, accumulate all independent authenticated
claims, and replay byte-identical source uploads once with their selected page
union. Deduplication uses the authority's byte-derived source identity only;
labels, filenames, marks and equal quantities do not prove equivalence. A
quantity-id collision between different source groups requires review of both
claims. A failed source cannot stop an independent sibling claim.

Preserve each original verified value through the existing row contract and
SQLite writer. Restrict material labels and facade replacement to the matching
source documents. Retain unsupported sibling facade evidence under its existing
status. Scope runtime registry attachments to the current selected source hashes
and reset producer state per invocation/workspace. No new physical identity,
geometry, quantities, authority flags, scoring or truth rules are introduced.

Before building a row, the typed live claim must agree with its original
publication's quantity id/value/unit and physical wall inputs. Those canonical
walls must retain the selected source hash/revision, and the claim's source
pages must belong to the selection. Conflicts, ambiguity and failed-source
review cannot fall through to the registered-wall path. Independent valid
sibling sources still publish.

The separate registered-wall fallback retains its existing authority policy;
its missing canonical registry remains explicit and is not represented as
CONNECTED. Cross-file physical equivalence beyond byte-identical source replay,
and source-proven missing geometry in other families, remain separate tasks.

The user assigned tests, CI review and merge to normal GPT. This branch includes
focused hostile/parity regressions; syntax and diff checks are performed here.
