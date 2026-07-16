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
from datetime import date, datetime, timedelta
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


def _verbit_date(iso_date: str) -> str:
    """YYYY-MM-DD -> 'Mon DD, YY' (הפורמט שמוצג בשדה Date של Verbit)."""
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%b %d, %y")
    except ValueError:
        return iso_date


def _time_candidates(hhmm: str) -> list[str]:
    """פורמטים אפשריים של שעה. Verbit משתמש ב-'09:00am' (12 שעות, am/pm קטן,
    בלי רווח, שעה בת שתי ספרות); שאר הפורמטים הם נפילות ביטחון."""
    try:
        h24, m = (int(x) for x in hhmm.split(":"))
    except (ValueError, AttributeError):
        return [hhmm]
    h12 = h24 % 12 or 12
    lo = "am" if h24 < 12 else "pm"
    return [
        f"{h12:02d}:{m:02d}{lo}",       # 09:00am  <- הפורמט של Verbit
        f"{h12}:{m:02d}{lo}",           # 9:00am
        f"{h12:02d}:{m:02d} {lo.upper()}",  # 09:00 AM
        f"{h24:02d}:{m:02d}",           # 09:00
    ]


def _end_time_for(hearing: Hearing, sched: dict) -> str:
    """שעת הסיום לטופס: מהיומן אם קיימת, אחרת התחלה + משך ברירת מחדל."""
    if hearing.end_time:
        return hearing.end_time
    try:
        start = datetime.strptime(hearing.time, "%H:%M")
        minutes = int(sched.get("default_duration_minutes", 60))
        return (start + timedelta(minutes=minutes)).strftime("%H:%M")
    except (ValueError, TypeError):
        return hearing.time


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
        """האם קביעה אוטומטית ב-Verbit מופעלת? מחזיר (כן/לא, הסבר)."""
        if not self.vcfg.get("scheduling", {}).get("enabled", False):
            return False, "קביעה אוטומטית ב-Verbit כבויה (verbit.scheduling.enabled=false)"
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

    def schedule(self, hearing: Hearing, headless: bool = False) -> Hearing:
        """קובע דיון חדש בטופס 'New live order' של Verbit.

        פותח את "Place new order", ממלא את שדות החובה (שם הדיון, שפת קלט/פלט,
        תאריך + שעות ההתחלה והסיום) ולוחץ "Place session". רץ בדפדפן גלוי
        כברירת מחדל - כדי שאפשר לצפות ולהשלים כניסה בפעם הראשונה.

        אם שדה כלשהו לא נמצא, נשמרים צילום מסך ו-HTML של הטופס תחת
        data/calibration/schedule-error-*, והשגיאה מפנה אליהם - כדי שאפשר
        יהיה לתקן את ה-selector המדויק בלי לנחש.
        """
        sched = self.vcfg.get("scheduling", {})
        with sync_playwright() as p:
            context, page = self._launch(p, headless=headless)
            try:
                page.goto(self.vcfg["base_url"], wait_until="domcontentloaded")
                self._require_login(page)
                self._goto_live_bookings(page)

                self._step(page, "פתיחת Place new order", lambda:
                    page.get_by_role("button", name="Place new order").click(timeout=30_000))
                page.locator("input[data-is-editable-input='true']").first.wait_for(
                    state="attached", timeout=20_000)

                # שם הדיון - רכיב verbit-editable: input מוסתר מאחורי preview שלוחצים עליו
                self._step(page, "שם הדיון (Session name)", lambda:
                    self._fill_session_name(page, session_name_for(hearing)))

                # מקור אודיו (Audio source) - שדה react-select חובה
                self._step(page, "מקור אודיו (Audio source)", lambda:
                    self._select_react(page, "select media source",
                                       sched.get("media_source", "Verbit Connect (On-Site)")))

                # שפות - react-select (aria-label האמיתי שונה מהתווית המוצגת)
                self._step(page, "שפת קלט (Input language)", lambda:
                    self._select_react(page, "select audio language",
                                       sched.get("input_language", "Hebrew")))
                self._step(page, "שפת פלט (Output language)", lambda:
                    self._select_react(page, "select captions language",
                                       sched.get("output_language", "Hebrew")))

                # "Schedule for later" הוא ברירת המחדל; לוחצים ליתר ביטחון
                try:
                    page.get_by_text("Schedule for later", exact=False).first.click(timeout=4_000)
                except PlaywrightError:
                    pass

                self._step(page, "תאריך (Date)", lambda:
                    self._pick_date(page, hearing.date))
                self._step(page, "שעת התחלה (Start time)", lambda:
                    self._select_time(page, "pick order start time", hearing.time))
                self._step(page, "שעת סיום (End time)", lambda:
                    self._select_time(page, "pick order end time", _end_time_for(hearing, sched)))

                if sched.get("add_parties_as_terms", True):
                    terms = ", ".join(participants_for(hearing, self.cfg))
                    if terms:
                        try:
                            page.locator("textarea[name='input.glossary']").first.fill(
                                terms, timeout=5_000)
                        except PlaywrightError:
                            pass  # שדה עזר בלבד - לא מפילים על זה את הקביעה

                self._step(page, "שליחה (Place session)", lambda:
                    page.get_by_role("button", name="Place session").click(timeout=15_000))

                # ודא שההזמנה באמת נוצרה - אחרת נשארים בטופס עם שגיאות ולידציה
                page.wait_for_timeout(4_000)
                if self._still_on_create_form(page):
                    invalid = self._invalid_fields(page)
                    path = self._debug_dump(page, "after-submit-not-created")
                    raise RuntimeError(
                        "נלחץ 'Place session' אך ההזמנה לא נוצרה - נשארנו בטופס. "
                        f"שדות עם שגיאה: {invalid or '(לא זוהו)'} . צילום/HTML: {path}"
                    )
                hearing.verbit_url = page.url
            finally:
                context.close()
        hearing.status = "scheduled"
        return hearing

    def _require_login(self, page) -> None:
        """מוודא שמחוברים ל-Verbit; אחרת עוצר עם הודעה ברורה להריץ --login."""
        try:
            page.get_by_role("button", name="Place new order").wait_for(timeout=8_000)
            return  # מחוברים - הכפתור קיים
        except PlaywrightError:
            pass
        try:
            page.get_by_role("link", name="Live Bookings").wait_for(timeout=5_000)
            return  # ניווט ראשי מוצג => מחוברים
        except PlaywrightError:
            raise RuntimeError(
                "לא מחוברים ל-Verbit (מוצג מסך התחברות). הרץ פעם אחת: "
                "python -m agent.verbit --login , התחבר, ואז הרץ שוב את הקביעה."
            ) from None

    def _goto_live_bookings(self, page) -> None:
        """מנווט לעמוד Live Bookings שבו נמצא הכפתור 'Place new order'."""
        try:
            page.get_by_role("button", name="Place new order").wait_for(timeout=3_000)
            return  # כבר על העמוד הנכון
        except PlaywrightError:
            pass
        try:
            page.get_by_role("link", name="Live Bookings").first.click(timeout=8_000)
            page.wait_for_load_state("domcontentloaded")
        except PlaywrightError:
            pass  # אם אין קישור כזה - ננסה להמשיך מהעמוד הנוכחי

    def _step(self, page, description: str, action) -> None:
        """מריץ שלב בטופס; אם נכשל - שומר צילום/HTML ומעלה שגיאה מפנה."""
        try:
            action()
        except PlaywrightError as e:
            path = self._debug_dump(page, description)
            first_line = str(e).splitlines()[0] if str(e) else ""
            raise RuntimeError(
                f"קביעת הדיון נכשלה בשלב '{description}'. נשמרו צילום מסך ו-HTML "
                f"של הטופס ב: {path} - שלח אותם ל-Claude להתאמת ה-selector. ({first_line})"
            ) from e

    def _fill_session_name(self, page, value: str) -> None:
        """ממלא את 'Session name' - input מוסתר ברכיב verbit-editable."""
        page.locator(".verbit-editable__preview").first.click(timeout=6_000)
        inp = page.locator("input[data-is-editable-input='true']").first
        inp.fill(value, timeout=6_000)
        inp.press("Tab")  # יציאה ממצב עריכה ואישור הערך

    def _select_react(self, page, aria_label: str, value: str) -> None:
        """פותח react-select לפי ה-aria-label, מסנן לפי טקסט, ובוחר אפשרות."""
        ctrl = page.get_by_label(aria_label, exact=True).first
        ctrl.click(timeout=10_000)          # מחכה גם שהשדה יהפוך פעיל (למשל שפת פלט)
        try:
            ctrl.fill(value, timeout=3_000)
        except PlaywrightError:
            page.keyboard.type(value)
        page.get_by_role("option", name=value, exact=False).first.click(timeout=6_000)

    def _select_time(self, page, aria_label: str, hhmm: str) -> None:
        """בוחר שעה ב-react-select; מנסה מספר פורמטים (24 שעות ו-AM/PM)."""
        ctrl = page.get_by_label(aria_label, exact=True).first
        ctrl.click(timeout=10_000)
        for cand in _time_candidates(hhmm):
            try:
                ctrl.fill(cand, timeout=2_000)
            except PlaywrightError:
                page.keyboard.type(cand)
            try:
                page.get_by_role("option", name=cand, exact=True).first.click(timeout=2_500)
                return
            except PlaywrightError:
                try:
                    ctrl.fill("", timeout=1_000)
                except PlaywrightError:
                    pass
                continue
        raise PlaywrightError(f"no time option matched {hhmm!r}")

    def _pick_date(self, page, iso_date: str) -> None:
        """בוחר תאריך דרך לוח השנה (popover) - השדה עצמו אינו ניתן להקלדה.

        פותח את ה-popover ולוחץ על תא היום. אם הבחירה נכשלת, לוח השנה נשאר
        פתוח - כך שצילום השגיאה יראה את מבנה לוח השנה לתיקון מדויק.
        """
        page.locator('[id="popover-trigger-input.schedule.date"]').first.click(timeout=6_000)
        dialog = page.locator('[id="popover-content-input.schedule.date"]').first
        dialog.wait_for(state="visible", timeout=6_000)

        day = str(int(iso_date.split("-")[2]))  # '16' בלי אפס מוביל
        strategies = (
            lambda: dialog.get_by_role("button", name=day, exact=True).first.click(timeout=3_000),
            lambda: dialog.get_by_role("gridcell", name=day, exact=True).first.click(timeout=3_000),
            lambda: dialog.locator(
                "xpath=.//*[normalize-space(text())=" + repr(day) +
                " and not(@disabled) and not(@aria-disabled='true')"
                " and not(contains(@class,'outside')) and not(contains(@class,'disabled'))]"
            ).first.click(timeout=3_000),
        )
        for attempt in strategies:
            try:
                attempt()
                return
            except PlaywrightError:
                continue
        raise PlaywrightError(f"could not click day {day} in the calendar popover")

    def _still_on_create_form(self, page) -> bool:
        """האם עדיין על טופס יצירת ההזמנה (כלומר השליחה לא עברה)?"""
        if "create_live_order" in page.url or "/create" in page.url:
            return True
        try:
            return page.get_by_role("button", name="Place session").first.is_visible()
        except PlaywrightError:
            return False

    def _invalid_fields(self, page) -> str:
        """שמות השדות שסומנו כשגויים (aria-invalid) + הודעות שגיאה גלויות."""
        found = []
        try:
            loc = page.locator("[aria-invalid='true']")
            for i in range(min(loc.count(), 15)):
                el = loc.nth(i)
                name = (el.get_attribute("aria-label") or el.get_attribute("id")
                        or el.get_attribute("name"))
                if name:
                    found.append(name)
        except PlaywrightError:
            pass
        try:
            errs = page.get_by_text("required field", exact=False)
            if errs.count():
                found.append(f"({errs.count()} 'required field')")
        except PlaywrightError:
            pass
        return ", ".join(dict.fromkeys(found))  # ייחודי, בסדר הופעה

    def _debug_dump(self, page, tag: str) -> str:
        """שומר צילום מסך + HTML של המצב הנוכחי לצורך תיקון selector."""
        out_dir = Path(self.cfg["storage"]["data_dir"]) / "calibration"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe = "".join(c if c.isalnum() else "_" for c in tag)[:30]
        base = out_dir / f"schedule-error-{date.today().isoformat()}-{safe}"
        try:
            page.screenshot(path=str(base) + ".png", full_page=True)
            Path(str(base) + ".html").write_text(page.content(), encoding="utf-8")
        except PlaywrightError:
            pass
        return str(base) + ".png"

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


def _login(cfg: dict) -> None:
    """פותח את Verbit בפרופיל הקבוע וממתין שתתחבר - כדי לשמור את ההתחברות."""
    client = BrowserVerbit(cfg)
    with sync_playwright() as p:
        context, page = client._launch(p, headless=False)
        page.goto(client.vcfg["base_url"], wait_until="domcontentloaded")
        print()
        print("נפתח דפדפן על Verbit. התחבר עם שם המשתמש והסיסמה,")
        print("והמתן עד שאתה רואה את מסך ההזמנות (Live Bookings).")
        print("חשוב: אל תסגור את חלון הדפדפן.")
        input("כשאתה מחובר ורואה את ההזמנות - חזור לכאן ולחץ Enter... ")
        context.close()
    print("ההתחברות נשמרה בפרופיל. עכשיו הרץ: python -m agent.verbit --schedule-test")


def _schedule_test(cfg: dict, start_time: str | None = None) -> None:
    """בדיקה: קובע ב-Verbit את הדיון הראשון שעדיין לא נקבע מקובץ היום.

    אם קובץ היום ריק, קורא קודם את היומן משירה - כך שאפשר להריץ את הבדיקה
    בפקודה אחת בלי לפתוח את הדשבורד.
    """
    from .shira import fetch_today
    from .store import DayStore

    store = DayStore(cfg["storage"]["data_dir"])
    hearings = store.load()
    if not hearings:
        print("קובץ היום ריק - קורא את היומן משירה...")
        hearings = store.merge(fetch_today(cfg, headless=True))
        print(f"נמצאו {len(hearings)} דיונים.")
    hearing = next((h for h in hearings if h.status in ("pending", "error")), None)
    if hearing is None:
        print("אין דיון להיום שממתין לקביעה.")
        return
    if start_time:
        hearing.time = start_time     # לצורך בדיקה: שעה מובחנת
        hearing.end_time = ""         # תחושב מחדש מהמשך ברירת המחדל
    print(f"קובע ב-Verbit לבדיקה: {hearing.time} {hearing.case_number} "
          f"{hearing.case_title} ...")
    client = BrowserVerbit(cfg)
    client.schedule(hearing, headless=False)
    store.update(hearing.id, status="scheduled", verbit_url=hearing.verbit_url, error="")
    print(f"נקבע בהצלחה. קישור: {hearing.verbit_url or '(לא נלכד)'}")


if __name__ == "__main__":
    import sys

    parser = argparse.ArgumentParser(description="Verbit: כיול מסכים ובדיקת קביעת דיון")
    parser.add_argument("--calibrate", action="store_true", help="שמירת צילום/HTML של מסך Verbit")
    parser.add_argument("--login", action="store_true",
                        help="התחברות חד-פעמית ל-Verbit (שמירת ההתחברות בפרופיל)")
    parser.add_argument("--schedule-test", action="store_true",
                        help="קביעת הדיון הראשון מקובץ היום ב-Verbit (דפדפן גלוי)")
    parser.add_argument("--time", metavar="HH:MM", default=None,
                        help="לבדיקה: לקבוע בשעה מובחנת (משבצות של 15 דקות)")
    args = parser.parse_args()
    try:
        if args.calibrate:
            calibrate(load_config())
        elif args.login:
            _login(load_config())
        elif args.schedule_test:
            _schedule_test(load_config(), start_time=args.time)
        else:
            parser.print_help()
    except RuntimeError as e:
        print(f"שגיאה: {e}", file=sys.stderr)
        sys.exit(1)
