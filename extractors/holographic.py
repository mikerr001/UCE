"""
Holographic Codebook Mapper — for high-entropy / random / encrypted data.

Wraps engine/codebook.py encode/decode with the UCE seed format.
The codebook is the pre-shared entropy source that makes 1000:1 possible
for incompressible data.
"""

import os
import sys
import struct
import zstd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.codebook import encode as cb_encode, decode as cb_decode


def encode(file_path: str, codebook_path: str) -> bytes:
    with open(file_path, 'rb') as f:
        raw = f.read()

    if not os.path.exists(codebook_path):
        raise FileNotFoundError(f'Codebook not found: {codebook_path}')

    seed = cb_encode(raw, codebook_path)

    fallback = zstd.compress(raw, 19)
    if len(fallback) < len(seed):
        return struct.pack('<B', 0) + fallback
    return struct.pack('<B', 1) + seed


def decode(seed_blob: bytes, codebook_path: str) -> bytes:
    mode = struct.unpack('<B', seed_blob[:1])[0]
    payload = seed_blob[1:]

    if mode == 0:
        return zstd.decompress(payload)
    return cb_decode(payload, codebook_path)
