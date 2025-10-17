# Auto-fill Courses Feature

## Overview
The auto-fill feature allows users to automatically extract their course list from Moodle instead of manually adding each course. This is especially useful for first-time users or when you want to download all your enrolled courses.

## How It Works

### 1. Manual Auto-fill
You can manually trigger the auto-fill feature at any time by:
1. Entering your Moodle credentials (username and password)
2. Clicking the **"Auto-fill Courses"** button in the course management section
3. Choosing whether to replace your existing course list or merge with it
4. The program will:
   - Log in to Moodle using your credentials
   - Navigate to your dashboard
   - Extract all courses from the dashboard HTML
   - Add them to your course list automatically

### 2. First-Time User Prompt
When you open MoodleDown for the first time (no saved courses), the program will:
- Display a welcome dialog
- Offer to automatically extract your courses
- If you accept and have credentials entered, it will run the auto-fill process
- If credentials are missing, it will prompt you to enter them first

### 3. Auto-fill Before Download
There's a checkbox option: **"Auto-fill courses before download (for first-time users)"**

When this is enabled:
- If you click "Start Download" with no courses selected
- The program will prompt you to auto-fill courses first
- After successful auto-fill, it will automatically:
  - Select all extracted courses
  - Begin downloading them

## Technical Details

### New Components

#### 1. `course_extractor.py`
- Contains the `extract_courses()` function
- Parses Moodle dashboard HTML using BeautifulSoup
- Extracts course names and URLs from the `#my-courses-section` div

#### 2. Updated `MoodleBrowser` class
- Now accepts `year_range` parameter (e.g., "2024-25")
- Dynamically constructs BASE_URL based on year range
- New method: `navigate_to_dashboard()` - navigates to the `/my/` page after login

#### 3. `AutofillWorker` Thread
- Runs auto-fill operation in background (doesn't freeze UI)
- Handles login, navigation, and course extraction
- Emits signals for status updates and completion

#### 4. GUI Updates
- New "Auto-fill Courses" button
- New checkbox: "Auto-fill courses before download"
- First-time user detection and suggestion
- Threaded operation with status updates

### Workflow

1. **User clicks "Auto-fill Courses"**
   ↓
2. **Credentials validation**
   ↓
3. **Ask: Replace or Merge courses?**
   ↓
4. **AutofillWorker starts**
   - Setup browser with selected year range
   - Login to Moodle
   - Navigate to dashboard (/my/)
   - Get page HTML content
   - Parse HTML with BeautifulSoup
   - Extract courses from `#my-courses-section`
   ↓
5. **Courses added to list**
   ↓
6. **Optional: Auto-start download** (if "Auto-fill before download" was triggered)

## Benefits

1. **Time-saving**: No need to manually copy-paste course URLs
2. **First-time user friendly**: Makes setup much easier for new users
3. **Complete coverage**: Gets ALL enrolled courses automatically
4. **Year-aware**: Works with the selected academic year
5. **Non-destructive**: Can merge with existing courses instead of replacing

## Usage Example

### Scenario 1: First-time user
1. Open MoodleDown
2. See welcome message → Click "Yes" to auto-fill
3. Enter username and password if not already filled
4. Click "Auto-fill Courses"
5. Wait for extraction
6. All courses appear in the list
7. Select which ones to download
8. Click "Start Download"

### Scenario 2: Existing user wants to add new semester courses
1. Open MoodleDown
2. Change "Academic Year" to new semester
3. Click "Auto-fill Courses"
4. Choose "No" to merge with existing courses
5. New courses are added without removing old ones

### Scenario 3: Quick download everything
1. Enable "Auto-fill courses before download" checkbox
2. Enter credentials
3. Click "Start Download"
4. Program auto-fills courses, selects all, and starts downloading

## Error Handling

- **Login failure**: Clears password, prompts for credentials
- **No courses found**: Informs user, doesn't modify existing list
- **Network errors**: Shows error message with details
- **Duplicate courses**: Skips duplicates when merging

## Requirements

- BeautifulSoup4 (already in requirements.txt)
- Working internet connection
- Valid Moodle credentials
- Playwright Chromium browser installed
