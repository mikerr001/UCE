"""
Central compression dispatcher.
Selects the best extractor for each file type, runs compression,
stores the seed in the HDM, and handles decompression/retrieval.
"""

import os
import sys
import struct
import zstd
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.classifier import classify
from engine.hdm import HDM


def _get_paths(base_dir: str):
    matrix_path = os.path.join(base_dir, 'engine', 'hdm.matrix.npy')
    db_path = os.path.join(base_dir, 'engine', 'index.db')
    codebook_path = os.path.join(base_dir, 'engine', 'codebook.bin')
    return matrix_path, db_path, codebook_path


def compress_file(file_path: str, base_dir: str,
                  progress_cb=None) -> dict:
    """
    Compress a file and store its seed in the HDM.
    Returns a result dict with extractor used, ratios, sizes, etc.
    """
    matrix_path, db_path, codebook_path = _get_paths(base_dir)
    hdm = HDM(matrix_path, db_path)

    original_size = os.path.getsize(file_path)
    file_type = classify(file_path)

    if progress_cb:
        progress_cb(0.05, f'Classified as: {file_type}')

    seed_blob, extractor_name = _run_extractor(
        file_path, file_type, codebook_path, progress_cb)

    if progress_cb:
        progress_cb(0.90, 'Storing in HDM...')

    hdm.store(file_path, extractor_name, original_size, seed_blob)

    seed_size = len(seed_blob)
    ratio = original_size / seed_size if seed_size > 0 else 0

    if progress_cb:
        progress_cb(1.0, 'Done')

    return {
        'file_path': file_path,
        'file_type': file_type,
        'extractor': extractor_name,
        'original_size': original_size,
        'seed_size': seed_size,
        'ratio': round(ratio, 1),
    }


def compress_folder(folder_path: str, base_dir: str,
                    progress_cb=None) -> dict:
    """
    Recursively compress every file in a folder and store all seeds in HDM.
    Returns a summary dict with totals and any per-file errors.
    progress_cb(fraction, message) is called for each file.
    """
    all_files = []
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
        for fname in sorted(files):
            if not fname.startswith('.'):
                all_files.append(os.path.join(root, fname))

    total = len(all_files)
    if total == 0:
        return {
            'files': 0, 'errors': 0,
            'original_size': 0, 'seed_size': 0, 'ratio': 0,
            'error_list': [],
        }

    results = []
    errors = []

    for i, file_path in enumerate(all_files):
        if progress_cb:
            progress_cb(i / total,
                        f'[{i + 1}/{total}] {os.path.basename(file_path)}')
        try:
            r = compress_file(file_path, base_dir)
            results.append(r)
        except Exception as e:
            errors.append((file_path, str(e)))

    if progress_cb:
        progress_cb(1.0, f'Done — {len(results)} files compressed')

    total_orig = sum(r['original_size'] for r in results)
    total_seed = sum(r['seed_size'] for r in results)
    ratio = round(total_orig / total_seed, 1) if total_seed > 0 else 0

    return {
        'files': len(results),
        'errors': len(errors),
        'original_size': total_orig,
        'seed_size': total_seed,
        'ratio': ratio,
        'error_list': errors,
    }


def _run_extractor(file_path: str, file_type: str,
                   codebook_path: str, progress_cb=None):
    """
    Run the best extractor for the file type.
    Each extractor internally picks the smallest result (seed vs zstd fallback).
    Returns (seed_blob, extractor_name).
    """
    ext = os.path.splitext(file_path)[1].lower()
    candidates = []

    if file_type == 'image' and ext != '.svg':
        if progress_cb:
            progress_cb(0.2, 'Running Fractal IFS extractor...')
        try:
            from extractors.fractal_ifs import encode
            seed = encode(file_path)
            candidates.append((seed, 'fractal_ifs'))
        except Exception:
            pass

    elif file_type == '3d':
        if progress_cb:
            progress_cb(0.2, 'Running Fractal IFS extractor (3D geometry)...')
        try:
            from extractors.fractal_ifs import encode
            seed = encode(file_path)
            candidates.append((seed, 'fractal_ifs'))
        except Exception:
            pass
        if progress_cb:
            progress_cb(0.5, 'Running Grammar Inference on 3D file...')
        try:
            from extractors.grammar_infer import encode
            seed = encode(file_path)
            candidates.append((seed, 'grammar_infer'))
        except Exception:
            pass

    elif file_type == 'tabular':
        if progress_cb:
            progress_cb(0.2, 'Running Tensor Network decomposer...')
        try:
            from extractors.tensor_net import encode
            seed = encode(file_path)
            candidates.append((seed, 'tensor_net'))
        except Exception:
            pass

    elif file_type in ('document', 'code', 'structured'):
        if progress_cb:
            progress_cb(0.10, 'Running Semantic Domain Encoder...')
        try:
            from extractors.semantic_sde import encode
            seed = encode(file_path)
            candidates.append((seed, 'semantic_sde'))
        except Exception:
            pass
        if progress_cb:
            progress_cb(0.30, 'Running Program Synthesis...')
        try:
            from extractors.program_synth import encode
            seed = encode(file_path)
            candidates.append((seed, 'program_synth'))
        except Exception:
            pass
        if progress_cb:
            progress_cb(0.50, 'Running Grammar Inference...')
        try:
            from extractors.grammar_infer import encode
            seed = encode(file_path)
            candidates.append((seed, 'grammar_infer'))
        except Exception:
            pass

    elif file_type in ('video', 'audio'):
        if progress_cb:
            progress_cb(0.2, 'Running Boundary Constraint extractor...')
        try:
            from extractors.boundary import encode
            seed = encode(file_path)
            if seed:
                candidates.append((seed, 'boundary'))
        except Exception:
            pass

    elif file_type in ('random', 'binary', 'archive', 'executable'):
        if os.path.exists(codebook_path):
            if progress_cb:
                progress_cb(0.2, 'Running Holographic Codebook mapper...')
            try:
                from extractors.holographic import encode
                seed = encode(file_path, codebook_path)
                candidates.append((seed, 'holographic'))
            except Exception:
                pass

    if candidates:
        best = min(candidates, key=lambda x: len(x[0]))
        return best

    if progress_cb:
        progress_cb(0.2, 'Running Program Synthesis extractor...')
    try:
        from extractors.program_synth import encode
        seed = encode(file_path)

        fallback = _zstd_fallback(file_path)
        if len(seed) <= len(fallback):
            return seed, 'program_synth'
        return fallback, 'zstd_fallback'
    except Exception:
        pass

    return _zstd_fallback(file_path), 'zstd_fallback'


def _zstd_fallback(file_path: str) -> bytes:
    with open(file_path, 'rb') as f:
        raw = f.read()
    return struct.pack('<B', 99) + zstd.compress(raw, 19)


def decompress_file(file_path: str, output_path: str, base_dir: str,
                    progress_cb=None) -> bool:
    """
    Retrieve and reconstruct a file from the HDM.
    Writes the reconstructed data to output_path.
    Returns True on success.
    """
    matrix_path, db_path, codebook_path = _get_paths(base_dir)
    hdm = HDM(matrix_path, db_path)

    if progress_cb:
        progress_cb(0.1, 'Querying HDM...')

    record = hdm.retrieve(file_path)
    if record is None:
        return False

    extractor = record['extractor']
    seed_blob = record['seed_blob']

    if progress_cb:
        progress_cb(0.3, f'Reconstructing via {extractor}...')

    data = _run_decoder(extractor, seed_blob, codebook_path, output_path, progress_cb)

    if progress_cb:
        progress_cb(0.9, 'Writing output...')

    if data:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(data)

    if progress_cb:
        progress_cb(1.0, 'Done')

    return True


def _run_decoder(extractor: str, seed_blob: bytes,
                 codebook_path: str, output_path: str, progress_cb=None) -> bytes:
    if extractor == 'fractal_ifs':
        from extractors.fractal_ifs import decode
        return decode(seed_blob)

    if extractor == 'tensor_net':
        from extractors.tensor_net import decode
        return decode(seed_blob)

    if extractor == 'grammar_infer':
        from extractors.grammar_infer import decode
        return decode(seed_blob)

    if extractor == 'boundary':
        from extractors.boundary import decode
        result = decode(seed_blob, output_path)
        return result

    if extractor == 'holographic':
        from extractors.holographic import decode
        return decode(seed_blob, codebook_path)

    if extractor == 'semantic_sde':
        from extractors.semantic_sde import decode
        return decode(seed_blob)

    if extractor == 'program_synth':
        from extractors.program_synth import decode
        return decode(seed_blob)

    if extractor == 'zstd_fallback':
        mode = struct.unpack('<B', seed_blob[:1])[0]
        if mode == 99:
            return zstd.decompress(seed_blob[1:])

    return zstd.decompress(seed_blob)


def list_stored_files(base_dir: str) -> list:
    matrix_path, db_path, _ = _get_paths(base_dir)
    hdm = HDM(matrix_path, db_path)
    return hdm.list_files()


def delete_stored_file(file_path: str, base_dir: str) -> bool:
    matrix_path, db_path, _ = _get_paths(base_dir)
    hdm = HDM(matrix_path, db_path)
    return hdm.delete(file_path)
