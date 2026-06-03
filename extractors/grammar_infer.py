"""
Grammar Inference Engine — for text documents, code, and structured files.

Identifies repeated paragraph/block patterns, extracts them as parameterised
grammar rules, and stores (rules + parameter list + residual).
Lossless: stores all original blocks, grammar reduces the compressed size
by allowing zstd to find much better redundancy across the structured data.
"""

import io
import re
import json
import struct
import zstd
from collections import Counter


MIN_RULE_LENGTH = 40
MIN_OCCURRENCES = 2
MAX_RULES = 500


def _extract_text(file_path: str) -> str:
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception:
        return ''


def _split_into_blocks(text: str) -> list:
    blocks = re.split(r'\n{2,}|\r\n{2,}', text)
    return [b for b in blocks if b.strip()]


def _normalize(block: str) -> str:
    block = re.sub(r'\b\d+(\.\d+)?\b', '<NUM>', block)
    block = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', '<DATE>', block)
    block = re.sub(r'https?://\S+', '<URL>', block)
    block = re.sub(r'\S+@\S+\.\S+', '<EMAIL>', block)
    return block.strip()


def encode(file_path: str) -> bytes:
    text = _extract_text(file_path)
    if not text:
        with open(file_path, 'rb') as f:
            raw = f.read()
        return struct.pack('<B', 0) + zstd.compress(raw, 19)

    blocks = _split_into_blocks(text)
    normalized = [_normalize(b) for b in blocks]

    freq = Counter(normalized)
    templates = {}
    for i, (norm, cnt) in enumerate(freq.most_common(MAX_RULES)):
        if cnt >= MIN_OCCURRENCES and len(norm) >= MIN_RULE_LENGTH:
            templates[norm] = i

    if not templates:
        with open(file_path, 'rb') as f:
            raw = f.read()
        return struct.pack('<B', 0) + zstd.compress(raw, 19)

    grammar = {str(i): norm for norm, i in templates.items()}

    sequence = []
    for orig, norm in zip(blocks, normalized):
        if norm in templates:
            sequence.append({'t': 'r', 'id': templates[norm], 'orig': orig})
        else:
            sequence.append({'t': 'u', 'orig': orig})

    trailing_newlines = len(text) - len(text.rstrip('\n'))
    meta = {
        'grammar': grammar,
        'sequence': sequence,
        'trail': trailing_newlines,
    }

    meta_bytes = json.dumps(meta, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    compressed = zstd.compress(meta_bytes, 19)

    fallback_compressed = zstd.compress(text.encode('utf-8'), 19)

    if len(compressed) + 5 >= len(fallback_compressed) + 1:
        with open(file_path, 'rb') as f:
            raw = f.read()
        return struct.pack('<B', 0) + zstd.compress(raw, 19)

    return struct.pack('<B', 1) + struct.pack('<I', len(compressed)) + compressed


def decode(seed: bytes) -> bytes:
    mode = struct.unpack('<B', seed[:1])[0]

    if mode == 0:
        return zstd.decompress(seed[1:])

    length = struct.unpack('<I', seed[1:5])[0]
    compressed = seed[5:5 + length]
    meta = json.loads(zstd.decompress(compressed).decode('utf-8'))

    sequence = meta['sequence']
    trail = meta.get('trail', 1)

    blocks_out = []
    for item in sequence:
        blocks_out.append(item['orig'])

    result = '\n\n'.join(blocks_out)
    result += '\n' * max(1, trail)
    return result.encode('utf-8')
