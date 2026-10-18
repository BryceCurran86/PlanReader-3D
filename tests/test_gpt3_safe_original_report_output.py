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
