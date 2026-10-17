"""The original-source provisioning action: SHA-verified, size-pinned, fail closed, token never echoed."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
ACTION_DIR = ROOT / ".github" / "actions" / "provision-original-sources"


def _load():
    spec = importlib.util.spec_from_file_location("provision_original_sources_under_test", ACTION_DIR / "provision.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


P = _load()
TOKEN = "ghp_SECRETTOKENVALUE0123456789"


def _doc(name: str, payload: bytes) -> dict:
    return {"name": name, "role": "architectural_drawings", "sha256": hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload), "page_count": 1}


def _manifests(tmp_path: Path, projects: dict) -> Path:
    root = tmp_path / "projects"
    for project, docs in projects.items():
        folder = root / project
        folder.mkdir(parents=True)
        (folder / "source_manifest.json").write_text(json.dumps({
            "schema_version": "1", "project_id": project, "source_documents": docs,
        }), encoding="utf-8")
    return root


PAYLOAD_A = b"%PDF-1.7 synthetic A " + b"a" * 4000
PAYLOAD_B = b"%PDF-1.7 synthetic B " + b"b" * 3000


@pytest.fixture()
def world(tmp_path):
    root = _manifests(tmp_path, {
        "proj_one": [_doc("Plan A (REV 1).pdf", PAYLOAD_A)],
        "proj_two": [_doc("Plan B.pdf", PAYLOAD_B), _doc("Plan A (REV 1).pdf", PAYLOAD_A)],
    })
    return {"manifests": root, "dest": tmp_path / "documents" / "sources", "files": {
        "Plan A (REV 1).pdf": PAYLOAD_A, "Plan B.pdf": PAYLOAD_B}}


def _fetcher(files: dict, calls: list, chunk: int = 1000):
    def fetch(url: str, token: str):
        calls.append((url, token))
        name = next(n for n in files if urllib.parse.unquote(url).endswith("/" + n))
        data = files[name]
        return (data[i:i + chunk] for i in range(0, len(data), chunk))
    return fetch


def _run(world, calls=None, **kw):
    calls = [] if calls is None else calls
    args = dict(manifest_root=world["manifests"], destination=world["dest"], repository="owner/sources", token=TOKEN,
                fetcher=_fetcher(world["files"], calls))
    args.update(kw)
    return P.provision(**args), calls


# ---------------------------------------------------------------------------------------------------------------------
# manifests and selection
# ---------------------------------------------------------------------------------------------------------------------


def test_expected_merges_projects_and_pins_digest_and_size(world):
    expected = P.load_expected(world["manifests"])
    assert sorted(expected) == ["Plan A (REV 1).pdf", "Plan B.pdf"]
    assert expected["Plan A (REV 1).pdf"]["projects"] == ["proj_one", "proj_two"]
    assert expected["Plan B.pdf"]["sha256"] == hashlib.sha256(PAYLOAD_B).hexdigest()
    assert expected["Plan B.pdf"]["size_bytes"] == len(PAYLOAD_B)


@pytest.mark.parametrize("bad_name", ["../escape.pdf", "sub/dir.pdf", "back\\slash.pdf", "C:evil.pdf", "notpdf.txt", "", " lead.pdf", ".."])
def test_manifest_names_must_be_plain_pdf_file_names(tmp_path, bad_name):
    root = _manifests(tmp_path, {"p": [_doc(bad_name, b"x")]})
    with pytest.raises(P.ProvisionError):
        P.load_expected(root)


def test_manifest_with_bad_digest_size_or_conflict_is_rejected(tmp_path):
    good = _doc("A.pdf", b"abc")
    with pytest.raises(P.ProvisionError):
        P.load_expected(_manifests(tmp_path / "1", {"p": [{**good, "sha256": "XYZ"}]}))
    with pytest.raises(P.ProvisionError):
        P.load_expected(_manifests(tmp_path / "2", {"p": [{**good, "size_bytes": 0}]}))
    with pytest.raises(P.ProvisionError):
        P.load_expected(_manifests(tmp_path / "3", {"p": [{**good, "size_bytes": True}]}))
    with pytest.raises(P.ProvisionError):
        P.load_expected(_manifests(tmp_path / "4", {"p": [good], "q": [_doc("A.pdf", b"different")]}))
    with pytest.raises(P.ProvisionError):
        P.load_expected(tmp_path / "nowhere")


def test_select_only_ever_picks_manifest_names(world):
    expected = P.load_expected(world["manifests"])
    assert P.select(expected, [], []) == ["Plan A (REV 1).pdf", "Plan B.pdf"]
    assert P.select(expected, [], ["proj_one"]) == ["Plan A (REV 1).pdf"]
    assert P.select(expected, ["Plan B.pdf", "Plan B.pdf"], []) == ["Plan B.pdf"]
    with pytest.raises(P.ProvisionError):
        P.select(expected, ["not-in-manifest.pdf"], [])
    with pytest.raises(P.ProvisionError):
        P.select(expected, [], ["no_such_project"])


# ---------------------------------------------------------------------------------------------------------------------
# provisioning behaviour
# ---------------------------------------------------------------------------------------------------------------------


def test_download_writes_verified_files_and_leaves_no_temp(world):
    result, calls = _run(world)
    assert result == {"Plan A (REV 1).pdf": "downloaded", "Plan B.pdf": "downloaded"}
    assert (world["dest"] / "Plan A (REV 1).pdf").read_bytes() == PAYLOAD_A
    assert (world["dest"] / "Plan B.pdf").read_bytes() == PAYLOAD_B
    assert sorted(p.name for p in world["dest"].iterdir()) == ["Plan A (REV 1).pdf", "Plan B.pdf"]
    assert all(token == TOKEN for _url, token in calls) and len(calls) == 2


def test_verified_files_already_present_need_no_token_and_no_network(world):
    world["dest"].mkdir(parents=True)
    (world["dest"] / "Plan B.pdf").write_bytes(PAYLOAD_B)
    calls: list = []
    result, _ = _run(world, calls, names=["Plan B.pdf"], token="", repository="")
    assert result == {"Plan B.pdf": "present"} and calls == []


def test_missing_token_fails_closed_and_writes_nothing(world):
    with pytest.raises(P.ProvisionError) as info:
        _run(world, token="")
    assert "refusing to continue" in str(info.value) and "Plan B.pdf" in str(info.value)
    assert not world["dest"].exists() or not list(world["dest"].iterdir())


def test_digest_mismatch_is_an_error_and_never_lands(world):
    world["files"]["Plan B.pdf"] = PAYLOAD_B[:-1] + b"Z"  # same size, different bytes
    with pytest.raises(P.ProvisionError, match="SHA-256"):
        _run(world, names=["Plan B.pdf"])
    assert list(world["dest"].iterdir()) == []


@pytest.mark.parametrize("mutate, message", [(lambda b: b + b"extra", "larger"), (lambda b: b[:-10], "pinned size")])
def test_size_mismatch_is_an_error_and_never_lands(world, mutate, message):
    world["files"]["Plan B.pdf"] = mutate(PAYLOAD_B)
    with pytest.raises(P.ProvisionError, match=message):
        _run(world, names=["Plan B.pdf"])
    assert list(world["dest"].iterdir()) == []


def test_a_download_step_that_leaves_nothing_behind_is_still_an_error(world, monkeypatch):
    """The final proof is independent of the download path: a no-op downloader must not look like success."""
    monkeypatch.setattr(P, "download_verified", lambda *a, **k: None)
    with pytest.raises(P.ProvisionError, match="not verified after provisioning"):
        _run(world, names=["Plan B.pdf"])


def test_oversize_stream_stops_before_the_whole_body_is_read(world):
    consumed = []

    def endless(url, token):
        for _ in range(10_000):
            consumed.append(1)
            yield b"x" * 1000

    with pytest.raises(P.ProvisionError, match="larger"):
        _run(world, names=["Plan B.pdf"], fetcher=endless)
    assert len(consumed) < 20


def test_wrong_existing_file_is_replaced_only_by_a_verified_download(world):
    world["dest"].mkdir(parents=True)
    target = world["dest"] / "Plan B.pdf"
    target.write_bytes(b"stale or substituted")
    world["files"]["Plan B.pdf"] = b"also wrong"
    with pytest.raises(P.ProvisionError):
        _run(world, names=["Plan B.pdf"])
    assert target.read_bytes() == b"stale or substituted"  # untouched, still unverified
    world["files"]["Plan B.pdf"] = PAYLOAD_B
    result, _ = _run(world, names=["Plan B.pdf"])
    assert result == {"Plan B.pdf": "downloaded"} and target.read_bytes() == PAYLOAD_B


def test_unlisted_names_are_never_requested(world):
    calls: list = []
    with pytest.raises(P.ProvisionError):
        _run(world, calls, names=["Plan B.pdf", "extra.pdf"])
    assert calls == []


@pytest.mark.parametrize("repository", ["", "no-slash", "a/b/c", "owner/na me", "../x/y"])
def test_repository_must_be_owner_slash_name(world, repository):
    calls: list = []
    with pytest.raises(P.ProvisionError):
        _run(world, calls, repository=repository)
    assert calls == []


def test_contents_url_quotes_names_and_refs():
    url = P.contents_url("o/r", "documents/sources", "1. Plan (REV E) #2 100%.pdf", "feature/x y")
    assert url.startswith("https://api.github.com/repos/o/r/contents/documents/sources/")
    assert "1.%20Plan%20%28REV%20E%29%20%232%20100%25.pdf" in url
    assert url.endswith("?ref=feature%2Fx%20y")
    assert P.contents_url("o/r", "d", "a.pdf", "") == "https://api.github.com/repos/o/r/contents/d/a.pdf"


def test_order_of_requested_names_does_not_matter(world):
    first, _ = _run(world, names=["Plan B.pdf", "Plan A (REV 1).pdf"])
    for f in world["dest"].iterdir():
        f.unlink()
    second, _ = _run(world, names=["Plan A (REV 1).pdf", "Plan B.pdf"])
    assert first == second


def test_redirect_to_another_host_drops_the_authorization_header():
    handler = P._NoAuthOnCrossHostRedirect()
    request = urllib.request.Request("https://api.github.com/repos/o/r/contents/x.pdf",
                                     headers={"Authorization": f"Bearer {TOKEN}", "Accept": "x"})
    cross = handler.redirect_request(request, None, 302, "Found", {}, "https://objects.githubusercontent.com/blob")
    same = handler.redirect_request(request, None, 302, "Found", {}, "https://api.github.com/other")
    assert "Authorization" not in cross.headers and "Authorization" not in cross.unredirected_hdrs
    assert same.headers.get("Authorization") == f"Bearer {TOKEN}"


# ---------------------------------------------------------------------------------------------------------------------
# command line behaviour
# ---------------------------------------------------------------------------------------------------------------------


def _cli(world, monkeypatch, tmp_path, *extra, token=TOKEN):
    out = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    if token:
        monkeypatch.setenv(P.TOKEN_ENV, token)
    else:
        monkeypatch.delenv(P.TOKEN_ENV, raising=False)
    argv = ["--manifest-root", str(world["manifests"]), "--destination", str(world["dest"]), *extra]
    return argv, out


def test_cli_fails_closed_without_a_token_and_never_prints_one(world, monkeypatch, tmp_path, capsys):
    argv, out = _cli(world, monkeypatch, tmp_path, "--repository", "owner/sources", token="")
    assert P.main(argv) == 1
    captured = capsys.readouterr().out
    assert "::error::original sources NOT provisioned" in captured
    assert "provisioned=false" in out.read_text()


def test_cli_allow_missing_warns_and_reports_false(world, monkeypatch, tmp_path, capsys):
    argv, out = _cli(world, monkeypatch, tmp_path, "--allow-missing", "true", token="")
    assert P.main(argv) == 0
    assert "::warning::original sources NOT provisioned" in capsys.readouterr().out
    assert "provisioned=false" in out.read_text()


def test_cli_success_reports_true_and_does_not_leak_the_token(world, monkeypatch, tmp_path, capsys):
    argv, out = _cli(world, monkeypatch, tmp_path, "--repository", "owner/sources", "--names", "Plan B.pdf")
    monkeypatch.setattr(P, "http_fetch", _fetcher(world["files"], []))
    assert P.main(argv) == 0
    text = capsys.readouterr().out
    assert "downloaded" in text and "Plan B.pdf" in text and TOKEN not in text
    assert "provisioned=true" in out.read_text()


def test_cli_a_failing_download_message_does_not_contain_the_token(world, monkeypatch, tmp_path, capsys):
    argv, _ = _cli(world, monkeypatch, tmp_path, "--repository", "owner/sources")

    def boom(url, token):
        raise P.ProvisionError("companion repository refused the request with HTTP 404")

    monkeypatch.setattr(P, "http_fetch", boom)
    assert P.main(argv) == 1
    assert TOKEN not in capsys.readouterr().out


# ---------------------------------------------------------------------------------------------------------------------
# the real repository
# ---------------------------------------------------------------------------------------------------------------------


def test_real_frozen_manifests_describe_the_ten_originals():
    expected = P.load_expected(ROOT / P.DEFAULT_MANIFEST_ROOT)
    assert len(expected) == 10
    assert all(len(m["sha256"]) == 64 and m["size_bytes"] > 0 for m in expected.values())
    assert {p for m in expected.values() for p in m["projects"]} >= {
        "au_qld_3laurel", "au_qld_lot16_power", "au_qld_maryborough_service_station", "au_qld_q5446_armstrong32_harlequin"}


def test_action_definition_is_well_formed_and_never_defaults_to_skipping():
    action = yaml.safe_load((ACTION_DIR / "action.yml").read_text(encoding="utf-8"))
    assert action["runs"]["using"] == "composite"
    inputs = action["inputs"]
    assert str(inputs["allow-missing"]["default"]) == "false"
    assert {"token", "repository", "ref", "names", "projects", "allow-missing"} <= set(inputs)
    step = action["runs"]["steps"][0]
    assert step["shell"] == "bash" and "provision.py" in step["run"]
    assert "ORIGINAL_SOURCES_TOKEN" in step["env"] and "::add-mask::" in step["run"]
    # the token travels in the environment only, never on the command line
    assert "--token" not in step["run"]


# ---------------------------------------------------------------------------------------------------------------------
# the real HTTP path, against two local servers (no GitHub, no secrets)
# ---------------------------------------------------------------------------------------------------------------------

import http.server
import threading


def _serve(handler_cls):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _quiet(cls):
    cls.log_message = lambda self, *a, **k: None
    return cls


def test_http_fetch_sends_the_token_only_to_the_first_host_across_a_redirect(world, monkeypatch, tmp_path):
    seen = {"object_store": [], "api": []}

    @_quiet
    class ObjectStore(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            seen["object_store"].append(self.headers.get("Authorization"))
            self.send_response(200)
            self.send_header("Content-Length", str(len(PAYLOAD_B)))
            self.end_headers()
            self.wfile.write(PAYLOAD_B)

    store = _serve(ObjectStore)

    @_quiet
    class Api(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            seen["api"].append((self.path, self.headers.get("Authorization"), self.headers.get("Accept")))
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{store.server_port}/blob")
            self.end_headers()

    api = _serve(Api)
    try:
        monkeypatch.setattr(P, "API_ROOT", f"http://127.0.0.1:{api.server_port}")
        result, _ = _run(world, names=["Plan B.pdf"], fetcher=P.http_fetch, ref="v1")
    finally:
        api.shutdown(); store.shutdown()
    assert result == {"Plan B.pdf": "downloaded"}
    assert (world["dest"] / "Plan B.pdf").read_bytes() == PAYLOAD_B
    path, auth, accept = seen["api"][0]
    assert path == "/repos/owner/sources/contents/documents/sources/Plan%20B.pdf?ref=v1"
    assert auth == f"Bearer {TOKEN}" and accept == "application/vnd.github.raw"
    assert seen["object_store"] == [None], "the token must not follow the redirect to another host"


@pytest.mark.parametrize("status", [401, 403, 404])
def test_auth_and_not_found_errors_are_final_and_not_retried(world, monkeypatch, status):
    hits = []

    @_quiet
    class Refuse(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(1)
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()

    server = _serve(Refuse)
    try:
        monkeypatch.setattr(P, "API_ROOT", f"http://127.0.0.1:{server.server_port}")
        with pytest.raises(P.ProvisionError, match=f"HTTP {status}") as info:
            _run(world, names=["Plan B.pdf"], fetcher=P.http_fetch)
    finally:
        server.shutdown()
    assert len(hits) == 1 and TOKEN not in str(info.value)
    assert list(world["dest"].iterdir()) == []


def test_server_errors_are_retried_then_succeed(world, monkeypatch):
    hits = []

    @_quiet
    class Flaky(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(1)
            if len(hits) < 3:
                self.send_response(503)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(PAYLOAD_B)))
            self.end_headers()
            self.wfile.write(PAYLOAD_B)

    server = _serve(Flaky)
    try:
        monkeypatch.setattr(P, "API_ROOT", f"http://127.0.0.1:{server.server_port}")
        monkeypatch.setattr(P.time, "sleep", lambda _s: None)
        result, _ = _run(world, names=["Plan B.pdf"], fetcher=P.http_fetch)
    finally:
        server.shutdown()
    assert result == {"Plan B.pdf": "downloaded"} and len(hits) == 3


def test_a_server_that_always_fails_ends_in_a_clear_error(world, monkeypatch):
    @_quiet
    class Down(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(502)
            self.send_header("Content-Length", "0")
            self.end_headers()

    server = _serve(Down)
    try:
        monkeypatch.setattr(P, "API_ROOT", f"http://127.0.0.1:{server.server_port}")
        monkeypatch.setattr(P.time, "sleep", lambda _s: None)
        with pytest.raises(P.ProvisionError, match="unreachable after 3 attempts"):
            _run(world, names=["Plan B.pdf"], fetcher=P.http_fetch)
    finally:
        server.shutdown()
