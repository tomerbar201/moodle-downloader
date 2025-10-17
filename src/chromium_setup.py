"""Minimal helpers for making sure Playwright Chromium is ready."""
from __future__ import annotations

import os
import subprocess
import sys
from functools import lru_cache
from typing import Tuple

try:
    from playwright.sync_api import Error as PlaywrightError, sync_playwright
except ImportError as exc:  # pragma: no cover - environment issue
    raise RuntimeError("playwright is required to run MoodleDown") from exc

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _browser_store() -> str:
    """Return a stable folder for Playwright browsers and export the env var."""
    existing = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if existing:
        os.makedirs(existing, exist_ok=True)
        return existing
    base_root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    target = os.path.join(base_root, "MoodleDown", "pw-browsers")
    os.makedirs(target, exist_ok=True)
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = target
    return target


def chromium_ready() -> bool:
    """Fast check that Chromium can be launched."""
    _browser_store()
    try:
        with sync_playwright() as playwright_sync:
            browser = playwright_sync.chromium.launch(headless=True)
            browser.close()
        return True
    except PlaywrightError:
        return False
    except Exception:
        return False


def _install_with_driver() -> Tuple[bool, str]:
    """Install Chromium using the bundled Playwright driver (PyInstaller safe)."""
    try:
        from playwright._impl._driver import compute_driver_executable, get_driver_env
    except Exception as exc:  # pragma: no cover - depends on Playwright internals
        return False, f"Could not import Playwright driver helpers: {exc}"

    node_path, cli_path = compute_driver_executable()
    if not os.path.exists(node_path) or not os.path.exists(cli_path):
        return False, "Playwright driver binaries are missing from the bundle"

    cmd = [node_path, cli_path, "install", "chromium"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=get_driver_env(),
            check=False,
            creationflags=_CREATE_NO_WINDOW,
        )
    except Exception as exc:  # pragma: no cover - subprocess failures
        return False, f"Playwright driver launch failed: {exc}"

    if proc.returncode == 0:
        return True, "Chromium downloaded"

    output = (proc.stderr or proc.stdout or "Unknown error").strip()
    return False, f"Playwright driver install failed (code {proc.returncode}): {output}"


def _install_with_cli() -> Tuple[bool, str]:
    """Install Chromium via the standard CLI for non-frozen runs."""
    cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
        creationflags=_CREATE_NO_WINDOW,
    )
    if proc.returncode == 0:
        return True, "Chromium downloaded"
    output = (proc.stderr or proc.stdout or "Unknown error").strip()
    return False, f"Playwright install failed (code {proc.returncode}): {output}"


def install_chromium() -> Tuple[bool, str]:
    """Download Chromium using the best available method."""
    _browser_store()
    if getattr(sys, "frozen", False):
        return _install_with_driver()
    return _install_with_cli()


def ensure_chromium() -> Tuple[bool, str]:
    """Make sure Chromium exists and passes a launch check."""
    if chromium_ready():
        return True, "Chromium already installed"
    success, message = install_chromium()
    if not success:
        return False, message
    if chromium_ready():
        return True, message
    return False, "Chromium installation completed but launch verification failed"


@lru_cache(maxsize=1)
def ensure_chromium_once() -> Tuple[bool, str]:
    """Cached wrapper to avoid repeating expensive checks."""
    return ensure_chromium()
