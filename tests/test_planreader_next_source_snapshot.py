"""Native drafts must describe the exact authenticated PDF byte snapshot."""
from hashlib import sha256
import os
from pathlib import Path

import fitz
import pytest

from planreader_next import engine


def _pdf_bytes(text):
    with fitz.open() as document:
        page = document.new_page(width=300, height=300)
        page.insert_text((40, 60), text)
        page.draw_rect(fitz.Rect(40, 90, 200, 240))
        return document.tobytes(garbage=4, deflate=False)


@pytest.fixture
def originals(tmp_path):
    authentic = _pdf_bytes("AUTHENTIC")
    replacement = _pdf_bytes("REPLACED!")
    length = max(len(authentic), len(replacement))
    authentic += b"\n" * (length - len(authentic))
    replacement += b"\n" * (length - len(replacement))
    path = tmp_path / "drawing.pdf"
    path.write_bytes(authentic)
    return path, authentic, replacement


def test_native_loader_retains_original_digest_and_primitives(originals):
    path, authentic, _ = originals
    result = engine.load_native_page(path, 0)
    assert result.source_sha256 == sha256(authentic).hexdigest()
    assert result.page_index == 0
    assert any(word.text == "AUTHENTIC" for word in result.words)
    assert result.rectangles and result.segments
    assert path.read_bytes() == authentic


def test_parser_receives_authenticated_bytes_instead_of_reopening_path(
    originals, monkeypatch,
):
    path, authentic, _ = originals
    real_open = fitz.open
    observed = []

    def inspect_input(*args, **kwargs):
        observed.append((args, kwargs))
        assert args == ()
        assert kwargs["stream"] == authentic
        assert kwargs["filetype"] == "pdf"
        return real_open(*args, **kwargs)

    monkeypatch.setattr(fitz, "open", inspect_input)
    result = engine.load_native_page(path, 0)
    assert len(observed) == 1
    assert result.source_sha256 == sha256(authentic).hexdigest()


def test_same_size_same_mtime_source_replacement_cannot_borrow_original_sha(
    originals, monkeypatch,
):
    path, authentic, replacement = originals
    before = path.stat()
    assert len(authentic) == len(replacement)
    real_open = fitz.open
    replaced = False

    def replace_before_parser_reads(*args, **kwargs):
        nonlocal replaced
        assert not replaced
        replaced = True
        path.write_bytes(replacement)
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        assert path.stat().st_size == before.st_size
        assert path.stat().st_mtime_ns == before.st_mtime_ns
        return real_open(*args, **kwargs)

    monkeypatch.setattr(fitz, "open", replace_before_parser_reads)
    with pytest.raises(engine.SourceConflict, match="source_changed_during_read"):
        engine.load_native_page(path, 0)
    assert replaced
    assert path.read_bytes() == replacement


def test_same_byte_different_inode_source_swap_is_rejected(originals, monkeypatch):
    path, authentic, _ = originals
    before = path.stat()
    other = path.with_name("other.pdf")
    other.write_bytes(authentic)
    os.utime(other, ns=(before.st_atime_ns, before.st_mtime_ns))
    real_open = fitz.open
    replaced = False

    def swap_before_parser_reads(*args, **kwargs):
        nonlocal replaced
        assert not replaced
        replaced = True
        other.replace(path)
        assert path.stat().st_ino != before.st_ino
        return real_open(*args, **kwargs)

    monkeypatch.setattr(fitz, "open", swap_before_parser_reads)
    with pytest.raises(engine.SourceConflict, match="source_changed_during_read"):
        engine.load_native_page(path, 0)
    assert replaced
    assert path.read_bytes() == authentic


def test_snapshot_changed_after_initial_authentication_is_rejected(
    originals, monkeypatch,
):
    path, _, replacement = originals
    read_bytes = Path.read_bytes

    def replace_before_snapshot(self):
        if self == path:
            path.write_bytes(replacement)
        return read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", replace_before_snapshot)
    with pytest.raises(engine.SourceConflict, match="source_changed_during_read"):
        engine.load_native_page(path, 0)


def test_missing_source_has_explicit_source_conflict(tmp_path):
    with pytest.raises(engine.SourceConflict, match="source_identity_unavailable"):
        engine.load_native_page(tmp_path / "missing.pdf", 0)
