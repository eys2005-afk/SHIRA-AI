"""
diagnose_spoof.py — find out WHY O365 quarantines our no-reply mail.
====================================================================
O365 (Exchange Online Protection) quarantines mail that claims to be
from rbc.gov.il but fails domain authentication. This script gathers
the exact policy so we can fix it:

  1. SPF record for rbc.gov.il  -> which servers MAY send as the domain
  2. DMARC policy              -> what O365 does on auth failure
  3. DKIM selectors            -> is the domain set up to sign mail?
  4. This server's public IP   -> is it allowed by SPF?
  5. A DSN-tracked test send   -> delivery receipt to a READABLE inbox

Run on the COURT SERVER:
    python diagnose_spoof.py > spoof.txt 2>&1
    type spoof.txt
"""
import sys, io, subprocess, smtplib
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
import datetime as dt

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

DOMAIN   = "rbc.gov.il"
RELAY    = "mail.rbc.gov.il"
PORT     = 25
# A REAL, readable mailbox — bounces / delivery receipts land here:
READABLE = "elchanans@rbc.gov.il"


def nslookup_txt(name):
    try:
        out = subprocess.run(["nslookup", "-type=txt", name],
                             capture_output=True, text=True, timeout=15).stdout
        lines = [l.strip() for l in out.splitlines()
                 if "text =" in l.lower() or "=\"" in l or '"' in l]
        return lines or [l.strip() for l in out.splitlines() if l.strip()]
    except Exception as e:
        return [f"(lookup error: {e})"]


def main():
    print("=" * 64)
    print("  Diagnose O365 anti-spoof quarantine")
    print("=" * 64)

    print(f"\n[1] SPF record for {DOMAIN}")
    print("    (lists the servers ALLOWED to send mail as @rbc.gov.il)")
    for l in nslookup_txt(DOMAIN):
        if "spf" in l.lower() or "include:" in l.lower() or "v=spf" in l.lower():
            print("    >>> " + l)
        else:
            print("        " + l)

    print(f"\n[2] DMARC policy  (_dmarc.{DOMAIN})")
    print("    (p=reject / p=quarantine / p=none -> what O365 does on failure)")
    for l in nslookup_txt(f"_dmarc.{DOMAIN}"):
        print("    " + l)

    print(f"\n[3] DKIM selectors  (is the domain configured to sign mail?)")
    for sel in ["selector1", "selector2", "default", "google", "s1", "s2",
                "k1", "betdin", "rbc", "shira", "mail", "dkim"]:
        recs = nslookup_txt(f"{sel}._domainkey.{DOMAIN}")
        hit  = [r for r in recs if "p=" in r or "DKIM" in r or "v=DKIM" in r.upper()]
        if hit:
            print(f"    FOUND selector '{sel}':")
            for r in hit:
                print("        " + r[:120])

    print(f"\n[4] This server's PUBLIC IP (what O365 sees)")
    try:
        import urllib.request
        ip = urllib.request.urlopen("https://api.ipify.org", timeout=8).read().decode()
        print(f"    public IP = {ip}")
        print(f"    -> if this IP is NOT in the SPF record above, SPF fails -> spoof")
    except Exception as e:
        print(f"    (could not determine public IP: {e})")

    print(f"\n[5] DSN-tracked test send (delivery receipt to {READABLE})")
    print(f"    Envelope sender = {READABLE} (so any bounce/receipt is READABLE)")
    try:
        msg = MIMEText("DSN-tracked diagnostic from ShiraAI.\n"
                       "If you received this, internal delivery works.\n"
                       f"Sent: {dt.datetime.now()}", "plain", "utf-8")
        msg["Subject"]    = "ShiraAI DSN test — please check inbox + quarantine"
        msg["From"]       = f"בית הדין הרבני <no-reply@{DOMAIN}>"
        msg["To"]         = READABLE
        msg["Date"]       = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain=DOMAIN)
        with smtplib.SMTP(RELAY, PORT, timeout=15) as srv:
            srv.set_debuglevel(1)
            srv.ehlo(DOMAIN)
            # envelope-from = readable mailbox; ask for full DSN
            srv.mail(READABLE, options=["RET=HDRS"])
            code, resp = srv.rcpt(READABLE, options=["NOTIFY=SUCCESS,FAILURE,DELAY"])
            print(f"    RCPT -> {code} {resp}")
            srv.data(msg.as_bytes())
        print("    [OK] queued with DSN tracking")
    except Exception as e:
        print(f"    [FAIL] {e}")

    print("\n" + "=" * 64)
    print("  NEXT: also send me the INTERNET HEADERS of:")
    print("   (a) a REAL no-reply@rbc.gov.il email that reached the INBOX")
    print("   (b) our QUARANTINED test email")
    print("  In OWA: open mail -> ... -> View -> View message details.")
    print("  The 'Authentication-Results' + 'X-Forefront-Antispam-Report'")
    print("  lines tell us exactly which check failed (spf/dkim/dmarc/compauth).")
    print("=" * 64)


if __name__ == "__main__":
    main()
