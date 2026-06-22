"""
option_b_replica_send.py — Option B that is IDENTICAL to a real case message.
=============================================================================
Sends the EXACT official body (see official_replica.py) with the same subject
and the case document(s) attached — the recipient sees the same email a real
case-postal message produces.

Sender options:
  * SHIRA_SEND_MODE=relay   (default) — send Gmail-From through the court
        relay mail.rbc.gov.il:25. Delivered, but may land in SPAM (SPF for
        gmail.com doesn't cover the relay).
  * SHIRA_SEND_MODE=gmail   — send AUTHENTICATED through smtp.gmail.com:587
        with an App Password -> DKIM-signed -> recipient INBOX.

Env vars:
    set SHIRA_UNOFFICIAL_FROM=shirabeitdinrehovot@gmail.com
    set SHIRA_REPLYTO=rehovot@rbc.gov.il
    set SHIRA_SEND_MODE=gmail              (or relay)
    set SHIRA_GMAIL_APP_PASS=<16-char app password>   (only for gmail mode)

Usage:
    python option_b_replica_send.py <recipient> [attachment1] [attachment2] ...
"""
import sys, io, os, smtplib
from official_replica import build_message, SUBJECT

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

FROM_ADDR = os.environ.get("SHIRA_UNOFFICIAL_FROM", "")
REPLYTO   = os.environ.get("SHIRA_REPLYTO", "")
SEND_MODE = os.environ.get("SHIRA_SEND_MODE", "relay").lower()
GMAIL_APP_PASS = os.environ.get("SHIRA_GMAIL_APP_PASS", "")
RELAY     = os.environ.get("SHIRA_RELAY", "mail.rbc.gov.il")
RELAY_PORT = int(os.environ.get("SHIRA_RELAY_PORT", "25"))

# --- Test case data (replace with real case data when wiring into ShiraAI) ---
COURT_NAME   = os.environ.get("SHIRA_COURT", "רחובות")
CASE_NUMBERS = os.environ.get("SHIRA_CASE_NUMBERS", "1466141/3")
CASE_SUBJECT = os.environ.get("SHIRA_CASE_SUBJECT", "חלוקת רכוש - כריכה")
SIDE_A       = os.environ.get("SHIRA_SIDE_A", "סמדר סאלם")
SIDE_B       = os.environ.get("SHIRA_SIDE_B", "אהרון סאלם")


def send(to_email, attachments):
    msg = build_message(
        from_addr=FROM_ADDR, to_email=to_email, court_name=COURT_NAME,
        case_numbers=CASE_NUMBERS, case_subject=CASE_SUBJECT,
        side_a=SIDE_A, side_b=SIDE_B, attachments=attachments,
        display_name=f"בית הדין הרבני האזורי {COURT_NAME}", reply_to=REPLYTO,
    )
    if SEND_MODE == "gmail":
        if not GMAIL_APP_PASS:
            return {"ok": False, "error": "gmail mode needs SHIRA_GMAIL_APP_PASS"}
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=25) as s:
            s.ehlo(); s.starttls(); s.ehlo()
            s.login(FROM_ADDR, GMAIL_APP_PASS)
            s.sendmail(FROM_ADDR, [to_email], msg.as_bytes())
        return {"ok": True, "via": "smtp.gmail.com:587 (signed)",
                "messageId": msg["Message-ID"]}
    else:
        with smtplib.SMTP(RELAY, RELAY_PORT, timeout=25) as s:
            s.ehlo()
            s.sendmail(FROM_ADDR, [to_email], msg.as_bytes())
        return {"ok": True, "via": f"{RELAY}:{RELAY_PORT} (relay, may be spam)",
                "messageId": msg["Message-ID"]}


if __name__ == "__main__":
    to = sys.argv[1] if len(sys.argv) > 1 else "elchanans@rbc.gov.il"
    attachments = sys.argv[2:]
    print("=" * 64)
    print("  Option B — EXACT replica of a real case message")
    print("=" * 64)
    print(f"  Mode      : {SEND_MODE}")
    print(f"  From      : {FROM_ADDR or '(NOT SET)'}")
    print(f"  Shown as  : בית הדין הרבני האזורי {COURT_NAME}")
    print(f"  Reply-To  : {REPLYTO or '(none)'}")
    print(f"  Subject   : {SUBJECT}")
    print(f"  To        : {to}")
    print(f"  Attach    : {attachments or '(none)'}")
    if not FROM_ADDR:
        print("\n  [!] set SHIRA_UNOFFICIAL_FROM first.")
        sys.exit(1)
    res = send(to, attachments)
    if res["ok"]:
        print(f"\n  [OK] sent via {res['via']}")
        print(f"  Message-ID: {res['messageId']}")
        print(f"  -> check INBOX (and Spam) of {to}")
    else:
        print(f"\n  [FAIL] {res['error']}")
    print("=" * 64)
