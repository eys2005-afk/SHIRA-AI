"""
official_replica.py — build an email IDENTICAL to a real Shira-case message.
============================================================================
Captured from a real message sent from inside a case (no-reply@rbc.gov.il):

    Subject: הודעה מבית הדין הרבני
    From:    no-reply@rbc.gov.il   (display: shown by client)
    Body:    fixed template — "מצורף בזאת מסמך..." + case numbers + parties
             + the standard SignAndVerify / Office-compat boilerplate
             + phone/fax + "נא לא להשיב למייל זה!"
    Attach:  the case document(s) (signed files)

This module reproduces that body EXACTLY and lets us attach the same files.
The only field we cannot reproduce from outside is the trusted @rbc.gov.il
sender (DMARC=reject). The From here is configurable; everything else is a
byte-for-byte match of the official template.
"""
import os, datetime as dt, html as _html
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.utils import formatdate, make_msgid, formataddr

SUBJECT = "הודעה מבית הדין הרבני"


def build_official_body(court_name, case_numbers, case_subject, side_a, side_b,
                        phone="-", fax="08-9492277"):
    """Reproduce the exact official case-message body."""
    cases_block = "\n".join([
        case_numbers if isinstance(case_numbers, str) else "\n".join(case_numbers),
        case_subject,
        side_a,
        side_b,
    ])
    return (
        "שלום,\n\n\n"
        f"מצורף בזאת מסמך מבית הדין הרבני {court_name}\n\n"
        "בנוגע לתיקים:\n"
        f"{cases_block}\n\n\n\n"
        "אם זו הפעם הראשונה שאת/ה מקבל/ת מכתב מבית הדין הרבני בדואר אלקטרוני,\n"
        "לצורך הצפייה בקבצים המצורפים עליך להוריד תוכנת עזר מפורטל השירותים והמידע הממשלתי:\n"
        "http://www.forms.gov.il/download/SignAndVerify.msi.\n\n\n"
        "סרטון הסבר לפתיחת קבצים מסוג signed\n"
        "https://youtu.be/F4fNkQP3vVs.\n\n\n"
        "שים לב : הקבצים נשלחים מבית הדין בגרסת 2007 OFFICE, אם אין ברשותך גרסא זו, נא פעל בהתאם להנחיות הבאות.\n\n"
        "בפעם הראשונה שאת/ה מקבל/ת מכתב מבית הדין יש להוריד תוכנה מאתר מיקרוסופט (Freeware) בהתאם למצב כדלהלן:\n"
        "אם ברשותך גרסא נמוכה יותר יש להוריד קובץ תאימות:\n"
        "http://www.microsoft.com/downloads/details.aspx?FamilyID=941B3470-3AE9-4AEE-8F43-C6BB74CD1466&displaylang=he.\n"
        "אם אין ברשותך כלל OFFICE, יש להוריד תכנת צפיה:\n"
        "http://www.microsoft.com/downloads/details.aspx?displaylang=he&FamilyID=3657ce88-7cfa-457a-9aec-f4f827f20cac.\n\n\n"
        "בכל בעיה בפתיחת הקבצים המצורפים, עומד לרשותכם אתר GOV.IL , תמיכה בטלפון 1299\n\n\n"
        "בברכה,\n"
        f"בית הדין הרבני {court_name}\n"
        f"טלפון: {phone}\n"
        f"פקס: {fax}\n\n\n"
        "**נא לא להשיב למייל זה!**\n"
    )


def build_message(from_addr, to_email, court_name, case_numbers, case_subject,
                  side_a, side_b, attachments=None, display_name=None,
                  reply_to="", phone="-", fax="08-9492277"):
    """
    attachments: list of file paths to attach (the signed case documents).
    display_name: shown sender name. Defaults to the official 'no-reply' look.
    """
    body = build_official_body(court_name, case_numbers, case_subject,
                               side_a, side_b, phone, fax)

    outer = MIMEMultipart("mixed")
    outer["Subject"] = SUBJECT
    if display_name:
        outer["From"] = formataddr((display_name, from_addr))
    else:
        outer["From"] = from_addr
    outer["To"] = to_email
    if reply_to:
        outer["Reply-To"] = reply_to
    outer["Date"] = formatdate(localtime=True)
    outer["Message-ID"] = make_msgid(
        domain=from_addr.split("@")[-1] if "@" in from_addr else "localhost")

    outer.attach(MIMEText(body, "plain", "utf-8"))

    for path in (attachments or []):
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as f:
            data = f.read()
        part = MIMEApplication(data, Name=os.path.basename(path))
        part["Content-Disposition"] = f'attachment; filename="{os.path.basename(path)}"'
        outer.attach(part)

    return outer
