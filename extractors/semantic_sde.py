"""
Semantic Domain Encoder (SDE)

Pipeline (all lossless):
  1. Build a phrase dictionary from the document's own n-gram frequencies.
  2. Maximal-munch tokenizer: text → token ID stream.
  3. LZ77 back-references on the token stream.
  4. Adaptive order-2 Markov model + range coder (arithmetic coding).
  5. Fallback to zstd if the SDE result is not smaller.

Seed format (mode 0xA5):
  [1B  mode=0xA5]
  [2B  dict_size uint16]
  [4B  dict_bytes_len uint32]  ← zstd-compressed JSON phrase list
  [dict_bytes]
  [4B  sym_count uint32]       ← number of symbols in flat stream
  [range-coded bytes]

Seed format (mode 0x00):
  [1B  mode=0x00] [zstd-compressed raw bytes]
"""

import os
import re
import json
import struct
import zstd
import bisect
from collections import defaultdict, Counter

MAX_PHRASES = 600
LZ_WINDOW   = 128
LZ_MIN      = 3
LZ_MAX      = 64
MARKOV_ORD  = 2
LAPLACE     = 1
_MODE_SDE   = 0xA5
_MODE_ZSTD  = 0x00

# Symbol layout (relative to dict_size ds):
#   0 .. ds-1           phrase IDs
#   ds .. ds+255        raw byte escapes  (byte b → ds+b)
#   ds+256              MATCH_FLAG
#   ds+257 .. ds+384    distance symbols  (dist d  → ds+257+d-1, d in 1..128)
#   ds+385 .. ds+446    length  symbols   (len  l  → ds+385+l-LZ_MIN, l in 3..64)
#   total alphabet      ds + 447


def _alpha(ds: int) -> int:
    return ds + 447


def _match_flag(ds):  return ds + 256
def _dist_sym(ds, d): return ds + 257 + d - 1
def _len_sym(ds, l):  return ds + 385 + l - LZ_MIN
def _sym_to_dist(ds, s): return s - (ds + 257) + 1
def _sym_to_len(ds, s):  return s - (ds + 385) + LZ_MIN


# ── Phrase dictionary ─────────────────────────────────────────────────────────

def _build_phrases(words: list, max_phrases: int = MAX_PHRASES) -> list:
    counts: Counter = Counter()
    wlen = len(words)
    for n in range(2, 5):
        for i in range(wlen - n + 1):
            counts[tuple(words[i:i + n])] += 1
    scored = sorted(
        ((freq * (len(g) - 1), g) for g, freq in counts.items() if freq >= 2),
        reverse=True,
    )
    phrases = [" ".join(g) for _, g in scored[:max_phrases]]
    phrases.sort(key=len, reverse=True)
    return phrases


def _merge_phrases(shared: list, words: list) -> list:
    """
    Merge a shared corpus dict with up to 200 document-specific novelties.
    Cap the shared dict at 1 800 entries so the total stays ≤ 2 000.
    """
    base     = shared[:1800]
    base_set = set(base)
    doc      = _build_phrases(words, max_phrases=500)
    extra    = [p for p in doc if p not in base_set][:200]
    merged   = base + extra
    merged.sort(key=len, reverse=True)
    return merged


# ── Tokenizer ─────────────────────────────────────────────────────────────────

def _tokenize(text: str, phrases: list) -> list:
    raw = text.encode("utf-8")
    pbs = [(p.encode("utf-8"), i) for i, p in enumerate(phrases)]
    ds = len(phrases)
    tokens = []
    pos = 0
    rlen = len(raw)
    while pos < rlen:
        matched = False
        for pb, i in pbs:
            pl = len(pb)
            if raw[pos: pos + pl] == pb:
                tokens.append(i)
                pos += pl
                matched = True
                break
        if not matched:
            tokens.append(ds + raw[pos])
            pos += 1
    return tokens


def _detokenize(tokens: list, phrases: list) -> bytes:
    ds = len(phrases)
    parts = []
    for t in tokens:
        if t < ds:
            parts.append(phrases[t].encode("utf-8"))
        else:
            parts.append(bytes([t - ds]))
    return b"".join(parts)


# ── LZ77 ──────────────────────────────────────────────────────────────────────

def _lz77_enc(tokens: list) -> list:
    out = []
    n = len(tokens)
    pos_map: dict = defaultdict(list)
    i = 0
    while i < n:
        best_len = 0
        best_dist = 0
        start = max(0, i - LZ_WINDOW)
        cands = [p for p in pos_map.get(tokens[i], []) if p >= start]
        for j in sorted(cands, reverse=True)[:12]:
            max_k = min(LZ_MAX, n - i, i - j)
            if max_k < LZ_MIN:
                continue
            k = 0
            while k < max_k and tokens[j + k] == tokens[i + k]:
                k += 1
            if k >= LZ_MIN and k > best_len:
                best_len = k
                best_dist = i - j
        if best_len >= LZ_MIN:
            for di in range(best_len):
                lst = pos_map[tokens[i + di]]
                lst.append(i + di)
                if len(lst) > 16:
                    del lst[:-16]
            out.append((best_dist, best_len))
            i += best_len
        else:
            lst = pos_map[tokens[i]]
            lst.append(i)
            if len(lst) > 16:
                del lst[:-16]
            out.append(tokens[i])
            i += 1
    return out


def _lz77_dec(stream: list) -> list:
    out: list = []
    for item in stream:
        if isinstance(item, int):
            out.append(item)
        else:
            d, l = item
            base = len(out) - d
            for k in range(l):
                out.append(out[base + k])
    return out


# ── Symbol stream flatten / unflatten ─────────────────────────────────────────

def _flatten(lz_stream: list, ds: int) -> list:
    MF = _match_flag(ds)
    out = []
    for item in lz_stream:
        if isinstance(item, int):
            out.append(item)
        else:
            d, l = item
            out.append(MF)
            out.append(_dist_sym(ds, d))
            out.append(_len_sym(ds, l))
    return out


def _unflatten(seq: list, ds: int) -> list:
    MF = _match_flag(ds)
    out = []
    i = 0
    while i < len(seq):
        if seq[i] == MF:
            d = _sym_to_dist(ds, seq[i + 1])
            l = _sym_to_len(ds, seq[i + 2])
            out.append((d, l))
            i += 3
        else:
            out.append(seq[i])
            i += 1
    return out


# ── Range coder ───────────────────────────────────────────────────────────────

class _RCEnc:
    def __init__(self):
        self.low = 0
        self.rng = 0xFFFFFFFF
        self.buf = bytearray()

    def _norm(self):
        while self.rng < 0x01000000:
            self.buf.append((self.low >> 24) & 0xFF)
            self.low  = (self.low  << 8) & 0xFFFFFFFF
            self.rng  = (self.rng  << 8) & 0xFFFFFFFF

    def put(self, cum: int, freq: int, total: int):
        self.rng //= total
        self.low   = (self.low + cum * self.rng) & 0xFFFFFFFF
        self.rng  *= freq
        self._norm()

    def flush(self) -> bytes:
        for _ in range(5):
            self.buf.append((self.low >> 24) & 0xFF)
            self.low = (self.low << 8) & 0xFFFFFFFF
        return bytes(self.buf)


class _RCDec:
    def __init__(self, data: bytes):
        self.data = data
        self.pos  = 0
        self.low  = 0
        self.rng  = 0xFFFFFFFF
        self.code = 0
        for _ in range(4):
            self.code = ((self.code << 8) | self._b()) & 0xFFFFFFFF

    def _b(self) -> int:
        if self.pos < len(self.data):
            v = self.data[self.pos]; self.pos += 1; return v
        return 0

    def _norm(self):
        while self.rng < 0x01000000:
            self.code = ((self.code << 8) | self._b()) & 0xFFFFFFFF
            self.low  = (self.low  << 8) & 0xFFFFFFFF
            self.rng  = (self.rng  << 8) & 0xFFFFFFFF

    def peek(self, total: int) -> int:
        rng_div = max(1, self.rng // total)
        return (self.code - self.low) // rng_div

    def advance(self, cum: int, freq: int, total: int):
        rng_div    = max(1, self.rng // total)
        self.low   = (self.low + cum * rng_div) & 0xFFFFFFFF
        self.rng   = rng_div * freq
        self._norm()


# ── Adaptive order-2 Markov model ─────────────────────────────────────────────

class _Markov:
    def __init__(self, order: int, alpha: int):
        self.order  = order
        self.alpha  = alpha
        self.counts: dict = defaultdict(lambda: defaultdict(lambda: LAPLACE))
        self.totals: dict = defaultdict(lambda: alpha * LAPLACE)

    def _ctx(self, hist: list) -> tuple:
        return tuple(hist[-self.order:]) if len(hist) >= self.order else tuple(hist)

    def encode_sym(self, hist: list, sym: int, rc: _RCEnc):
        ctx   = self._ctx(hist)
        c     = self.counts[ctx]
        total = self.totals[ctx]
        cum   = sum(c[s] for s in range(sym))
        freq  = c[sym]
        rc.put(cum, freq, total)

    def decode_sym(self, hist: list, rc: _RCDec) -> int:
        ctx   = self._ctx(hist)
        c     = self.counts[ctx]
        total = self.totals[ctx]
        val   = rc.peek(total)
        running = 0
        for sym in range(self.alpha):
            freq = c[sym]
            if running + freq > val:
                rc.advance(running, freq, total)
                return sym
            running += freq
        sym = self.alpha - 1
        rc.advance(total - c[sym], c[sym], total)
        return sym

    def update(self, hist: list, sym: int):
        ctx = self._ctx(hist)
        self.counts[ctx][sym] += 1
        self.totals[ctx]      += 1


# ── Public encode / decode ────────────────────────────────────────────────────

def encode(file_path: str, shared_phrases=None) -> bytes:
    """
    Compress file_path with the SDE pipeline.

    shared_phrases — optional list of pre-trained corpus phrases loaded from
                     engine/domain_dict.bin.  When supplied, document-specific
                     novelties (up to 200) are merged on top, giving much better
                     coverage for same-domain files without rebuilding the whole
                     dictionary from scratch.
    """
    with open(file_path, "rb") as f:
        raw = f.read()

    zstd_seed = struct.pack("<B", _MODE_ZSTD) + zstd.compress(raw, 22)

    if not raw:
        return zstd_seed

    text = None
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            pass
    if text is None:
        return zstd_seed

    words = re.findall(r"\S+", text)
    if len(words) < 30:
        return zstd_seed

    if shared_phrases:
        phrases = _merge_phrases(shared_phrases, words)
    else:
        phrases = _build_phrases(words)
    ds      = len(phrases)
    alpha   = _alpha(ds)

    tokens     = _tokenize(text, phrases)
    lz_stream  = _lz77_enc(tokens)
    sym_seq    = _flatten(lz_stream, ds)

    model = _Markov(MARKOV_ORD, alpha)
    rc    = _RCEnc()
    hist: list = []
    for sym in sym_seq:
        model.encode_sym(hist, sym, rc)
        model.update(hist, sym)
        hist.append(sym)
        if len(hist) > MARKOV_ORD:
            hist.pop(0)
    coded = rc.flush()

    dict_bytes = zstd.compress(
        json.dumps(phrases, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        22,
    )

    seed = (
        struct.pack("<B",  _MODE_SDE)
        + struct.pack("<H",  ds)
        + struct.pack("<I",  len(dict_bytes))
        + dict_bytes
        + struct.pack("<I",  len(sym_seq))
        + coded
    )

    return seed if len(seed) < len(zstd_seed) else zstd_seed


def decode(seed: bytes) -> bytes:
    mode = struct.unpack("<B", seed[:1])[0]

    if mode == _MODE_ZSTD:
        return zstd.decompress(seed[1:])

    if mode != _MODE_SDE:
        return zstd.decompress(seed)

    offset = 1
    ds     = struct.unpack("<H", seed[offset:offset + 2])[0]; offset += 2
    dl     = struct.unpack("<I", seed[offset:offset + 4])[0]; offset += 4
    dict_bytes = seed[offset:offset + dl];                     offset += dl
    sym_count  = struct.unpack("<I", seed[offset:offset + 4])[0]; offset += 4
    coded      = seed[offset:]

    phrases = json.loads(zstd.decompress(dict_bytes).decode("utf-8"))
    alpha   = _alpha(ds)

    model = _Markov(MARKOV_ORD, alpha)
    rc    = _RCDec(coded)
    hist: list  = []
    sym_seq: list = []
    for _ in range(sym_count):
        sym = model.decode_sym(hist, rc)
        model.update(hist, sym)
        hist.append(sym)
        if len(hist) > MARKOV_ORD:
            hist.pop(0)
        sym_seq.append(sym)

    lz_stream = _unflatten(sym_seq, ds)
    tokens    = _lz77_dec(lz_stream)
    return _detokenize(tokens, phrases)
