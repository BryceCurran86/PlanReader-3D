# Independent GPT MAX fifth-generation source-wall enclosure negative.
# Expected RED against #4353 until authentic connected room cycles replace corner counts.

def test_open_bottom_two_joined_corners_never_issue_customer_quantities():
    """Regression: two joined corners + two open bottom gaps cannot authorize FIRM.
    Synthetic PDF only; no real source or benchmark content. SHA patch isolates the
    quantity authority gate after genuine byte identity is replaced by test bytes.
    """
    from pathlib import Path
    from contextlib import ExitStack
    from tempfile import TemporaryDirectory
    from unittest.mock import patch
    import hashlib
    import fitz
    import pb_three_laurel_ceiling_customer as ceiling
    import pb_three_laurel_vinyl_floor_customer as vinyl
    import pb_three_laurel_wet_area_floor_customer as wet
    import pb_three_laurel_wall_tile_customer as wall

    terms = [
        "GROUND FLOOR PLAN AREA SCHEDULE VINYL TILES MEDIA BED 2 BED 3",
        "SECTION A-A 2,700 GYPROCK",
    ]
    for spec in wet._WET_FLOOR_SPECS.values():
        terms.extend(["TILES", *map(str, spec["dim_strings"])])
    for spec in vinyl._VINYL_FLOOR_SPECS.values():
        terms.extend(["VINYL", str(spec["room_label"]), *map(str, spec["dim_strings"])])
    for spec in wall._WALL_TILE_SPECS.values():
        terms.extend(map(str, spec["evidence_tokens"]))

    with TemporaryDirectory() as dirname:
        path=Path(dirname)/"native_unrelated_geometry.pdf"
        d=fitz.open()
        for page_i in range(18):
            page=d.new_page(width=1400,height=950)
            # Original adversarial decoy geometry, plus *unrelated* orthogonal
            # strokes meeting AntiGravity #4346 global H/V/long-line population.
            # They are disjoint, far from source room labels and finish boundaries.
            for i in range(1100):
                x=40+(i%100)*7
                y=380+(i//100)*17
                page.draw_line((x,y),(x+2.1,y+1.6),color=(0,0,0),width=.2)
            for i in range(60):
                page.draw_line((900,80+8*i),(924,80+8*i),color=(0,0,0),width=.2)
                page.draw_line((1100+2*i,80),(1100+2*i,104),color=(0,0,0),width=.2)
            # Native text, with real geometry and 20+ words on every page, but
            # no source-owned association to the 610 unrelated line fragments.
            text=" ".join(terms)
            words=text.split()
            for j in range(0,len(words),10):
                row=" ".join(words[j:j+10])
                page.insert_text((30,36+14*(j//10)),row,fontsize=7.4)
            # Dispersed real native words (not anchored to any physically
            # enclosed room). Meets x>=300,y>=200 dispersion.
            page.insert_text((1000,750),"FLOOR PLAN",fontsize=8)
            # Single unrelated thick ink stroke suffices for global 'authentic CAD'
            # feature check; it is not an enclosure, wall face or finish ownership.
            page.draw_line((1290,850),(1320,850),color=(0,0,0),width=0.8)
            if page_i==2:
                vals=[
                    "MAIN LIVING 12.34 m2",
                    "GARAGE 12.34 m2",
                    "MAIN PORCH 12.34 m2",
                    "MAIN ALFRESCO 12.34 m2",
                    "GF LIVING 12.34 m2",
                    "GF ALFRESCO 12.34 m2",
                    "GF PORCH 12.34 m2",
                ]
                for k,row in enumerate(vals):
                    page.insert_text((961,632+13*k),row,fontsize=8)
        # This page contains real native text and extra CAD strokes, but not one
        # enclosed physical room. Four detached strokes per label deliberately
        # satisfy the current quadrant-midpoint-only predicate.
        page=d[2]
        # All these are native words alone, without any associated physical wall.
        for i, label in enumerate(("BATH", "BATHROOM", "LAUNDRY", "ENSUITE", "WC")):
            page.insert_text((480, 195 + 47*i), label, fontsize=8)
        words=page.get_text("words")
        labels=("MEDIA","BED 2","BED 3","BATH","BATHROOM","LAUNDRY",
                "ENSUITE","LIVING","GARAGE","WC")
        for label in labels:
            toks=label.split()
            matches=[
                words[i:i+len(toks)] for i in range(len(words)-len(toks)+1)
                if all(toks[k].upper()==words[i+k][4].upper() for k in range(len(toks)))
            ]
            if not matches:
                print("MISSING_SOURCE_TOKEN",label,flush=True)
                continue
            token_words=matches[0]
            cx=(min(w[0] for w in token_words)+max(w[2] for w in token_words))/2
            cy=(min(w[1] for w in token_words)+max(w[3] for w in token_words))/2
            # All endpoints are isolated from every other stroke in this quartet.
            # 5th-gen open-bottom boundary: exactly TWO top corners touch;
            # both bottom corners have a visible 35-point gap, so NO room cycle.
            lines=(
                ((cx-35,cy-30),(cx+35,cy-30)),
                ((cx-35,cy+40),(cx+35,cy+40)),
                ((cx-35,cy-30),(cx-35,cy+5)),
                ((cx+35,cy-30),(cx+35,cy+5)),
            )
            for a,b in lines:
                page.draw_line(a,b,color=(0,0,0),width=0.2)
            # Extra local CAD fill, but the four disjoint lines do not connect
            page.draw_circle((cx+35,cy+35),radius=2,color=(0,0,0),fill=(0,0,0),width=.8)
            print("DISCONNECTED_QUADRANT_STROKES",label,round(cx,2),round(cy,2),flush=True)
        d.save(path)
        d.close()
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        with fitz.open(path) as check:
            print("NATIVE_SOURCE", "pages",check.page_count,
                  "vectors",len(check[2].get_drawings()),
                  "words",len(check[2].get_text("words")),
                  "schedule",ceiling._parse_schedule_table(check[2]),flush=True)
        for name,module,fn in (
            ("VINYL",vinyl,vinyl.issue_original_three_laurel_vinyl_floor_customer_quantities),
            ("WET_FLOOR",wet,wet.issue_original_three_laurel_wet_area_floor_customer_quantities),
            ("WALL_TILE",wall,wall.issue_original_three_laurel_wall_tile_customer_quantities),
            ("CEILING",ceiling,ceiling.issue_original_three_laurel_ceiling_customer_quantities),
        ):
            with ExitStack() as stack:
                stack.enter_context(patch.object(module,"THREE_LAUREL_SOURCE_SHA256",digest))
                stack.enter_context(patch.object(module,"THREE_LAUREL_DOCUMENT_ID",f"live-source:{digest[:32]}"))
                stack.enter_context(patch.object(module,"THREE_LAUREL_REVISION_ID",f"3laurel_sha_{digest[:20]}"))
                try:
                    result=fn(path)
                    print(name,"status",result.status,"quantity_count",len(result.quantities),
                          "customer_count",len(result.customer_rows),
                          "reasons",result.reason_codes,flush=True)
                    assert result.status == "ABSTAIN", (name,result.status,result.reason_codes)
                    assert not result.quantities, name
                    assert not result.customer_rows, name
                except Exception:
                    raise
