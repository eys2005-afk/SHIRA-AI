"""
test_send_email.py — verify that mail.rbc.gov.il:25 delivers outbound email.
=============================================================================
Sends ONE real test email through the open internal relay.
No Shira document is created. No auth required.

Usage:
    python test_send_email.py <to_address>

Example:
    python test_send_email.py elchanans@rbc.gov.il
"""
import sys, io, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

RELAY   = "mail.rbc.gov.il"
PORT    = 25
SENDER  = "no-reply@rbc.gov.il"
DOMAIN  = "rbc.gov.il"

def send_test(to_addr: str):
    subject = "בדיקת שליחה - ShiraAI"
    body_he = (
        "שלום,\n\n"
        "זוהי הודעת בדיקה שנשלחה ממערכת ShiraAI.\n\n"
        "פרטי שליחה:\n"
        f"  מועד: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        f"  שרת: {RELAY}:{PORT}\n"
        f"  שולח: {SENDER}\n"
        f"  נמען: {to_addr}\n\n"
        "אם קיבלת הודעה זו, ממסר הדואר הפנימי עובד כהלכה.\n\n"
        "בית הדין הרבני\n"
        "מערכת ShiraAI"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"]    = subject
    msg["From"]       = f"בית הדין הרבני <{SENDER}>"
    msg["To"]         = to_addr
    msg["Date"]       = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=DOMAIN)
    msg.attach(MIMEText(body_he, "plain", "utf-8"))

    print("=" * 60)
    print("  ShiraAI — test email via open internal relay")
    print("=" * 60)
    print(f"  Relay  : {RELAY}:{PORT}")
    print(f"  From   : {SENDER}")
    print(f"  To     : {to_addr}")
    print(f"  Subject: {subject}")
    print()

    try:
        with smtplib.SMTP(RELAY, PORT, timeout=10) as srv:
            srv.set_debuglevel(1)          # show SMTP conversation
            greeting = srv.ehlo(DOMAIN)
            print(f"\n  EHLO response: {greeting}")
            srv.sendmail(SENDER, [to_addr], msg.as_bytes())
        print("\n  [OK] sendmail() returned without error — message accepted by relay.")
        print("  Check the inbox of", to_addr)
    except smtplib.SMTPRecipientsRefused as e:
        print(f"\n  [FAIL] Recipient refused: {e}")
        print("  The relay may be filtering outbound destinations.")
    except smtplib.SMTPSenderRefused as e:
        print(f"\n  [FAIL] Sender refused: {e}")
        print("  Try a different From address.")
    except smtplib.SMTPException as e:
        print(f"\n  [FAIL] SMTP error: {e}")
    except Exception as e:
        print(f"\n  [FAIL] Connection error: {e}")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_send_email.py <to_address>")
        print("Example: python test_send_email.py elchanans@rbc.gov.il")
        sys.exit(1)
    send_test(sys.argv[1])
