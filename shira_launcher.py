"""
ShiraAI Launcher — compiled once into ShiraAI.exe via PyInstaller.

On every launch:
  1. Download the latest shira_proxy.py from GitHub (through corporate proxy).
  2. Save it next to the EXE (or in %TEMP% as fallback).
  3. Find a real system Python interpreter (never sys.executable, which IS this EXE).
  4. Run shira_proxy.py with that interpreter and wait for it to exit.

No Python installation is needed on the machine for the EXE itself, but Python
must be installed so Flask/requests/etc. are available for the actual app.
If no system Python is found the EXE falls back to running the locally-saved
copy without updating, so the last-known-good version still works.
"""

import os
import sys
import subprocess
import tempfile
import urllib.request
import urllib.error

# ── Configuration ────────────────────────────────────────────────────────────

GITHUB_RAW_URL = (
    "https://raw.githubusercontent.com/eys2005-afk/SHIRA-AI/master/shira_proxy.py"
)
CORPORATE_PROXY = "http://192.168.174.80:8080"
SCRIPT_NAME = "shira_proxy.py"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _exe_dir() -> str:
    """Directory that contains the running EXE (or script during dev)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _local_script_path() -> str:
    return os.path.join(_exe_dir(), SCRIPT_NAME)


def _download_script() -> bool:
    """
    Try to download the latest shira_proxy.py via the corporate proxy.
    Returns True on success, False on any failure.
    """
    proxy_handler = urllib.request.ProxyHandler(
        {"http": CORPORATE_PROXY, "https": CORPORATE_PROXY}
    )
    opener = urllib.request.build_opener(proxy_handler)
    try:
        print(f"[launcher] Downloading latest {SCRIPT_NAME} …")
        with opener.open(GITHUB_RAW_URL, timeout=15) as resp:
            content = resp.read()

        dest = _local_script_path()
        # Write atomically: temp file → rename
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=os.path.dirname(dest), suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "wb") as f:
                f.write(content)
            os.replace(tmp_path, dest)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        print(f"[launcher] Updated {SCRIPT_NAME} ({len(content):,} bytes).")
        return True

    except Exception as exc:
        print(f"[launcher] Update skipped ({exc}). Using local copy.")
        return False


def _find_system_python() -> str | None:
    """
    Return the path to a real Python interpreter that is NOT this EXE.

    Search order:
      1. PYTHON / PYTHONEXE environment variables (let admins override).
      2. 'python' / 'python3' on PATH — but skip if it resolves to our EXE.
      3. Common Windows install locations.
    """
    our_exe = os.path.abspath(sys.executable).lower()

    candidates: list[str] = []

    # Env-var overrides
    for var in ("PYTHON", "PYTHONEXE"):
        val = os.environ.get(var)
        if val:
            candidates.append(val)

    # PATH lookup
    import shutil
    for name in ("python", "python3", "python.exe", "python3.exe"):
        found = shutil.which(name)
        if found:
            candidates.append(found)

    # Hard-coded common locations (Windows)
    for base in (
        r"C:\Python313",
        r"C:\Python312",
        r"C:\Python311",
        r"C:\Python310",
        r"C:\Python39",
        r"C:\Python38",
    ):
        candidates.append(os.path.join(base, "python.exe"))

    # User-local installs
    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        import glob
        for hit in sorted(
            glob.glob(os.path.join(local_app, "Programs", "Python", "Python3*", "python.exe")),
            reverse=True,  # newest version first
        ):
            candidates.append(hit)

    for path in candidates:
        abs_path = os.path.abspath(path).lower()
        if abs_path == our_exe:
            continue  # skip ourselves — this caused the infinite loop
        if os.path.isfile(path):
            return path

    return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    script = _local_script_path()

    # Step 1: try to pull the latest version
    _download_script()

    # Step 2: make sure we have something to run
    if not os.path.isfile(script):
        print(
            f"[launcher] ERROR: {script} not found and download failed.\n"
            "Place shira_proxy.py next to ShiraAI.exe and try again."
        )
        input("Press Enter to exit…")
        sys.exit(1)

    # Step 3: locate a real Python
    python = _find_system_python()
    if python is None:
        print(
            "[launcher] ERROR: No Python interpreter found on this machine.\n"
            "Install Python 3.10+ from python.org and make sure it is on PATH."
        )
        input("Press Enter to exit…")
        sys.exit(1)

    print(f"[launcher] Using Python: {python}")
    print(f"[launcher] Launching {script} …\n")

    # Step 4: run the app; this process just waits for it to finish
    result = subprocess.run([python, script])
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
