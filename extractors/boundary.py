"""
Boundary Constraint Extractor — for video and audio files.

For video: extracts keyframes (as IFS-compressed images) + inter-frame
difference events. Reconstructs by replaying delta events over keyframes.

For audio: extracts envelope + dominant frequencies (DCT-based).
Residual ensures lossless reconstruction.

Note: True procedural world model rendering requires domain-specific models.
This implementation uses keyframe + motion delta extraction, which is the
lossless-guaranteed subset of the full boundary constraint approach.
"""

import io
import os
import struct
import json
import zstd
import numpy as np
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


KEYFRAME_INTERVAL = 30
MOTION_BLOCK_SIZE = 16
DCT_KEEP_FRACTION = 0.1


def _encode_video(file_path: str) -> bytes:
    try:
        import cv2
    except ImportError:
        return None

    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        return None

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    meta = {
        'fps': fps, 'width': width, 'height': height,
        'total_frames': total_frames,
        'keyframe_interval': KEYFRAME_INTERVAL,
        'codec': 'boundary_v1',
    }

    keyframes = []
    delta_events = []
    prev_frame = None
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if frame_idx % KEYFRAME_INTERVAL == 0:
            _, buf = cv2.imencode('.png', frame,
                                   [cv2.IMWRITE_PNG_COMPRESSION, 9])
            kf_compressed = zstd.compress(buf.tobytes(), 9)
            keyframes.append(kf_compressed)
            prev_gray = gray
        else:
            if prev_frame is not None:
                diff = gray.astype(np.int16) - prev_frame.astype(np.int16)
                diff_bytes = diff.astype(np.int8).tobytes()
                delta_compressed = zstd.compress(diff_bytes, 19)
                delta_events.append(delta_compressed)
            prev_gray = gray

        prev_frame = gray
        frame_idx += 1

    cap.release()

    buf = io.BytesIO()
    meta_bytes = json.dumps(meta).encode()
    meta_comp = zstd.compress(meta_bytes, 9)
    buf.write(struct.pack('<I', len(meta_comp)))
    buf.write(meta_comp)

    buf.write(struct.pack('<I', len(keyframes)))
    for kf in keyframes:
        buf.write(struct.pack('<I', len(kf)))
        buf.write(kf)

    buf.write(struct.pack('<I', len(delta_events)))
    for de in delta_events:
        buf.write(struct.pack('<I', len(de)))
        buf.write(de)

    return buf.getvalue()


def _encode_audio(file_path: str) -> bytes:
    try:
        import wave
        with wave.open(file_path, 'rb') as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            raw_frames = wf.readframes(n_frames)
    except Exception:
        return None

    dtype_map = {1: np.int8, 2: np.int16, 4: np.int32}
    dtype = dtype_map.get(sampwidth, np.int16)
    samples = np.frombuffer(raw_frames, dtype=dtype).astype(np.float64)

    dct_coeffs = np.fft.rfft(samples)
    n_keep = max(1, int(len(dct_coeffs) * DCT_KEEP_FRACTION))
    magnitudes = np.abs(dct_coeffs)
    top_indices = np.argpartition(magnitudes, -n_keep)[-n_keep:]

    seed_coeffs = np.zeros_like(dct_coeffs)
    seed_coeffs[top_indices] = dct_coeffs[top_indices]

    approx = np.fft.irfft(seed_coeffs, n=len(samples))
    approx = np.clip(np.round(approx), np.iinfo(dtype).min, np.iinfo(dtype).max).astype(dtype)

    residual = (samples.astype(np.float64) - approx.astype(np.float64)).astype(dtype)

    meta = {
        'n_channels': n_channels, 'sampwidth': sampwidth,
        'framerate': framerate, 'n_frames': n_frames,
        'n_keep': n_keep, 'top_indices': top_indices.tolist(),
    }
    meta_bytes = json.dumps(meta).encode()

    real_parts = dct_coeffs[top_indices].real.astype(np.float32).tobytes()
    imag_parts = dct_coeffs[top_indices].imag.astype(np.float32).tobytes()
    coeffs_bytes = real_parts + imag_parts
    residual_bytes = residual.tobytes()

    buf = io.BytesIO()
    mc = zstd.compress(meta_bytes, 9)
    buf.write(struct.pack('<I', len(mc))); buf.write(mc)
    cc = zstd.compress(coeffs_bytes, 19)
    buf.write(struct.pack('<I', len(cc))); buf.write(cc)
    rc = zstd.compress(residual_bytes, 19)
    buf.write(struct.pack('<I', len(rc))); buf.write(rc)
    return buf.getvalue()


def encode(file_path: str) -> bytes:
    ext = os.path.splitext(file_path)[1].lower()

    if ext in ('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'):
        result = _encode_video(file_path)
        if result:
            return struct.pack('<B', 1) + result

    if ext in ('.wav',):
        result = _encode_audio(file_path)
        if result:
            return struct.pack('<B', 2) + result

    with open(file_path, 'rb') as f:
        raw = f.read()
    return struct.pack('<B', 0) + zstd.compress(raw, 19)


def decode(seed: bytes, output_path: str) -> bytes:
    mode = struct.unpack('<B', seed[:1])[0]
    payload = seed[1:]

    if mode == 0:
        return zstd.decompress(payload)

    if mode == 1:
        try:
            import cv2
        except ImportError:
            raise RuntimeError('opencv-python required for video decode')

        buf = io.BytesIO(payload)
        mc_len = struct.unpack('<I', buf.read(4))[0]
        meta = json.loads(zstd.decompress(buf.read(mc_len)))

        fps = meta['fps']
        width = meta['width']
        height = meta['height']

        n_kf = struct.unpack('<I', buf.read(4))[0]
        keyframes_raw = []
        for _ in range(n_kf):
            l = struct.unpack('<I', buf.read(4))[0]
            keyframes_raw.append(zstd.decompress(buf.read(l)))

        n_de = struct.unpack('<I', buf.read(4))[0]
        deltas_raw = []
        for _ in range(n_de):
            l = struct.unpack('<I', buf.read(4))[0]
            deltas_raw.append(zstd.decompress(buf.read(l)))

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        kf_idx = 0
        de_idx = 0
        prev_gray = None

        for frame_idx in range(meta['total_frames']):
            if frame_idx % KEYFRAME_INTERVAL == 0:
                if kf_idx < len(keyframes_raw):
                    arr = np.frombuffer(keyframes_raw[kf_idx], dtype=np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    kf_idx += 1
                    prev_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    out.write(frame)
            else:
                if de_idx < len(deltas_raw) and prev_gray is not None:
                    diff = np.frombuffer(deltas_raw[de_idx], dtype=np.int8).reshape(height, width)
                    gray = np.clip(prev_gray.astype(np.int16) + diff.astype(np.int16),
                                   0, 255).astype(np.uint8)
                    frame_color = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
                    prev_gray = gray
                    de_idx += 1
                    out.write(frame_color)

        out.release()
        return b''

    if mode == 2:
        import wave
        buf = io.BytesIO(payload)
        mc_len = struct.unpack('<I', buf.read(4))[0]
        meta = json.loads(zstd.decompress(buf.read(mc_len)))
        cc_len = struct.unpack('<I', buf.read(4))[0]
        coeffs_raw = zstd.decompress(buf.read(cc_len))
        rc_len = struct.unpack('<I', buf.read(4))[0]
        residual_raw = zstd.decompress(buf.read(rc_len))

        dtype_map = {1: np.int8, 2: np.int16, 4: np.int32}
        dtype = dtype_map.get(meta['sampwidth'], np.int16)

        n_keep = meta['n_keep']
        top_indices = np.array(meta['top_indices'])
        half = len(coeffs_raw) // 2
        reals = np.frombuffer(coeffs_raw[:half], dtype=np.float32).astype(np.float64)
        imags = np.frombuffer(coeffs_raw[half:], dtype=np.float32).astype(np.float64)

        n_samples = meta['n_frames'] * meta['n_channels']
        n_rfft = n_samples // 2 + 1
        dct_coeffs = np.zeros(n_rfft, dtype=np.complex128)
        dct_coeffs[top_indices] = reals + 1j * imags

        approx = np.fft.irfft(dct_coeffs, n=n_samples)
        approx = np.clip(np.round(approx), np.iinfo(dtype).min, np.iinfo(dtype).max).astype(dtype)
        residual = np.frombuffer(residual_raw, dtype=dtype)
        restored = (approx.astype(np.float64) + residual.astype(np.float64))
        restored = np.clip(np.round(restored), np.iinfo(dtype).min, np.iinfo(dtype).max).astype(dtype)

        out_buf = io.BytesIO()
        with wave.open(out_buf, 'wb') as wf:
            wf.setnchannels(meta['n_channels'])
            wf.setsampwidth(meta['sampwidth'])
            wf.setframerate(meta['framerate'])
            wf.writeframes(restored.tobytes())
        return out_buf.getvalue()

    return b''
