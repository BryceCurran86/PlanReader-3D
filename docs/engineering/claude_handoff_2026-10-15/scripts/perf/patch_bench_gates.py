import pathlib

ROOT = pathlib.Path(r"C:\claude-work\gate-bench\scripts")


def load(name):
    p = ROOT / name
    raw = p.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    return p, raw.replace("\r\n", "\n"), nl


def save(p, t, nl):
    p.write_bytes(t.replace("\n", nl).encode("utf-8"))


# ------------------------------------------------------------------ integrity script
p, t, nl = load("check_full_plan_v2_integrity.py")
old = 'DEFAULT_ROOT = Path("benchmarks/frozen_holdout/full_plan_v2")\n'
new = old + 'DEFAULT_SOURCE_DIR = REPO_ROOT / "documents" / "sources"\n'
assert t.count(old) == 1
t = t.replace(old, new)

old = "def validate_suite(root: Path = DEFAULT_ROOT) -> list[str]:\n"
helper = '''def source_document_failures(manifests: Any, source_dir: Path = DEFAULT_SOURCE_DIR) -> list[str]:
    """A pinned source document that IS in the repository must have exactly the pinned SHA-256 and size.

    Some pinned documents are not distributed with the repository; those are skipped (nothing to compare). A present file whose
    bytes differ from the frozen manifest is a changed source and fails closed, so a source PDF cannot be replaced unnoticed.
    """
    failures: list[str] = []
    for manifest in manifests:
        for source in manifest.source_documents:
            path = source_dir / source.name
            if not path.is_file():
                continue
            data = path.read_bytes()
            actual_sha = hashlib.sha256(data).hexdigest()
            if actual_sha != source.sha256:
                failures.append(
                    f"{manifest.project_id}: source document {source.name} SHA mismatch "
                    f"(manifest={source.sha256}, actual={actual_sha})"
                )
            if len(data) != source.size_bytes:
                failures.append(
                    f"{manifest.project_id}: source document {source.name} size mismatch "
                    f"(manifest={source.size_bytes}, actual={len(data)})"
                )
    return failures


'''
assert t.count(old) == 1
t = t.replace(old, helper + "def validate_suite(root: Path = DEFAULT_ROOT, source_dir: Path = DEFAULT_SOURCE_DIR) -> list[str]:\n")

old = "                    f\"records: {', '.join(missing)}\"\n                )\n\n    return failures\n"
assert t.count(old) == 1, t.count(old)
t = t.replace(old, "                    f\"records: {', '.join(missing)}\"\n                )\n\n    failures.extend(source_document_failures(manifests, source_dir))\n    return failures\n")
save(p, t, nl)

# ------------------------------------------------------------------ separation script
p, t, nl = load("check_v2_truth_separation.py")
old = '_PRODUCTION_SUFFIXES = {".py", ".js", ".html"}\n'
new = '_SOURCE_PDF_ROOT = "documents/sources/"\n' + old
assert t.count(old) == 1
t = t.replace(old, new)

old = "def is_production_code_file(path: str) -> bool:\n"
fn = '''def is_benchmark_defining_file(path: str) -> bool:
    """Everything that defines or feeds the frozen benchmark: the named truth files, ANY other file in the V2 tree
    (evaluators, reconcilers, identity maps, runners) and the original source PDFs.

    ``is_v2_truth_file`` stays the narrow predicate for the six truth filenames; this wider one is what the separation gate uses, so
    scorer code, tolerances or a source PDF cannot change in the same PR as production code.
    """
    normalized = _normalize(path)
    if is_v2_truth_file(normalized) or normalized.startswith(_V2_ROOT):
        return True
    lowered = normalized.lower()
    return lowered.startswith(_SOURCE_PDF_ROOT) and PurePosixPath(lowered).suffix == ".pdf"


'''
assert t.count(old) == 1
t = t.replace(old, fn + old)

old = "    truth_files = sorted({p for p in changed_paths if is_v2_truth_file(p)})\n"
assert t.count(old) == 1
t = t.replace(old, "    truth_files = sorted({p for p in changed_paths if is_benchmark_defining_file(p)})\n")
old = '                "V2 truth files:",\n'
assert t.count(old) == 1
t = t.replace(old, '                "V2 truth / benchmark-defining / source-PDF files:",\n')
save(p, t, nl)
print("patched both")
