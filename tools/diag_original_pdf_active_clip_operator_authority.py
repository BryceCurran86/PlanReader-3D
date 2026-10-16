"""Literal-safe, fail-closed PDF graphics-state source text clip proof.

This is NOT a second visibility/Unicode/material authority. It proves one
narrow proposition directly from original content operator ancestry:
EVERY page-content BT...ET text object is outside any active W/W* clipping
scope, with q/Q stack balanced and no Form XObjects/inline image streams.

The existing pb_pdf_text_integrity_authority still proves native word
presence, exact original glyph bytes, paint/occlusion, trace identity and
optional content. A malformed, nested-clipped, unknown-source or adversarial
page has no positive result. No source text, room, quantity or material is
emitted by this module.
"""
from __future__ import annotations


_WHITE=frozenset(b"\x00\x09\x0a\x0c\x0d\x20")
_DELIMS=frozenset(b"()<>[]{}/%")


def _original_source_operators(content:bytes, *, max_bytes:int=16_000_000):
    """Enumerate actual PDF operators, ignoring all literal/hex/name tokens.

    Delimiter-state handling is essential: arbitrary data inside a text
    string such as '(q W* BT Q ET)' must NEVER affect graphics-state
    ancestry. Inline images fail-closed at BI before binary ID/EI body.
    """
    if type(content) is not bytes or not content or len(content)>max_bytes:
        return None
    size=len(content); i=0; out=[]
    while i<size:
        b=content[i]
        if b in _WHITE or b in b"[]{}":
            i+=1
            continue
        if b==ord("%"):
            i+=1
            while i<size and content[i] not in b"\r\n":
                i+=1
            continue
        if b==ord("("):
            depth=1;i+=1
            while i<size and depth:
                ch=content[i]
                if ch==ord("\\"):
                    i+=2
                    if i>size: return None
                    continue
                if ch==ord("("):depth+=1
                elif ch==ord(")"):depth-=1
                i+=1
            if depth:return None
            continue
        if b==ord("<"):
            if i+1<size and content[i+1]==ord("<"):
                i+=2
                continue
            i+=1
            while i<size and content[i]!=ord(">"):
                if content[i] not in _WHITE and chr(content[i]).lower() not in "0123456789abcdef":
                    return None
                i+=1
            if i==size:return None
            i+=1
            continue
        if b==ord(">"):
            if i+1<size and content[i+1]==ord(">"):
                i+=2
                continue
            return None
        if b==ord("/"):
            i+=1
            while i<size and content[i] not in _WHITE and content[i] not in _DELIMS:
                i+=1
            continue
        if b==ord(")"):
            return None
        start=i
        while i<size and content[i] not in _WHITE and content[i] not in _DELIMS:
            i+=1
        if i==start:
            return None
        token=content[start:i]
        # The interpreter only needs graphics/text control operators.
        if token in (b"q",b"Q",b"W",b"W*",b"BT",b"ET",b"BI",b"ID",b"EI",b"BX",b"EX"):
            out.append(token)
    return tuple(out)


def original_content_has_unclipped_text_blocks(
    content:bytes, *, max_source_operators:int=200000,
) -> tuple[bool,dict]:
    if type(max_source_operators) is not int or max_source_operators<1:
        raise ValueError("positive_bounded_source_operator_scope_required")
    ops=_original_source_operators(content)
    if ops is None or len(ops)>max_source_operators:
        return False,{"reason":"source_operator_lexical_scope_unresolved"}
    graphic_stack=[False]
    open_text=False
    text_count=0
    clip_count=0
    for op in ops:
        if op in (b"BI",b"ID",b"EI",b"BX",b"EX"):
            return False,{"reason":"unsupported_graphics_or_inline_image_operator"}
        if op==b"q":
            if len(graphic_stack)>=1024:
                return False,{"reason":"unbounded_graphics_state_nesting"}
            graphic_stack.append(graphic_stack[-1])
        elif op==b"Q":
            if len(graphic_stack)==1:
                return False,{"reason":"unbalanced_graphics_restore"}
            graphic_stack.pop()
        elif op in (b"W",b"W*"):
            # Conservatively mark clip active immediately on W; PDF applies
            # the clip after path termination, never before the next BT.
            graphic_stack[-1]=True
            clip_count+=1
        elif op==b"BT":
            if open_text:
                return False,{"reason":"nested_text_object"}
            if graphic_stack[-1]:
                return False,{"reason":"text_during_original_active_source_clip"}
            open_text=True
            text_count+=1
        elif op==b"ET":
            if not open_text:
                return False,{"reason":"text_object_without_original_begin"}
            open_text=False
    if open_text or len(graphic_stack)!=1 or text_count==0:
        return False,{"reason":"incomplete_original_graphics_or_text_scope"}
    if graphic_stack[-1]:
        return False,{"reason":"unclosed_original_page_clip"}
    return True,{
        "reason":"all_original_text_objects_outside_active_clip",
        "original_source_text_object_count":text_count,
        "original_raw_clipping_operator_count":clip_count,
        "original_qQ_scopes_balanced":True,
        "source_text_semantic_or_quantity_authority":False,
    }


def source_page_all_native_text_unclipped(page) -> bool:
    """Positive only for original page text streams with no Form XObjects."""
    try:
        if page.get_xobjects():
            return False
        content=page.read_contents()
        if type(content) is not bytes:
            content=bytes(content)
        okay,receipt=original_content_has_unclipped_text_blocks(content)
        if not okay:
            return False
        # Independent original native graphic-device clip count must match
        # raw operator count. This is a negative cross-check, never another
        # interpretation of word geometry/meaning.
        clips=sum(x.get("type")=="clip" for x in page.get_drawings(extended=True))
        return clips==receipt["original_raw_clipping_operator_count"]
    except (TypeError,ValueError,AttributeError,RuntimeError):
        return False
