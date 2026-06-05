"""
Domain Dictionary Trainer for NexForge UCE.

Scans a folder of documents, accumulates corpus-wide n-gram frequencies,
and saves the top phrases to engine/domain_dict.bin (zstd-compressed JSON).

The shared dict is loaded by the Semantic Domain Encoder at compress time
so every file in the same domain benefits from corpus-wide phrase knowledge
instead of rebuilding the dictionary from scratch per document.

CLI usage:
    python engine/domain_dict.py /path/to/manual/folder
"""

import os
import re
import sys
import json
import zstd
from collections import Counter

DICT_FILE   = 'domain_dict.bin'
MAX_PHRASES = 10_000
MIN_FREQ    = 3
MAX_NGRAM   = 5
FILE_CAP_B  = 2 * 1024 * 1024  # 2 MB per file

TEXT_EXTS = {
    '.txt', '.md', '.rst', '.log', '.tex',
    '.csv', '.tsv',
    '.json', '.xml', '.yaml', '.yml', '.toml', '.ini',
    '.html', '.htm', '.svg',
    '.py', '.js', '.ts', '.java', '.c', '.cpp', '.h',
    '.go', '.rs', '.rb', '.php', '.cs', '.swift', '.kt', '.sh',
}


def _dict_path(base_dir: str) -> str:
    return os.path.join(base_dir, 'engine', DICT_FILE)


def is_trained(base_dir: str) -> bool:
    return os.path.exists(_dict_path(base_dir))


def load(base_dir: str):
    """Return the shared phrase list, or None if not trained."""
    p = _dict_path(base_dir)
    if not os.path.exists(p):
        return None
    try:
        with open(p, 'rb') as f:
            raw = f.read()
        return json.loads(zstd.decompress(raw).decode('utf-8'))
    except Exception:
        return None


def train(folder_path: str, base_dir: str, progress_cb=None) -> dict:
    """
    Scan every readable text file in folder_path (recursively),
    accumulate n-gram frequencies across the whole corpus, and save
    the top MAX_PHRASES phrases to engine/domain_dict.bin.

    progress_cb(fraction, message) is called throughout.
    Returns {'files': N, 'phrases': M, 'path': path}.
    """
    all_files = []
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
        for fname in sorted(files):
            if os.path.splitext(fname)[1].lower() in TEXT_EXTS:
                all_files.append(os.path.join(root, fname))

    if not all_files:
        return {'files': 0, 'phrases': 0, 'path': _dict_path(base_dir)}

    counts: Counter = Counter()
    processed = 0
    total = len(all_files)

    for i, fpath in enumerate(all_files):
        if progress_cb:
            progress_cb(
                0.05 + 0.80 * (i / total),
                f'[{i + 1}/{total}] {os.path.basename(fpath)}',
            )
        try:
            with open(fpath, 'rb') as f:
                raw = f.read(FILE_CAP_B)
            text = None
            for enc in ('utf-8', 'utf-8-sig', 'latin-1'):
                try:
                    text = raw.decode(enc)
                    break
                except Exception:
                    pass
            if text is None:
                continue
            words = re.findall(r'\S+', text)
            wlen = len(words)
            for n in range(2, MAX_NGRAM + 1):
                for j in range(wlen - n + 1):
                    counts[tuple(words[j: j + n])] += 1
            processed += 1
        except Exception:
            pass

    if progress_cb:
        progress_cb(0.87, f'Ranking {len(counts):,} n-grams…')

    scored = sorted(
        (
            (freq * (len(g) - 1), g)
            for g, freq in counts.items()
            if freq >= MIN_FREQ
        ),
        reverse=True,
    )
    phrases = [' '.join(g) for _, g in scored[:MAX_PHRASES]]
    phrases.sort(key=len, reverse=True)

    if progress_cb:
        progress_cb(0.95, f'Saving {len(phrases):,} phrases…')

    out_path = _dict_path(base_dir)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    payload = zstd.compress(
        json.dumps(phrases, ensure_ascii=False, separators=(',', ':')).encode('utf-8'),
        22,
    )
    with open(out_path, 'wb') as f:
        f.write(payload)

    if progress_cb:
        progress_cb(1.0, f'Done — {len(phrases):,} phrases from {processed} file(s).')

    return {'files': processed, 'phrases': len(phrases), 'path': out_path}


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python engine/domain_dict.py <folder>')
        sys.exit(1)

    _folder = sys.argv[1]
    _base   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _cb(frac, msg):
        print(f'  {int(frac * 100):3d}%  {msg}')

    _result = train(_folder, _base, progress_cb=_cb)
    print(f'\nSaved {_result["phrases"]:,} phrases from {_result["files"]} files.')
    print(f'Path: {_result["path"]}')
