"""
UCE Installer — initialises the engine directory on a fresh install.
Creates the holographic codebook and sets up the SQLite index.
"""

import os
import sqlite3


CODEBOOK_SIZE_MB = 64


def is_initialized(base_dir: str) -> bool:
    db_path = os.path.join(base_dir, 'engine', 'index.db')
    codebook_path = os.path.join(base_dir, 'engine', 'codebook.bin')
    return os.path.exists(db_path) and os.path.exists(codebook_path)


def initialize(base_dir: str, progress_cb=None):
    """
    First-time setup. Creates all engine assets.
    progress_cb(fraction, message) is called throughout.
    """
    engine_dir = os.path.join(base_dir, 'engine')
    os.makedirs(engine_dir, exist_ok=True)

    codebook_path = os.path.join(engine_dir, 'codebook.bin')
    db_path = os.path.join(engine_dir, 'index.db')

    if not os.path.exists(codebook_path):
        if progress_cb:
            progress_cb(0.05, 'Generating holographic codebook...')
        _generate_codebook(codebook_path, CODEBOOK_SIZE_MB, progress_cb)

    if not os.path.exists(db_path):
        if progress_cb:
            progress_cb(0.95, 'Creating HDM index database...')
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                path          TEXT    UNIQUE NOT NULL,
                path_hvec     BLOB    NOT NULL,
                extractor     TEXT    NOT NULL,
                original_size INTEGER NOT NULL,
                seed_size     INTEGER NOT NULL,
                compressed_at TEXT    NOT NULL,
                seed_blob     BLOB    NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    if progress_cb:
        progress_cb(1.0, 'Engine ready.')


def _generate_codebook(path: str, size_mb: int, progress_cb=None):
    from engine.codebook import generate_codebook

    blocks_per_mb = (1024 * 1024) // 16
    n_blocks = size_mb * blocks_per_mb

    def _cb(frac):
        if progress_cb:
            progress_cb(0.05 + frac * 0.85,
                        f'Generating codebook... {int(frac * 100)}%')

    generate_codebook(path, n_blocks=n_blocks, seed=0xDEADBEEF, progress_cb=_cb)
