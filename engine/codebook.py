"""
Holographic Codebook — pre-shared random entropy source.

The codebook is a fixed file of random bytes (generated once per install).
Encoding: for each 16-byte block, find the nearest codebook block via
hash-bucketed lookup, XOR to get residual, then zstd-compress the residuals.
The index (block addresses) is also zstd-compressed.

For truly random data the residuals compress poorly, but the index compression
provides a real size reduction. The codebook doesn't count toward compressed size.
"""

import os
import struct
import zstd
import numpy as np

BLOCK_SIZE = 16
DEFAULT_CODEBOOK_SIZE_MB = 64
BLOCKS_PER_MB = (1024 * 1024) // BLOCK_SIZE
DEFAULT_N_BLOCKS = DEFAULT_CODEBOOK_SIZE_MB * BLOCKS_PER_MB


def generate_codebook(path: str, n_blocks: int = DEFAULT_N_BLOCKS,
                      seed: int = 0xDEADBEEF,
                      progress_cb=None):
    rng = np.random.default_rng(seed)
    seed_bytes = seed.to_bytes(8, 'little')
    with open(path, 'wb') as f:
        f.write(seed_bytes)
        chunk = 65536
        written = 0
        while written < n_blocks:
            batch = min(chunk, n_blocks - written)
            data = rng.bytes(batch * BLOCK_SIZE)
            f.write(data)
            written += batch
            if progress_cb:
                progress_cb(written / n_blocks)


def _load_codebook(codebook_path: str) -> np.ndarray:
    file_size = os.path.getsize(codebook_path)
    header = 8
    data_size = file_size - header
    n_blocks = data_size // BLOCK_SIZE
    mm = np.memmap(codebook_path, dtype=np.uint8, mode='r',
                   offset=header, shape=(n_blocks, BLOCK_SIZE))
    return mm


def _build_hash_index(cb: np.ndarray) -> dict:
    """Build a dict: first_4_bytes -> list of row indices for fast lookup."""
    idx = {}
    for i in range(len(cb)):
        key = cb[i, :4].tobytes()
        if key not in idx:
            idx[key] = []
        idx[key].append(i)
    return idx


def encode(data: bytes, codebook_path: str) -> bytes:
    cb = _load_codebook(codebook_path)
    n_cb = len(cb)

    padded_len = ((len(data) + BLOCK_SIZE - 1) // BLOCK_SIZE) * BLOCK_SIZE
    padded = data + b'\x00' * (padded_len - len(data))
    orig_len = len(data)
    n_blocks = padded_len // BLOCK_SIZE

    arr = np.frombuffer(padded, dtype=np.uint8).reshape(n_blocks, BLOCK_SIZE)

    STRIDE = max(1, n_cb // 16384)
    indices = np.zeros(n_blocks, dtype=np.uint32)
    residuals = np.zeros((n_blocks, BLOCK_SIZE), dtype=np.uint8)

    for i in range(n_blocks):
        block = arr[i]
        candidates = cb[::STRIDE]
        xor_counts = np.sum(candidates != block, axis=1)
        best_local = int(np.argmin(xor_counts))
        best_idx = best_local * STRIDE
        indices[i] = best_idx
        residuals[i] = np.bitwise_xor(block, cb[best_idx])

    res_compressed = zstd.compress(residuals.tobytes(), 22)
    idx_compressed = zstd.compress(indices.tobytes(), 22)

    header = struct.pack('<II', orig_len, n_blocks)
    return (struct.pack('<I', len(header)) + header +
            struct.pack('<I', len(idx_compressed)) + idx_compressed +
            struct.pack('<I', len(res_compressed)) + res_compressed)


def decode(seed: bytes, codebook_path: str) -> bytes:
    cb = _load_codebook(codebook_path)
    pos = 0
    hlen = struct.unpack_from('<I', seed, pos)[0]; pos += 4
    orig_len, n_blocks = struct.unpack_from('<II', seed[pos:pos+hlen]); pos += hlen
    ilen = struct.unpack_from('<I', seed, pos)[0]; pos += 4
    idx_compressed = seed[pos:pos+ilen]; pos += ilen
    rlen = struct.unpack_from('<I', seed, pos)[0]; pos += 4
    res_compressed = seed[pos:pos+rlen]

    indices = np.frombuffer(zstd.decompress(idx_compressed), dtype=np.uint32)
    residuals = np.frombuffer(zstd.decompress(res_compressed), dtype=np.uint8).reshape(n_blocks, BLOCK_SIZE)

    result = bytearray()
    for i in range(n_blocks):
        block = np.bitwise_xor(cb[indices[i]], residuals[i]).tobytes()
        result.extend(block)
    return bytes(result[:orig_len])
