# PlanReader Next source snapshot — 11 November 2026

Integrated into PR #4284 from child #4286. Current parent is this Next
engine, not original-app production.

Observed: `load_native_page` hashed a PDF through one path open, parsed a
second path open and compared only file size/mtime afterwards. Same-size
replacement with restored mtime could carry the earlier file's SHA.

Correction: reuse `_stable_original_digest`, verify the byte snapshot
against that digest, parse that snapshot with the existing native extractor
and drawing collector, then recheck original digest and identity. No second
parser, geometry graph or measurement authority.

Validation is input ownership only. It does not authenticate physical
wall/room/finish authority or commercial readiness. Frozen 120, signed
quantities and original-app files are unchanged.
