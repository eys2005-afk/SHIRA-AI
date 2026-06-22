"""
test_ports.py — which outbound mail paths can this server reach?
================================================================
Port 25 direct to O365 is firewalled. Check the alternatives:
  * 587 (authenticated submission)  -> the clean permanent fix
  * 465 (implicit TLS submission)
  * the relay on other ports
This only opens a TCP connection. No mail is sent.

Run:
    python test_ports.py
"""
import sys, io, socket
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ENDPOINTS = [
    # Authenticated submission (the path we want if 25 is blocked)
    ("smtp.office365.com",                     587),
    ("smtp.office365.com",                     25),
    ("smtp-mail.outlook.com",                  587),
    ("outlook.office365.com",                  587),
    # O365 MX directly (already known-blocked on 25, retest for the record)
    ("rbc-gov-il.mail.protection.outlook.com", 25),
    ("rbc-gov-il.mail.protection.outlook.com", 587),
    # The internal relay on alternate ports
    ("mail.rbc.gov.il",                        25),
    ("mail.rbc.gov.il",                        587),
    ("mail.rbc.gov.il",                        465),
    ("mail.rbc.gov.il",                        2525),
]

def check(host, port, timeout=6):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception as e:
        return str(e)

def main():
    print("=" * 60)
    print("  Outbound mail-port reachability (no mail sent)")
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
    if any(p == 587 for _, p in open_paths):
        print("  >>> Port 587 is reachable — authenticated submission is")
        print("      possible. We need a court mailbox + app password.")
    elif open_paths:
        print(f"  >>> Only these are reachable: {open_paths}")
        print("      Likely the relay is the ONLY way out -> needs an")
        print("      Exchange-admin allowlist, or use Option A.")
    else:
        print("  >>> Nothing reachable (unexpected).")
    print("=" * 60)

if __name__ == "__main__":
    main()
