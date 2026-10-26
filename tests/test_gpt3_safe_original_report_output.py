"""Original-source replay publication is strictly create-only and fail-closed."""
from pathlib import Path
import pytest
from tools import gpt3_safe_original_report_output as pub


def test_create_only_diagnostic_preserves_signed_inputs_and_originals(tmp_path):
    original = tmp_path / "original.pdf"
    original.write_bytes(b"%PDF-original-secret")
    sealed = tmp_path / "signed.json"
    sealed.write_bytes(b"original-signed-v1")
    frozen = tmp_path / "frozen"
    frozen.mkdir()
    destination = tmp_path / "reports" / "new.json"
    pub.write_new_diagnostic(destination, '{"score":null}\n',
                             protected_roots=(original, sealed, frozen))
    assert destination.read_text() == '{"score":null}\n'
    assert sealed.read_bytes() == b"original-signed-v1"
    assert original.read_bytes() == b"%PDF-original-secret"
    with pytest.raises(FileExistsError, match="new path"):
        pub.write_new_diagnostic(destination, '{}',
                                 protected_roots=(original, sealed, frozen))
    assert destination.read_text() == '{"score":null}\n'


@pytest.mark.parametrize("target", ["original", "signed", "frozen", "nested"])
def test_replay_rejects_source_frozen_aliases_and_children(tmp_path, target):
    original = tmp_path / "source.pdf"
    original.write_bytes(b"%PDF-original")
    signed = tmp_path / "original-signed-v1.json"
    signed.write_bytes(b"original-signed-v1")
    frozen = tmp_path / "frozen"
    frozen.mkdir()
    targets = {"original": original, "signed": signed,
               "frozen": frozen, "nested": frozen / "projects" / "new.json"}
    with pytest.raises((ValueError, FileExistsError)):
        pub.preflight_new_diagnostic(targets[target],
                                     protected_roots=(original, signed, frozen))
    assert signed.read_bytes() == b"original-signed-v1"
    assert not (frozen / "projects").exists()


def test_external_existing_json_and_symlink_diagnostics_cannot_be_replaced(tmp_path):
    unrelated = tmp_path / "unrelated.json"
    unrelated.write_text('{"customer":"original"}')
    source = tmp_path / "signed.json"
    source.write_text("immutable")
    for target in (unrelated, tmp_path / "linked.json"):
        if target.name == "linked.json":
            target.symlink_to(source)
        with pytest.raises(FileExistsError, match="new path"):
            pub.write_new_diagnostic(target, '{}', protected_roots=(source,))
    assert unrelated.read_text() == '{"customer":"original"}'
    assert source.read_text() == "immutable"


def test_atomic_exclusive_publication_rolls_back_temp_after_competing_writer(
    tmp_path, monkeypatch,
):
    target = tmp_path / "report.json"
    origin = tmp_path / "original.pdf"
    origin.write_bytes(b"secret")
    real_link = pub.os.link

    def competing_link(temp, dest):
        Path(dest).write_text("competing-writer")
        return real_link(temp, dest)

    monkeypatch.setattr(pub.os, "link", competing_link)
    with pytest.raises(FileExistsError):
        pub.write_new_diagnostic(target, "our-new-report", protected_roots=(origin,))
    assert target.read_text() == "competing-writer"
    assert origin.read_bytes() == b"secret"
    assert not list(tmp_path.glob(".gpt3-original-report-*.tmp"))


def test_none_root_is_accepted_and_payload_must_be_unicode(tmp_path):
    target = tmp_path / "report.json"
    with pytest.raises(TypeError):
        pub.write_new_diagnostic(target, b"not Unicode", protected_roots=(None,))
    assert not target.exists()
    assert not list(tmp_path.glob(".gpt3-original-report-*.tmp"))


def test_original_replay_cli_preflights_existing_destination_before_source_reader(
    tmp_path, monkeypatch,
):
    from tools import run_gpt3_original_byte_gated_exact_project as gate
    output = tmp_path / "existing-unrelated.json"
    output.write_text('{"signed":"unchanged"}')
    monkeypatch.setattr(
        gate, "build_original_byte_gated_project_report",
        lambda **kw: (_ for _ in ()).throw(AssertionError("must not read PDF or signed input")),
    )
    with pytest.raises(FileExistsError, match="new path"):
        gate.main([
            "--manifest", str(tmp_path / "manifest.json"),
            "--sealed-run", str(tmp_path / "signed.json"),
            "--identity-map", str(tmp_path / "map.json"),
            "--source", str(tmp_path / "source.pdf"),
            "--output", str(output),
        ])
    assert output.read_text() == '{"signed":"unchanged"}'


def test_original_report_replaced_after_exclusive_link_cannot_claim_success(
    tmp_path, monkeypatch,
):
    output = tmp_path / "report.json"
    source = tmp_path / "original.pdf"
    source.write_bytes(b"%PDF-source-unchanged")
    actual_link = pub.os.link
    def replace_after_link(staged, destination):
        actual_link(staged, destination)
        Path(destination).unlink()
        Path(destination).write_text("racing-writer-report", encoding="utf-8")
    monkeypatch.setattr(pub.os, "link", replace_after_link)
    with pytest.raises(ValueError, match="output changed"):
        pub.write_new_diagnostic(output, '{"source":"verified"}\n',
                                 protected_roots=(source,))
    assert output.read_text(encoding="utf-8") == "racing-writer-report"
    assert source.read_bytes() == b"%PDF-source-unchanged"
    assert not list(tmp_path.glob(".gpt3-original-report-*.tmp"))


def test_original_report_in_place_mutation_is_not_accepted_as_same_inode(
    tmp_path, monkeypatch,
):
    output = tmp_path / "report.json"
    source = tmp_path / "original.pdf"
    source.write_bytes(b"%PDF-source-unchanged")
    actual_link = pub.os.link
    def tamper_after_link(staged, destination):
        actual_link(staged, destination)
        # Changes BOTH destination and staging via their shared inode.
        Path(destination).write_text("mutated-but-still-same-inode", encoding="utf-8")
    monkeypatch.setattr(pub.os, "link", tamper_after_link)
    with pytest.raises(ValueError, match="output changed"):
        pub.write_new_diagnostic(output, '{"source":"verified"}\n',
                                 protected_roots=(source,))
    assert not output.exists()
    assert source.read_bytes() == b"%PDF-source-unchanged"
    assert not list(tmp_path.glob(".gpt3-original-report-*.tmp"))


def test_competing_report_after_second_input_verification_keeps_other_writer(
    tmp_path,
):
    output = tmp_path / "report.json"
    original = tmp_path / "original.pdf"
    original.write_bytes(b"%PDF-untouched")
    callbacks = []
    def verifier():
        callbacks.append("checked")
        if len(callbacks) == 2:
            output.unlink()
            output.write_text("replacement-after-input-check", encoding="utf-8")
    with pytest.raises(ValueError, match="output changed"):
        pub.write_new_diagnostic(output, '{"source":"verified"}\n',
                                 protected_roots=(original,), verify_inputs=verifier)
    assert callbacks == ["checked", "checked"]
    assert output.read_text(encoding="utf-8") == "replacement-after-input-check"
    assert original.read_bytes() == b"%PDF-untouched"
    assert not list(tmp_path.glob(".gpt3-original-report-*.tmp"))


def test_uncontested_new_report_still_keeps_exact_original_utf8_bytes(tmp_path):
    output = tmp_path / "new.json"
    payload = '{"state":"verified","note":"café"}\n'
    pub.write_new_diagnostic(output, payload, protected_roots=(None,))
    assert output.read_bytes() == payload.encode("utf-8")


@pytest.mark.parametrize("replacement_kind", ["same_bytes_regular", "same_bytes_symlink"])
def test_same_byte_report_replacement_between_identity_and_read_is_rejected(
    tmp_path, monkeypatch, replacement_kind,
):
    """The two old path reads accepted a different inode with identical bytes."""
    output = tmp_path / "report.json"
    replacement = tmp_path / "other-report.json"
    source = tmp_path / "original.pdf"
    payload = '{"verified":true}\\n'
    source.write_bytes(b"%PDF-private-source-unchanged")
    replacement.write_text(payload, encoding="utf-8")
    real_samefile = Path.samefile
    real_open = pub.os.open
    swapped = False

    def swap():
        nonlocal swapped
        if swapped:
            return
        swapped = True
        if replacement_kind == "same_bytes_regular":
            replacement.replace(output)
        else:
            output.unlink()
            output.symlink_to(replacement)

    # Old implementation calls samefile() then read_bytes() on two separate
    # path opens. Inject just after its successful identity comparison.
    def swap_after_old_identity(self, other):
        result = real_samefile(self, other)
        if self == output and result:
            swap()
        return result

    # New implementation checks the same identity on a no-follow descriptor.
    # Inject between its lstat and descriptor open instead.
    def swap_before_descriptor_open(path, flags, *args, **kwargs):
        if Path(path) == output:
            swap()
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(Path, "samefile", swap_after_old_identity)
    monkeypatch.setattr(pub.os, "open", swap_before_descriptor_open)
    with pytest.raises(ValueError, match="output changed"):
        pub.write_new_diagnostic(output, payload, protected_roots=(source,))
    assert swapped
    assert output.read_bytes() == payload.encode("utf-8")
    assert output.is_symlink() == (replacement_kind == "same_bytes_symlink")
    assert source.read_bytes() == b"%PDF-private-source-unchanged"
    assert not list(tmp_path.glob(".gpt3-original-report-*.tmp"))


def test_same_byte_report_replacement_after_descriptor_read_is_rejected(
    tmp_path, monkeypatch,
):
    """Rechecking the published path catches a post-read inode swap."""
    output = tmp_path / "report.json"
    replacement = tmp_path / "replacement.json"
    payload = '{"verified":"same-bytes"}\\n'
    replacement.write_text(payload, encoding="utf-8")
    real_fstat = pub.os.fstat
    reads = 0

    def replace_on_completed_descriptor_stat(fd):
        nonlocal reads
        result = real_fstat(fd)
        reads += 1
        if reads == 2:
            replacement.replace(output)
        return result

    monkeypatch.setattr(pub.os, "fstat", replace_on_completed_descriptor_stat)
    with pytest.raises(ValueError, match="output changed"):
        pub.write_new_diagnostic(output, payload, protected_roots=(None,))
    assert reads >= 2
    assert output.read_bytes() == payload.encode("utf-8")
    assert not list(tmp_path.glob(".gpt3-original-report-*.tmp"))
