# Moodle Downloader

A Python application for automating the download of course materials from Moodle. Features both a graphical interface and command-line interface for downloading files from enrolled courses.

## Features

- **Automated Login**: Secure authentication with Moodle
- **Course Detection**: Lists all enrolled courses  
- **Batch Downloads**: Downloads all course files with folder structure preservation
- **Archive Extraction**: Automatically extracts ZIP files
- **GUI Interface**: User-friendly PyQt5 interface
- **Progress Tracking**: Real-time download progress and status updates
- **Cross-Platform**: Works on Windows, macOS, and Linux

## Technology Stack

- **Python 3.x**: Core language
- **PyQt5**: GUI framework
- **Playwright**: Browser automation
- **BeautifulSoup4**: HTML parsing
- **Keyring**: Secure credential storage

## Prerequisites

- Python 3.8 or higher
- Modern web browser (Chrome, Firefox, or Edge)

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/tomerbar201/moodle-downloader.git
   cd moodle-downloader
   ```

2. **Create and activate virtual environment:**
   ```bash
   python -m venv venv
   
   # On Windows:
   venv\Scripts\activate
   
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   playwright install
   ```

4. **(Optional) Build a standalone Windows executable:**
   ```bash
   pip install pyinstaller
   pyinstaller --noconfirm --clean moodle_downloader.spec
   ```
   The executable will be written to `dist/MoodleDownloader/MoodleDownloader.exe`. On first launch it will download Playwright's Chromium build into `%LOCALAPPDATA%\MoodleDown\pw-browsers` if it is not already present.

## Usage

### GUI Mode (Recommended)
```bash
python run_gui.py
```

### Command Line Mode
```bash
python run_cli.py <course_url> <username> <password> <download_folder>
```

Follow the prompts to enter your Moodle credentials and select courses to download.

## Project Structure

```
moodle-downloader/
├── src/                      # Source code
│   ├── main.py              # Core download logic
│   ├── moodledown_gui.py    # GUI application  
│   ├── moodle_browser.py    # Browser automation
│   ├── content_extractor.py # HTML parsing
│   ├── course_extractor.py  # Course extraction
│   ├── download_handler.py  # File download management
│   ├── file_operations.py   # File utilities
│   ├── data_structures.py   # Data classes
│   ├── unzipper.py          # Archive extraction
│   └── chromium_setup.py    # Browser setup
├── tests/                    # Test files
│   ├── test_course_extractor.py
│   └── test_moodle_downloader.py
├── docs/                     # Documentation
│   ├── AUTO_FILL_FEATURE.md
│   ├── AUTOFILL_UPDATE.md
│   └── CHANGES.md
├── run_gui.py               # GUI entry point
├── run_cli.py               # CLI entry point
├── setup.py                 # Package setup
├── requirements.txt         # Dependencies
└── moodle_downloader.spec   # PyInstaller spec
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

Distributed under the MIT License. See `LICENSE` for more information.

## Contact

Tomer Bar - tomerbar2021@gmail.com

Project Link: [https://github.com/tomerbar201/moodle-downloader](https://github.com/tomerbar201/moodle-downloader)
