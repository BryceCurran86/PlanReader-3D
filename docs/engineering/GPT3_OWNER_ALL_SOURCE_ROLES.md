# GPT3 owner-controlled all-source-role handoff

This is an **opt-in source-run capability** added to bridge an original source
coverage gap: existing `four_job_windows_launcher` correctly verifies ten
original PDFs but sends only the primary architectural PDF per project to the
producer. That cannot prove the structural Lot16 role or six-source Q5446
source universe in the final signed project envelope.

With the ten original PDFs held **privately on the owner's computer**, from
a checked-out copy of public PlanReader-3D, run:

```powershell
python -m tools.gpt3_owner_all_source_role_handoff `
  --project-id au_qld_lot16_power `
  --source-dir "D:\PrivatePlanSources" `
  --output-dir "D:\PrivateReports\Lot16AllRoles"
```

`--source-dir` may contain flat original filenames, or project-ID folders.
Each source is independently checked against the *frozen* size, SHA-256 and
page count **before any producer starts**. The runner then launches the
existing one-PDF source-closed producer separately for every frozen role
with independent process memory/timeout guards. Each independent signed run
is SHA/issuer-verified, and only when **all declared source roles**
successfully seal does the existing `combine_sealed_run_files` combine them,
with the full source SHA universe checked again.

Results are stored privately in a new output directory:
`SOURCE_ROLE_STATUS.json` is path-free, source-content-free and safe to share.
Individual original-role handoff outputs retain their distinct authorship.
`ALL_SOURCE_ROLES.sealed.json` is created exclusively when every original
source role really sealed; no source hash is appended to a single-PDF run to
fake completion.

**A document with no floor-plan geometry may produce
`role_producer_no_sealable_result`**. That is useful negative evidence:
the role remains incomplete and its SHA is not smuggled into a signed
quantity. Those roles may need a separate producer stage owned by GPT1/GPT2,
rather than forcing unsupported objects out of a siting, structural,
inclusions or specification document. Do not increase memory guards just
to mask a missing source family.

A role-complete signed run still needs actual FIRM quantities, independent
frozen identity maps, customer projection, verified project source closure,
and official suite reconciliation. The runner never invokes frozen truth or
an evaluator, and explicitly reports benchmark score as unavailable.
The frozen 120-item V2, all ten original PDF bytes, 20,000 raster safety
cap and public-repo privacy policy are unchanged.
