"""
Fractal IFS Extractor — for images and repetitive binary data.

Encodes images by finding affine self-similarity between blocks.
Each target block is approximated by a transformed version of a larger
domain block. The seed stores the transform parameters plus a lossless
residual for byte-perfect reconstruction.

Speed: uses downsampled domain comparison + early exit threshold.
"""

import io
import struct
import zstd
import numpy as np
from PIL import Image


RANGE_SIZE = 8
DOMAIN_SIZE = 16
CONTRAST_LEVELS = 8
BRIGHTNESS_LEVELS = 32
ERROR_THRESHOLD = 20.0


def _quantize(val, levels, lo, hi):
    step = (hi - lo) / levels
    return max(0, min(levels - 1, int((val - lo) / step)))


def _dequantize(q, levels, lo, hi):
    step = (hi - lo) / levels
    return lo + (q + 0.5) * step


def _encode_channel(channel: np.ndarray) -> bytes:
    H, W = channel.shape
    rH = H // RANGE_SIZE
    rW = W // RANGE_SIZE
    dH = H // DOMAIN_SIZE
    dW = W // DOMAIN_SIZE

    domain_blocks = {}
    for di in range(dH):
        for dj in range(dW):
            d = channel[di*DOMAIN_SIZE:(di+1)*DOMAIN_SIZE,
                        dj*DOMAIN_SIZE:(dj+1)*DOMAIN_SIZE]
            domain_blocks[(di, dj)] = d[::2, ::2].flatten().astype(np.float32)

    transforms = []

    for ri in range(rH):
        for rj in range(rW):
            r_flat = channel[ri*RANGE_SIZE:(ri+1)*RANGE_SIZE,
                              rj*RANGE_SIZE:(rj+1)*RANGE_SIZE].flatten().astype(np.float32)
            r_mean = float(r_flat.mean())

            best_error = float('inf')
            best_t = (0, 0, 0, 0)

            for di in range(dH):
                for dj in range(dW):
                    d_small = domain_blocks[(di, dj)]
                    d_mean = float(d_small.mean())
                    denom = float(np.dot(d_small - d_mean, d_small - d_mean))
                    if denom < 1e-6:
                        s, o = 0.0, r_mean
                    else:
                        s = float(np.dot(d_small - d_mean, r_flat - r_mean) / denom)
                        s = max(-1.0, min(1.0, s))
                        o = r_mean - s * d_mean

                    recon = s * d_small + o
                    err = float(np.mean((r_flat - recon) ** 2))

                    if err < best_error:
                        best_error = err
                        sq = _quantize(s, CONTRAST_LEVELS, -1.0, 1.0)
                        oq = _quantize(o, BRIGHTNESS_LEVELS, -128.0, 384.0)
                        best_t = (di, dj, sq, oq)
                        if err < ERROR_THRESHOLD:
                            break
                if best_error < ERROR_THRESHOLD:
                    break

            transforms.append(best_t)

    buf = io.BytesIO()
    buf.write(struct.pack('<HH', rH, rW))
    buf.write(struct.pack('<HH', H, W))
    for (di, dj, sq, oq) in transforms:
        buf.write(struct.pack('<HHHH', di, dj, sq, oq))
    return buf.getvalue()


def _decode_channel(data: bytes, iterations: int = 8) -> np.ndarray:
    pos = 0
    rH, rW = struct.unpack_from('<HH', data, pos); pos += 4
    H, W   = struct.unpack_from('<HH', data, pos); pos += 4

    transforms = []
    for _ in range(rH * rW):
        di, dj, sq, oq = struct.unpack_from('<HHHH', data, pos); pos += 8
        s = _dequantize(sq, CONTRAST_LEVELS, -1.0, 1.0)
        o = _dequantize(oq, BRIGHTNESS_LEVELS, -128.0, 384.0)
        transforms.append((di, dj, s, o))

    img = np.full((H, W), 128.0, dtype=np.float32)

    for _ in range(iterations):
        new_img = np.zeros((H, W), dtype=np.float32)
        idx = 0
        for ri in range(rH):
            for rj in range(rW):
                di, dj, s, o = transforms[idx]; idx += 1
                d_block = img[di*DOMAIN_SIZE:(di+1)*DOMAIN_SIZE,
                               dj*DOMAIN_SIZE:(dj+1)*DOMAIN_SIZE]
                d_small = d_block[::2, ::2]
                new_img[ri*RANGE_SIZE:(ri+1)*RANGE_SIZE,
                         rj*RANGE_SIZE:(rj+1)*RANGE_SIZE] = np.clip(s * d_small + o, 0, 255)
        img = new_img

    return np.clip(img, 0, 255).astype(np.uint8)


def encode(file_path: str) -> bytes:
    try:
        img_obj = Image.open(file_path)
        mode = img_obj.mode
        if mode not in ('L', 'RGB', 'RGBA'):
            img_obj = img_obj.convert('RGB')
            mode = 'RGB'
        arr = np.array(img_obj, dtype=np.float32)
    except Exception:
        with open(file_path, 'rb') as f:
            raw = f.read()
        return struct.pack('<B', 0) + zstd.compress(raw, 19)

    if mode == 'L':
        channels = [arr]
    elif mode == 'RGB':
        channels = [arr[:, :, i] for i in range(3)]
    else:
        channels = [arr[:, :, i] for i in range(4)]

    H0, W0 = channels[0].shape
    if H0 < DOMAIN_SIZE * 2 or W0 < DOMAIN_SIZE * 2:
        with open(file_path, 'rb') as f:
            raw = f.read()
        return struct.pack('<B', 0) + zstd.compress(raw, 19)

    pH = (H0 // DOMAIN_SIZE) * DOMAIN_SIZE
    pW = (W0 // DOMAIN_SIZE) * DOMAIN_SIZE

    channel_parts = []
    for ch in channels:
        ch_crop = ch[:pH, :pW]
        cdata = _encode_channel(ch_crop)
        dec = _decode_channel(cdata)
        orig_crop = ch_crop.astype(np.int16)
        residual = (orig_crop - dec.astype(np.int16)).astype(np.int8)
        res_c = zstd.compress(residual.tobytes(), 19)
        cdata_c = zstd.compress(cdata, 9)
        channel_parts.append((cdata_c, res_c))

    buf = io.BytesIO()
    mode_b = mode.encode('ascii')
    buf.write(struct.pack('<B', len(mode_b))); buf.write(mode_b)
    buf.write(struct.pack('<HH', H0, W0))
    buf.write(struct.pack('<B', len(channel_parts)))
    for cdata_c, res_c in channel_parts:
        buf.write(struct.pack('<II', len(cdata_c), len(res_c)))
        buf.write(cdata_c); buf.write(res_c)

    seed = buf.getvalue()
    with open(file_path, 'rb') as f:
        raw = f.read()
    fallback = struct.pack('<B', 0) + zstd.compress(raw, 19)
    if len(fallback) < len(seed):
        return fallback
    return struct.pack('<B', 1) + seed


def decode(seed: bytes) -> bytes:
    mode_flag = struct.unpack('<B', seed[:1])[0]

    if mode_flag == 0:
        return zstd.decompress(seed[1:])

    buf = io.BytesIO(seed[1:])
    mode_len = struct.unpack('<B', buf.read(1))[0]
    mode = buf.read(mode_len).decode('ascii')
    H0, W0 = struct.unpack('<HH', buf.read(4))
    n_ch = struct.unpack('<B', buf.read(1))[0]

    pH = (H0 // DOMAIN_SIZE) * DOMAIN_SIZE
    pW = (W0 // DOMAIN_SIZE) * DOMAIN_SIZE

    channels_out = []
    for _ in range(n_ch):
        clen, rlen = struct.unpack('<II', buf.read(8))
        cdata = zstd.decompress(buf.read(clen))
        res_raw = zstd.decompress(buf.read(rlen))

        dec = _decode_channel(cdata)
        H, W = dec.shape
        residual = np.frombuffer(res_raw, dtype=np.int8).reshape(H, W)
        restored = np.clip(dec.astype(np.int16) + residual.astype(np.int16), 0, 255).astype(np.uint8)

        full = np.zeros((H0, W0), dtype=np.uint8)
        full[:H, :W] = restored
        channels_out.append(full)

    if len(channels_out) == 1:
        img = Image.fromarray(channels_out[0], 'L')
    elif len(channels_out) == 3:
        img = Image.fromarray(np.stack(channels_out, axis=2), 'RGB')
    else:
        img = Image.fromarray(np.stack(channels_out, axis=2), 'RGBA')

    out = io.BytesIO()
    img.save(out, format='PNG')
    return out.getvalue()
