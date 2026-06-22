"""
option_b_auth_send.py — the REAL Option B: authenticated send via O365.
=======================================================================
Why: O365 quarantines our relay mail as PHISHING ("דיוג") because we
impersonate rbc.gov.il without authentication, and the domain enforces
DMARC p=reject. The only robust fix is to AUTHENTICATE: log in to O365
as a real court mailbox over port 587. O365 then DKIM-signs the message
for us -> DMARC passes -> it lands in the recipient's INBOX, From the
court address, with NO document created in Shira.

What IT must provide (one-time):
  * A mailbox to send as — ideally  no-reply@rbc.gov.il  (a shared or
    licensed mailbox), or a dedicated  shira-noreply@rbc.gov.il
  * SMTP AUTH enabled for it + an APP PASSWORD
  * Outbound port 587 to smtp.office365.com open from this server
    (run test_ports.py to confirm)

Credentials are read from environment variables — never hard-coded:
    set SHIRA_SMTP_USER=no-reply@rbc.gov.il
    set SHIRA_SMTP_PASS=<app-password>
    set SHIRA_SMTP_HOST=smtp.office365.com      (optional, this is default)
    set SHIRA_SMTP_PORT=587                       (optional)

Usage:
    python option_b_auth_send.py elchanans@rbc.gov.il
"""
import sys, io, os, smtplib, datetime as dt, html as _html
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SMTP_HOST = os.environ.get("SHIRA_SMTP_HOST", "smtp.office365.com")
SMTP_PORT = int(os.environ.get("SHIRA_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SHIRA_SMTP_USER", "")
SMTP_PASS = os.environ.get("SHIRA_SMTP_PASS", "")
# Address shown to the recipient. Defaults to the login mailbox; can be a
# Send-As address if the mailbox is permitted to send as it.
FROM_ADDR = os.environ.get("SHIRA_SMTP_FROM", SMTP_USER)


def build_message(from_addr, to_email, subject, text, court_name="רחובות",
                  case_data=None):
    case_data = case_data or {}
    today = dt.date.today().strftime("%d/%m/%Y")
    fn   = case_data.get("fileNumber", "")
    a, b = case_data.get("sideA", ""), case_data.get("sideB", "")
    subj = case_data.get("subject", "")

    plain = [f"בית הדין הרבני האזורי {court_name}", "-"*40]
    if fn:   plain.append(f"תיק מס': {fn}")
    if a or b: plain.append(f"{a} נ' {b}")
    if subj: plain.append(f"נושא: {subj}")
    plain += [f"תאריך: {today}", "-"*40, "", *text.split("\n"),
              "", "-"*40, f"בית הדין הרבני האזורי {court_name}", from_addr]

    head2 = ""
    if fn:   head2 += f"<div>תיק מס': {_html.escape(fn)}</div>"
    if a or b: head2 += f"<div>{_html.escape(a)} נ' {_html.escape(b)}</div>"
    if subj: head2 += f"<div>נושא: {_html.escape(subj)}</div>"
    body_html = "<br>".join(_html.escape(l) for l in text.split("\n"))
    html = f"""<!DOCTYPE html><html dir="rtl" lang="he"><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;font-size:14px;color:#222;direction:rtl;">
<table width="600" cellpadding="0" cellspacing="0" style="margin:20px auto;border:1px solid #ccc;">
<tr><td style="background:#1a3a5c;color:#fff;padding:16px;text-align:center;">
<div style="font-size:18px;font-weight:bold;">בית הדין הרבני האזורי</div>
<div style="font-size:16px;">{_html.escape(court_name)}</div></td></tr>
<tr><td style="padding:12px 20px;background:#f5f7fa;border-bottom:1px solid #ddd;font-size:13px;color:#555;">
{head2}<div>תאריך: {today}</div></td></tr>
<tr><td style="padding:20px;line-height:1.7;">{body_html}</td></tr>
<tr><td style="padding:16px;text-align:center;background:#f5f7fa;border-top:1px solid #ddd;font-size:12px;color:#888;">
בית הדין הרבני האזורי {_html.escape(court_name)} &nbsp;|&nbsp; {from_addr}</td></tr>
</table></body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"]    = subject
    msg["From"]       = f"בית הדין הרבני האזורי {court_name} <{from_addr}>"
    msg["To"]         = to_email
    msg["Date"]       = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="rbc.gov.il")
    msg["X-Mailer"]   = "ShiraAI"
    msg.attach(MIMEText("\n".join(plain), "plain", "utf-8"))
    msg.attach(MIMEText(html,             "html",  "utf-8"))
    return msg


def auth_send(to_email, subject, text, court_name="רחובות", case_data=None):
    if not SMTP_USER or not SMTP_PASS:
        return {"ok": False, "error":
                "missing SHIRA_SMTP_USER / SHIRA_SMTP_PASS environment variables"}
    msg = build_message(FROM_ADDR, to_email, subject, text, court_name, case_data)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as srv:
            srv.ehlo()
            srv.starttls()
            srv.ehlo()
            srv.login(SMTP_USER, SMTP_PASS)
            srv.sendmail(FROM_ADDR, [to_email], msg.as_bytes())
        return {"ok": True, "messageId": msg["Message-ID"]}
    except smtplib.SMTPAuthenticationError as e:
        return {"ok": False, "error": f"auth failed: {e}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    to = sys.argv[1] if len(sys.argv) > 1 else "elchanans@rbc.gov.il"
    print("=" * 64)
    print("  Option B — authenticated send via O365 (port 587)")
    print("=" * 64)
    print(f"  SMTP host : {SMTP_HOST}:{SMTP_PORT}")
    print(f"  Login as  : {SMTP_USER or '(NOT SET)'}")
    print(f"  From      : {FROM_ADDR or '(NOT SET)'}")
    print(f"  To        : {to}")
    if not SMTP_USER or not SMTP_PASS:
        print("\n  [!] Set credentials first:")
        print('      set SHIRA_SMTP_USER=no-reply@rbc.gov.il')
        print('      set SHIRA_SMTP_PASS=<app-password>')
        print("  Then re-run. (IT must enable SMTP AUTH + give an app password.)")
        sys.exit(1)
    res = auth_send(
        to,
        "הודעה מבית הדין הרבני — בדיקת מסירה מאומתת",
        "שלום רב,\n\nזוהי הודעת בדיקה מאומתת מבית הדין.\n"
        "אם הודעה זו הגיעה לתיבת הדואר הנכנס — הפתרון עובד.\n\nבברכה,\nבית הדין הרבני",
    )
    if res["ok"]:
        print(f"\n  [OK] sent. Message-ID: {res['messageId']}")
        print(f"  -> check the INBOX of {to}")
    else:
        print(f"\n  [FAIL] {res['error']}")
    print("=" * 64)
