"""קביעת דיונים והפעלת הקלטות ב-Verbit.

שני מימושים מאחורי אותו ממשק, נבחרים לפי verbit.mode ב-config.yaml:

  BrowserVerbit - אוטומציה של ממשק הווב של Verbit (ברירת המחדל).
                  משתמש בפרופיל דפדפן קבוע כך שההתחברות נשמרת בין ריצות.
  ApiVerbit     - עבודה מול ה-API של Verbit. ניסיון אינטגרציה קודם (במייל)
                  לא צלח, ולכן זה כבוי עד שנאמת מול Verbit את הכתובות
                  והפורמט; המבנה כאן מוכן כדי שהמעבר יהיה החלפת mode בלבד.

כמו בשירה, יש מצב כיול:

  python -m agent.verbit --calibrate
      פותח את Verbit, שומר צילום מסך + HTML למילוי ה-selectors.
"""

import argparse
from datetime import date
from pathlib import Path

import requests
from playwright.sync_api import Error as PlaywrightError, sync_playwright

from .config import load_config
from .models import Hearing


def session_name_for(hearing: Hearing) -> str:
    """שם הדיון כפי שיופיע ב-Verbit - מספר תיק, כותרת ושעה."""
    parts = [hearing.case_number]
    if hearing.case_title:
        parts.append(hearing.case_title)
    parts.append(hearing.time)
    return " - ".join(p for p in parts if p)


def participants_for(hearing: Hearing, cfg: dict) -> list[str]:
    """הגורמים לדיון: הקבועים מההגדרות + הצדדים שנקראו מהיומן של אותו יום."""
    fixed = [
        f"{p.get('name', '')} ({p.get('role', '')})".replace(" ()", "").strip()
        for p in cfg.get("fixed_participants", [])
        if p.get("name")
    ]
    return fixed + hearing.parties


class BrowserVerbit:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.vcfg = cfg["verbit"]
        self.sel = self.vcfg["selectors"]

    def _require_selectors(self, *keys: str) -> None:
        missing = [k for k in keys if not self.sel.get(k)]
        if missing:
            raise RuntimeError(
                f"ה-selectors הבאים של Verbit ריקים ב-config.yaml: {', '.join(missing)}. "
                "הרץ: python -m agent.verbit --calibrate (ראה README)."
            )

    def _open(self, p, url: str | None = None, headless: bool = True):
        context = p.chromium.launch_persistent_context(
            self.vcfg["profile_dir"],
            channel=self.cfg["shira"].get("browser_channel", "msedge"),
            headless=headless,
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url or self.vcfg["base_url"], wait_until="domcontentloaded")
        return context, page

    def schedule(self, hearing: Hearing) -> Hearing:
        """יוצר דיון חדש ב-Verbit עבור הדיון הנתון."""
        self._require_selectors("new_session_button", "session_name_input", "save_button")
        with sync_playwright() as p:
            context, page = self._open(p)
            page.click(self.sel["new_session_button"])
            page.fill(self.sel["session_name_input"], session_name_for(hearing))
            if self.sel.get("session_time_input"):
                page.fill(self.sel["session_time_input"], hearing.time)
            if self.sel.get("participant_input"):
                for participant in participants_for(hearing, self.cfg):
                    page.fill(self.sel["participant_input"], participant)
                    page.keyboard.press("Enter")
            page.click(self.sel["save_button"])
            page.wait_for_load_state("networkidle")
            # הכתובת אחרי השמירה היא בדרך כלל דף הדיון עצמו - נשמרת כדי
            # שכפתור ההפעלה בדשבורד יגיע ישירות לדיון הנכון.
            hearing.verbit_url = page.url
            context.close()
        hearing.status = "scheduled"
        return hearing

    def _click_in_session(self, hearing: Hearing, selector_key: str) -> None:
        self._require_selectors(selector_key)
        if not hearing.verbit_url:
            raise RuntimeError("לדיון אין קישור Verbit שמור - קבע אותו קודם (רענון בוקר).")
        with sync_playwright() as p:
            context, page = self._open(p, url=hearing.verbit_url)
            page.click(self.sel[selector_key], timeout=30_000)
            context.close()

    def start_recording(self, hearing: Hearing) -> None:
        self._click_in_session(hearing, "start_recording_button")

    def stop_recording(self, hearing: Hearing) -> None:
        self._click_in_session(hearing, "stop_recording_button")


class ApiVerbit:
    """שלד לעבודה מול ה-API של Verbit.

    הנתיבים (paths) כאן הם השערה סבירה בלבד ומסומנים לאימות מול התיעוד
    שיתקבל מ-Verbit; עד אז mode צריך להישאר browser.
    """

    def __init__(self, cfg: dict):
        api = cfg["verbit"]["api"]
        self.base_url = (api.get("base_url") or "").rstrip("/")
        self.token = api.get("token", "")
        if not self.base_url or not self.token:
            raise RuntimeError(
                "מצב api דורש verbit.api.base_url ב-config.yaml ו-VERBIT_API_TOKEN ב-.env."
            )
        self.cfg = cfg

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def schedule(self, hearing: Hearing) -> Hearing:
        resp = requests.post(
            f"{self.base_url}/sessions",  # TODO: לאמת נתיב מול תיעוד Verbit
            headers=self._headers(),
            json={
                "name": session_name_for(hearing),
                "scheduled_at": f"{hearing.date}T{hearing.time}:00",
                "participants": participants_for(hearing, self.cfg),
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        hearing.verbit_session_id = str(data.get("id", ""))
        hearing.verbit_url = data.get("url", "")
        hearing.status = "scheduled"
        return hearing

    def start_recording(self, hearing: Hearing) -> None:
        resp = requests.post(
            f"{self.base_url}/sessions/{hearing.verbit_session_id}/start",  # TODO: לאמת
            headers=self._headers(), timeout=30,
        )
        resp.raise_for_status()

    def stop_recording(self, hearing: Hearing) -> None:
        resp = requests.post(
            f"{self.base_url}/sessions/{hearing.verbit_session_id}/stop",  # TODO: לאמת
            headers=self._headers(), timeout=30,
        )
        resp.raise_for_status()


def get_client(cfg: dict):
    mode = cfg["verbit"].get("mode", "browser")
    if mode == "api":
        return ApiVerbit(cfg)
    return BrowserVerbit(cfg)


def calibrate(cfg: dict) -> None:
    out_dir = Path(cfg["storage"]["data_dir"]) / "calibration"
    out_dir.mkdir(parents=True, exist_ok=True)
    client = BrowserVerbit(cfg)
    with sync_playwright() as p:
        context, page = client._open(p, headless=False)
        print()
        print("נפתח דפדפן על Verbit. התחבר אם צריך, ופתח את המסך שבו קובעים דיון חדש.")
        print("חשוב: אל תסגור את חלון הדפדפן! השאר אותו פתוח על המסך הזה.")
        input("כשהמסך מוצג - חזור לכאן ולחץ Enter... ")
        try:
            # אם המשתמש פתח טאב חדש וסגר את המקורי - ניקח את הטאב האחרון שפתוח
            open_pages = [pg for pg in context.pages if not pg.is_closed()]
            if not open_pages:
                raise PlaywrightError("no open pages")
            page = open_pages[-1]

            stamp = date.today().isoformat()
            png = out_dir / f"verbit-{stamp}.png"
            html = out_dir / f"verbit-{stamp}.html"
            page.screenshot(path=str(png), full_page=True)
            html.write_text(page.content(), encoding="utf-8")
        except PlaywrightError:
            raise RuntimeError(
                "חלון הדפדפן נסגר לפני השמירה. הרץ שוב את הכיול, והשאר את "
                "הדפדפן פתוח על המסך עד שמופיעה כאן ההודעה 'נשמר'."
            ) from None
        print(f"\nנשמר: {png}\nנשמר: {html}")
        print("שלח את הקבצים ל-Claude למילוי ה-selectors של Verbit ב-config.yaml.")
        context.close()


if __name__ == "__main__":
    import sys

    parser = argparse.ArgumentParser(description="כיול מסכי Verbit")
    parser.add_argument("--calibrate", action="store_true")
    args = parser.parse_args()
    if args.calibrate:
        try:
            calibrate(load_config())
        except RuntimeError as e:
            print(f"שגיאה: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
