"""
test_gmail_ports.py — can this server reach Gmail's SMTP to send authenticated?
==============================================================================
The relay delivers our Gmail-From mail to SPAM (SPF fails for gmail.com).
The clean fix is to send through GMAIL'S OWN server with an App Password,
so Gmail DKIM-signs it -> SPF+DKIM+DMARC pass -> recipient INBOX.

This only checks if the ports are reachable. No mail is sent.

Run:
    python test_gmail_ports.py
"""
import sys, io, socket
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ENDPOINTS = [
    ("smtp.gmail.com", 587),   # STARTTLS submission (preferred)
    ("smtp.gmail.com", 465),   # implicit TLS submission
    ("smtp.gmail.com", 25),
]

def check(host, port, timeout=6):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception as e:
        return str(e)

def main():
    print("=" * 60)
    print("  Gmail SMTP reachability (no mail sent)")
    print("=" * 60)
    open_paths = []
    for host, port in ENDPOINTS:
        r = check(host, port)
        if r is True:
            print(f"  OPEN     {host}:{port}")
            open_paths.append((host, port))
        else:
            print(f"  blocked  {host}:{port}   ({r[:50]})")
    print("-" * 60)
    if open_paths:
        print("  >>> Gmail SMTP is reachable. We can send AUTHENTICATED")
        print("      through Gmail (App Password) -> lands in INBOX, signed.")
    else:
        print("  >>> Gmail SMTP is blocked too. Then the only path is the")
        print("      relay (spam) or Option A (Shira's own postal).")
    print("=" * 60)

if __name__ == "__main__":
    main()
