# Quick Start Guide

Get started with Moodle Downloader in 3 simple steps!

## For Windows Users (Using Executable)

### 1. Download
- Get the latest `.exe` file from [Releases](https://github.com/tomerbar201/moodle-downloader/releases)
- Double-click to run (no installation needed!)

### 2. First Launch
- Enter your Moodle **username** and **password**
- Select **academic year** (e.g., 2024-25)
- Choose **download folder** (Browse button)

### 3. Download Your Courses

**Easy Mode (Recommended):**
1. ✅ Check **"Auto-fill courses before download"**
2. Click **"Start Download"**
3. Click "Yes" when prompted
4. Done! All your courses will download automatically

**Manual Mode:**
1. Click **"Auto-fill Courses"** button
2. Select courses you want to download
3. Click **"Start Download"**

---

## For Python Users (Running from Source)

### 1. Install
```bash
git clone https://github.com/tomerbar201/moodle-downloader.git
cd moodle-downloader
pip install -r requirements.txt
playwright install chromium
```

### 2. Run
```bash
python run_gui.py
```

### 3. Download Your Courses
Same as above (Easy Mode or Manual Mode)

---

## Tips

- ✅ **Save Credentials**: Check this box to avoid re-entering password
- 🔄 **Auto-fill**: Gets all your courses automatically from Moodle
- 📁 **Folder Structure**: Each course downloads to its own folder
- 📦 **ZIP Files**: Automatically extracted after download
- ⏸️ **Stop Anytime**: Use "Stop Download" button to cancel

## Need Help?

See the full [README.md](README.md) for detailed instructions and troubleshooting.
