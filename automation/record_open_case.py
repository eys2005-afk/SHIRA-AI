#!/usr/bin/env python3
"""
מקליט פעולות בשירה (Shira) בעזרת Playwright Codegen.

פותח דפדפן מבוקר מול דף פתיחת תיק בשירה, ומתעד כל קליק/הקלדה כקוד
Python, כדי שאפשר יהיה להפוך אותו לאוטומציה (ראו open_case_automation.py).

הרצה (אחרי יצירת config.json לפי config.example.json):
    python record_open_case.py
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "config.json"
RECORDINGS_DIR = ROOT / "recordings"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit(
            f"לא נמצא קובץ הגדרות: {CONFIG_PATH}\n"
            "העתיקו את config.example.json לקובץ בשם config.json ומלאו בו את הפרטים."
        )
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def main() -> None:
    config = load_config()
    RECORDINGS_DIR.mkdir(exist_ok=True)

    target_url = config["shira_base_url"].rstrip("/") + config["open_case_path"]
    channel = config.get("browser_channel", "msedge")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = RECORDINGS_DIR / f"open_case_{timestamp}.py"

    cmd = [
        sys.executable, "-m", "playwright", "codegen",
        "--target", "python",
        "--channel", channel,
        "-o", str(output_file),
        target_url,
    ]

    print("=" * 60)
    print("מקליט שירה - פתיחת תיק")
    print("=" * 60)
    print(f"כתובת יעד : {target_url}")
    print(f"דפדפן     : {channel}")
    print(f"קובץ פלט  : {output_file}")
    print()
    print("בצעו עכשיו בדפדפן שנפתח את כל תהליך פתיחת התיק, צעד אחר צעד.")
    print("השתמשו אך ורק בנתוני בדיקה/דמה - אסור להקליד ת\"ז או שם אמיתיים!")
    print("בסיום, סגרו את חלון הדפדפן כדי לשמור את ההקלטה.")
    print("=" * 60)

    subprocess.run(cmd, cwd=ROOT)

    if output_file.exists() and output_file.stat().st_size > 0:
        print(f"\nההקלטה נשמרה ב-: {output_file}")
        print("השלב הבא: העבירו את הסלקטורים הרלוונטיים אל open_case_automation.py")
    else:
        print("\nלא נוצר קובץ הקלטה. ייתכן שהדפדפן נסגר לפני שבוצעה פעולה כלשהי.")


if __name__ == "__main__":
    main()
