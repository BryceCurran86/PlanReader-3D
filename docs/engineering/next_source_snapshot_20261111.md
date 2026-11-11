# PlanReader Next source snapshot ? 11 November 2026

Base: PR #4284 at `705a4cb3c2ffa816407c5e99e6cad7ce535f90ad`.

Observed: `load_native_page` hashes a PDF through one path open, parses a
second path open and compares only file size/mtime afterwards. Generated-PDF
reproductions on Windows 3.13 show that both a same-size replacement with
restored mtime and a same-byte different-inode replacement are accepted.
The native receipt can therefore carry a digest from another input snapshot.

Inference: size/mtime equality cannot bind parser input to the original bytes.

Correction: reuse the existing stable original-file digest/identity check,
verify the byte snapshot against that digest, parse that immutable snapshot
with the existing native extractor, then recheck original digest and identity.
Do not add another parser, geometry graph or measurement authority. Missing or
changed input is a SourceConflict. Existing native primitive IDs and measured
draft semantics remain unchanged.

Validation: generated originals and deterministic substitutions before parser
open and snapshot read; same-byte inode replacement; explicit unavailable
input; all existing Next floor/wall/ceiling/door/frame tests; read-only smoke
against an authorized original. Full exact-head Python 3.13/3.14 CI remains
required. These checks validate input ownership, not physical wall/room/finish
authority or commercial readiness.

Benchmark observations are excluded from implementation. No frozen item,
source quantity, customer row, 20,000 cap or 2.5pt snap changes. The existing
four-project result is retained; draft measurements earn no benchmark credit.
