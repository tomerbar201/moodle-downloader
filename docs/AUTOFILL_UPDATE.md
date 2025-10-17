# Auto-fill Before Download - Feature Update

## What Changed

The "Auto-fill courses before download" checkbox now works exactly as intended:

### Before This Update
- Download button was **disabled** when no courses were selected
- User had to manually select courses before clicking "Start Download"
- The checkbox didn't actually enable downloading without selection

### After This Update
- Download button is **enabled** when the checkbox is checked, even with no courses selected
- User can click "Start Download" without selecting any courses
- The program will automatically:
  1. Ask for confirmation
  2. Auto-fill courses from Moodle
  3. Select all extracted courses
  4. Begin downloading them

## How It Works Now

### Option 1: Manual Course Selection (Traditional)
1. Uncheck "Auto-fill courses before download"
2. Select courses from the list
3. Click "Start Download"
4. Downloads selected courses

### Option 2: Auto-fill and Download (New)
1. Check "Auto-fill courses before download"
2. **Don't select any courses** (or select some if you want)
3. Click "Start Download"
4. If no courses selected:
   - Confirmation dialog appears
   - Auto-fills from Moodle
   - Selects all courses
   - Downloads everything
5. If courses already selected:
   - Just downloads the selected courses (normal behavior)

## Technical Changes

### 1. Updated `update_selection()` Method
```python
# Enable download button if:
# 1. There are selected courses, OR
# 2. Auto-fill before download is enabled
autofill_enabled = self.autofill_and_download_cb.isChecked()
self.download_btn.setEnabled((count > 0 or autofill_enabled) and not is_downloading and ready)
```

### 2. Added State Change Listener
The checkbox now triggers `update_selection()` when toggled:
```python
self.autofill_and_download_cb.stateChanged.connect(self.update_selection)
```

### 3. Enhanced Status Messages
- When courses selected: "Selected X course(s)"
- When auto-fill enabled, no selection: "Ready to auto-fill and download"
- Otherwise: "Ready"

### 4. Improved Download Flow
- Better confirmation dialog explaining the 3-step process
- Automatically sets `autofill_replace_existing = True` for first-time users
- Bypasses the replace/merge dialog when triggered from download button
- Only shows auto-fill prompt when no courses are selected

### 5. Created Helper Method
`_start_autofill_worker()` - Internal method to start autofill without user prompts

## User Experience

### First-Time User Scenario
```
1. Open MoodleDown (no courses in list)
2. Enter username and password
3. Check "Auto-fill courses before download"
4. Click "Start Download" ← Works even with empty selection!
5. See confirmation: "Continue?"
6. Click "Yes"
7. Watch as it:
   - Logs in to Moodle
   - Extracts all courses
   - Selects all courses
   - Downloads everything
```

### Status Bar Updates
The status bar now provides better feedback:
- Shows "Ready to auto-fill and download" when checkbox is checked
- Shows "Selected X courses" when courses are manually selected
- Updates immediately when checkbox is toggled

## Benefits

1. **True one-click experience** - Click download without any preparation
2. **Clear expectations** - Confirmation dialog explains what will happen
3. **Smart behavior** - Only auto-fills when needed (no courses selected)
4. **No confusion** - Button is always enabled when checkbox is checked
5. **Better feedback** - Status bar clearly indicates the current mode

## Edge Cases Handled

- ✓ Checkbox enabled, courses selected → Downloads selected courses normally
- ✓ Checkbox enabled, no courses → Auto-fills then downloads all
- ✓ Checkbox disabled, no courses → Button disabled, prompts to select
- ✓ Checkbox disabled, courses selected → Downloads selected courses
- ✓ Toggling checkbox updates button state immediately
- ✓ Status bar reflects current mode at all times
