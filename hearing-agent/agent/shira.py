"""קריאת יומן הדיונים ממערכת שירה, דרך דפדפן עם פרופיל קבוע.

ההזדהות לשירה אוטומטית (SSO ארגוני), ולכן הסוכן לא מתעסק בסיסמאות:
הוא פותח Edge/Chrome עם פרופיל ייעודי קבוע. בפעם הראשונה ייתכן שתידרש
כניסה ידנית אחת; מאז הפרופיל שומר את ההזדהות והריצות הבוקריות שקטות.

שני מצבי הפעלה:

  python -m agent.shira --calibrate
      פותח את היומן, ממתין שתגיע למסך הדיונים של היום, ושומר צילום מסך
      ו-HTML לתיקיית data/calibration/. את הקבצים האלה שולחים אליי
      (Claude) כדי שאמלא את ה-selectors ב-config.yaml.

  python -m agent.shira
      קריאה רגילה: מדפיס את דיוני היום לפי ה-selectors שבהגדרות.
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError, sync_playwright

from .config import load_config
from .models import Hearing

TIME_RE = re.compile(r"\b(\d{1,2}:\d{2})\b")

# פורמט שורת דיון ביומן DayPilot של שירה, למשל:
#   עיון - 1597286/1, תיק ארכיב, משה אסף, מרים אסף /דהן (21:00 - 21:15) מספר תיקים בדיון: 1
ROW_RE = re.compile(
    r"^(?P<kind>.+?)\s*-\s*(?P<case>[\d/.-]+)\s*,\s*(?P<rest>.+?)\s*"
    r"\(\s*(?P<start>\d{1,2}:\d{2})\s*-\s*(?P<end>\d{1,2}:\d{2})\s*\)"
)


def parse_row_text(text: str, today: str) -> Hearing | None:
    """מפענח שורת דיון אחת מהיומן; מחזיר None אם הטקסט אינו שורת דיון."""
    m = ROW_RE.search(text.strip())
    if not m:
        return None
    rest = [s.strip() for s in m.group("rest").split(",") if s.strip()]
    kind = m.group("kind").strip()
    title = f"{kind} - {rest[0]}" if rest else kind
    return Hearing(
        date=today,
        time=m.group("start"),
        case_number=m.group("case"),
        case_title=title,
        parties=rest[1:],
    )


def _open_calendar(p, cfg: dict, headless: bool):
    shira = cfg["shira"]
    context = p.chromium.launch_persistent_context(
        shira["profile_dir"],
        channel=shira.get("browser_channel", "msedge"),
        headless=headless,
    )
    page = context.pages[0] if context.pages else context.new_page()
    page.goto(shira["calendar_url"], wait_until="domcontentloaded")
    return context, page


def fetch_today(cfg: dict, headless: bool = True) -> list[Hearing]:
    """קורא את דיוני היום מהיומן ומחזיר רשימת Hearing."""
    shira = cfg["shira"]
    sel = shira["selectors"]
    if not sel.get("hearing_row"):
        raise RuntimeError(
            "ה-selectors של שירה עדיין ריקים ב-config.yaml. "
            "הרץ קודם: python -m agent.shira --calibrate (ראה README)."
        )

    today = date.today().isoformat()
    hearings = []
    with sync_playwright() as p:
        context, page = _open_calendar(p, cfg, headless)
        try:
            page.wait_for_selector(sel["hearing_row"], timeout=30_000)
        except PlaywrightError:
            context.close()
            return []  # יום בלי דיונים - היומן פשוט ריק

        for row in page.query_selector_all(sel["hearing_row"]):
            if not sel.get("case_number"):
                # מצב "שורה משולבת": כל פרטי הדיון בטקסט אחד (יומן DayPilot).
                # הטקסט הפנימי עדיף על מאפיין title - שמות עם גרשיים (") קוטעים אותו.
                text = row.inner_text().strip() or (row.get_attribute("title") or "")
                hearing = parse_row_text(text, today)
                if hearing:
                    hearings.append(hearing)
                continue

            def text_of(key: str) -> str:
                el = row.query_selector(sel[key]) if sel.get(key) else None
                return el.inner_text().strip() if el else ""

            time_text = text_of("hearing_time") or row.inner_text()
            time_match = TIME_RE.search(time_text)
            parties_text = text_of("parties")

            hearings.append(Hearing(
                date=today,
                time=time_match.group(1) if time_match else "",
                case_number=text_of("case_number"),
                case_title=text_of("case_title"),
                parties=[s.strip() for s in re.split(r"[,;\n]| נ' ", parties_text) if s.strip()],
            ))
        context.close()

    seen: set[str] = set()
    unique = []
    for h in hearings:
        if h.case_number and h.id not in seen:
            seen.add(h.id)
            unique.append(h)
    return unique


def calibrate(cfg: dict) -> None:
    """מצב כיול: שומר צילום מסך + HTML של היומן לניתוח ומילוי selectors."""
    out_dir = Path(cfg["storage"]["data_dir"]) / "calibration"
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context, page = _open_calendar(p, cfg, headless=False)
        print()
        print("נפתח דפדפן. נווט בו אל יומן הדיונים של היום (התחבר אם צריך).")
        print("חשוב: אל תסגור את חלון הדפדפן! השאר אותו פתוח על מסך היומן.")
        input("כשהמסך מציג את רשימת הדיונים - חזור לכאן ולחץ Enter... ")

        try:
            # אם המשתמש פתח טאב חדש וסגר את המקורי - ניקח את הטאב האחרון שפתוח
            open_pages = [pg for pg in context.pages if not pg.is_closed()]
            if not open_pages:
                raise PlaywrightError("no open pages")
            page = open_pages[-1]

            stamp = date.today().isoformat()
            png = out_dir / f"shira-{stamp}.png"
            html = out_dir / f"shira-{stamp}.html"
            page.screenshot(path=str(png), full_page=True)
            html.write_text(page.content(), encoding="utf-8")
        except PlaywrightError:
            raise RuntimeError(
                "חלון הדפדפן נסגר לפני השמירה. הרץ שוב את הכיול, והשאר את "
                "הדפדפן פתוח על מסך היומן עד שמופיעה כאן ההודעה 'נשמר'."
            ) from None
        print(f"\nנשמר: {png}\nנשמר: {html}")
        print("שלח את שני הקבצים האלה ל-Claude כדי למלא את ה-selectors ב-config.yaml.")
        print(f"וכן עדכן ב-config.yaml את הכתובת הנוכחית: {page.url}")
        context.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="קריאת יומן הדיונים משירה")
    parser.add_argument("--calibrate", action="store_true", help="מצב כיול (שמירת צילום/HTML)")
    parser.add_argument("--headed", action="store_true", help="הרצה עם דפדפן גלוי")
    args = parser.parse_args()

    cfg = load_config()
    if args.calibrate:
        calibrate(cfg)
        return

    hearings = fetch_today(cfg, headless=not args.headed)
    if not hearings:
        print("לא נמצאו דיונים להיום.")
        return
    for h in hearings:
        print(f"{h.time}  {h.case_number}  {h.case_title}  ({', '.join(h.parties)})")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"שגיאה: {e}", file=sys.stderr)
        sys.exit(1)
