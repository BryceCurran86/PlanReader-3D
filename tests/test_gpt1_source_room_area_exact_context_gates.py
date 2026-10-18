"""An original source room cannot inherit another page, viewport or revision."""
from types import SimpleNamespace as NS
from pb_source_room_area_bridge import _context_matches


class Context:
    document_id="doc"
    source_sha256="a"*64
    current_revision_id="rev1"
    revision_id="rev1"
    def trusted_page_numbers(self): return (7,)
    def trusted_viewport_ids(self): return ("view7",)
    def page_for_viewport(self, view): return 7 if view == "view7" else None


def sample(index_overrides=None, context_overrides=None, document_overrides=None, viewport_overrides=None, page_no=7):
    ix = dict(document_id="doc", source_sha256="a"*64,
              revision_id="rev1", viewport_id="view7", page_id="p7", page_no=7)
    ix.update(index_overrides or {})
    ct=Context()
    for k,v in (context_overrides or {}).items(): setattr(ct,k,v)
    doc=dict(document_id="doc",source_sha256="a"*64,page_ids=("p7",))
    doc.update(document_overrides or {})
    view=dict(viewport_id="view7",page_id="p7")
    view.update(viewport_overrides or {})
    return _context_matches(room_index=NS(**ix),context=ct,document=NS(**doc),viewport=NS(**view),page_no=page_no)


def test_same_original_page_and_revision_remains_eligible(): assert sample()
def test_foreign_source_sha_never_binds(): assert not sample(index_overrides={"source_sha256":"b"*64})
def test_stale_current_revision_does_not_publish(): assert not sample(context_overrides={"revision_id":"rev0"})
def test_untrusted_page_cannot_be_published(): assert not sample(page_no=8,index_overrides={"page_no":8})
def test_wrong_document_page_id_cannot_bind(): assert not sample(document_overrides={"page_ids":("p8",)})
def test_untrusted_viewport_cannot_bind(): assert not sample(viewport_overrides={"viewport_id":"view8"})
def test_string_float_and_bool_page_aliases_are_rejected():
    for value in ("7",7.0,True,7.9,None):
        assert not sample(page_no=value)
        assert not sample(index_overrides={"page_no":value})
def test_original_page_id_and_viewport_membership_are_exact():
    assert not sample(index_overrides={"page_id":"p9"})
    assert not sample(index_overrides={"viewport_id":"view9"})
