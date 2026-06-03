"""
ShiraAI Launcher — compiled once into ShiraAI.exe via PyInstaller.

On every launch:
  1. Read update_url.txt (next to the EXE) to get the internal update server URL.
  2. Download the latest shira_proxy.py from that server.
  3. Run shira_proxy.py using runpy.run_path() — inside THIS process.
     No subprocess, no system Python needed, no infinite loop.
     All libraries (Flask, etc.) are already bundled in the EXE by PyInstaller.

update_url.txt contains one line: the base URL, e.g. http://10.67.4.32:8081
The launcher fetches: <base_url>/shira_proxy.py
"""

import os
import sys
import runpy
import tempfile
import urllib.request

# ── Configuration ─────────────────────────────────────────────────────────────

UPDATE_URL_FILE = "update_url.txt"
SCRIPT_NAME = "shira_proxy.py"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _exe_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _local_script_path() -> str:
    return os.path.join(_exe_dir(), SCRIPT_NAME)


def _read_update_url() -> str | None:
    path = os.path.join(_exe_dir(), UPDATE_URL_FILE)
    try:
        with open(path, encoding="utf-8") as f:
            url = f.read().strip().rstrip("/")
        return url or None
    except FileNotFoundError:
        print(f"[launcher] {UPDATE_URL_FILE} not found — skipping update.")
    except Exception as exc:
        print(f"[launcher] Could not read {UPDATE_URL_FILE}: {exc}")
    return None


def _download_script() -> bool:
    base_url = _read_update_url()
    if base_url is None:
        return False

    download_url = f"{base_url}/{SCRIPT_NAME}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        print(f"[launcher] Downloading latest {SCRIPT_NAME} from {download_url} ...")
        with opener.open(download_url, timeout=10) as resp:
            content = resp.read()

        dest = _local_script_path()
        tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(dest), suffix=".tmp")
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


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    _download_script()

    script = _local_script_path()
    if not os.path.isfile(script):
        print(
            f"[launcher] ERROR: {script} not found and download failed.\n"
            "Place shira_proxy.py next to ShiraAI.exe and try again."
        )
        input("Press Enter to exit...")
        sys.exit(1)

    print(f"[launcher] Running {script} ...\n")

    # Run shira_proxy.py inside this same process.
    # All bundled libraries (Flask, requests_negotiate_sspi, etc.) are already
    # available — no subprocess or system Python needed.
    runpy.run_path(script, run_name="__main__")


if __name__ == "__main__":
    main()
