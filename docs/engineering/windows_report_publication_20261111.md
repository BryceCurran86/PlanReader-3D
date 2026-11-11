# Windows create-only report publication ? 11 November 2026

Base: `7e3b36ca0bcb66d166ac07f1894ca89d4c32333f`.

Observed: `report_gpt3_four_project_evidence.main` calls
`write_new_diagnostic`, which exclusively hard-links a staged UTF-8 report,
rechecks inputs, then calls `_assert_published_report_unchanged`. On the owner
Windows PC, a harmless report reproduced rejection despite identical bytes,
device, nonzero inode, mode, link count, size and mtime. Path `lstat` ctime
remained constant while descriptor `fstat` ctime was approximately 2 ms later.
An immediate-timing run passed, so the defect can be intermittent.

Inference: ctime observations from the two Windows APIs are not interchangeable.
This is an output-publication defect; it does not indicate a changed original
PDF, failed quantity, or completed benchmark execution.

Proposed bounded correction: retain common identity/content fields across all
six snapshots. Require a nonzero inode. Require ctime stability within path
observations and within descriptor observations. On POSIX additionally require
ctime equality across those two groups; on Windows permit the observed stable
cross-API offset. Preserve regular-file checks, no-follow open where supported,
exact UTF-8 bytes, exclusive publication, input revalidation and rollback that
retains another writer's replacement. No timing tolerance or read fallback.

Validation: reproduce the Windows positive and zero-inode refusal as failing
tests before implementation; exercise cross-platform ctime behavior, every
retained identity field, changed ctime within either API, and the existing
same-byte replacement/symlink/in-place mutation/competing-writer negatives.
Run the actual Windows writer and existing caller suites, then exact-head
Python 3.13/3.14 CI.

Benchmark observations must not influence the correction: all four frozen
manifests remain incomplete, while the existing development scorer can accept
four genuinely reconciled packets. This change supplies neither packet nor
score. Frozen truth, identity maps, originals, quantities and customer bodies
remain untouched. A read-only existing 3Laurel packet may validate the report
CLI after the correction; missing project packets remain explicit blockers.
