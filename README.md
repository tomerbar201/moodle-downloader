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

## Usage

### GUI Mode (Recommended)
```bash
python moodledown_gui.py
```

### Command Line Mode
```bash
python main.py
```

Follow the prompts to enter your Moodle credentials and select courses to download.

## Project Structure

```
├── main.py                 # Command-line interface
├── moodledown_gui.py      # GUI application  
├── moodle_browser.py      # Browser automation
├── content_extractor.py   # HTML parsing
├── download_handler.py    # File download management
├── file_operations.py     # File utilities
├── data_structures.py     # Data classes
├── unzipper.py           # Archive extraction
└── requirements.txt      # Dependencies
```

## Usage

To run the application, execute the `moodledown_gui.py` file:

```bash
python moodledown_gui.py
```

Upon launching, you will be prompted to enter your Moodle username and password. The application will then log in, fetch your courses, and display them. You can then select the courses you want to download files from and choose a destination folder.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

Distributed under the MIT License. See `LICENSE` for more information.

## Contact

Tomer Bar - tomerbar2021@gmail.com

Project Link: [https://github.com/tomerbar2021/moodle-downloader](https://github.com/tomerbar2021/moodle-downloader)
