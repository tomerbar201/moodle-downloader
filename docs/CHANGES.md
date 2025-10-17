# MoodleDown - Auto-fill Courses Feature

## Summary of Changes

This update adds a powerful **Auto-fill Courses** feature that automatically extracts your course list from Moodle, making it much easier for first-time users and for downloading all enrolled courses.

## New Features

### 1. Auto-fill Courses Button
- Located in the course management section
- Automatically logs in to Moodle and extracts all courses from your dashboard
- Options to replace existing courses or merge with them
- Runs in a background thread (doesn't freeze the UI)

### 2. First-Time User Experience
- When you first open MoodleDown with no saved courses, you'll see a welcome dialog
- Option to automatically extract courses instead of manually adding them
- Guides you through credential entry if needed

### 3. Auto-fill Before Download Option
- New checkbox: "Auto-fill courses before download (for first-time users)"
- When enabled and no courses are selected, clicking "Start Download" will:
  - Prompt you to auto-fill courses
  - Extract all courses from Moodle
  - Select all courses automatically
  - Begin downloading them

### 4. Year-Range Support
- `MoodleBrowser` now accepts `year_range` parameter
- Dynamically constructs URLs based on selected academic year (e.g., "2024-25")
- All download operations respect the selected year

## New Files

### `course_extractor.py`
Contains the `extract_courses()` function that:
- Parses Moodle dashboard HTML using BeautifulSoup
- Extracts course names and URLs from the course list section
- Returns a list of dictionaries with 'name' and 'href' keys

### `test_course_extractor.py`
Unit tests for the course extraction functionality:
- Tests normal extraction
- Tests empty HTML handling
- Tests malformed HTML handling

### `AUTO_FILL_FEATURE.md`
Detailed documentation of the auto-fill feature including:
- Usage scenarios
- Technical details
- Workflow diagrams
- Error handling

## Modified Files

### `moodledown_gui.py`
- Added `AutofillSignals` and `AutofillWorker` classes for threaded operation
- Added "Auto-fill Courses" button to UI
- Added "Auto-fill courses before download" checkbox
- New methods: `autofill_courses()`, `autofill_finished()`, `suggest_autofill()`, etc.
- First-time user detection and suggestion dialog
- Auto-download after auto-fill when triggered from "Start Download"

### `moodle_browser.py`
- Constructor now accepts `year_range` parameter (defaults to "2024-25")
- `BASE_URL` is now dynamically set based on `year_range`
- New method: `navigate_to_dashboard()` - navigates to the Moodle dashboard page

### `main.py`
- `download_course()` function now accepts `year_range` parameter
- Passes `year_range` to `MoodleBrowser` initialization

## Usage Examples

### Example 1: First-Time User Quick Start
```
1. Open MoodleDown
2. Click "Yes" on welcome dialog to auto-fill
3. Enter username and password
4. Click "Auto-fill Courses" button
5. Wait for extraction (shows progress)
6. All courses appear in the list
7. Select courses you want to download
8. Click "Start Download"
```

### Example 2: Download Everything Automatically
```
1. Open MoodleDown
2. Check "Auto-fill courses before download" option
3. Enter credentials and download location
4. Click "Start Download"
5. Program auto-fills courses and downloads all of them
```

### Example 3: Add Courses from New Semester
```
1. Change "Academic Year" dropdown to new semester
2. Click "Auto-fill Courses"
3. Choose "No" to merge with existing courses
4. New semester courses are added to the list
```

## Technical Implementation

### Auto-fill Workflow
1. User triggers auto-fill (button or automatically)
2. `AutofillWorker` thread starts
3. Creates `MoodleBrowser` with selected year range
4. Logs in to Moodle with provided credentials
5. Navigates to dashboard (`/my/`)
6. Gets HTML content of the page
7. Calls `extract_courses()` to parse HTML
8. Emits signal with extracted courses
9. Main thread updates course list
10. Optionally triggers download if requested

### Key Components

**AutofillWorker Thread:**
- Runs in background to prevent UI freezing
- Emits status updates during operation
- Emits finished signal with success/failure and course list

**extract_courses() Function:**
- Uses BeautifulSoup to parse HTML
- Looks for `div#my-courses-section`
- Finds all `li.list-group-item` elements
- Extracts `<a>` tags with course names and URLs

**Navigate to Dashboard:**
- New method in `MoodleBrowser`
- Goes to `{BASE_URL}/my/` after login
- Verifies navigation success

## Error Handling

- **Login failure:** Clears password, shows error dialog
- **No courses found:** Informs user without modifying existing list
- **Network errors:** Shows detailed error message
- **Duplicate courses:** Skips duplicates when merging
- **Browser setup failure:** Guides user to install Chromium

## Dependencies

All required dependencies are already in `requirements.txt`:
- `beautifulsoup4~=4.13.3` - HTML parsing
- `PyQt5~=5.15.11` - GUI framework
- `playwright~=1.51.0` - Browser automation

## Testing

Run the test suite:
```bash
python test_course_extractor.py
```

All tests should pass:
- Course extraction from valid HTML
- Empty HTML handling
- Malformed HTML handling

## Benefits

1. **Time-saving**: No manual URL copying needed
2. **User-friendly**: Much easier for first-time setup
3. **Complete**: Gets ALL enrolled courses automatically
4. **Flexible**: Can replace or merge with existing courses
5. **Year-aware**: Works with any academic year selection
6. **Non-blocking**: UI remains responsive during extraction
7. **Error-tolerant**: Handles failures gracefully

## Backward Compatibility

All existing functionality remains unchanged:
- Manual course addition still works
- Existing course lists are preserved
- Default year_range is "2024-25" (same as before)
- All download features work as before

## Future Enhancements

Potential improvements:
- Course filtering (by department, level, etc.)
- Selective course selection after auto-fill
- Save/load course list presets
- Export course list to file
- Import course list from file
