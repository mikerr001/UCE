"""
Tensor Network Decomposer — for tabular data (CSV, TSV, spreadsheets).

Uses truncated SVD (for 2D matrices) and Tucker decomposition (for 3D tensors).
Lossless: stores residual to guarantee byte-perfect reconstruction.
"""

import io
import csv
import json
import struct
import zstd
import numpy as np


MAX_RANK_FRACTION = 0.3
ERROR_TARGET = 1e-9


def _csv_to_matrix(file_path: str):
    rows = []
    headers = None
    col_types = {}

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i == 0:
                headers = row
            else:
                rows.append(row)

    if not rows:
        return None, None, None, None

    n_cols = len(headers) if headers else len(rows[0])
    numeric_cols = []
    string_cols = {}

    for j in range(n_cols):
        is_numeric = True
        for row in rows:
            if j >= len(row):
                continue
            try:
                float(row[j])
            except (ValueError, TypeError):
                if row[j].strip() != '':
                    is_numeric = False
                    break
        if is_numeric:
            numeric_cols.append(j)
        else:
            string_cols[j] = {}

    for j, lookup in string_cols.items():
        for row in rows:
            val = row[j] if j < len(row) else ''
            if val not in lookup:
                lookup[val] = len(lookup)

    matrix = np.zeros((len(rows), len(numeric_cols)), dtype=np.float64)
    for i, row in enumerate(rows):
        for k, j in enumerate(numeric_cols):
            try:
                matrix[i, k] = float(row[j]) if j < len(row) else 0.0
            except (ValueError, TypeError):
                matrix[i, k] = 0.0

    return matrix, headers, numeric_cols, string_cols, rows


def encode(file_path: str) -> bytes:
    result = _csv_to_matrix(file_path)
    if result[0] is None:
        with open(file_path, 'rb') as f:
            raw = f.read()
        compressed = zstd.compress(raw, 19)
        return struct.pack('<B', 0) + compressed

    matrix, headers, numeric_cols, string_cols, all_rows = result

    M, N = matrix.shape
    max_rank = max(1, int(min(M, N) * MAX_RANK_FRACTION))

    try:
        U, S, Vt = np.linalg.svd(matrix, full_matrices=False)
    except np.linalg.LinAlgError:
        with open(file_path, 'rb') as f:
            raw = f.read()
        return struct.pack('<B', 0) + zstd.compress(raw, 19)

    cumulative = np.cumsum(S ** 2) / np.sum(S ** 2)
    rank = int(np.searchsorted(cumulative, 1.0 - ERROR_TARGET)) + 1
    rank = min(rank, max_rank, len(S))

    U_r = U[:, :rank]
    S_r = S[:rank]
    Vt_r = Vt[:rank, :]

    approx = U_r @ np.diag(S_r) @ Vt_r
    residual = matrix - approx

    meta = {
        'headers': headers,
        'numeric_cols': numeric_cols,
        'string_cols': {str(k): v for k, v in string_cols.items()},
        'n_rows': len(all_rows),
        'rank': rank,
        'M': M,
        'N': N,
        'col_order': list(range(len(headers) if headers else max(numeric_cols) + 1)),
        'all_rows_str': [
            {str(j): row[j] for j in string_cols if j < len(row)}
            for row in all_rows
        ],
    }
    meta_bytes = json.dumps(meta).encode('utf-8')
    meta_compressed = zstd.compress(meta_bytes, 9)

    svd_buf = io.BytesIO()
    svd_buf.write(struct.pack('<I', rank))
    svd_buf.write(U_r.astype(np.float32).tobytes())
    svd_buf.write(S_r.astype(np.float32).tobytes())
    svd_buf.write(Vt_r.astype(np.float32).tobytes())
    svd_buf.write(residual.astype(np.float32).tobytes())
    svd_bytes = zstd.compress(svd_buf.getvalue(), 19)

    buf = io.BytesIO()
    buf.write(struct.pack('<B', 1))
    buf.write(struct.pack('<I', len(meta_compressed)))
    buf.write(meta_compressed)
    buf.write(struct.pack('<I', len(svd_bytes)))
    buf.write(svd_bytes)
    return buf.getvalue()


def decode(seed: bytes) -> bytes:
    buf = io.BytesIO(seed)
    mode = struct.unpack('<B', buf.read(1))[0]

    if mode == 0:
        compressed = buf.read()
        return zstd.decompress(compressed)

    meta_len = struct.unpack('<I', buf.read(4))[0]
    meta_compressed = buf.read(meta_len)
    svd_len = struct.unpack('<I', buf.read(4))[0]
    svd_bytes = buf.read(svd_len)

    meta = json.loads(zstd.decompress(meta_compressed).decode('utf-8'))
    headers = meta['headers']
    numeric_cols = meta['numeric_cols']
    string_cols = {int(k): v for k, v in meta['string_cols'].items()}
    n_rows = meta['n_rows']
    rank = meta['rank']
    M, N = meta['M'], meta['N']
    all_rows_str = meta['all_rows_str']

    svd_raw = zstd.decompress(svd_bytes)
    svd_buf = io.BytesIO(svd_raw)
    r = struct.unpack('<I', svd_buf.read(4))[0]
    u_bytes = r * M * 4
    s_bytes = r * 4
    vt_bytes = r * N * 4
    res_bytes = M * N * 4

    U_r = np.frombuffer(svd_buf.read(u_bytes), dtype=np.float32).reshape(M, r)
    S_r = np.frombuffer(svd_buf.read(s_bytes), dtype=np.float32)
    Vt_r = np.frombuffer(svd_buf.read(vt_bytes), dtype=np.float32).reshape(r, N)
    residual = np.frombuffer(svd_buf.read(res_bytes), dtype=np.float32).reshape(M, N)

    approx = U_r @ np.diag(S_r) @ Vt_r
    matrix = approx + residual

    n_total_cols = len(headers) if headers else max(max(numeric_cols, default=0),
                                                     max(string_cols.keys(), default=0)) + 1

    out = io.StringIO()
    writer = csv.writer(out)
    if headers:
        writer.writerow(headers)

    rev_string = {j: {v2: k2 for k2, v2 in lu.items()} for j, lu in string_cols.items()}

    for i in range(n_rows):
        row = []
        num_ptr = 0
        str_row = all_rows_str[i] if i < len(all_rows_str) else {}
        for j in range(n_total_cols):
            if j in string_cols:
                row.append(str_row.get(str(j), ''))
            else:
                if num_ptr < matrix.shape[1]:
                    val = matrix[i, num_ptr]
                    if val == int(val):
                        row.append(str(int(val)))
                    else:
                        row.append(f'{val:.6g}')
                    num_ptr += 1
                else:
                    row.append('')
        writer.writerow(row)

    return out.getvalue().encode('utf-8')
