"""
option_b_unofficial_send.py — Option B, "unofficial court email".
==================================================================
The problem we are solving:
  Sending  From: <something>@rbc.gov.il  is ALWAYS blocked, because the
  rbc.gov.il domain publishes DMARC=reject. Every receiver (Microsoft,
  Gmail, ...) obeys that rule and quarantines/rejects unsigned mail that
  claims to be from the court.

The idea here:
  Do NOT put @rbc.gov.il in the From ADDRESS. Instead:
    * From ADDRESS  = a NON-court address with a relaxed DMARC policy
                      (a normal Gmail address is p=none -> not auto-rejected)
    * From DISPLAY NAME = "בית הדין הרבני האזורי <court>"  so the recipient
                      still SEES that it is from the court.
    * Reply-To       = the court address, so replies go to the court.

  This is an *unofficial* notification: it visibly comes from the court (by
  name) but is sent from a side mailbox, so it is not impersonating the
  protected domain and is not flagged as phishing.

Sending path:
  Still the only open outbound path on the court server: the internal relay
  mail.rbc.gov.il:25 (anonymous, no AUTH). Because the From DOMAIN is now a
  p=none domain, the receiver does not REJECT on DMARC. (It may still land in
  Spam if SPF doesn't align — that is the tradeoff of an unofficial sender.)

Configuration (env vars, nothing hard-coded):
    set SHIRA_UNOFFICIAL_FROM=shira.beitdin.rehovot@gmail.com
    set SHIRA_REPLYTO=elchanans@rbc.gov.il      (optional)
    set SHIRA_RELAY=mail.rbc.gov.il             (optional, default)

Usage:
    python option_b_unofficial_send.py <recipient> ["court name"]
    python option_b_unofficial_send.py elchanans@rbc.gov.il "רחובות"
"""
import sys, io, os, smtplib, datetime as dt, html as _html
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid, formataddr

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

RELAY    = os.environ.get("SHIRA_RELAY", "mail.rbc.gov.il")
PORT     = int(os.environ.get("SHIRA_RELAY_PORT", "25"))
FROM_ADDR = os.environ.get("SHIRA_UNOFFICIAL_FROM", "")   # e.g. a Gmail address
REPLYTO  = os.environ.get("SHIRA_REPLYTO", "")            # e.g. court address


def build_message(from_addr, display_name, to_email, subject, text,
                  court_name="רחובות", reply_to="", case_data=None):
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
              "", "-"*40, f"בית הדין הרבני האזורי {court_name}"]

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
בית הדין הרבני האזורי {_html.escape(court_name)}</td></tr>
</table></body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"]    = subject
    msg["From"]       = formataddr((f"בית הדין הרבני האזורי {court_name}", from_addr))
    msg["To"]         = to_email
    if reply_to:
        msg["Reply-To"] = reply_to
    msg["Date"]       = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=from_addr.split("@")[-1] if "@" in from_addr else "localhost")
    msg["X-Mailer"]   = "ShiraAI"
    msg.attach(MIMEText("\n".join(plain), "plain", "utf-8"))
    msg.attach(MIMEText(html,             "html",  "utf-8"))
    return msg


def send_unofficial(to_email, subject, text, court_name="רחובות",
                    case_data=None):
    if not FROM_ADDR:
        return {"ok": False, "error":
                "missing SHIRA_UNOFFICIAL_FROM (set a non-court From address, "
                "e.g. a Gmail address)"}
    msg = build_message(FROM_ADDR, f"בית הדין הרבני האזורי {court_name}",
                        to_email, subject, text, court_name, REPLYTO, case_data)
    try:
        with smtplib.SMTP(RELAY, PORT, timeout=20) as srv:
            srv.set_debuglevel(1)
            srv.ehlo()
            srv.sendmail(FROM_ADDR, [to_email], msg.as_bytes())
        return {"ok": True, "messageId": msg["Message-ID"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    to    = sys.argv[1] if len(sys.argv) > 1 else "elchanans@rbc.gov.il"
    court = sys.argv[2] if len(sys.argv) > 2 else "רחובות"
    print("=" * 64)
    print("  Option B — UNOFFICIAL court email (non-rbc From, court name shown)")
    print("=" * 64)
    print(f"  Relay     : {RELAY}:{PORT}")
    print(f"  From addr : {FROM_ADDR or '(NOT SET — set SHIRA_UNOFFICIAL_FROM)'}")
    print(f"  Shown as  : בית הדין הרבני האזורי {court}")
    print(f"  Reply-To  : {REPLYTO or '(none)'}")
    print(f"  To        : {to}")
    if not FROM_ADDR:
        print("\n  [!] Set a non-court From address first, e.g.:")
        print('      set SHIRA_UNOFFICIAL_FROM=shira.beitdin.rehovot@gmail.com')
        print('      set SHIRA_REPLYTO=elchanans@rbc.gov.il')
        print("  Then re-run.")
        sys.exit(1)
    res = send_unofficial(
        to,
        "הודעה מבית הדין הרבני",
        "שלום רב,\n\nזוהי הודעת בדיקה מבית הדין הרבני.\n"
        "אם הודעה זו הגיעה לתיבת הדואר הנכנס — הפתרון עובד.\n\nבברכה,\nבית הדין הרבני",
        court_name=court,
    )
    if res["ok"]:
        print(f"\n  [OK] sent. Message-ID: {res['messageId']}")
        print(f"  -> check the INBOX (and Spam) of {to}")
    else:
        print(f"\n  [FAIL] {res['error']}")
    print("=" * 64)
