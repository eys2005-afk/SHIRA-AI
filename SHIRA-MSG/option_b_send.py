"""
option_b_send.py — send a court message WITHOUT creating a Shira document.
==========================================================================
Uses the open internal SMTP relay (mail.rbc.gov.il:25, no AUTH) to send
a formatted court email From: no-reply@rbc.gov.il.

No document is stored in Shira. The email looks identical to the real
court system emails (same sender, same formatting).

Usage (standalone test):
    python option_b_send.py

Or import and call send_court_message() from shira_proxy.py.
"""
import sys, io, smtplib, datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formatdate, make_msgid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

RELAY  = "mail.rbc.gov.il"
PORT   = 25
SENDER = "no-reply@rbc.gov.il"
DOMAIN = "rbc.gov.il"

COURT_NAMES = {
    1: "ירושלים", 2: "תל אביב", 3: "חיפה", 4: "פתח תקוה",
    5: "רחובות",  6: "באר שבע", 7: "טבריה", 8: "צפת",
    9: "אשדוד",  10: "אשקלון", 11: "נתניה",
    12: "בית הדין הגדול", 13: "אריאל",
}


def build_html_body(text: str, case_data: dict, court_name: str) -> str:
    """Build an HTML email body that matches the court's own email format."""
    file_number = case_data.get("fileNumber", "")
    side_a      = case_data.get("sideA", "")
    side_b      = case_data.get("sideB", "")
    subject     = case_data.get("subject", "")
    today       = datetime.date.today().strftime("%d/%m/%Y")

    # Escape message text for HTML
    import html as _html
    escaped_lines = [_html.escape(line) for line in text.split("\n")]
    body_html = "<br>".join(escaped_lines)

    header_line2 = ""
    if side_a or side_b:
        header_line2 = f"<div>{_html.escape(side_a)} נ' {_html.escape(side_b)}</div>"
    if file_number:
        header_line2 += f"<div>תיק מס': {_html.escape(file_number)}</div>"
    if subject:
        header_line2 += f"<div>נושא: {_html.escape(subject)}</div>"

    return f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;font-size:14px;color:#222;direction:rtl;">
  <table width="600" cellpadding="0" cellspacing="0" style="margin:20px auto;border:1px solid #ccc;">
    <tr>
      <td style="background:#1a3a5c;color:#fff;padding:16px;text-align:center;">
        <div style="font-size:18px;font-weight:bold;">בית הדין הרבני האזורי</div>
        <div style="font-size:16px;">{_html.escape(court_name)}</div>
      </td>
    </tr>
    <tr>
      <td style="padding:12px 20px;background:#f5f7fa;border-bottom:1px solid #ddd;font-size:13px;color:#555;">
        {header_line2}
        <div>תאריך: {today}</div>
      </td>
    </tr>
    <tr>
      <td style="padding:20px;line-height:1.7;">
        {body_html}
      </td>
    </tr>
    <tr>
      <td style="padding:16px;text-align:center;background:#f5f7fa;border-top:1px solid #ddd;
                 font-size:12px;color:#888;">
        בית הדין הרבני האזורי {_html.escape(court_name)} &nbsp;|&nbsp; {SENDER}
      </td>
    </tr>
  </table>
</body>
</html>"""


def build_plain_body(text: str, case_data: dict, court_name: str) -> str:
    file_number = case_data.get("fileNumber", "")
    side_a      = case_data.get("sideA", "")
    side_b      = case_data.get("sideB", "")
    subject     = case_data.get("subject", "")
    today       = datetime.date.today().strftime("%d/%m/%Y")

    lines = [
        f"בית הדין הרבני האזורי {court_name}",
        "-" * 40,
    ]
    if file_number:
        lines.append(f"תיק מס': {file_number}")
    if side_a or side_b:
        lines.append(f"{side_a} נ' {side_b}")
    if subject:
        lines.append(f"נושא: {subject}")
    lines.append(f"תאריך: {today}")
    lines.append("-" * 40)
    lines.append("")
    lines.extend(text.split("\n"))
    lines += ["", "-" * 40, f"בית הדין הרבני האזורי {court_name}", SENDER]
    return "\n".join(lines)


def send_court_message(
    to_email:   str,
    subject:    str,
    text:       str,
    case_data:  dict,
    court_id:   int  = 5,
    court_name: str  = "",
    docx_buf          = None,   # optional io.BytesIO for attachment
    docx_filename: str = "message.docx",
) -> dict:
    """
    Send a formatted court message via the open internal relay.

    Returns {"ok": True, "message_id": "..."} or {"ok": False, "error": "..."}.
    """
    if not court_name:
        court_name = COURT_NAMES.get(court_id, f"בית הדין #{court_id}")

    msg = MIMEMultipart("mixed")
    msg["Subject"]    = subject
    msg["From"]       = f"בית הדין הרבני האזורי {court_name} <{SENDER}>"
    msg["To"]         = to_email
    msg["Date"]       = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=DOMAIN)
    msg["X-Mailer"]   = "ShiraAI"

    # Prefer HTML with plain fallback
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(build_plain_body(text, case_data, court_name), "plain", "utf-8"))
    alt.attach(MIMEText(build_html_body(text, case_data, court_name),  "html",  "utf-8"))
    msg.attach(alt)

    # Optional docx attachment
    if docx_buf is not None:
        part = MIMEBase("application",
                        "vnd.openxmlformats-officedocument.wordprocessingml.document")
        part.set_payload(docx_buf.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment",
                        filename=("utf-8", "", docx_filename))
        msg.attach(part)

    try:
        with smtplib.SMTP(RELAY, PORT, timeout=15) as srv:
            srv.ehlo(DOMAIN)
            srv.sendmail(SENDER, [to_email], msg.as_bytes())
        return {"ok": True, "message_id": msg["Message-ID"]}
    except smtplib.SMTPRecipientsRefused as e:
        return {"ok": False, "error": f"Recipient refused: {e}"}
    except smtplib.SMTPSenderRefused as e:
        return {"ok": False, "error": f"Sender refused: {e}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Option B — standalone send test")
    print("=" * 60)

    TO      = "elchanans@rbc.gov.il"   # change to your address
    SUBJECT = "הודעה מבית הדין - בדיקת מערכת"
    TEXT    = (
        "שלום רב,\n\n"
        "הנכם מוזמנים להתייצב לדיון שנקבע בתיק זה.\n\n"
        "פרטי הדיון יימסרו בנפרד.\n\n"
        "בברכה,"
    )
    CASE = {
        "fileNumber": "1295887/3",
        "sideA":      "שמריה אלחנן ישראל",
        "sideB":      "הצד השני",
        "subject":    "גירושין",
    }

    result = send_court_message(
        to_email   = TO,
        subject    = SUBJECT,
        text       = TEXT,
        case_data  = CASE,
        court_id   = 5,
    )

    if result["ok"]:
        print(f"  [OK] Sent. Message-ID: {result['message_id']}")
        print(f"  Check inbox: {TO}")
    else:
        print(f"  [FAIL] {result['error']}")

    print("=" * 60)
