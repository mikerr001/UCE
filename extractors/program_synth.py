"""
Program Synthesis Extractor — lightweight symbolic pattern search.

Attempts to find a compact program (mathematical formula or sequence generator)
that reproduces the data. Works well on:
- Pure numeric sequences (sine waves, arithmetic progressions, polynomials)
- Highly regular binary patterns

Falls back to zstd compression when no pattern is found.
Lossless residual guarantees byte-perfect reconstruction.
"""

import io
import struct
import json
import zstd
import numpy as np


MAX_PROGRAM_SEARCH_BYTES = 1_000_000


def _try_arithmetic(values: np.ndarray):
    if len(values) < 4:
        return None
    diffs = np.diff(values)
    if np.allclose(diffs, diffs[0], rtol=1e-6, atol=1e-9):
        return {'type': 'arithmetic', 'start': float(values[0]),
                'step': float(diffs[0]), 'n': len(values)}
    return None


def _try_geometric(values: np.ndarray):
    if len(values) < 4:
        return None
    if np.any(values == 0):
        return None
    ratios = values[1:] / values[:-1]
    if np.allclose(ratios, ratios[0], rtol=1e-6):
        return {'type': 'geometric', 'start': float(values[0]),
                'ratio': float(ratios[0]), 'n': len(values)}
    return None


def _try_polynomial(values: np.ndarray, max_degree: int = 4):
    if len(values) < max_degree + 2:
        return None
    x = np.arange(len(values), dtype=np.float64)
    for degree in range(1, max_degree + 1):
        coeffs = np.polyfit(x, values, degree)
        reconstructed = np.polyval(coeffs, x)
        if np.allclose(values, reconstructed, rtol=1e-5, atol=1e-7):
            return {'type': 'polynomial', 'coeffs': coeffs.tolist(), 'n': len(values)}
    return None


def _try_sinusoidal(values: np.ndarray):
    if len(values) < 8:
        return None
    from numpy.fft import fft
    n = len(values)
    spectrum = np.abs(fft(values))
    dominant = np.argmax(spectrum[1:n // 2]) + 1
    freq = dominant / n

    amplitude = 2 * spectrum[dominant] / n
    phase = np.angle(fft(values)[dominant])
    offset = np.mean(values)

    x = np.arange(n, dtype=np.float64)
    reconstructed = amplitude * np.sin(2 * np.pi * freq * x + phase) + offset

    if np.allclose(values, reconstructed, rtol=1e-4, atol=1e-4 * max(1, abs(amplitude))):
        return {'type': 'sinusoidal', 'amplitude': float(amplitude),
                'frequency': float(freq), 'phase': float(phase),
                'offset': float(offset), 'n': n}
    return None


def _try_repeat_pattern(data: bytes, max_period: int = 256):
    n = len(data)
    for period in range(1, min(max_period + 1, n // 2)):
        tile = data[:period]
        expected = (tile * ((n // period) + 1))[:n]
        if expected == data:
            return {'type': 'repeat', 'pattern': list(tile), 'n': n}
    return None


def _try_constant(data: bytes):
    if len(set(data)) == 1:
        return {'type': 'constant', 'byte': data[0], 'n': len(data)}
    return None


def _synthesize(file_path: str, raw: bytes):
    if _try_constant(raw):
        return _try_constant(raw)

    pattern = _try_repeat_pattern(raw)
    if pattern:
        return pattern

    try:
        text = raw.decode('utf-8')
        lines = text.strip().split('\n')
        numeric_lines = []
        for line in lines:
            try:
                numeric_lines.append(float(line.strip()))
            except ValueError:
                numeric_lines = []
                break
        if len(numeric_lines) >= 4:
            values = np.array(numeric_lines, dtype=np.float64)
            for fn in (_try_arithmetic, _try_geometric, _try_polynomial, _try_sinusoidal):
                prog = fn(values)
                if prog:
                    prog['source'] = 'text_numeric'
                    return prog
    except UnicodeDecodeError:
        pass

    if len(raw) <= MAX_PROGRAM_SEARCH_BYTES:
        arr = np.frombuffer(raw, dtype=np.uint8).astype(np.float64)
        if len(arr) >= 4:
            for fn in (_try_arithmetic, _try_geometric, _try_polynomial, _try_sinusoidal):
                prog = fn(arr)
                if prog:
                    prog['source'] = 'bytes'
                    return prog

    return None


def _run_program(prog: dict) -> bytes:
    ptype = prog['type']
    n = prog['n']
    source = prog.get('source', 'bytes')

    if ptype == 'constant':
        return bytes([prog['byte']] * n)
    elif ptype == 'repeat':
        pat = bytes(prog['pattern'])
        return (pat * ((n // len(pat)) + 1))[:n]
    elif ptype == 'arithmetic':
        values = np.array([prog['start'] + i * prog['step'] for i in range(n)])
    elif ptype == 'geometric':
        values = np.array([prog['start'] * (prog['ratio'] ** i) for i in range(n)])
    elif ptype == 'polynomial':
        x = np.arange(n, dtype=np.float64)
        values = np.polyval(prog['coeffs'], x)
    elif ptype == 'sinusoidal':
        x = np.arange(n, dtype=np.float64)
        values = (prog['amplitude'] * np.sin(2 * np.pi * prog['frequency'] * x + prog['phase'])
                  + prog['offset'])
    else:
        return b''

    if source == 'text_numeric':
        lines = [f'{v:.10g}' for v in values]
        return ('\n'.join(lines) + '\n').encode('utf-8')
    else:
        arr = np.clip(np.round(values), 0, 255).astype(np.uint8)
        return arr.tobytes()


def encode(file_path: str) -> bytes:
    with open(file_path, 'rb') as f:
        raw = f.read()

    prog = _synthesize(file_path, raw)

    if prog is None:
        compressed = zstd.compress(raw, 19)
        return struct.pack('<B', 0) + compressed

    prog_bytes = json.dumps(prog).encode('utf-8')
    reconstructed = _run_program(prog)

    if len(reconstructed) != len(raw):
        compressed = zstd.compress(raw, 19)
        return struct.pack('<B', 0) + compressed

    residual = bytes([a ^ b for a, b in zip(raw, reconstructed)])
    residual_compressed = zstd.compress(residual, 19)

    prog_compressed = zstd.compress(prog_bytes, 19)

    candidate = (struct.pack('<B', 1) +
                 struct.pack('<I', len(prog_compressed)) + prog_compressed +
                 struct.pack('<I', len(residual_compressed)) + residual_compressed)

    fallback = struct.pack('<B', 0) + zstd.compress(raw, 19)

    return candidate if len(candidate) < len(fallback) else fallback


def decode(seed: bytes) -> bytes:
    mode = struct.unpack('<B', seed[:1])[0]

    if mode == 0:
        return zstd.decompress(seed[1:])

    pos = 1
    plen = struct.unpack_from('<I', seed, pos)[0]; pos += 4
    prog_compressed = seed[pos:pos + plen]; pos += plen
    rlen = struct.unpack_from('<I', seed, pos)[0]; pos += 4
    residual_compressed = seed[pos:pos + rlen]

    prog = json.loads(zstd.decompress(prog_compressed).decode('utf-8'))
    reconstructed = _run_program(prog)
    residual = zstd.decompress(residual_compressed)

    result = bytes([a ^ b for a, b in zip(reconstructed, residual)])
    return result
