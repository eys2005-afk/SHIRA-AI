"""שלב ג' (עתידי): השוואת הפרוטוקול שנכתב בדיון מול תמלול ההקלטה.

    python -m agent.compare protocol.txt transcript.txt -o report.md

מקבל את הפרוטוקול שכתבת ואת התמלול מ-Verbit, ומפיק דוח השוואה:
מה נאמר בדיון ולא מופיע בפרוטוקול, אי-דיוקים, והצעות שיפור.

דורש מפתח Claude API ב-.env (ANTHROPIC_API_KEY) ו: pip install anthropic
זהו שלב מאוחר יותר בתוכנית - הקוד כאן עובד, אבל שווה לחזור אליו אחרי
ששלבים א'-ב' רצים ביציבות ויש תמלולים אמיתיים לעבוד איתם.
"""

import argparse
import os
import sys
from pathlib import Path

PROMPT = """אתה עוזר משפטי מדויק. לפניך פרוטוקול דיון שנכתב על ידי בית הדין בזמן אמת, \
ותמלול מלא של הקלטת אותו דיון.

הפק דוח השוואה בעברית, בפורמט Markdown, עם הסעיפים הבאים:

## דברים מהותיים שנאמרו בדיון ואינם משתקפים בפרוטוקול
פרט כל אמירה או התרחשות מהותית שמופיעה בתמלול ולא בפרוטוקול, עם ציטוט קצר מהתמלול.

## אי-התאמות בין הפרוטוקול לתמלול
מקומות שבהם הפרוטוקול מנסח משהו באופן שונה מהותית ממה שנאמר בפועל.

## דברים בפרוטוקול שלא נמצאו בתמלול
ייתכן שנכתבו מסיכום או מזיכרון - לציין אותם לבדיקה.

## הערכה כללית והצעות שיפור
2-4 נקודות קצרות.

התייחס רק להבדלים מהותיים; אל תציין הבדלי ניסוח סגנוניים חסרי משמעות.

<פרוטוקול>
{protocol}
</פרוטוקול>

<תמלול>
{transcript}
</תמלול>"""


def compare(protocol_path: str, transcript_path: str) -> str:
    try:
        import anthropic
    except ImportError:
        sys.exit("חסרה החבילה anthropic. התקן עם: pip install anthropic")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("חסר ANTHROPIC_API_KEY בקובץ .env (ראה README).")

    protocol = Path(protocol_path).read_text(encoding="utf-8")
    transcript = Path(transcript_path).read_text(encoding="utf-8")

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=8000,
        messages=[{
            "role": "user",
            "content": PROMPT.format(protocol=protocol, transcript=transcript),
        }],
    )
    return response.content[0].text


def main() -> None:
    parser = argparse.ArgumentParser(description="השוואת פרוטוקול מול תמלול הקלטה")
    parser.add_argument("protocol", help="קובץ טקסט של הפרוטוקול")
    parser.add_argument("transcript", help="קובץ טקסט של התמלול מ-Verbit")
    parser.add_argument("-o", "--output", default="", help="קובץ פלט (ברירת מחדל: הדפסה למסך)")
    args = parser.parse_args()

    from .config import load_config  # טוען גם את .env
    load_config()

    report = compare(args.protocol, args.transcript)
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"הדוח נשמר: {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
