"""
Phase A — Step 1: Connect to Shira and verify authentication.
Run this first. If it prints the user info, auth works and we can proceed.

Run:
    python phase_a_step1.py
"""

import requests
from requests_negotiate_sspi import HttpNegotiateAuth

SHIRA = "http://shira2"

def make_session():
    s = requests.Session()
    s.auth = HttpNegotiateAuth()
    s.headers.update({
        "Content-Type": "application/json; charset=UTF-8",
        "Origin": SHIRA,
    })
    s.proxies = {"http": None, "https": None}
    s.verify = False
    return s

def main():
    print("=" * 50)
    print("Step 1 — Connecting to Shira")
    print("=" * 50)

    session = make_session()

    # Test 1: Get current user
    print("\n[1] Fetching logged-in user...")
    try:
        r = session.get(f"{SHIRA}/api/api/userController/GetUser", timeout=10)
        r.raise_for_status()
        d = r.json()
        user_id    = d.get("userId")
        user_name  = d.get("userName")
        first_name = d.get("firstName", "")
        last_name  = d.get("lastName", "")
        courts     = d.get("courtList", [])
        court_id   = courts[0]["courtId"] if courts else None
        court_name = courts[0].get("courtName", "") if courts else ""
        print(f"    User   : {first_name} {last_name} ({user_name})")
        print(f"    UserID : {user_id}")
        print(f"    Court  : {court_name} (ID={court_id})")
        print("    ✅ Authentication OK")
    except Exception as e:
        print(f"    ❌ Failed: {e}")
        return

    # Test 2: Check SPFE connectivity
    print("\n[2] Checking SPFE document service...")
    SPFE = "http://prod-spfe:1000"
    try:
        r = session.get(f"{SPFE}/ShiraDocsMngWS.asmx", timeout=5)
        print(f"    Status : {r.status_code}")
        if r.status_code == 200:
            print("    ✅ SPFE reachable")
        else:
            print("    ⚠️  Unexpected status — check manually")
    except Exception as e:
        print(f"    ❌ Failed: {e}")

    # Test 3: Check WsShiraUtils WSDL (to discover available methods)
    print("\n[3] Checking WsShiraUtils web service...")
    try:
        r = session.get(
            f"{SHIRA}/classic/WS/App/WsShiraUtils.asmx?WSDL",
            timeout=10,
            headers={"Content-Type": "text/html"}
        )
        print(f"    Status : {r.status_code}")
        if "wsdl" in r.text.lower() or "definitions" in r.text.lower():
            # Extract operation names
            import re
            ops = re.findall(r'<operation name="([^"]+)"', r.text)
            print(f"    Found {len(ops)} operations:")
            for op in ops[:30]:
                print(f"      - {op}")
            if len(ops) > 30:
                print(f"      ... and {len(ops)-30} more")
            print("    ✅ WsShiraUtils reachable")
        else:
            print("    ⚠️  WSDL not returned — service may require different auth")
    except Exception as e:
        print(f"    ❌ Failed: {e}")

    print("\n" + "=" * 50)
    print("Done. If all checks passed, run phase_a_step2.py next.")
    print("=" * 50)

if __name__ == "__main__":
    main()
