"""ריצת הבוקר: שירה -> Verbit -> קובץ היום.

    python -m agent.morning

1. קורא מהיומן בשירה את דיוני היום.
2. ממזג עם המצב השמור (דיונים שכבר נקבעו לא נקבעים שוב).
3. קובע ב-Verbit כל דיון שעדיין pending, עם הגורמים הקבועים + צדדי היומן.
4. שומר הכול ב-data/hearings-YYYY-MM-DD.json - זה מה שהדשבורד מציג.

מיועדת לרוץ אוטומטית כל בוקר (Windows Task Scheduler - ראה README),
וגם ידנית מכפתור "רענון" בדשבורד.
"""

import sys
import traceback

from .config import load_config
from .shira import fetch_today
from .store import DayStore
from .verbit import get_client


def run_morning(headless: bool = True) -> list:
    cfg = load_config()
    store = DayStore(cfg["storage"]["data_dir"])

    print(f"[{store.day}] קורא את יומן הדיונים משירה...")
    hearings = store.merge(fetch_today(cfg, headless=headless))
    print(f"נמצאו {len(hearings)} דיונים להיום.")

    client = get_client(cfg)
    for h in hearings:
        if h.status != "pending":
            continue
        try:
            print(f"קובע ב-Verbit: {h.time} {h.case_number} ...", end=" ")
            client.schedule(h)
            store.update(h.id, status=h.status, verbit_session_id=h.verbit_session_id,
                         verbit_url=h.verbit_url, error="")
            print("נקבע.")
        except Exception as e:  # noqa: BLE001 - דיון אחד שנכשל לא מפיל את השאר
            store.update(h.id, status="error", error=str(e))
            print(f"נכשל: {e}")
            traceback.print_exc(file=sys.stderr)

    result = store.load()
    scheduled = sum(1 for h in result if h.status == "scheduled")
    errors = sum(1 for h in result if h.status == "error")
    print(f"סיכום: {scheduled} נקבעו, {errors} נכשלו, מתוך {len(result)} דיונים.")
    return result


if __name__ == "__main__":
    run_morning(headless="--headed" not in sys.argv)
