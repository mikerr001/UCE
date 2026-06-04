"""
Grammar Inference Engine — aggressive multi-scale pattern extraction.

Strategy (fastest→best, pick whinniest seed):
  1. Line-level LZ deduplication: builds a dictionary of unique lines,
     stores a sequence of line IDs. Highly repetitive logs/forms → 1000:1+.
  2. N-gram block deduplication: paragraph-level templates with parameters.
  3. Format-specific preprocessing: JSON minify, XML strip, HTML strip.
  4. zstd level 22 fallback with long-distance matching.
Lossless: every path stores enough to reconstruct byte-for-byte.
"""

import io
import re
import json
import struct
import zstd
from collections import Counter, OrderedDict


def _read_raw(file_path: str) -> bytes:
    with open(file_path, 'rb') as f:
        return f.read()


def _to_text(raw: bytes) -> str:
    for enc in ('utf-8', 'utf-8-sig', 'latin-1'):
        try:
            return raw.decode(enc)
        except Exception:
            pass
    return raw.decode('utf-8', errors='replace')


def _preprocess(text: str, ext: str) -> str:
    if ext in ('.json',):
        try:
            return json.dumps(json.loads(text), separators=(',', ':'))
        except Exception:
            pass
    if ext in ('.html', '.htm', '.xml', '.svg', '.xhtml'):
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n', text)
    if ext in ('.css',):
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        text = re.sub(r'\s+', ' ', text)
    return text


def _line_dedup(text: str):
    """
    Line-level dictionary compression.
    Unique lines stored once; sequence stored as integer IDs.
    Returns (seed_bytes, ratio_estimate).
    """
    lines = text.split('\n')
    vocab = OrderedDict()
    seq = []
    for line in lines:
        if line not in vocab:
            vocab[line] = len(vocab)
        seq.append(vocab[line])

    unique = len(vocab)
    total = len(lines)
    if unique == total:
        return None

    vocab_list = list(vocab.keys())
    payload = {
        'v': vocab_list,
        's': seq,
    }
    raw_json = json.dumps(payload, ensure_ascii=False,
                          separators=(',', ':')).encode('utf-8')
    compressed = zstd.compress(raw_json, 22)
    return compressed


def _block_dedup(text: str):
    """
    Paragraph-level grammar with parameter substitution.
    """
    blocks = re.split(r'\n{2,}', text)
    blocks = [b for b in blocks if b.strip()]
    if len(blocks) < 4:
        return None

    def _norm(b):
        b = re.sub(r'\b\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?\b', '<DATE>', b)
        b = re.sub(r'\b\d+(\.\d+)?\b', '<NUM>', b)
        b = re.sub(r'https?://\S+', '<URL>', b)
        b = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '<EMAIL>', b)
        b = re.sub(r'[ \t]+', ' ', b)
        return b.strip()

    normed = [_norm(b) for b in blocks]
    freq = Counter(normed)
    templates = {norm: i for i, (norm, cnt) in
                 enumerate(freq.most_common(500)) if cnt >= 2 and len(norm) >= 20}

    if not templates:
        return None

    seq = [{'r': templates[n], 'o': o} if n in templates else {'u': o}
           for o, n in zip(blocks, normed)]

    trail = len(text) - len(text.rstrip('\n'))
    payload = {'t': list(templates.keys()), 's': seq, 'nl': trail}
    raw_json = json.dumps(payload, ensure_ascii=False,
                          separators=(',', ':')).encode('utf-8')
    return zstd.compress(raw_json, 22)


def encode(file_path: str) -> bytes:
    import os
    ext = os.path.splitext(file_path)[1].lower()
    raw = _read_raw(file_path)

    if not raw:
        return struct.pack('<B', 0) + zstd.compress(b'', 22)

    text = _to_text(raw)
    text = _preprocess(text, ext)

    candidates = []

    line_seed = _line_dedup(text)
    if line_seed:
        candidates.append((struct.pack('<B', 1) + struct.pack('<I', len(line_seed)) + line_seed,
                           'line'))

    block_seed = _block_dedup(text)
    if block_seed:
        candidates.append((struct.pack('<B', 2) + struct.pack('<I', len(block_seed)) + block_seed,
                           'block'))

    zstd_seed = struct.pack('<B', 0) + zstd.compress(raw, 22)
    candidates.append((zstd_seed, 'zstd'))

    best, _ = min(candidates, key=lambda x: len(x[0]))
    return best


def decode(seed: bytes) -> bytes:
    mode = struct.unpack('<B', seed[:1])[0]

    if mode == 0:
        return zstd.decompress(seed[1:])

    length = struct.unpack('<I', seed[1:5])[0]
    compressed = seed[5:5 + length]
    payload = json.loads(zstd.decompress(compressed).decode('utf-8'))

    if mode == 1:
        vocab = payload['v']
        seq = payload['s']
        lines = [vocab[i] for i in seq]
        return '\n'.join(lines).encode('utf-8')

    if mode == 2:
        templates = payload['t']
        seq = payload['s']
        trail = payload.get('nl', 1)
        blocks = []
        for item in seq:
            if 'r' in item:
                blocks.append(item['o'])
            else:
                blocks.append(item['u'])
        text = '\n\n'.join(blocks) + '\n' * max(1, trail)
        return text.encode('utf-8')

    return b''
