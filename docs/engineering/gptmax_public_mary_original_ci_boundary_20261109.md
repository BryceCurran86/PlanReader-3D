# Maryborough public CI / protected original boundary — 2026-11-09

## First real infrastructure failure
On exact AntiGravity PR #4253 head `5dcca05bb17c8bb3a06ae403c62df72d71d1d1e9`, public PR runs `42568507918` and `42568507991` failed while opening `documents/sources/Arch_Combined_Maryborough_Service_Station.pdf`. That original is intentionally NOT in public checkouts. These are **not** trustworthy original-source test results.

## Fix
The two legacy public workflows retain their existing source-neutral suites, frozen V2 integrity and provider-gold isolation. The unprovisioned original-specific invocation is no longer run. Every successful public run explicitly marks **original Maryborough NOT RUN** in both notice and step summary; it checks the private PDF did not leak into the public checkout.

## Mandatory independent protected proof
Use exact immutable public PR head, private owner-managed originals, a SHA-verified byte snapshot, network-disabled read-only container, and no uploaded private logs or PDFs. The independently invoked private runs are:
- [Office FT3 and GRID positive + negatives and Lot16 signed-eight fixture](https://github.com/BryceCurran86/PlanReader-3D-sources/actions/runs/42571524741)
- [Full Maryborough source-role and sealed/customer producer](https://github.com/BryceCurran86/PlanReader-3D-sources/actions/runs/42572087754)

Those runs prove only what their final results actually show. They do not automatically cover every historical FT3 native-text or room-source replay; run any remaining original-specific checks in the private environment before release. Keep the signed Maryborough three, Lot16 eight, original SHA custody and source/customer bijection as independent gates. Do not merge #4253 merely because public CI turns green.

## Explicit non-authority
No original PDF changes, quantities, project scopes, identity map, frozen120 evaluator, source manifests, or accuracy claims. The change fixes two misleading CI failures, not customer takeoff itself.
