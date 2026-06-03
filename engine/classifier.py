"""
File classifier — two-tier detection:
  1. Magic bytes / file extension  (instant)
  2. Content sniffing for ambiguous types
"""

import os
import struct

MAGIC = {
    b'\xff\xd8\xff': 'image',
    b'\x89PNG':      'image',
    b'GIF8':         'image',
    b'BM':           'image',
    b'\x00\x00\x01\x00': 'image',
    b'%PDF':         'document',
    b'PK\x03\x04':  'archive',
    b'\x1f\x8b':    'archive',
    b'BZh':         'archive',
    b'\xfd7zXZ':    'archive',
    b'7z\xbc\xaf':  'archive',
    b'\x25\x21':    'code',
    b'MZ':           'executable',
    b'\x7fELF':     'executable',
    b'ID3':         'audio',
    b'fLaC':        'audio',
    b'OggS':        'audio',
    b'\xff\xfb':    'audio',
    b'\xff\xf3':    'audio',
    b'\xff\xf2':    'audio',
    b'RIFF':        'audio',
}

EXT_MAP = {
    '.txt': 'document', '.md': 'document', '.rst': 'document',
    '.pdf': 'document', '.doc': 'document', '.docx': 'document',
    '.odt': 'document', '.rtf': 'document', '.tex': 'document',
    '.csv': 'tabular',  '.tsv': 'tabular',  '.xlsx': 'tabular',
    '.xls': 'tabular',  '.ods': 'tabular',  '.parquet': 'tabular',
    '.json': 'structured', '.xml': 'structured', '.yaml': 'structured',
    '.yml': 'structured', '.toml': 'structured', '.ini': 'structured',
    '.png': 'image',  '.jpg': 'image',  '.jpeg': 'image',
    '.gif': 'image',  '.bmp': 'image',  '.tiff': 'image',
    '.webp': 'image', '.ico': 'image',  '.svg': 'structured',
    '.mp4': 'video',  '.avi': 'video',  '.mkv': 'video',
    '.mov': 'video',  '.wmv': 'video',  '.flv': 'video',
    '.webm': 'video', '.m4v': 'video',
    '.mp3': 'audio',  '.wav': 'audio',  '.flac': 'audio',
    '.ogg': 'audio',  '.m4a': 'audio',  '.aac': 'audio',
    '.wma': 'audio',
    '.obj': '3d',     '.stl': '3d',     '.fbx': '3d',
    '.ply': '3d',     '.gltf': '3d',    '.glb': '3d',
    '.dxf': '3d',     '.dwg': '3d',     '.step': '3d',
    '.py': 'code',    '.js': 'code',    '.ts': 'code',
    '.c': 'code',     '.cpp': 'code',   '.h': 'code',
    '.java': 'code',  '.go': 'code',    '.rs': 'code',
    '.rb': 'code',    '.php': 'code',   '.cs': 'code',
    '.swift': 'code', '.kt': 'code',    '.sh': 'code',
    '.zip': 'archive', '.tar': 'archive', '.gz': 'archive',
    '.bz2': 'archive', '.7z': 'archive', '.rar': 'archive',
    '.xz': 'archive',
    '.exe': 'executable', '.dll': 'executable', '.so': 'executable',
    '.bin': 'binary',
}

ENTROPY_THRESHOLD = 7.6


def _shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    from collections import Counter
    import math
    counts = Counter(data)
    total = len(data)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def classify(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in EXT_MAP:
        candidate = EXT_MAP[ext]
    else:
        candidate = None

    try:
        with open(file_path, 'rb') as f:
            header = f.read(16)
        for magic, ftype in MAGIC.items():
            if header.startswith(magic):
                if candidate and candidate != ftype:
                    return candidate
                return ftype
    except (IOError, OSError):
        return candidate or 'binary'

    if candidate:
        return candidate

    try:
        with open(file_path, 'rb') as f:
            sample = f.read(4096)
        entropy = _shannon_entropy(sample)
        if entropy > ENTROPY_THRESHOLD:
            return 'random'
        try:
            sample.decode('utf-8')
            return 'document'
        except UnicodeDecodeError:
            return 'binary'
    except (IOError, OSError):
        return 'binary'
