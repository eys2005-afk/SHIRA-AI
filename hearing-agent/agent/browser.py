"""פתיחת דפדפן עם פרופיל קבוע, בעמידה בפני דפדפן שאינו מותקן.

הסוכן מזדהה לשירה ול-Verbit דרך דפדפן ממותג (Edge/Chrome) עם פרופיל
קבוע, כדי שההזדהות האוטומטית (SSO ארגוני) תישמר בין ריצות. אם הדפדפן
שהוגדר ב-config.yaml לא נמצא במחשב, מנסים את הדפדפן הממותג החלופי לפני
שנעצרים - כך לחיצה על "רענון" לא מתרסקת עם חריגה טכנית של Playwright
אלא, במקרה הגרוע, מציגה הודעה ברורה מה להתקין.

אפשר גם לבחור במפורש ב-Chromium המצורף ל-Playwright (ללא הזדהות SSO)
על ידי browser_channel ריק או "chromium" ב-config.yaml.
"""

from playwright.sync_api import Error as PlaywrightError

# הדפדפנים הממותגים שנושאים את ההזדהות האוטומטית של Windows.
_FALLBACKS = ("msedge", "chrome")

# פירורי טקסט שמזהים שגיאת "הדפדפן לא מותקן" (להבדיל משגיאות אחרות
# כמו פרופיל נעול, שאותן אין טעם לעקוף בדפדפן אחר).
_NOT_FOUND_HINTS = ("is not found", "Executable doesn't exist", "not found at")


def launch_persistent_context(p, profile_dir: str, channel: str = "msedge",
                              headless: bool = True):
    """פותח context מתמשך; נופל לדפדפן ממותג חלופי אם המוגדר אינו מותקן.

    p          - מופע sync_playwright פעיל
    channel    - הערוץ המוגדר (msedge / chrome / chromium / ריק)
    """
    channel = (channel or "").strip().lower()

    # Chromium המצורף ל-Playwright - נבחר במפורש (בלי ערוץ ממותג ובלי SSO).
    if channel in ("", "chromium"):
        return p.chromium.launch_persistent_context(profile_dir, headless=headless)

    # סדר הניסיונות: הערוץ המוגדר קודם, ואז הממותג החלופי.
    order = [channel] + [c for c in _FALLBACKS if c != channel]
    last_err: PlaywrightError | None = None
    for ch in order:
        try:
            return p.chromium.launch_persistent_context(
                profile_dir, channel=ch, headless=headless)
        except PlaywrightError as e:
            if any(hint in str(e) for hint in _NOT_FOUND_HINTS):
                last_err = e
                continue  # דפדפן זה לא מותקן - ננסה את הבא
            raise  # שגיאה אחרת (פרופיל נעול וכו') - לא נפתרת בדפדפן חלופי

    raise RuntimeError(
        f"לא נמצא דפדפן להרצת הסוכן (ניסיתי: {', '.join(order)}). "
        "התקן Edge או Chrome, או הרץ: python -m playwright install msedge. "
        'לחלופין הגדר browser_channel: "chromium" ב-config.yaml כדי להשתמש '
        "ב-Chromium המצורף ל-Playwright (בלי הזדהות SSO ארגונית)."
    ) from last_err
