# Moodle Course Downloader (GUI)

Python GUI tool to authenticate to a Moodle instance and download course content (files, zips, etc.), with optional extraction and structured storage.

## Features

- GUI front-end (`moodledown_gui.py`) for user-friendly operation
- Automated login & navigation via Playwright
- Download manager with retry logic
- Content extraction / unzip support
- Structured data utilities (`data_structures.py`)
- Packaged executable build via PyInstaller (`build_exe.ps1` + `.spec` file)

## Quick Start (Developer Mode)

1. Create & activate a virtual environment (recommended):
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
3. (If Playwright browsers not yet installed) install them:
   ```powershell
   python -m playwright install
   ```
4. Run the GUI:
   ```powershell
   python moodledown_gui.py
   ```

## Building a Standalone EXE

The repo includes a PyInstaller spec and helper script.

```powershell
pwsh ./build_exe.ps1
```

Artifacts are created under `dist/` (ignored by git). The script may also generate a `build/` working directory.

## Repository Layout (Key Files)

| File | Purpose |
|------|---------|
| `moodledown_gui.py` | Main GUI entry point |
| `main.py` | Possibly CLI / core startup (if applicable) |
| `moodle_browser.py` | Playwright browser automation helpers |
| `download_handler.py` | Handles file download logic |
| `content_extractor.py` | Extraction / unzip logic |
| `file_operations.py` | Filesystem utilities |
| `data_structures.py` | Data containers / models |
| `unzipper.py` | Additional unzip utilities |
| `moodledown_gui.spec` | PyInstaller build spec |
| `build_exe.ps1` | PowerShell build script |
| `requirements.txt` | Python dependencies |
| `README_BUILD.md` | Extra build details (advanced) |

## Notes

- The `browsers/` directory (Playwright downloads) is ignored; Playwright will re-download as needed.
- Avoid committing large binary artifacts; reproducible builds keep the repo lean.
- Adjust `.gitignore` if you decide to vendor specific runtime binaries.

## Next Steps / Ideas

- Add automated tests
- CI workflow (GitHub Actions) for linting & packaging
- Configurable output directory in GUI
- Logging panel inside the GUI

## License

Add a LICENSE file (MIT / Apache-2.0 / etc.) if you plan to share publicly.
