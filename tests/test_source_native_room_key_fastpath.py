"""Full-page key OCR is optional on genuinely native room-labelled plans."""
from pb_new_numbered_space_key import detect_numbered_space_key
import pb_portable_raster_ocr_authority as ocr

SHA = "d" * 64


class FakeNativePlan:
    def __init__(self, room_names=True):
        names = (
            ["LIVING", "DINING", "BED", "BEDROOM", "MEDIA", "BATH",
             "GARAGE", "KITCHEN", "WC", "ENS", "LAUNDRY", "ENTRY"]
            if room_names else ["01", "02", "03", "ELEV", "A101"]
        )
        self.words = [
            (0, 0, 10, 5, t, 0, 0, n)
            for n, t in enumerate((["1000"] * 125) + names)
        ]
        self.drawings = [{}] * 3601

    def get_text(self, mode):
        assert mode == "words"
        return self.words

    def get_drawings(self):
        return self.drawings


def test_rich_native_room_labels_skip_auxiliary_full_page_ocr(monkeypatch):
    def forbidden():
        raise AssertionError("readable native labels must not start OCR")
    monkeypatch.setattr(ocr, "RapidOCRBackend", forbidden)
    report = detect_numbered_space_key(
        FakeNativePlan(), page_index=2, source_sha256=SHA
    )
    assert report.status == "ABSTAINED"
    assert report.reason == "native_room_names_visible_numbered_key_ocr_deferred"
    assert report.commercial_publishable is False


def test_sparse_native_room_names_keep_outlined_key_ocr_fallback(monkeypatch):
    calls = []
    class UnavailableOCR:
        def __init__(self):
            calls.append("called")
        def is_available(self):
            return False
    monkeypatch.setattr(ocr, "RapidOCRBackend", UnavailableOCR)
    report = detect_numbered_space_key(
        FakeNativePlan(room_names=False), page_index=2, source_sha256=SHA
    )
    assert calls == ["called"]
    assert report.reason == "source_numbered_key_ocr_backend_unavailable"


def test_explicit_forced_key_scan_still_available(monkeypatch):
    calls = []
    class UnavailableOCR:
        def __init__(self):
            calls.append("called")
        def is_available(self):
            return False
    monkeypatch.setattr(ocr, "RapidOCRBackend", UnavailableOCR)
    report = detect_numbered_space_key(
        FakeNativePlan(), page_index=2, source_sha256=SHA, force_ocr=True
    )
    assert calls == ["called"]
    assert report.reason == "source_numbered_key_ocr_backend_unavailable"


def test_native_key_anchor_cannot_be_skipped_on_room_label_count(monkeypatch):
    calls = []
    class UnavailableOCR:
        def __init__(self):
            calls.append("called")
        def is_available(self):
            return False
    monkeypatch.setattr(ocr, "RapidOCRBackend", UnavailableOCR)
    page = FakeNativePlan()
    page.words.append((0, 0, 10, 5, "KEY", 0, 0, 140))
    report = detect_numbered_space_key(
        page, page_index=2, source_sha256=SHA
    )
    assert calls == ["called"]
    assert report.reason == "source_numbered_key_ocr_backend_unavailable"


def test_explicit_ocr_request_overrides_low_vector_count(monkeypatch):
    called = []
    class UnavailableOCR:
        def __init__(self):
            called.append(True)
        def is_available(self):
            return False
    monkeypatch.setattr(ocr, "RapidOCRBackend", UnavailableOCR)
    page = FakeNativePlan()
    page.drawings = [{}] * 25
    got = detect_numbered_space_key(
        page, page_index=2, source_sha256=SHA, force_ocr=True
    )
    assert called == [True]
    assert got.reason == "source_numbered_key_ocr_backend_unavailable"
