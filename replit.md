# NexForge UCE — Universal Compression Engine

A Python implementation of the NexForge UCE architecture from the technical specification. Fuses 6 compression principles into a unified engine with a drag-and-drop GUI.

## Running the app

```
python sce.py
```

On first launch, the engine initialises itself (generates the holographic codebook and HDM index). This takes ~30 seconds.

## Architecture

```
sce.py                  — Main entry point
engine/
  classifier.py         — File type detection (magic bytes + extension)
  hdm.py                — Hyperdimensional Memory (SDM + SQLite backend)
  codebook.py           — Holographic codebook generator and XOR mapper
  compressor.py         — Central dispatcher: routes files to extractors
  installer.py          — First-time setup (codebook, HDM init)
extractors/
  fractal_ifs.py        — Fractal IFS for images (affine block transform)
  tensor_net.py         — SVD/Tucker decomposition for tabular data
  grammar_infer.py      — Grammar inference for repetitive text/docs
  program_synth.py      — Pattern/program synthesis for sequences
  holographic.py        — Holographic codebook for random/encrypted data
  boundary.py           — Boundary constraint extractor for video/audio
ui/
  app.py                — Tkinter drag-and-drop GUI
```

## Turning this into a Windows .exe

See `build_exe.bat`. Run it on Windows with PyInstaller installed:

```
build_exe.bat
```

This produces `dist/NexForge_UCE.exe`. Copy the entire project folder to the flash drive. Add `autorun.inf` and `launch.bat` to the root of the drive for auto-launch on USB connection.

## Flash drive setup

1. Copy all project files to the flash drive
2. `autorun.inf` + `launch.bat` are already included for Windows auto-launch
3. The `engine/` folder is created automatically on first run (codebook + index)
4. No internet connection needed after first install

## User preferences

- No unnecessary comments in code
- Honest about compression ratios (no inflated claims)
- Lossless reconstruction guaranteed for all file types via stored residuals
