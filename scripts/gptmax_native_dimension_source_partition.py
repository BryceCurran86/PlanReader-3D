"""Authenticate original numeric text paint partitions in a read-only audit.

This retains the existing word receipt as owner. It never guesses a split in
a numeric string, changes the live producer, or publishes a host or quantity.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, replace
from hashlib import sha256
import json
import math
from pathlib import Path

import fitz

from pb_figured_dimension_evidence import classify_dimension_token
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_native_dimension_cap_evidence import (
    compile_native_dimension_cap_components, native_dimension_cap_evidence_from_components,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import NATIVE_PDF_VISIBLE_SEGMENT, SourceVisibilityProducer


def _signature(character):
    return (ord(character['c']), *character['origin'])


def _paint_partitions(*, words, raw_blocks, traces, paint_commands):
    """Exact glyph ownership, complete command coverage, no arbitrary slicing.

    This helper has no source authority. The public audit supplies these facts
    freshly decoded from its authenticated original PDF and owned text receipts.
    Ambiguous, partial, invisible or cross-word commands cannot nominate splits.
    """
    additions, receipts = [], []
    for word in sorted(words, key=lambda w: w['id']):
        if not classify_dimension_token(word['text']).is_linear_dimension:
            continue
        try:
            line = raw_blocks[word['block_no']]['lines'][word['line_no']]
        except (IndexError, KeyError):
            continue
        x0, y0, x1, y1 = word['bbox']
        characters = [c for span in line['spans'] for c in span['chars']
            if x0 <= (c['bbox'][0] + c['bbox'][2]) / 2 <= x1
            and y0 <= (c['bbox'][1] + c['bbox'][3]) / 2 <= y1]
        if (not characters or ''.join(c['c'] for c in characters) != word['text']
                or any(c.get('synthetic', False) or len(c['c']) != 1 for c in characters)):
            continue
        signatures = tuple(_signature(c) for c in characters)
        if (len(set(signatures)) != len(signatures)
                or any(not all(math.isfinite(v) for v in sig) for sig in signatures)):
            continue
        positions = {sig: n for n, sig in enumerate(signatures)}
        runs = []
        for trace in traces:
            glyphs = trace['chars']
            keys = tuple((c[0], *c[2]) for c in glyphs)
            if not keys or not set(keys) <= positions.keys():
                continue
            indices = tuple(positions[key] for key in keys)
            # The original text command must own a consecutive, ordered run.
            if indices != tuple(range(indices[0], indices[0] + len(indices))):
                continue
            text = ''.join(chr(key[0]) for key in keys)
            if (trace['type'] not in (0, 1) or trace['opacity'] != 1.0
                    or tuple(trace['dir']) != tuple(word['axis'])
                    or not classify_dimension_token(text).is_linear_dimension
                    or not all(math.isfinite(v) for v in trace['bbox'])
                    or type(trace['seqno']) is not int):
                continue
            runs.append((indices, trace, text))
        coverage = Counter(i for indices, _trace, _text in runs for i in indices)
        if (len(runs) < 2 or coverage != Counter(range(len(signatures)))
                or len({trace['seqno'] for _indices, trace, _text in runs}) != len(runs)):
            continue
        ordered = sorted(runs, key=lambda row: row[0])
        if ''.join(text for _indices, _trace, text in ordered) != word['text']:
            continue
        # These remain owned by the original word observation. A paint command
        # is not a new text authority, dimension value or physical identity.
        partitions = []
        for indices, trace, text in ordered:
            partitions.append(dict(seqno=trace['seqno'], text=text,
                bbox=tuple(trace['bbox']), axis=tuple(trace['dir']),
                owned_character_indices=indices, glyph_signatures=tuple(signatures[i] for i in indices)))
        paint_seqnos = {part['seqno'] for part in partitions}
        if min(paint_seqnos) < 0 or max(paint_seqnos) >= len(paint_commands):
            continue
        authenticated = (word['text_integrity_status'] == EvidenceResolutionStatus.CORROBORATED.value
            and paint_seqnos == set(word['receipt_trace_sequence_numbers']))
        if authenticated:
            additions.extend(dict(id=word['id'], text=part['text'], bbox=part['bbox'], axis=part['axis'])
                for part in partitions)
        payload = dict(text_observation_id=word['id'], raw_text=word['text'],
            text_integrity_status=word['text_integrity_status'],
            text_integrity_reason_codes=word['text_integrity_reason_codes'],
            receipt_trace_sequence_numbers=word['receipt_trace_sequence_numbers'],
            text_integrity_authenticated=authenticated,
            owned_word_bbox=tuple(word['bbox']), original_paint_partitions=partitions,
            intervening_paint_commands=[dict(seqno=n, kind=paint_commands[n][0], bbox=paint_commands[n][1])
                for n in range(min(paint_seqnos), max(paint_seqnos) + 1) if n not in paint_seqnos])
        receipts.append(dict(partition_id=stable_contract_id('native_text_paint_partition', payload), **payload))
    return additions, receipts


def _candidate_state(result):
    return dict(status=result.status.value, reason_codes=result.reason_codes,
        candidate=asdict(result.candidate) if result.candidate is not None else None,
        existence_record_id=result.existence_record.record_id if result.existence_record is not None else None,
        opposing_evidence_ids=tuple(a.evidence_id for a in result.opposing_evidence_atoms))


def source_partition_report(source_bytes: bytes, *, page_ids, representative_observation_ids):
    """Reingest immutable bytes, authenticate all inputs, preserve live state."""
    if not isinstance(source_bytes, bytes):
        raise TypeError('original PDF must be immutable bytes')
    pages = tuple(page_ids)
    selected = tuple(representative_observation_ids)
    if (not pages or len(set(pages)) != len(pages)
            or any(not isinstance(p, str) or not p.isdecimal() or int(p) < 1 for p in pages)
            or not selected or len(set(selected)) != len(selected)):
        raise ValueError('invalid source page or representative universe')
    digest = sha256(source_bytes).hexdigest()
    source = SourceVisibilityProducer(producer_method='live-physical-net-wall',
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
    published = source.ingest_native_pdf_bytes(document_id=f'live-source:{digest[:32]}',
        source_bytes=source_bytes, source_locator='memory://live-physical-net-wall-source.pdf', page_ids=pages)
    records = {i: r for i, r in source.authority().authenticated_visible_observations(published)
        if r.observation_kind == NATIVE_PDF_VISIBLE_SEGMENT}
    if len(records) > 20000 or not set(selected) <= records.keys():
        raise ValueError('native source primitive cap or ownership unavailable')
    authority, text_authority = source._producer.authority(), source.text_integrity_authority()
    physical = source.physical_opening_authority()
    page_inputs, rows = {}, []
    with fitz.open(stream=source_bytes, filetype='pdf') as pdf:
        for representative in sorted(selected):
            selector = ObservationSelector(published.revision.document_id, published.revision.revision_id,
                digest, published.snapshot.snapshot_id, representative)
            before = physical.prove_existence(selector)
            candidate = before.candidate
            if candidate is None or candidate.page_id not in pages:
                raise ValueError('representative lacks an owned native opening hypothesis')
            support = frozenset(candidate.source_observation_ids)
            if (not support or not support <= records.keys()
                    or any(records[i].page_id != candidate.page_id for i in support)):
                raise ValueError('candidate support ownership unavailable')
            if candidate.page_id not in page_inputs:
                page = pdf[int(candidate.page_id) - 1]
                raw_blocks = page.get_text('rawdict', flags=fitz.TEXTFLAGS_WORDS)['blocks']
                words = []
                for observation_id in published.text_observation_ids:
                    query = replace(selector, observation_id=observation_id)
                    record = authority.resolve(query)
                    if record.status is not EvidenceResolutionStatus.CORROBORATED or record.observation is None:
                        raise RuntimeError('original text source integrity unavailable')
                    if record.observation.page_id != candidate.page_id:
                        continue
                    text = text_authority.resolve_text(query)
                    if text.status is EvidenceResolutionStatus.CONFLICT:
                        raise RuntimeError('original text receipt conflicts')
                    if text.receipt is None:
                        continue
                    receipt = text.receipt
                    axis = tuple(raw_blocks[receipt.block_no]['lines'][receipt.line_no]['dir'])
                    words.append(dict(id=observation_id, text=receipt.raw_text, bbox=receipt.geometry,
                        axis=axis, block_no=receipt.block_no, line_no=receipt.line_no,
                        text_integrity_status=text.status.value, text_integrity_reason_codes=text.reason_codes,
                        receipt_trace_sequence_numbers=receipt.trace_sequence_numbers))
                additions, partitions = _paint_partitions(words=words, raw_blocks=raw_blocks,
                    traces=page.get_texttrace(), paint_commands=page.get_bboxlog())
                segments = {i: tuple(r.geometry) for i, r in records.items() if r.page_id == candidate.page_id}
                trusted_words = [w for w in words if w['text_integrity_status'] == EvidenceResolutionStatus.CORROBORATED.value]
                original = compile_native_dimension_cap_components(segments=segments, words=trusted_words)
                expanded = compile_native_dimension_cap_components(segments=segments, words=[*trusted_words, *additions])
                page_inputs[candidate.page_id] = original, expanded, partitions
            original, expanded, partitions = page_inputs[candidate.page_id]
            atoms = native_dimension_cap_evidence_from_components(components=expanded,
                selected_ids=tuple(support), document_id=selector.document_id, page_id=candidate.page_id,
                revision_id=selector.revision_id, source_sha256=digest, snapshot_id=selector.snapshot_id)
            word_ids = {a.metadata['text_observation_id'] for a in atoms}
            support_geometries = [records[i].geometry for i in support]
            # Relevance is an audit inventory, not evidence nomination. Keep all
            # partitions intersecting the complete support extent, including
            # untrusted text, without feeding them to the component compiler.
            x0 = min(min(g[::2]) for g in support_geometries)
            x1 = max(max(g[::2]) for g in support_geometries)
            y0 = min(min(g[1::2]) for g in support_geometries)
            y1 = max(max(g[1::2]) for g in support_geometries)
            relevant = [p for p in partitions if p['text_observation_id'] in word_ids
                or (p['owned_word_bbox'][0] <= x1 and p['owned_word_bbox'][2] >= x0
                    and p['owned_word_bbox'][1] <= y1 and p['owned_word_bbox'][3] >= y0)]
            original_covered = frozenset(i for _lines, _word, covered in original for i in covered)
            expanded_covered = frozenset(i for _lines, _word, covered in expanded for i in covered)
            after = physical.prove_existence(selector)
            if _candidate_state(before) != _candidate_state(after):
                raise RuntimeError('shadow partition audit changed live physical state')
            rows.append(dict(representative_observation_id=representative,
                original_live_state=_candidate_state(before), live_state_unchanged=True,
                source_supports=[dict(observation_id=i, geometry=records[i].geometry,
                    source_primitive_ref=records[i].source_primitive_ref) for i in sorted(support)],
                original_uncovered_support_ids=sorted(support - original_covered),
                partition_uncovered_support_ids=sorted(support - expanded_covered),
                complete_shadow_dimension_opposition=bool(atoms),
                shadow_opposing_evidence_atoms=[asdict(atom) for atom in atoms],
                relevant_original_text_paint_partitions=relevant))
    return dict(source_sha256=digest, revision_id=published.revision.revision_id,
        snapshot_id=published.snapshot.snapshot_id, selected_geometry_page_ids=pages,
        primitive_safety_cap=20000, original_native_segment_count=len(records),
        source_reauthenticated=True, candidate_audits=rows,
        live_producer_changed=False, hypotheses_deletion_allowed=False,
        physical_nonexistence_proven=False, host_publication_allowed=False,
        opening_count_publication_allowed=False, metric_quantity_publication_allowed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', type=Path, required=True)
    parser.add_argument('--page-id', action='append', required=True)
    parser.add_argument('--representative-observation-id', action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = source_partition_report(args.pdf.read_bytes(), page_ids=args.page_id,
        representative_observation_ids=args.representative_observation_id)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(source_sha256=report['source_sha256'],
        complete_shadow_oppositions=sum(r['complete_shadow_dimension_opposition'] for r in report['candidate_audits']),
        live_producer_changed=False)))


if __name__ == '__main__':
    main()
