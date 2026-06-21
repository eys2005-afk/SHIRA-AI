"""
find_mail.py — discover how the court can send email (no email is sent).
=======================================================================
Investigates, from the Shira server itself:
  1. MX records for the court mail domains (via nslookup)
  2. Which SMTP endpoints are reachable (candidate relays x ports 25/587/465)
  3. For each open one: the SMTP greeting + ESMTP features (AUTH? STARTTLS?
     does it look like an open internal relay?)

It does NOT send any email. It only opens a connection and says EHLO.

Run:
    python find_mail.py > mail.txt 2>&1
    type mail.txt
"""
import sys, io, socket, smtplib, subprocess, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

DOMAINS = ["rbc.gov.il", "gov.il"]
PORTS   = [25, 587, 465]

# Common internal relay names to try, plus per-domain guesses
BASE_HOSTS = [
    "localhost", "127.0.0.1",
    "smtp", "mail", "exchange", "mailrelay", "smtprelay", "relay",
]
def domain_hosts(d):
    return [f"smtp.{d}", f"mail.{d}", f"smtprelay.{d}", f"relay.{d}",
            f"mailgw.{d}", f"mx.{d}"]

def mx_lookup(domain):
    """Use Windows nslookup to find MX hosts."""
    hosts = []
    try:
        out = subprocess.run(["nslookup", "-type=mx", domain],
                             capture_output=True, text=True, timeout=15).stdout
        # lines like:  rbc.gov.il   MX preference = 10, mail exchanger = mail.x.y
        for m in re.finditer(r'mail exchanger\s*=\s*([^\s]+)', out):
            hosts.append(m.group(1).strip().rstrip('.'))
        print(f"  MX[{domain}]: {hosts if hosts else '(none found)'}")
        if not hosts and out.strip():
            print("    raw nslookup:")
            for line in out.splitlines():
                if line.strip():
                    print("      " + line.strip())
    except Exception as e:
        print(f"  MX[{domain}] lookup error: {e}")
    return hosts

def tcp_open(host, port, timeout=4):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False

def probe_smtp(host, port):
    """Connect, EHLO, return greeting + features. No mail sent."""
    try:
        if port == 465:
            srv = smtplib.SMTP_SSL(host, port, timeout=6)
        else:
            srv = smtplib.SMTP(host, port, timeout=6)
        greeting = srv.ehlo()
        feats = dict(srv.esmtp_features) if hasattr(srv, "esmtp_features") else {}
        has_auth     = "auth" in feats
        has_starttls = "starttls" in feats
        srv.quit()
        return {
            "greeting": str(greeting)[:160],
            "auth": has_auth,
            "starttls": has_starttls,
            "features": list(feats.keys()),
        }
    except Exception as e:
        return {"error": str(e)[:160]}

def main():
    print("=" * 60)
    print("  Court mail discovery (no email is sent)")
    print("=" * 60)

    print("\n[1] MX records")
    mx_hosts = []
    for d in DOMAINS:
        mx_hosts += mx_lookup(d)

    # Build candidate host list
    candidates = []
    for h in BASE_HOSTS:
        candidates.append(h)
    for d in DOMAINS:
        candidates += domain_hosts(d)
    candidates += mx_hosts
    # de-dup preserve order
    seen = set(); hosts = []
    for h in candidates:
        if h and h not in seen:
            seen.add(h); hosts.append(h)

    print(f"\n[2] Testing {len(hosts)} hosts x {len(PORTS)} ports (TCP connect)")
    open_eps = []
    for h in hosts:
        for p in PORTS:
            if tcp_open(h, p):
                open_eps.append((h, p))
                print(f"   OPEN  {h}:{p}")
    if not open_eps:
        print("   (no SMTP endpoints reachable)")

    print(f"\n[3] EHLO probe of open endpoints (still no mail sent)")
    for h, p in open_eps:
        info = probe_smtp(h, p)
        print(f"\n   --- {h}:{p} ---")
        if "error" in info:
            print(f"     error: {info['error']}")
            continue
        print(f"     greeting : {info['greeting']}")
        print(f"     AUTH     : {info['auth']}   STARTTLS: {info['starttls']}")
        print(f"     features : {info['features']}")
        if not info["auth"]:
            print("     >>> No AUTH required — possible open internal relay (good for us)")

    print("\n" + "=" * 60)
    print("  Done. Look for an OPEN endpoint with 'No AUTH required',")
    print("  or one with AUTH that we can log into with a court mailbox.")
    print("=" * 60)

if __name__ == "__main__":
    main()
