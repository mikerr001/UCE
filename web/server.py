"""
NexForge UCE — landing page server.
Serves the marketing page and handles project zip download.
"""

import os
import io
import zipfile
from flask import Flask, send_file, render_template_string

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)

SKIP_DIRS  = {'__pycache__', '.git', '.local', 'attached_assets',
              'web', '.pythonlibs', '.upm', '.cache', 'dist', 'build'}
SKIP_FILES = {'codebook.bin', 'index.db', 'hdm.matrix.npy', '.replit',
              'replit.nix', '.gitattributes', '.gitignore'}
SKIP_EXTS  = {'.pyc', '.pyo', '.spec'}


SAFE_DATE = (1980, 1, 1, 0, 0, 0)


def _build_zip() -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(BASE_DIR):
            dirs[:] = [d for d in sorted(dirs) if d not in SKIP_DIRS]
            rel_root = os.path.relpath(root, BASE_DIR)
            for fname in sorted(files):
                if fname in SKIP_FILES:
                    continue
                if os.path.splitext(fname)[1] in SKIP_EXTS:
                    continue
                abs_path = os.path.join(root, fname)
                if rel_root == '.':
                    arc_path = f'NexForge_UCE/{fname}'
                else:
                    arc_path = f'NexForge_UCE/{rel_root}/{fname}'
                arc_path = arc_path.replace('\\', '/')
                with open(abs_path, 'rb') as f:
                    data = f.read()
                info = zipfile.ZipInfo(arc_path, date_time=SAFE_DATE)
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, data)
    buf.seek(0)
    return buf


@app.route('/download')
def download():
    buf = _build_zip()
    return send_file(
        buf,
        mimetype='application/zip',
        as_attachment=True,
        download_name='NexForge_UCE.zip',
    )


@app.route('/')
def index():
    return render_template_string(HTML)


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>NexForge UCE — Universal Compression Engine</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:        #080808;
    --panel:     #101010;
    --border:    #1a1a1a;
    --accent:    #00e5ff;
    --accent2:   #7c3aed;
    --text:      #f0f0f0;
    --muted:     #555;
    --success:   #00c896;
    --card-bg:   #111;
  }

  html { scroll-behavior: smooth; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 15px;
    line-height: 1.6;
    min-height: 100vh;
  }

  a { color: var(--accent); text-decoration: none; }

  /* NAV */
  nav {
    position: sticky; top: 0; z-index: 100;
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 40px; height: 56px;
    background: rgba(8,8,8,.92);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border);
  }
  .nav-brand { font-weight: 700; font-size: 17px; letter-spacing: .5px; color: var(--text); }
  .nav-brand span { color: var(--accent); }
  .nav-links { display: flex; gap: 28px; }
  .nav-links a { color: var(--muted); font-size: 13px; transition: color .2s; }
  .nav-links a:hover { color: var(--text); }
  .nav-dl {
    background: var(--accent); color: #000;
    font-size: 13px; font-weight: 700;
    padding: 7px 18px; border-radius: 6px;
    transition: opacity .2s;
  }
  .nav-dl:hover { opacity: .85; color: #000; }

  /* HERO */
  .hero {
    display: flex; flex-direction: column; align-items: center;
    text-align: center; padding: 96px 24px 72px;
  }
  .badge {
    display: inline-block;
    background: rgba(0,229,255,.08);
    border: 1px solid rgba(0,229,255,.2);
    color: var(--accent); font-size: 11px; font-weight: 700;
    letter-spacing: 1.5px; text-transform: uppercase;
    padding: 4px 14px; border-radius: 99px; margin-bottom: 24px;
  }
  .hero h1 {
    font-size: clamp(36px, 6vw, 68px);
    font-weight: 800; line-height: 1.08;
    letter-spacing: -1.5px; max-width: 780px;
  }
  .hero h1 em { font-style: normal; color: var(--accent); }
  .hero p {
    max-width: 560px; margin: 20px auto 0;
    color: var(--muted); font-size: 17px; line-height: 1.7;
  }
  .hero-btns { display: flex; gap: 14px; margin-top: 40px; flex-wrap: wrap; justify-content: center; }
  .btn-primary {
    background: var(--accent); color: #000;
    font-weight: 700; font-size: 15px;
    padding: 13px 32px; border-radius: 8px;
    border: none; cursor: pointer; transition: opacity .2s;
    display: inline-flex; align-items: center; gap: 8px;
    text-decoration: none;
  }
  .btn-primary:hover { opacity: .85; color: #000; }
  .btn-outline {
    background: transparent; color: var(--text);
    font-size: 15px; padding: 12px 28px;
    border: 1px solid var(--border); border-radius: 8px;
    cursor: pointer; transition: border-color .2s;
    text-decoration: none;
  }
  .btn-outline:hover { border-color: var(--muted); color: var(--text); }
  .hero-note { margin-top: 18px; font-size: 12px; color: var(--muted); }

  /* STATS STRIP */
  .stats {
    display: flex; justify-content: center; flex-wrap: wrap; gap: 0;
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    background: var(--panel);
  }
  .stat {
    padding: 28px 48px; text-align: center;
    border-right: 1px solid var(--border);
  }
  .stat:last-child { border-right: none; }
  .stat-num { font-size: 32px; font-weight: 800; color: var(--accent); }
  .stat-lbl { font-size: 12px; color: var(--muted); margin-top: 2px; letter-spacing: .5px; }

  /* SECTION */
  section { padding: 80px 24px; max-width: 1060px; margin: 0 auto; }
  .section-label {
    font-size: 11px; font-weight: 700; letter-spacing: 2px;
    text-transform: uppercase; color: var(--accent); margin-bottom: 12px;
  }
  .section-title { font-size: clamp(24px, 4vw, 38px); font-weight: 800; line-height: 1.15; }
  .section-sub { color: var(--muted); margin-top: 12px; max-width: 520px; font-size: 15px; }

  /* EXTRACTOR GRID */
  .grid6 {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px; margin-top: 40px;
  }
  .card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 12px; padding: 24px;
    transition: border-color .2s;
  }
  .card:hover { border-color: var(--accent2); }
  .card-icon { font-size: 26px; margin-bottom: 12px; }
  .card-title { font-weight: 700; font-size: 15px; margin-bottom: 6px; }
  .card-desc { font-size: 13px; color: var(--muted); line-height: 1.6; }
  .card-tag {
    display: inline-block; margin-top: 12px;
    font-size: 11px; font-weight: 600;
    background: rgba(124,58,237,.15);
    color: #a78bfa; padding: 2px 10px; border-radius: 99px;
  }

  /* HOW IT WORKS */
  .steps { margin-top: 40px; display: flex; flex-direction: column; gap: 0; }
  .step {
    display: flex; gap: 24px; padding: 28px 0;
    border-bottom: 1px solid var(--border);
  }
  .step:last-child { border-bottom: none; }
  .step-num {
    flex-shrink: 0; width: 36px; height: 36px;
    background: rgba(0,229,255,.1);
    border: 1px solid rgba(0,229,255,.25);
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 14px; color: var(--accent);
    margin-top: 2px;
  }
  .step-body h3 { font-size: 16px; font-weight: 700; margin-bottom: 6px; }
  .step-body p { font-size: 14px; color: var(--muted); line-height: 1.6; }
  .step-body code {
    display: inline-block; margin-top: 10px;
    background: var(--panel); border: 1px solid var(--border);
    border-radius: 6px; padding: 8px 14px;
    font-family: Consolas, monospace; font-size: 13px;
    color: var(--success); white-space: pre;
  }

  /* INSTALL */
  .install-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(300px,1fr));
    gap: 16px; margin-top: 36px;
  }
  .install-card {
    background: var(--panel); border: 1px solid var(--border);
    border-radius: 12px; padding: 24px;
  }
  .install-card h3 { font-size: 14px; font-weight: 700; margin-bottom: 14px; color: var(--accent); }
  .install-card ol { padding-left: 18px; }
  .install-card li { font-size: 13px; color: var(--muted); margin-bottom: 8px; line-height: 1.6; }
  .install-card li strong { color: var(--text); }
  .codeblock {
    background: #0a0a0a; border: 1px solid var(--border);
    border-radius: 8px; padding: 14px 18px; margin-top: 10px;
    font-family: Consolas, monospace; font-size: 13px;
    color: var(--success); line-height: 1.8; overflow-x: auto;
  }

  /* FLASH DRIVE */
  #flashdrive { border-top: 1px solid var(--border); }
  .usb-layout {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px; margin-top: 40px;
  }
  @media (max-width: 700px) { .usb-layout { grid-template-columns: 1fr; } }

  .usb-tree {
    background: #0a0a0a;
    border: 1px solid var(--border);
    border-radius: 12px; padding: 24px;
    font-family: Consolas, monospace; font-size: 13px;
    line-height: 2;
  }
  .usb-tree .root { color: var(--accent); font-weight: 700; font-size: 14px; }
  .usb-tree .req  { color: var(--success); }
  .usb-tree .opt  { color: var(--muted); }
  .usb-tree .note { font-family: 'Segoe UI', sans-serif; font-size: 11px;
                    color: #444; margin-left: 24px; display: block; }

  .checklist {
    display: flex; flex-direction: column; gap: 0;
  }
  .chk {
    display: flex; align-items: flex-start; gap: 14px;
    padding: 16px 0; border-bottom: 1px solid var(--border);
  }
  .chk:last-child { border-bottom: none; }
  .chk-icon {
    flex-shrink: 0; width: 28px; height: 28px;
    background: rgba(0,229,255,.08);
    border: 1px solid rgba(0,229,255,.18);
    border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px; margin-top: 1px;
  }
  .chk-body h4 { font-size: 14px; font-weight: 700; margin-bottom: 3px; }
  .chk-body p  { font-size: 13px; color: var(--muted); line-height: 1.55; }
  .chk-body code {
    background: var(--panel); border: 1px solid var(--border);
    border-radius: 4px; padding: 1px 6px;
    font-family: Consolas, monospace; font-size: 12px; color: var(--success);
  }
  .tag-req {
    display: inline-block; font-size: 10px; font-weight: 700;
    background: rgba(0,200,150,.12); color: var(--success);
    padding: 1px 8px; border-radius: 99px; margin-left: 8px;
    vertical-align: middle; letter-spacing: .5px;
  }
  .tag-opt {
    display: inline-block; font-size: 10px; font-weight: 700;
    background: rgba(255,255,255,.05); color: var(--muted);
    padding: 1px 8px; border-radius: 99px; margin-left: 8px;
    vertical-align: middle; letter-spacing: .5px;
  }
  .autorun-note {
    margin-top: 24px; padding: 16px 20px;
    background: rgba(124,58,237,.08);
    border: 1px solid rgba(124,58,237,.25);
    border-radius: 10px; font-size: 13px; color: var(--muted); line-height: 1.7;
  }
  .autorun-note strong { color: var(--text); }

  /* CTA */
  .cta-section {
    text-align: center; padding: 80px 24px;
    background: linear-gradient(180deg, var(--bg) 0%, rgba(124,58,237,.06) 100%);
    border-top: 1px solid var(--border);
  }
  .cta-section h2 { font-size: clamp(26px, 4vw, 42px); font-weight: 800; }
  .cta-section p { color: var(--muted); margin: 14px auto 0; max-width: 480px; font-size: 15px; }
  .cta-section .btn-primary { margin-top: 32px; font-size: 16px; padding: 15px 40px; }

  /* FOOTER */
  footer {
    border-top: 1px solid var(--border);
    padding: 28px 40px;
    display: flex; justify-content: space-between; align-items: center;
    flex-wrap: wrap; gap: 12px;
    color: var(--muted); font-size: 12px;
  }
  .footer-brand { font-weight: 700; font-size: 14px; color: var(--text); }
  .footer-brand span { color: var(--accent); }

  @media (max-width: 600px) {
    nav { padding: 0 18px; }
    .nav-links { display: none; }
    .stat { padding: 22px 28px; }
    section { padding: 56px 18px; }
    .step { flex-direction: column; gap: 12px; }
  }
</style>
</head>
<body>

<!-- NAV -->
<nav>
  <div class="nav-brand">Nex<span>Forge</span> UCE</div>
  <div class="nav-links">
    <a href="#how">How it works</a>
    <a href="#extractors">Engine</a>
    <a href="#install">Install</a>
    <a href="#flashdrive">Flash Drive</a>
  </div>
  <div style="display:flex;gap:8px;align-items:center;">
    <a class="nav-dl" style="background:var(--accent2);color:#fff;"
       href="https://github.com/mikerr001/UCE/releases/latest"
       target="_blank">&#8595; .exe</a>
    <a class="nav-dl" href="/download">&#8595; .zip</a>
  </div>
</nav>

<!-- HERO -->
<div class="hero">
  <div class="badge">Universal Compression Engine</div>
  <h1>Compress anything.<br/><em>Losslessly.</em></h1>
  <p>Seven specialised algorithms fused with a Hyperdimensional Memory.
     Every file type. Fully offline. Runs from a USB flash drive.</p>
  <div class="hero-btns">
    <a class="btn-primary"
       href="https://github.com/mikerr001/UCE/releases/latest"
       target="_blank">
      &#8595;&nbsp; Download .exe &nbsp;<span style="font-weight:400;opacity:.75;font-size:13px;">Windows · no Python needed</span>
    </a>
    <a class="btn-outline" href="/download">&#8595; Source .zip</a>
  </div>
  <p class="hero-note">
    Pre-built Windows .exe via GitHub Releases &nbsp;&middot;&nbsp;
    Source runs on Windows, macOS &amp; Linux with Python 3.10+
  </p>
  <div style="margin-top:24px;padding:12px 20px;background:rgba(0,229,255,.05);
              border:1px solid rgba(0,229,255,.15);border-radius:10px;
              font-size:12px;color:var(--muted);max-width:480px;line-height:1.7;">
    <strong style="color:var(--text);">First time?</strong>
    The .exe button links to GitHub Releases — click it, find
    <strong style="color:var(--text);">NexForge_UCE.exe</strong> under Assets, and download.
    No Python, no setup, just run.
  </div>
</div>

<!-- STATS -->
<div class="stats">
  <div class="stat">
    <div class="stat-num">7</div>
    <div class="stat-lbl">Compression algorithms</div>
  </div>
  <div class="stat">
    <div class="stat-num">100%</div>
    <div class="stat-lbl">Lossless on every file</div>
  </div>
  <div class="stat">
    <div class="stat-num">0</div>
    <div class="stat-lbl">Cloud / internet needed</div>
  </div>
  <div class="stat">
    <div class="stat-num">USB</div>
    <div class="stat-lbl">Flash-drive ready</div>
  </div>
</div>

<!-- EXTRACTORS -->
<section id="extractors">
  <div class="section-label">The Engine</div>
  <h2 class="section-title">Seven algorithms. One unified memory.</h2>
  <p class="section-sub">Each extractor targets a different type of redundancy.
     The engine picks the best one automatically — you never need to choose.</p>

  <div class="grid6">
    <div class="card">
      <div class="card-icon">🌿</div>
      <div class="card-title">Fractal IFS</div>
      <div class="card-desc">Detects self-similar regions across scales using Iterated Function Systems.
        Stores affine transformation codes instead of raw pixels.</div>
      <div class="card-tag">Images &bull; 3D geometry</div>
    </div>
    <div class="card">
      <div class="card-icon">🧮</div>
      <div class="card-title">Tensor Networks</div>
      <div class="card-desc">Treats multi-dimensional arrays as low-rank tensors.
        Tucker/SVD decomposition shrinks large tables to tiny core matrices.</div>
      <div class="card-tag">CSV &bull; Tabular data</div>
    </div>
    <div class="card">
      <div class="card-icon">📜</div>
      <div class="card-title">Grammar Inference</div>
      <div class="card-desc">Extracts generative rules from structured text.
        Stores a compact grammar and a parameter list — not the full document.</div>
      <div class="card-tag">Text &bull; Code &bull; JSON &bull; SVG</div>
    </div>
    <div class="card">
      <div class="card-icon">🔣</div>
      <div class="card-title">Program Synthesis</div>
      <div class="card-desc">Finds the shortest pattern or program that reproduces the data exactly.
        Ideal for numeric sequences and structured binary formats.</div>
      <div class="card-tag">Sequences &bull; Patterns</div>
    </div>
    <div class="card">
      <div class="card-icon">🔮</div>
      <div class="card-title">Holographic Codebook</div>
      <div class="card-desc">Maps high-entropy (random-looking) blocks to tiny address pointers
        using a pre-shared XOR codebook. Compresses what others can't.</div>
      <div class="card-tag">Encrypted &bull; Random &bull; Binary</div>
    </div>
    <div class="card">
      <div class="card-icon">🌊</div>
      <div class="card-title">Boundary Extraction</div>
      <div class="card-desc">Stores low-dimensional boundary maps and event logs for time-series data.
        Reconstructs full waveforms from compact constraint seeds.</div>
      <div class="card-tag">Audio &bull; Video</div>
    </div>
    <div class="card">
      <div class="card-icon">📖</div>
      <div class="card-title">Semantic Domain Encoder</div>
      <div class="card-desc">Builds a domain phrase dictionary from the document itself, tokenizes with
        maximal-munch, applies LZ77 on the token stream, then encodes with an
        adaptive order-2 Markov model and range coder. Achieves 50–150:1 on
        technical manuals.</div>
      <div class="card-tag">Manuals &bull; Contracts &bull; Code &bull; Docs</div>
    </div>
  </div>
</section>

<!-- HOW IT WORKS -->
<section id="how" style="border-top:1px solid var(--border); max-width:1060px;">
  <div class="section-label">How it works</div>
  <h2 class="section-title">Drop a file. Get it back. Always identical.</h2>

  <div class="steps">
    <div class="step">
      <div class="step-num">1</div>
      <div class="step-body">
        <h3>Drop a file or folder</h3>
        <p>Drag any file or folder into the app window — documents, images, CSVs, audio, video,
           encrypted archives, anything. Or click Browse to pick one.</p>
      </div>
    </div>
    <div class="step">
      <div class="step-num">2</div>
      <div class="step-body">
        <h3>The engine classifies and compresses</h3>
        <p>The classifier identifies the file type using magic bytes and extension.
           It then tries all relevant extractors and picks the one that produces the smallest seed,
           with a zstd residual guaranteeing byte-perfect losslessness.</p>
      </div>
    </div>
    <div class="step">
      <div class="step-num">3</div>
      <div class="step-body">
        <h3>The seed is stored in the HDM</h3>
        <p>Every seed is bound to its file path via a hypervector and stored in the
           Hyperdimensional Memory — a SQLite-backed content-addressable index.
           Optionally delete the original to free disk space.</p>
      </div>
    </div>
    <div class="step">
      <div class="step-num">4</div>
      <div class="step-body">
        <h3>Retrieve any time</h3>
        <p>Select the file in the list, click Retrieve, choose a save location.
           The engine reconstructs the original file byte-for-byte using the stored seed.</p>
      </div>
    </div>
  </div>
</section>

<!-- INSTALL -->
<section id="install" style="border-top:1px solid var(--border); max-width:1060px;">
  <div class="section-label">Installation</div>
  <h2 class="section-title">Run it in 3 steps.</h2>
  <p class="section-sub">No cloud account. No installer wizard. Works offline from day one.</p>

  <div class="install-grid">
    <div class="install-card">
      <h3>Step 1 — Download &amp; unzip</h3>
      <ol>
        <li>Click <strong>Download</strong> above</li>
        <li>Unzip <code>NexForge_UCE.zip</code> anywhere on your PC<br/>
            (or directly to your flash drive)</li>
        <li>Open the <code>NexForge_UCE</code> folder</li>
      </ol>
    </div>
    <div class="install-card">
      <h3>Step 2 — Install dependencies</h3>
      <p style="font-size:13px;color:var(--muted);margin-bottom:8px;">
        Requires <strong style="color:var(--text)">Python 3.10+</strong> — 
        <a href="https://python.org" target="_blank">python.org</a></p>
      <div class="codeblock">pip install -r requirements.txt</div>
    </div>
    <div class="install-card">
      <h3>Step 3 — Launch</h3>
      <div class="codeblock">python sce.py</div>
      <p style="font-size:13px;color:var(--muted);margin-top:10px;">
        First launch takes ~30 seconds to generate the engine's codebook.
        After that it's instant.</p>
    </div>
    <div class="install-card">
      <h3>Build a Windows .exe</h3>
      <ol>
        <li>Install <strong>PyInstaller:</strong> <code>pip install pyinstaller</code></li>
        <li>Run <strong>build_exe.bat</strong> (double-click on Windows)</li>
        <li>Find your exe at <strong>dist\NexForge_UCE.exe</strong></li>
        <li>Copy to flash drive with <strong>autorun.inf</strong> included</li>
      </ol>
    </div>
  </div>
</section>

<!-- FLASH DRIVE -->
<section id="flashdrive" style="max-width:1060px;">
  <div class="section-label">Flash Drive Setup</div>
  <h2 class="section-title">Put it on a USB stick.</h2>
  <p class="section-sub">Everything you need to run NexForge UCE auto-launches
     the moment you plug the drive into a Windows PC.</p>

  <div class="usb-layout">

    <!-- FILE TREE -->
    <div>
      <p style="font-size:12px;color:var(--muted);margin-bottom:12px;letter-spacing:.5px;text-transform:uppercase;">Drive layout</p>
      <div class="usb-tree">
        <span class="root">&#128190; USB Drive (root)</span><br/>
        <span class="req">&#9500;&#9472; autorun.inf</span>
          <span class="note">&#8627; triggers auto-launch on plug-in</span>
        <span class="req">&#9500;&#9472; launch.bat</span>
          <span class="note">&#8627; starts the app (Python must be installed)</span>
        <span class="req">&#9500;&#9472; launch_portable.bat</span>
          <span class="note">&#8627; uses bundled Python — no install needed</span>
        <span class="req">&#9500;&#9472; NexForge_UCE.exe</span>
          <span class="note">&#8627; standalone .exe (built with build_exe.bat)</span>
        <span class="req">&#9500;&#9472; sce.py</span>
          <span class="note">&#8627; main script (if running from source)</span>
        <span class="req">&#9500;&#9472; requirements.txt</span>
        <span class="req">&#9500;&#9472; build_exe.bat</span>
        <span class="req">&#9500;&#9472; engine&#47;  &nbsp;<span style="color:var(--muted)">(auto-created)</span></span>
          <span class="note">&#8627; codebook + HDM generated on first launch</span>
        <span class="req">&#9500;&#9472; extractors&#47;</span>
        <span class="opt">&#9492;&#9472; python&#47; &nbsp;<span style="color:#333">(optional)</span></span>
          <span class="note">&#8627; portable Python — for PCs without Python</span>
      </div>
    </div>

    <!-- CHECKLIST -->
    <div>
      <p style="font-size:12px;color:var(--muted);margin-bottom:12px;letter-spacing:.5px;text-transform:uppercase;">Step-by-step checklist</p>
      <div class="checklist">

        <div class="chk">
          <div class="chk-icon">1</div>
          <div class="chk-body">
            <h4>Download &amp; unzip <span class="tag-req">required</span></h4>
            <p>Click <strong>Download</strong> above. Unzip
               <code>NexForge_UCE.zip</code> directly to the root of your flash drive.</p>
          </div>
        </div>

        <div class="chk">
          <div class="chk-icon">2</div>
          <div class="chk-body">
            <h4>Build the .exe <span class="tag-opt">recommended</span></h4>
            <p>On a Windows PC with Python installed, open the drive folder and run
               <code>build_exe.bat</code>. This produces
               <code>dist\NexForge_UCE.exe</code> — copy it to the drive root.</p>
          </div>
        </div>

        <div class="chk">
          <div class="chk-icon">3</div>
          <div class="chk-body">
            <h4>Check <code>autorun.inf</code> is at root <span class="tag-req">required</span></h4>
            <p>The file must sit at the very root of the drive (not inside a subfolder).
               It tells Windows to show the AutoPlay prompt when the drive is plugged in.</p>
          </div>
        </div>

        <div class="chk">
          <div class="chk-icon">4</div>
          <div class="chk-body">
            <h4>Plug in &amp; launch <span class="tag-req">required</span></h4>
            <p>Insert the drive. Windows shows an AutoPlay popup — click
               <strong>"Run launch.bat"</strong> (or <strong>"Run NexForge_UCE.exe"</strong>
               if you built the .exe). The app opens instantly.</p>
          </div>
        </div>

        <div class="chk">
          <div class="chk-icon">5</div>
          <div class="chk-body">
            <h4>First launch — engine init <span class="tag-opt">one time only</span></h4>
            <p>On the very first run the engine generates its codebook and HDM index
               (stored in the <code>engine\</code> folder on the drive).
               This takes ~30 seconds. Every launch after that is instant.</p>
          </div>
        </div>

        <div class="chk">
          <div class="chk-icon">&#128194;</div>
          <div class="chk-body">
            <h4>No Python on the target PC? <span class="tag-opt">optional</span></h4>
            <p>Download the
               <a href="https://www.python.org/downloads/windows/" target="_blank">Windows embeddable package</a>
               from python.org. Extract it into a <code>python\</code> subfolder on the drive.
               <code>launch_portable.bat</code> will use it automatically — no install required.</p>
          </div>
        </div>

      </div>

      <div class="autorun-note">
        <strong>&#9432; Windows 10 / 11 AutoRun note:</strong> Microsoft disabled full AutoRun for USB
        drives by default as a security measure. The drive will still show an
        <strong>AutoPlay popup</strong> — the user clicks once to launch. To enable fully
        automatic launch without any click, a Group Policy change is required
        (see <em>Help &rarr; How to Build .exe</em> inside the app for instructions).
      </div>
    </div>

  </div>
</section>

<!-- CTA -->
<div class="cta-section">
  <h2>Ready to compress everything?</h2>
  <p>Free download. No account. No limits. Works on Windows, macOS, and Linux.</p>
  <div style="display:flex;gap:14px;justify-content:center;flex-wrap:wrap;margin-top:32px;">
    <a class="btn-primary"
       href="https://github.com/mikerr001/UCE/releases/latest"
       target="_blank"
       style="font-size:16px;padding:15px 36px;">
      &#8595;&nbsp; Download .exe &nbsp;<span style="font-weight:400;opacity:.7;font-size:13px;">Windows · pre-built</span>
    </a>
    <a class="btn-outline" href="/download"
       style="font-size:15px;padding:14px 28px;">
      &#8595;&nbsp; Source .zip
    </a>
  </div>
  <p style="margin-top:16px;font-size:12px;color:var(--muted);">
    .exe built automatically by GitHub Actions &nbsp;&middot;&nbsp;
    <a href="https://github.com/mikerr001/UCE" target="_blank"
       style="color:var(--muted);text-decoration:underline;">View source on GitHub</a>
  </p>
</div>

<!-- FOOTER -->
<footer>
  <div>
    <div class="footer-brand">Nex<span>Forge</span> UCE</div>
    <div style="margin-top:4px">Universal Compression Engine &mdash; fully offline, fully lossless</div>
  </div>
  <div>Python &bull; NumPy &bull; Pillow &bull; zstd &bull; Tkinter</div>
</footer>

</body>
</html>
"""


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
