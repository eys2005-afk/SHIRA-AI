"""
send_direct_mx.py — send straight to the recipient's mail server (MX),
======================================================================
NOT through the mail.rbc.gov.il relay.

Why this beats the relay:
  The court server's public IP (147.237.70.171) is INSIDE the SPF record
  for rbc.gov.il  (ip4:147.237.70.0/24).  When we connect DIRECTLY to the
  recipient's MX from this IP and send From: no-reply@rbc.gov.il, the
  receiving server sees:
      SPF   = pass   (147.237.70.171 is authorised)
      DMARC = pass   (envelope-from rbc.gov.il aligns with From rbc.gov.il)
  -> the message is trusted and goes to the INBOX, not quarantine.

The relay path failed because O365 distrusts mail injected by the internal
relay (no DKIM, anonymous source) under DMARC p=reject.

Usage:
    python send_direct_mx.py elchanans@rbc.gov.il
"""
import sys, io, smtplib, subprocess, re, socket, datetime as dt, html as _html
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SENDER     = "no-reply@rbc.gov.il"
HELO_NAME  = "rbc.gov.il"          # SPF-covered HELO identity
COURT_NAME = "רחובות"


def mx_lookup(domain):
    """Return MX hostnames for a domain, best first."""
    try:
        out = subprocess.run(["nslookup", "-type=mx", domain],
                             capture_output=True, text=True, timeout=15).stdout
        pairs = re.findall(r'preference\s*=\s*(\d+).*?mail exchanger\s*=\s*([^\s]+)',
                           out, re.S)
        if pairs:
            pairs.sort(key=lambda x: int(x[0]))
            return [h.strip().rstrip('.') for _, h in pairs]
    except Exception as e:
        print(f"  MX lookup error: {e}")
    # Known fallback for the court domain
    if domain.lower() == "rbc.gov.il":
        return ["rbc-gov-il.mail.protection.outlook.com"]
    return []


def build_message(to_email, subject, text):
    today = dt.date.today().strftime("%d/%m/%Y")
    plain = (f"בית הדין הרבני האזורי {COURT_NAME}\n" + "-"*40 + "\n" +
             f"תאריך: {today}\n" + "-"*40 + "\n\n" + text +
             "\n\n" + "-"*40 + f"\nבית הדין הרבני האזורי {COURT_NAME}\n{SENDER}")
    body_html = "<br>".join(_html.escape(l) for l in text.split("\n"))
    html = f"""<!DOCTYPE html><html dir="rtl" lang="he"><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;font-size:14px;color:#222;direction:rtl;">
<table width="600" cellpadding="0" cellspacing="0" style="margin:20px auto;border:1px solid #ccc;">
<tr><td style="background:#1a3a5c;color:#fff;padding:16px;text-align:center;">
<div style="font-size:18px;font-weight:bold;">בית הדין הרבני האזורי</div>
<div style="font-size:16px;">{_html.escape(COURT_NAME)}</div></td></tr>
<tr><td style="padding:12px 20px;background:#f5f7fa;border-bottom:1px solid #ddd;font-size:13px;color:#555;">
<div>תאריך: {today}</div></td></tr>
<tr><td style="padding:20px;line-height:1.7;">{body_html}</td></tr>
<tr><td style="padding:16px;text-align:center;background:#f5f7fa;border-top:1px solid #ddd;font-size:12px;color:#888;">
בית הדין הרבני האזורי {_html.escape(COURT_NAME)} &nbsp;|&nbsp; {SENDER}</td></tr>
</table></body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"]    = subject
    msg["From"]       = f"בית הדין הרבני האזורי {COURT_NAME} <{SENDER}>"
    msg["To"]         = to_email
    msg["Date"]       = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="rbc.gov.il")
    msg["X-Mailer"]   = "ShiraAI"
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html,  "html",  "utf-8"))
    return msg


def send_direct(to_email, subject, text):
    domain = to_email.split("@", 1)[1]
    mxs = mx_lookup(domain)
    print(f"  MX for {domain}: {mxs}")
    if not mxs:
        print("  [FAIL] no MX found")
        return False

    msg = build_message(to_email, subject, text)

    last_err = None
    for mx in mxs:
        print(f"\n  --- trying MX {mx}:25 directly (from this server) ---")
        try:
            srv = smtplib.SMTP(mx, 25, timeout=25)
            srv.set_debuglevel(1)
            srv.ehlo(HELO_NAME)
            if srv.has_extn("starttls"):
                srv.starttls()
                srv.ehlo(HELO_NAME)
                print("  (STARTTLS negotiated)")
            srv.mail(SENDER)
            code, resp = srv.rcpt(to_email)
            print(f"  RCPT -> {code} {resp}")
            srv.data(msg.as_bytes())
            srv.quit()
            print(f"\n  [OK] accepted by {mx}")
            print(f"  -> check the INBOX of {to_email} (and quarantine, to compare)")
            return True
        except Exception as e:
            last_err = e
            print(f"  [FAIL on {mx}] {e}")
    print(f"\n  All MX attempts failed. Last error: {last_err}")
    print("  (If it's a timeout/refused: this server's outbound port 25")
    print("   is firewalled — only the relay may send out. Tell me and")
    print("   we switch to the admin-allowlist or authenticated-send fix.)")
    return False


if __name__ == "__main__":
    to = sys.argv[1] if len(sys.argv) > 1 else "elchanans@rbc.gov.il"
    print("=" * 64)
    print("  Direct-to-MX send (SPF-authorised path, no relay)")
    print("=" * 64)
    print(f"  From   : {SENDER}")
    print(f"  To     : {to}")
    subject = "הודעה מבית הדין הרבני — בדיקת מסירה ישירה"
    text = ("שלום רב,\n\n"
            "זוהי הודעת בדיקה הנשלחת ישירות משרת בית הדין.\n"
            "אם הודעה זו הגיעה לתיבת הדואר הנכנס (ולא להסגר) — הפתרון עובד.\n\n"
            "בברכה,\nבית הדין הרבני")
    send_direct(to, subject, text)
    print("=" * 64)
