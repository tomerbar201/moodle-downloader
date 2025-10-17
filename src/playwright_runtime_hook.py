"""Runtime hook to set a persistent Playwright browser path for frozen app.

This prevents Playwright from trying to install browsers inside the temporary
_MEIPASS directory used by PyInstaller and keeps browser binaries in a stable
user-local folder. Browsers are installed on first run by the GUI logic.
"""
import os

def _ensure_env():
	if "PLAYWRIGHT_BROWSERS_PATH" in os.environ:
		return
	base_root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
	target = os.path.join(base_root, "MoodleDown", "pw-browsers")
	os.makedirs(target, exist_ok=True)
	os.environ["PLAYWRIGHT_BROWSERS_PATH"] = target

_ensure_env()
