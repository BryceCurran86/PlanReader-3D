"""Lossless fragmented fill/stroke native word chains; no commercial authority."""
from copy import deepcopy
import fitz
import pytest
import pb_pdf_text_integrity_authority as authority


class _Page:
    def __init__(self, *,text="M-AMB"):
        self.word={"text":text,"bbox":(10.,20.,40.,30.)}
        self.spans=[]
        self.bboxlog=[("ignore",(0.,0.,0.,0.)) for _ in range(18)]
        self.draws=[]
        pieces=(text[0],text[1],text[2:])
        positions=(10.,15.,20.)
        for index,(piece,x) in enumerate(zip(pieces,positions)):
            start=10+index*3
            characters=tuple(
                (ord(c),ord(c),(x+4*i,20.),(x+4*i,20.,x+4*i+3.,30.))
                for i,c in enumerate(piece)
            )
            box=(x,20.,x+max(4.,4.*len(piece)),30.)
            for mode in (0,1):
                seq=start+mode
                span={"chars":characters,"seqno":seq,"type":mode,
                      "font":"ISO","bbox":box,"opacity":1.0,"layer":""}
                self.spans.append(span)
                self.bboxlog[seq]=( "fill-text" if mode==0 else "stroke-text",box)
            if index < 2:
                seq=start+2
                rect=fitz.Rect(10.+index,31.,30.+index,35.)
                self.draws.append({
                    "seqno":seq,"type":"f","fill":(1.,1.,1.),
                    "fill_opacity":1.0,"items":[("re",rect,1)],
                    "rect":rect,
                })
                self.bboxlog[seq]=("fill-path",tuple(rect))
    def get_texttrace(self): return self.spans
    def get_bboxlog(self): return self.bboxlog
    def get_drawings(self): return self.draws


def test_native_word_recovered_from_three_exact_paired_source_fragments():
    page=_Page()
    before=deepcopy(page.word)
    chain,text,reasons=authority._matching_trace_spans(page,page.word)
    assert text=="M-AMB" and not reasons and len(chain)==6
    assert tuple(s["seqno"] for s in chain)==(10,11,13,14,16,17)
    assert page.word==before


@pytest.mark.parametrize("change",(
    "unknown_paint","black_path","transparent_path","missing_rect",
    "extra_interleaved_paint","wrong_fragment","wrong_stroke","glyph_mismatch",
    "foreign_font","different_layer","half_opacity","extra_trace",
))
def test_untrusted_fragmented_word_does_not_gain_source_ownership(change):
    page=_Page()
    if change=="unknown_paint":
        page.bboxlog[12]=("stroke-path",page.bboxlog[12][1])
    elif change=="black_path":
        page.draws[0]["fill"]=(0.,0.,0.)
    elif change=="transparent_path":
        page.draws[0]["fill_opacity"]=0.6
    elif change=="missing_rect":
        page.draws[0]["items"]=[]
    elif change=="extra_interleaved_paint":
        page.draws.append({**page.draws[0],"seqno":18})
        page.spans[2]["seqno"]=19
    elif change=="wrong_fragment":
        page.spans[-2]["chars"]=tuple(
            (ord("X") if i==0 else c[0],c[1],c[2],c[3])
            for i,c in enumerate(page.spans[-2]["chars"])
        )
    elif change=="wrong_stroke":
        page.spans[-1]["type"]=0
    elif change=="glyph_mismatch":
        chars=list(page.spans[-1]["chars"])
        c=chars[0]
        chars[0]=(c[0],c[1]+1,c[2],c[3])
        page.spans[-1]["chars"]=tuple(chars)
    elif change=="foreign_font":
        page.spans[2]["font"]="FOREIGN"
    elif change=="different_layer":
        page.spans[2]["layer"]="other"
    elif change=="half_opacity":
        page.spans[3]["opacity"]=0.5
    elif change=="extra_trace":
        page.spans.append({**page.spans[0],"seqno":18})
    chain,text,reasons=authority._matching_trace_spans(page,page.word)
    assert chain==() and text=="" and reasons


def test_fragment_chain_does_not_override_ordinary_text_visibility_and_decode(monkeypatch):
    page=_Page()
    monkeypatch.setattr(authority,"_decode_status",
                        lambda p,s,t:("validated",(),2,"Type1","ISO"))
    def visibility(_page,_subject,span,**kwargs):
        if span["seqno"]==13:
            return ("unresolved_or_blocked",
                    (authority.TEXT_OCCLUDED_BY_LATER_PAINT,),13)
        return ("proven_visible",(),span["seqno"])
    monkeypatch.setattr(authority,"_visibility_status",visibility)
    result=authority.classify_native_word_integrity(page,page.word)
    assert result.trusted is False
    assert authority.TEXT_OCCLUDED_BY_LATER_PAINT in result.reason_codes
    assert result.trace_sequence_numbers==(10,11,13,14,16,17)


def test_private_original_split_source_words_are_never_faked_by_public_ci():
    from pathlib import Path
    import hashlib
    path=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
    if not path.exists():
        pytest.skip("Private original PDF not mounted; synthetic tests alone are not source proof")
    raw=path.read_bytes()
    assert hashlib.sha256(raw).hexdigest()=="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
    with fitz.open(stream=raw,filetype="pdf") as doc:
        page=doc[10]
        candidates=tuple(w for w in page.get_text("words",sort=False)
                         if w[4] in ("M-AMB","F-AMB") and w[5]<130)
        assert len(candidates)==2
        for rawword in candidates:
            word={"text":rawword[4],"bbox":tuple(rawword[:4])}
            spans,text,reasons=authority._matching_trace_spans(page,word)
            assert text==word["text"] and reasons==()
            assert len(spans)==6
    assert hashlib.sha256(path.read_bytes()).hexdigest()=="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
