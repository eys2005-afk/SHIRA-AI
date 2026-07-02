"""הדשבורד: מסך אחד פשוט להפעלת הקלטות בלי להיכנס ל-Verbit.

    python -m dashboard.app   (או scripts/run_dashboard.bat)

מציג את דיוני היום (מתוך קובץ היום שריצת הבוקר יצרה), עם כפתור גדול
"התחל הקלטה" ליד כל דיון - כי הדיונים לא תמיד מתחילים בשעה שנקבעה,
וההפעלה בפועל נשארת בשליטתך.
"""

import sys
import threading
from pathlib import Path

from flask import Flask, jsonify, render_template

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.config import load_config
from agent.morning import run_morning
from agent.store import DayStore
from agent.verbit import get_client

app = Flask(__name__)

# הפעלת/עצירת הקלטה דרך דפדפן אורכת כמה שניות - נעילה אחת מונעת שתי
# אוטומציות דפדפן מקבילות שידרכו זו על זו.
_browser_lock = threading.Lock()


def _store() -> DayStore:
    cfg = load_config()
    return DayStore(cfg["storage"]["data_dir"])


@app.route("/")
def index():
    store = _store()
    return render_template("index.html", day=store.day)


@app.route("/api/hearings")
def api_hearings():
    return jsonify([h.to_dict() for h in _store().load()])


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    with _browser_lock:
        try:
            run_morning()
            return jsonify({"ok": True})
        except Exception as e:  # noqa: BLE001
            return jsonify({"ok": False, "error": str(e)}), 500


def _recording_action(hearing_id: str, action: str):
    cfg = load_config()
    store = DayStore(cfg["storage"]["data_dir"])
    hearing = next((h for h in store.load() if h.id == hearing_id), None)
    if hearing is None:
        return jsonify({"ok": False, "error": "הדיון לא נמצא"}), 404

    with _browser_lock:
        try:
            client = get_client(cfg)
            if action == "start":
                message = client.start_recording(hearing)
                store.update(hearing_id, status="recording", error="")
            else:
                message = client.stop_recording(hearing)
                store.update(hearing_id, status="done", error="")
            return jsonify({"ok": True, "message": message})
        except Exception as e:  # noqa: BLE001
            store.update(hearing_id, status="error", error=str(e))
            return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/start/<hearing_id>", methods=["POST"])
def api_start(hearing_id):
    return _recording_action(hearing_id, "start")


@app.route("/api/stop/<hearing_id>", methods=["POST"])
def api_stop(hearing_id):
    return _recording_action(hearing_id, "stop")


if __name__ == "__main__":
    cfg = load_config()
    dash = cfg.get("dashboard", {})
    app.run(host=dash.get("host", "127.0.0.1"), port=dash.get("port", 8765))
