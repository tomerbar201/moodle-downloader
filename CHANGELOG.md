# Changelog

All notable changes to Moodle Downloader will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- Auto-fill courses feature that automatically extracts enrolled courses from Moodle dashboard
- "Auto-fill Courses" button in GUI for quick course extraction
- "Auto-fill courses before download" option for seamless first-time user experience
- First-time user welcome dialog with auto-fill suggestion
- Academic year selection support (dynamically constructs Moodle URLs based on year)
- `course_extractor.py` module for parsing Moodle dashboard HTML
- Background threading for auto-fill operations (prevents UI freezing)
- Option to replace or merge courses when auto-filling
- Real-time status updates during auto-fill process
- Automatic course selection and download after auto-fill (when triggered from download button)

### Changed
- Reorganized project structure into `src/`, `tests/`, and `docs/` directories
- Updated all imports to use relative imports within packages
- `MoodleBrowser` now accepts `year_range` parameter for flexible URL construction
- `download_course()` function now accepts `year_range` parameter
- Download button logic now enables when auto-fill checkbox is checked (even without course selection)
- Enhanced status bar messages based on selection state and auto-fill mode
- Improved confirmation dialogs for auto-fill and download workflows

### Fixed
- Download button state now properly respects auto-fill checkbox setting
- First-time user experience streamlined with better prompts and automation
- Auto-fill worker properly handles errors and updates UI accordingly

## [Previous Versions]

### Project Reorganization (October 17, 2025)
- Created modular project structure with separate directories
- Split functionality into focused modules:
  - `moodle_browser.py` - Browser automation
  - `content_extractor.py` - HTML parsing
  - `download_handler.py` - File download management
  - `file_operations.py` - File utilities
  - `data_structures.py` - Data classes
  - `unzipper.py` - Archive extraction
- Added entry point scripts: `run_gui.py` and `run_cli.py`
- Updated PyInstaller configuration for new structure

### Initial Features
- Automated Moodle login using Playwright
- Course file download with folder structure preservation
- Automatic ZIP file extraction
- PyQt5 GUI with progress tracking
- Command-line interface support
- Secure credential storage using system keyring
- Cross-platform support (Windows, macOS, Linux)
- Real-time download progress updates
