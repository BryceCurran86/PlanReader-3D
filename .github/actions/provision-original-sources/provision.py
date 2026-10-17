"""Provision the original owner/client source PDFs onto a CI runner, SHA-256 verified, fail closed.

The originals are not stored in this repository (docs/PRIVATE_ORIGINAL_SOURCES.md). Their names, sizes and SHA-256
digests are the frozen source manifests under benchmarks/frozen_holdout/full_plan_v2/projects/*/source_manifest.json.
This script reads those manifests, and for every selected document makes sure ``<destination>/<name>`` exists with exactly
the pinned size and digest. A missing file is downloaded from a private companion repository with a read-only token;
anything that cannot be verified is an error. Nothing is ever substituted, truncated or "close enough".

Python standard library only (it runs before ``pip install``). The token is read from the environment, never from argv,
and is never printed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence

DEFAULT_MANIFEST_ROOT = "benchmarks/frozen_holdout/full_plan_v2/projects"
DEFAULT_DESTINATION = "documents/sources"
DEFAULT_SOURCE_PATH_PREFIX = "documents/sources"
TOKEN_ENV = "ORIGINAL_SOURCES_TOKEN"
MAX_FILE_BYTES = 64 * 1024 * 1024
API_ROOT = "https://api.github.com"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_REF = re.compile(r"^[A-Za-z0-9_./-]{1,200}$")


class ProvisionError(Exception):
    """Raised for every condition that must fail the job; the message names the cause, never a secret."""


class Expected(dict):
    """name -> {"sha256", "size_bytes", "projects"}"""


# ---------------------------------------------------------------------------------------------------------------------
# manifests
# ---------------------------------------------------------------------------------------------------------------------


def _safe_name(name: object) -> str:
    if type(name) is not str or not name or name != name.strip():
        raise ProvisionError("manifest document name must be a non-empty trimmed string")
    if "/" in name or "\\" in name or name in {".", ".."} or "\x00" in name or ":" in name:
        raise ProvisionError(f"manifest document name is not a plain file name: {name!r}")
    if not name.lower().endswith(".pdf"):
        raise ProvisionError(f"manifest document is not a PDF: {name!r}")
    return name


def load_expected(manifest_root: Path) -> Expected:
    """Read every frozen source manifest; the same name must never carry two different digests."""
    manifest_root = Path(manifest_root)
    paths = sorted(manifest_root.glob("*/source_manifest.json"))
    if not paths:
        raise ProvisionError(f"no source_manifest.json found under {manifest_root}")
    expected = Expected()
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ProvisionError(f"cannot read {path}: {exc}") from None
        project = data.get("project_id")
        if type(project) is not str or not project:
            raise ProvisionError(f"{path}: project_id missing")
        documents = data.get("source_documents")
        if type(documents) is not list or not documents:
            raise ProvisionError(f"{path}: source_documents missing")
        for doc in documents:
            if type(doc) is not dict:
                raise ProvisionError(f"{path}: malformed source document entry")
            name = _safe_name(doc.get("name"))
            sha = doc.get("sha256")
            size = doc.get("size_bytes")
            if type(sha) is not str or not _SHA256.match(sha):
                raise ProvisionError(f"{path}: {name!r} has no valid sha256")
            if type(size) is not int or isinstance(size, bool) or not (0 < size <= MAX_FILE_BYTES):
                raise ProvisionError(f"{path}: {name!r} has no valid size_bytes")
            known = expected.get(name)
            if known is not None and (known["sha256"], known["size_bytes"]) != (sha, size):
                raise ProvisionError(f"conflicting manifest entries for {name!r}")
            if known is None:
                expected[name] = {"sha256": sha, "size_bytes": size, "projects": [project]}
            elif project not in known["projects"]:
                known["projects"].append(project)
    return expected


def select(expected: Expected, names: Sequence[str], projects: Sequence[str]) -> List[str]:
    """Names to provision. Only manifest names are ever selectable; an unknown name is an error, not a download."""
    if names:
        unknown = [n for n in names if n not in expected]
        if unknown:
            raise ProvisionError(f"not in any frozen source manifest: {unknown!r}")
        return sorted(dict.fromkeys(names))
    if projects:
        chosen = [n for n, meta in expected.items() if any(p in meta["projects"] for p in projects)]
        known_projects = {p for meta in expected.values() for p in meta["projects"]}
        missing = [p for p in projects if p not in known_projects]
        if missing:
            raise ProvisionError(f"unknown project id(s): {missing!r}")
        return sorted(chosen)
    return sorted(expected)


# ---------------------------------------------------------------------------------------------------------------------
# verification and download
# ---------------------------------------------------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_verified(path: Path, meta: Mapping[str, object]) -> bool:
    try:
        return path.is_file() and path.stat().st_size == meta["size_bytes"] and sha256_file(path) == meta["sha256"]
    except OSError:
        return False


class _NoAuthOnCrossHostRedirect(urllib.request.HTTPRedirectHandler):
    """GitHub answers a raw contents request with a redirect to its object store; never forward the token there."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and urllib.parse.urlparse(newurl).netloc != urllib.parse.urlparse(req.full_url).netloc:
            new.headers.pop("Authorization", None)
            new.unredirected_hdrs.pop("Authorization", None)
        return new


def http_fetch(url: str, token: str, *, timeout: float = 120.0, retries: int = 3) -> Iterable[bytes]:
    """Stream the body of a GitHub contents request. 401/403/404 are final; 5xx and network errors are retried."""
    opener = urllib.request.build_opener(_NoAuthOnCrossHostRedirect)
    last: Optional[str] = None
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.raw",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "planreader-provision-original-sources",
            },
        )
        try:
            response = opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403, 404):
                raise ProvisionError(
                    f"companion repository refused the request with HTTP {exc.code} "
                    "(check the token scope, the repository name, the ref and the file path)"
                ) from None
            last = f"HTTP {exc.code}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = type(exc).__name__
        else:
            def body(resp=response):
                with resp:
                    while True:
                        chunk = resp.read(1024 * 1024)
                        if not chunk:
                            return
                        yield chunk
            return body()
        if attempt < retries:
            time.sleep(2 ** attempt)
    raise ProvisionError(f"companion repository unreachable after {retries} attempts ({last})")


def contents_url(repository: str, prefix: str, name: str, ref: str) -> str:
    path = "/".join(urllib.parse.quote(part, safe="") for part in [*prefix.strip("/").split("/"), name] if part)
    url = f"{API_ROOT}/repos/{repository}/contents/{path}"
    return f"{url}?ref={urllib.parse.quote(ref, safe='')}" if ref else url


def download_verified(
    name: str,
    meta: Mapping[str, object],
    destination: Path,
    fetch: Callable[[], Iterable[bytes]],
) -> None:
    """Write the stream to a temporary file in the destination directory, verify size and digest, then rename."""
    destination.mkdir(parents=True, exist_ok=True)
    final = destination / name
    limit = int(meta["size_bytes"])
    handle, temp_name = tempfile.mkstemp(prefix=".provision-", suffix=".part", dir=destination)
    temp = Path(temp_name)
    try:
        digest = hashlib.sha256()
        total = 0
        with os.fdopen(handle, "wb") as out:
            for chunk in fetch():
                total += len(chunk)
                if total > limit:
                    raise ProvisionError(f"{name!r}: download is larger than the pinned {limit} bytes")
                digest.update(chunk)
                out.write(chunk)
        if total != limit:
            raise ProvisionError(f"{name!r}: downloaded {total} bytes, pinned size is {limit}")
        if digest.hexdigest() != meta["sha256"]:
            raise ProvisionError(f"{name!r}: SHA-256 does not match the frozen manifest")
        os.replace(temp, final)
    finally:
        if temp.exists():
            temp.unlink()


# ---------------------------------------------------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------------------------------------------------


def provision(
    *,
    manifest_root: Path,
    destination: Path,
    names: Sequence[str] = (),
    projects: Sequence[str] = (),
    repository: str = "",
    ref: str = "",
    source_path_prefix: str = DEFAULT_SOURCE_PATH_PREFIX,
    token: str = "",
    fetcher: Optional[Callable[[str, str], Iterable[bytes]]] = None,
) -> Dict[str, str]:
    """Return {name: "present" | "downloaded"}. Raises ProvisionError unless every selected file is verified."""
    expected = load_expected(manifest_root)
    selected = select(expected, list(names), list(projects))
    if not selected:
        raise ProvisionError("nothing selected")
    destination = Path(destination)
    result: Dict[str, str] = {}
    pending: List[str] = []
    for name in selected:
        if is_verified(destination / name, expected[name]):
            result[name] = "present"
        else:
            pending.append(name)
    if pending:
        if not token:
            raise ProvisionError(
                f"{len(pending)} original source file(s) are not present and no {TOKEN_ENV} is available "
                "(fork pull requests and unconfigured repositories get no secrets); refusing to continue: "
                + ", ".join(repr(n) for n in pending)
            )
        if not _REPO.match(repository or ""):
            raise ProvisionError("the companion repository must be given as owner/name")
        if ref and not _REF.match(ref):
            raise ProvisionError("the companion ref contains characters that are not allowed")
        fetch_with = fetcher or http_fetch
        for name in pending:
            url = contents_url(repository, source_path_prefix, name, ref)
            download_verified(name, expected[name], destination, lambda u=url: fetch_with(u, token))
            result[name] = "downloaded"
    # final proof, independent of the path taken above
    for name in selected:
        if not is_verified(destination / name, expected[name]):
            raise ProvisionError(f"{name!r}: not verified after provisioning")
    return dict(sorted(result.items()))


def _split_lines(value: str) -> List[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-root", default=DEFAULT_MANIFEST_ROOT)
    parser.add_argument("--destination", default=DEFAULT_DESTINATION)
    parser.add_argument("--names", default="", help="newline separated exact manifest names (default: all)")
    parser.add_argument("--projects", default="", help="newline or comma separated project ids")
    parser.add_argument("--repository", default="", help="private companion repository, owner/name")
    parser.add_argument("--ref", default="", help="companion branch, tag or commit (optional)")
    parser.add_argument("--source-path-prefix", default=DEFAULT_SOURCE_PATH_PREFIX)
    parser.add_argument("--allow-missing", default="false", choices=["true", "false"])
    args = parser.parse_args(argv)

    token = os.environ.get(TOKEN_ENV, "").strip()
    projects = [p.strip() for chunk in _split_lines(args.projects) for p in chunk.split(",") if p.strip()]
    outputs = os.environ.get("GITHUB_OUTPUT")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")

    def emit(provisioned: bool) -> None:
        if outputs:
            with open(outputs, "a", encoding="utf-8") as handle:
                handle.write(f"provisioned={'true' if provisioned else 'false'}\n")

    try:
        result = provision(
            manifest_root=Path(args.manifest_root),
            destination=Path(args.destination),
            names=_split_lines(args.names),
            projects=projects,
            repository=args.repository.strip(),
            ref=args.ref.strip(),
            source_path_prefix=args.source_path_prefix,
            token=token,
        )
    except ProvisionError as exc:
        emit(False)
        message = f"original sources NOT provisioned: {exc}"
        if args.allow_missing == "true":
            print(f"::warning::{message}")
            return 0
        print(f"::error::{message}")
        return 1

    emit(True)
    expected = load_expected(Path(args.manifest_root))
    for name, how in result.items():
        print(f"{how:10} {name} sha256={expected[name]['sha256'][:12]}… size={expected[name]['size_bytes']}")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("### Original sources\n")
            for name, how in result.items():
                handle.write(f"- {how}: `{name}` (sha256 `{expected[name]['sha256'][:12]}…`)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
