"""קביעת דיונים והפעלת הקלטות ב-Verbit.

זרימת ההקלטה (כפי שהיא נעשית ידנית ביומן ההזמנות של Verbit):

  1. פותחים את היומן (orders.verbit.co) ולוחצים על הדיון.
  2. בחלון שנפתח: Actions -> Edit transcript. נפתח עורך התמלול (trax.verbit.co).
  3. בעורך מוסיפים את הדוברים בצד ימין (בית הדין, הבעל, האשה, ב"כ...).
  4. לוחצים על כפתור ההקלטה האדום.

חשוב: ההקלטה נעשית דרך המיקרופון של הדפדפן, ולכן הדפדפן חייב להישאר
פתוח כל זמן שההקלטה רצה. החיבור נשמר ברמת המחלקה בין בקשות הדשבורד,
ונסגר רק בעצירת ההקלטה.

שני מימושים מאחורי אותו ממשק, נבחרים לפי verbit.mode ב-config.yaml:

  BrowserVerbit - אוטומציה של ממשק הווב (ברירת המחדל).
  ApiVerbit     - עבודה מול ה-API של Verbit; כבוי עד שיתקבל תיעוד ומפתח.

כמו בשירה, יש מצב כיול:

  python -m agent.verbit --calibrate
      פותח את Verbit, שומר צילום מסך + HTML למילוי ה-selectors.
"""

import argparse
from datetime import date
from pathlib import Path

import requests
from playwright.sync_api import Error as PlaywrightError, sync_playwright

from .browser import launch_persistent_context
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
    # הקלטות פעילות: hearing_id -> (playwright, context). הדפדפן נשאר פתוח
    # כל זמן שההקלטה רצה (המיקרופון מוקלט דרכו) ונסגר רק בעצירה.
    _active: dict = {}

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.vcfg = cfg["verbit"]
        self.sel = self.vcfg["selectors"]

    def can_schedule(self) -> tuple[bool, str]:
        """האם קביעת דיונים כוילה כבר? מחזיר (כן/לא, הסבר)."""
        missing = [k for k in ("new_session_button", "session_name_input", "save_button")
                   if not self.sel.get(k)]
        if missing:
            return False, (
                "קביעת דיונים ב-Verbit עדיין לא כוילה "
                f"(selectors חסרים: {', '.join(missing)})"
            )
        return True, ""

    def _require_selectors(self, *keys: str) -> None:
        missing = [k for k in keys if not self.sel.get(k)]
        if missing:
            raise RuntimeError(
                f"ה-selectors הבאים של Verbit ריקים ב-config.yaml: {', '.join(missing)}. "
                "צריך להשלים אותם בכיול (ראה README)."
            )

    def _launch(self, p, headless: bool = True):
        # Verbit מזדהה עם סיסמה (לא SSO), ולכן ברירת המחדל היא Chromium
        # מבודד - חלון משלו שלא מתנגש ב-Edge הרגיל של המשתמש (הריצה ב-Edge
        # במקביל לדפדפן פתוח גרמה לחלון הסוכן להיסגר מיד). אפשר לעקוף עם
        # verbit.browser_channel ב-config.yaml.
        channel = self.vcfg.get("browser_channel") or "chromium"
        context = launch_persistent_context(
            p,
            self.vcfg["profile_dir"],
            channel=channel,
            headless=headless,
        )
        page = context.pages[0] if context.pages else context.new_page()
        return context, page

    def schedule(self, hearing: Hearing) -> Hearing:
        """יוצר דיון חדש ביומן Verbit עבור הדיון הנתון.

        טרם כויל: צריך לתעד איך נקבע דיון חדש ביומן (New session? Duplicate?).
        עד אז הקריאה נכשלת עם הודעה ברורה ולא מנחשת.
        """
        self._require_selectors("new_session_button", "session_name_input", "save_button")
        with sync_playwright() as p:
            context, page = self._launch(p)
            page.goto(self.vcfg["base_url"], wait_until="domcontentloaded")
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
            hearing.verbit_url = page.url
            context.close()
        hearing.status = "scheduled"
        return hearing

    def _open_editor(self, context, page, hearing: Hearing):
        """מיומן ההזמנות אל עורך התמלול של הדיון (Actions -> Edit transcript)."""
        page.goto(self.vcfg["base_url"], wait_until="domcontentloaded")
        # הדיון מופיע ביומן עם מספר התיק בשם - לוחצים עליו לפתיחת החלון
        page.click(f"text={hearing.case_number}", timeout=30_000)
        page.click(self.sel["actions_button"], timeout=15_000)
        try:
            # Edit transcript נפתח בדרך כלל בטאב חדש
            with context.expect_page(timeout=15_000) as new_page:
                page.click(self.sel["edit_transcript_item"], timeout=15_000)
            editor = new_page.value
        except PlaywrightError:
            editor = page  # נפתח באותו טאב
        editor.wait_for_load_state("domcontentloaded")
        return editor

    def start_recording(self, hearing: Hearing) -> str:
        """פותח את עורך התמלול, מוסיף את הדוברים ומפעיל את ההקלטה.

        מחזיר הודעה למשתמש; הדפדפן נשאר פתוח כל זמן שההקלטה רצה.
        """
        self._require_selectors(
            "actions_button", "edit_transcript_item",
            "speaker_name_input", "add_speaker_button",
        )
        if BrowserVerbit._active:
            raise RuntimeError("כבר יש הקלטה פעילה - עצור אותה לפני שמתחילים חדשה.")

        pw = sync_playwright().start()
        try:
            context, page = self._launch(pw, headless=False)
            editor = self._open_editor(context, page, hearing)

            for speaker in self.vcfg.get("speakers", []):
                editor.fill(self.sel["speaker_name_input"], speaker)
                editor.click(self.sel["add_speaker_button"])

            record_sel = self.sel.get("record_button")
            if record_sel:
                editor.click(record_sel, timeout=15_000)
                message = "ההקלטה החלה."
            else:
                # כפתור ההקלטה טרם כויל - העורך נשאר פתוח להפעלה ידנית
                message = (
                    "העורך נפתח והדוברים נוספו - לחץ על כפתור ההקלטה האדום בעצמך "
                    "(כפתור ההקלטה טרם כויל אוטומטית)."
                )
            BrowserVerbit._active[hearing.id] = (pw, context)
            return message
        except Exception:
            pw.stop()
            raise

    def stop_recording(self, hearing: Hearing) -> str:
        """עוצר את ההקלטה וסוגר את הדפדפן ששמור מההפעלה."""
        held = BrowserVerbit._active.pop(hearing.id, None)
        if held:
            pw, context = held
            try:
                clicked = False
                for pg in reversed([p for p in context.pages if not p.is_closed()]):
                    try:
                        pg.click(self.sel["stop_recording_button"], timeout=10_000)
                        clicked = True
                        break
                    except PlaywrightError:
                        continue
                if not clicked:
                    raise RuntimeError(
                        "לא נמצא כפתור 'Stop recording' בדפדפן הפתוח - "
                        "עצור את ההקלטה ידנית לפני סגירת החלון."
                    )
            finally:
                try:
                    context.close()
                except PlaywrightError:
                    pass
                pw.stop()
            return "ההקלטה נעצרה."

        # אין דפדפן שמור (למשל אחרי הפעלה ידנית או ריסטארט לדשבורד) -
        # נפתח את העורך מחדש ונעצור שם
        self._require_selectors("actions_button", "edit_transcript_item",
                                "stop_recording_button")
        with sync_playwright() as p:
            context, page = self._launch(p, headless=False)
            editor = self._open_editor(context, page, hearing)
            editor.click(self.sel["stop_recording_button"], timeout=30_000)
            context.close()
        return "ההקלטה נעצרה."


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

    def can_schedule(self) -> tuple[bool, str]:
        return True, ""

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

    def start_recording(self, hearing: Hearing) -> str:
        resp = requests.post(
            f"{self.base_url}/sessions/{hearing.verbit_session_id}/start",  # TODO: לאמת
            headers=self._headers(), timeout=30,
        )
        resp.raise_for_status()
        return "ההקלטה החלה."

    def stop_recording(self, hearing: Hearing) -> str:
        resp = requests.post(
            f"{self.base_url}/sessions/{hearing.verbit_session_id}/stop",  # TODO: לאמת
            headers=self._headers(), timeout=30,
        )
        resp.raise_for_status()
        return "ההקלטה נעצרה."


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
        context, page = client._launch(p, headless=False)
        page.goto(client.vcfg["base_url"], wait_until="domcontentloaded")
        print()
        print("נפתח דפדפן על Verbit. התחבר אם צריך, והגע למסך קביעת דיון חדש")
        print("(המסך עם שדות השם/השעה וכפתור השמירה).")
        print("חשוב: אל תסגור את חלון הדפדפן! השאר אותו פתוח על המסך.")
        input("כשהמסך מוצג - חזור לכאן ולחץ Enter... ")

        # שומרים את כל הטאבים הפתוחים (אם מסך "דיון חדש" נפתח בטאב נפרד -
        # כך נלכד גם הוא וגם רשימת ההזמנות עם הכפתור, בפעם אחת).
        open_pages = [pg for pg in context.pages if not pg.is_closed()]
        stamp = date.today().isoformat()
        saved = []
        for i, pg in enumerate(open_pages, 1):
            suffix = f"-{i}" if len(open_pages) > 1 else ""
            png = out_dir / f"verbit-{stamp}{suffix}.png"
            html = out_dir / f"verbit-{stamp}{suffix}.html"
            try:
                pg.screenshot(path=str(png), full_page=True)
                html.write_text(pg.content(), encoding="utf-8")
                saved.append((pg.url, png, html))
            except PlaywrightError:
                continue  # טאב שנסגר תוך כדי - מדלגים עליו

        if not saved:
            raise RuntimeError(
                "חלון הדפדפן נסגר לפני השמירה. הרץ שוב את הכיול, והשאר את "
                "הדפדפן פתוח על המסך עד שמופיעה כאן ההודעה 'נשמר'."
            )

        for url, png, html in saved:
            print(f"\nנשמר: {png}\nנשמר: {html}\n  (מתוך: {url})")
        print("\nשלח את כל הקבצים האלה ל-Claude למילוי ה-selectors ב-config.yaml.")
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
