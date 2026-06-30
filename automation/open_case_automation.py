"""
תבנית אוטומציה לפתיחת תיק במערכת שירה (Shira).

איך להשתמש:
1. הריצו קודם את record_open_case.py ותעדו תהליך פתיחת תיק מלא,
   עם נתוני בדיקה/דמה בלבד (ראו אזהרה ב-README.md).
2. פתחו את הקובץ שנוצר תחת recordings/ והעתיקו משם לכאן את ה-selectors
   של כל שדה (לא את הערכים שהוקלדו!) - לתוך FIELD_SELECTORS.
3. הריצו `python open_case_automation.py` לבדיקה.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

OPEN_CASE_URL = CONFIG["shira_base_url"].rstrip("/") + CONFIG["open_case_path"]
BROWSER_CHANNEL = CONFIG.get("browser_channel", "msedge")

# TODO: למלא לפי מה שהוקלט תחת recordings/open_case_*.py
FIELD_SELECTORS = {
    "id_number": "REPLACE_ME",            # לדוגמה: "#MainContent_txtTZ"
    "full_name": "REPLACE_ME",
    "case_type": "REPLACE_ME",
    "submit_button": "REPLACE_ME",
    "result_case_number": "REPLACE_ME",   # אלמנט שמציג את מספר התיק שנוצר
}


class CaseData(TypedDict, total=False):
    id_number: str
    full_name: str
    case_type: str


def open_case(page: Page, case_data: CaseData) -> str:
    """ממלא את טופס פתיחת התיק בשירה ומחזיר את מספר התיק שנוצר."""
    page.goto(OPEN_CASE_URL)

    if "id_number" in case_data:
        page.fill(FIELD_SELECTORS["id_number"], case_data["id_number"])
    if "full_name" in case_data:
        page.fill(FIELD_SELECTORS["full_name"], case_data["full_name"])
    if "case_type" in case_data:
        page.select_option(FIELD_SELECTORS["case_type"], case_data["case_type"])

    page.click(FIELD_SELECTORS["submit_button"])
    page.wait_for_selector(FIELD_SELECTORS["result_case_number"])
    return page.text_content(FIELD_SELECTORS["result_case_number"]) or ""


def run(case_data: CaseData, headless: bool = False) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=BROWSER_CHANNEL, headless=headless)
        try:
            page = browser.new_page()
            return open_case(page, case_data)
        finally:
            browser.close()


if __name__ == "__main__":
    # נתוני דמה לבדיקה בלבד - אל תריצו עם נתונים אמיתיים לפני שבדקתם!
    test_data: CaseData = {
        "id_number": "000000000",
        "full_name": "בדיקה בדיקה",
        "case_type": "REPLACE_ME",
    }
    print(run(test_data, headless=False))
