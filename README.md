# Moodle Downloader

A Python application for automating the download of course materials from Moodle. Features both a graphical interface and command-line interface for downloading files from enrolled courses.

## Features

- **Automated Login**: Secure authentication with Moodle using Playwright browser automation
- **Auto-fill Courses**: Automatically extract all enrolled courses from your Moodle dashboard
- **Course Detection**: Browse and select from all enrolled courses  
- **Batch Downloads**: Download all course files with folder structure preservation
- **Archive Extraction**: Automatically extracts ZIP files after download
- **GUI Interface**: User-friendly PyQt5 interface with progress tracking
- **Academic Year Support**: Select different academic years (e.g., 2024-25, 2023-24)
- **Credential Management**: Secure credential storage using system keyring
- **Real-time Progress**: Live download progress and status updates
- **Cross-Platform**: Works on Windows, macOS, and Linux

## Installation

### Option 1: Windows Executable (Recommended for Windows Users)

Download the latest `.exe` file from the [Releases](https://github.com/tomerbar201/moodle-downloader/releases) page and run it directly. No installation required!

On first launch, the executable will automatically download Playwright's Chromium browser into `%LOCALAPPDATA%\MoodleDown\pw-browsers`.

### Option 2: Run from Source

**Prerequisites:**
- Python 3.8 or higher
- pip (Python package manager)

**Installation Steps:**

1. **Clone the repository:**
   ```bash
   git clone https://github.com/tomerbar201/moodle-downloader.git
   cd moodle-downloader
   ```

2. **Create and activate virtual environment (recommended):**
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
   playwright install chromium
   ```

## Usage Guide

### GUI Mode (Recommended)

#### Starting the Application

**From executable:**
- Double-click `MoodleDownloader.exe`

**From source:**
```bash
python run_gui.py
```

#### Step-by-Step Guide

##### 1. **Enter Your Credentials**
   - **Username**: Your Moodle username
   - **Password**: Your Moodle password
   - **Save Credentials**: Check this to securely store credentials in your system keyring

##### 2. **Select Academic Year**
   - Choose the academic year from the dropdown (e.g., "2024-25", "2023-24")
   - This determines which Moodle instance to connect to

##### 3. **Choose Download Location**
   - Click "Browse" to select where files should be downloaded
   - A folder structure will be created for each course

##### 4. **Add Courses to Download**

   **Option A: Auto-fill Courses (Recommended for First-Time Users)**
   
   1. Click the **"Auto-fill Courses"** button
   2. The application will:
      - Log in to Moodle
      - Navigate to your dashboard
      - Extract all enrolled courses automatically
   3. Choose whether to:
      - **Replace** existing courses in the list
      - **Merge** with existing courses
   4. All your courses will appear in the course list
   
   **Option B: Manual Course Entry**
   
   1. Click **"Add Course"**
   2. Enter the course URL (e.g., `https://moodle.huji.ac.il/course/view.php?id=12345`)
   3. Enter a display name for the course
   4. Click "OK"

##### 5. **Select Courses to Download**
   - Check the boxes next to courses you want to download
   - Use "Select All" / "Deselect All" buttons for quick selection
   - Remove unwanted courses with the "Remove Course" button

##### 6. **Start Download**
   
   **Standard Download:**
   - Select one or more courses
   - Click **"Start Download"**
   - Watch the progress bar and status updates
   
   **Quick Download (Auto-fill and Download):**
   - Check **"Auto-fill courses before download (for first-time users)"**
   - Click **"Start Download"** (even without selecting courses)
   - The application will:
     1. Auto-fill all courses from Moodle
     2. Select all courses automatically
     3. Begin downloading immediately

##### 7. **Monitor Progress**
   - Watch the progress bar for overall completion
   - Check the status bar for current operation
   - The "Stop Download" button allows you to cancel at any time

##### 8. **Find Your Files**
   - Downloaded files are organized in folders by course name
   - ZIP archives are automatically extracted (if desired)
   - Each course has its own folder structure matching Moodle's organization

### Command Line Mode

For automation or scripting purposes:

```bash
python run_cli.py <course_url> <username> <password> <download_folder> [--year-range YEAR]
```

**Example:**
```bash
python run_cli.py "https://moodle.huji.ac.il/course/view.php?id=12345" myuser mypass "C:\Downloads\Moodle" --year-range "2024-25"
```

**Parameters:**
- `course_url`: Full URL to the Moodle course
- `username`: Your Moodle username
- `password`: Your Moodle password
- `download_folder`: Path where files should be saved
- `--year-range`: (Optional) Academic year, defaults to "2024-25"

## Features Explained

### Auto-fill Courses

The auto-fill feature saves time by automatically extracting your course list from Moodle.

**When to use:**
- First time using the application
- New semester with many new courses
- Want to download all enrolled courses

**How it works:**
1. Uses Playwright to log in to Moodle
2. Navigates to your dashboard (`/my/`)
3. Parses the HTML to extract course names and URLs
4. Adds all courses to the list automatically

**Options:**
- **Replace**: Clear existing courses and add only new ones
- **Merge**: Keep existing courses and add new ones (duplicates are handled)

### Credential Storage

When you check "Save Credentials":
- Username and password are stored in your system's secure keyring
- On Windows: Windows Credential Manager
- On macOS: Keychain
- On Linux: Secret Service (GNOME Keyring, KWallet)

**Security:** Credentials are never stored in plain text files.

### Academic Year Support

Different academic years may have different Moodle instances. Select the appropriate year to ensure you're connecting to the right server.

**Example URL structure:**
- 2024-25: `https://moodle2425.cs.huji.ac.il/`
- 2023-24: `https://moodle2324.cs.huji.ac.il/`

### Archive Extraction

By default, downloaded ZIP files are automatically extracted:
- Preserves folder structure
- Original ZIP is kept for reference
- Can be disabled in settings (if implemented)

## Troubleshooting

### Login Issues
- **Wrong credentials**: Double-check username and password
- **Authentication failed**: Try logging in manually via browser first
- **Network error**: Check internet connection

### Download Issues
- **Files not downloading**: Check folder permissions
- **Slow downloads**: Large files may take time; check your internet speed
- **Incomplete downloads**: Use "Stop Download" and try again; already downloaded files are skipped

### Browser Issues
- **Browser not found**: Run `playwright install chromium`
- **Browser crashes**: Try closing other applications to free up memory

### First-Time Setup
- **Playwright not installed**: Run `pip install playwright` then `playwright install chromium`
- **PyQt5 issues**: Try `pip install --upgrade PyQt5`

## Development

### Project Structure

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
├── run_gui.py               # GUI entry point
├── run_cli.py               # CLI entry point
├── requirements.txt         # Dependencies
└── moodle_downloader.spec   # PyInstaller spec
```

### Running Tests

```bash
python -m pytest tests/
```

### Building Windows Executable

```bash
pip install pyinstaller
pyinstaller --noconfirm --clean moodle_downloader.spec
```

The executable will be in `dist/MoodleDownloader/MoodleDownloader.exe`.

## Technology Stack

- **Python 3.8+**: Core language
- **PyQt5**: GUI framework
- **Playwright**: Browser automation for login and navigation
- **BeautifulSoup4**: HTML parsing for course extraction
- **Keyring**: Secure credential storage

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

See [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and updates.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

Distributed under the MIT License. See `LICENSE` for more information.

## Contact

Tomer Bar - tomerbar2021@gmail.com

Project Link: [https://github.com/tomerbar201/moodle-downloader](https://github.com/tomerbar201/moodle-downloader)
