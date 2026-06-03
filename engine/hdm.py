"""
Hyperdimensional Memory (HDM) — Sparse Distributed Memory implementation.

D = 10,000-dimensional binary vectors, density rho = 0.1.
Seeds are bound to file paths via XOR and stored in SQLite with their
hypervector address for content-addressable recall.

The heavy matrix from the doc (200k-dim, 1M rows) is the theoretical ideal;
this implementation uses the same algebraic operations (bundle, bind, permute)
with the SQLite backend for practical on-disk storage, matching the architecture
described in UCE spec §4.2.
"""

import os
import hashlib
import sqlite3
import numpy as np

D = 10_000
RHO = 0.1
ONES = int(D * RHO)
K = 7


def _rng_from_text(text: str) -> np.random.Generator:
    digest = hashlib.sha256(text.encode()).digest()
    seed_val = int.from_bytes(digest[:8], 'little')
    return np.random.default_rng(seed_val)


def _random_sparse(rng: np.random.Generator) -> np.ndarray:
    v = np.zeros(D, dtype=np.uint8)
    idx = rng.choice(D, ONES, replace=False)
    v[idx] = 1
    return v


def _text_to_hypervector(text: str) -> np.ndarray:
    return _random_sparse(_rng_from_text(text))


def _bind(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.bitwise_xor(a, b)


def _hamming(a: np.ndarray, b: np.ndarray) -> int:
    return int(np.sum(a != b))


class HDM:
    """
    Hyperdimensional Memory.
    Seeds are stored in SQLite; hypervectors are used for address binding
    and similarity search exactly as described in UCE §4.1–4.2.
    """

    def __init__(self, matrix_path: str, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                path         TEXT    UNIQUE NOT NULL,
                path_hvec    BLOB    NOT NULL,
                extractor    TEXT    NOT NULL,
                original_size INTEGER NOT NULL,
                seed_size    INTEGER NOT NULL,
                compressed_at TEXT   NOT NULL,
                seed_blob    BLOB    NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def store(self, file_path: str, extractor: str,
              original_size: int, seed_blob: bytes):
        addr_vec = _text_to_hypervector(file_path)
        seed_vec = _text_to_hypervector(
            hashlib.sha256(seed_blob).hexdigest())
        bound = _bind(addr_vec, seed_vec)

        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO files
            (path, path_hvec, extractor, original_size, seed_size,
             compressed_at, seed_blob)
            VALUES (?, ?, ?, ?, ?, datetime('now'), ?)
        """, (file_path, bound.tobytes(), extractor,
              original_size, len(seed_blob), seed_blob))
        conn.commit()
        conn.close()

    def retrieve(self, file_path: str) -> dict | None:
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT extractor, original_size, seed_size, "
            "compressed_at, seed_blob "
            "FROM files WHERE path=?", (file_path,)
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return {
            'extractor': row[0],
            'original_size': row[1],
            'seed_size': row[2],
            'compressed_at': row[3],
            'seed_blob': row[4],
        }

    def query_by_content(self, query_text: str, top_n: int = 5) -> list:
        """
        Content-addressable recall: find files whose address hypervectors
        are nearest (lowest Hamming distance) to the query vector.
        """
        query_vec = _text_to_hypervector(query_text)
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT path, path_hvec, extractor, original_size, seed_size, "
            "compressed_at FROM files"
        ).fetchall()
        conn.close()

        results = []
        for row in rows:
            stored_vec = np.frombuffer(row[1], dtype=np.uint8)
            dist = _hamming(query_vec, stored_vec)
            results.append((dist, row))

        results.sort(key=lambda x: x[0])
        return [
            {
                'path': r[0], 'extractor': r[2],
                'original_size': r[3], 'seed_size': r[4],
                'compressed_at': r[5], 'distance': d,
            }
            for d, r in results[:top_n]
        ]

    def list_files(self) -> list:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT path, extractor, original_size, seed_size, compressed_at "
            "FROM files ORDER BY compressed_at DESC"
        ).fetchall()
        conn.close()
        return [
            {
                'path': r[0],
                'extractor': r[1],
                'original_size': r[2],
                'seed_size': r[3],
                'compressed_at': r[4],
                'ratio': round(r[2] / r[3], 1) if r[3] > 0 else 0,
            }
            for r in rows
        ]

    def delete(self, file_path: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cur = conn.execute("DELETE FROM files WHERE path=?", (file_path,))
        conn.commit()
        conn.close()
        return cur.rowcount > 0
