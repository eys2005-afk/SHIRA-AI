"""
Phase A — Step 1: Connect to Shira and verify authentication.
Run this first. If it prints OK for auth, we can proceed.

Run:
    python phase_a_step1.py
"""

import os
import requests
from requests_negotiate_sspi import HttpNegotiateAuth
import re

# Bypass proxy for internal servers — same as shira_proxy.py
os.environ['NO_PROXY'] = 'shira2,prod-spfe,localhost,127.0.0.1'
os.environ['no_proxy'] = 'shira2,prod-spfe,localhost,127.0.0.1'

SHIRA = "http://shira2"
SPFE  = "http://prod-spfe:1000"

def make_session():
    s = requests.Session()
    s.auth = HttpNegotiateAuth()
    s.trust_env = False
    s.proxies = {}        # explicitly clear all proxies
    s.verify = False
    return s

def main():
    print("=" * 50)
    print("Step 1 — Connecting to Shira")
    print("=" * 50)

    session = make_session()

    # Test 1: Basic connectivity — use a URL we know exists
    print("\n[1] Basic connectivity to Shira...")
    try:
        r = session.get(
            f"{SHIRA}/classic/Forms/File/Request/FileRequest.aspx"
            f"?FileRequestID=0&FileID=2923739",
            timeout=10
        )
        print(f"    Status  : {r.status_code}")
        print(f"    URL     : {r.url}")
        print(f"    Content-Type: {r.headers.get('Content-Type','?')}")
        print(f"    First 300 chars of response:")
        print(f"    {r.text[:300]}")
        if r.status_code == 200:
            print("    ✅ Shira reachable and authenticated")
        elif r.status_code == 401:
            print("    ❌ Authentication failed (401)")
            return
        else:
            print(f"    ⚠️  Unexpected status {r.status_code}")
    except Exception as e:
        print(f"    ❌ Cannot reach Shira: {e}")
        return

    # Test 2: Check WsShiraUtils WSDL — lists all available web service methods
    print("\n[2] Checking WsShiraUtils web service methods...")
    try:
        r = session.get(
            f"{SHIRA}/classic/WS/App/WsShiraUtils.asmx?WSDL",
            timeout=10,
        )
        print(f"    Status : {r.status_code}")
        if r.status_code == 200:
            ops = re.findall(r'<operation name="([^"]+)"', r.text)
            print(f"    Found {len(ops)} operations.")
            # Show document-related ones
            doc_ops = [o for o in ops if any(k in o.lower() for k in
                       ["doc", "create", "add", "insert", "upload", "import", "scan", "postal", "send"])]
            print(f"    Document/send-related operations:")
            for op in doc_ops:
                print(f"      - {op}")
            if not doc_ops:
                print("      (none found — showing first 20 instead)")
                for op in ops[:20]:
                    print(f"      - {op}")
            print("    ✅ WsShiraUtils accessible")
        else:
            print(f"    ❌ Status {r.status_code}")
    except Exception as e:
        print(f"    ❌ Failed: {e}")

    # Test 3: SPFE document service
    print("\n[3] Checking SPFE document service...")
    try:
        r = session.get(f"{SPFE}/ShiraDocsMngWS.asmx", timeout=5)
        print(f"    Status : {r.status_code}")
        if r.status_code == 200:
            print("    ✅ SPFE reachable")
        else:
            print(f"    ⚠️  Status {r.status_code}")
    except Exception as e:
        print(f"    ❌ Cannot reach SPFE: {e}")

    # Test 4: UNC path access
    print("\n[4] Checking UNC path write access...")
    import os, getpass
    username = getpass.getuser()
    unc_path = f"\\\\Prod-nas1\\filer$\\Root\\Data\\Users\\{username}\\ScanDocuments\\Temp"
    print(f"    Path   : {unc_path}")
    try:
        if os.path.exists(unc_path):
            # Try writing a test file
            test_file = os.path.join(unc_path, "_shira_msg_test.txt")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            print("    ✅ Write access confirmed")
        else:
            print("    ❌ Path does not exist or not accessible")
    except Exception as e:
        print(f"    ❌ Write test failed: {e}")

    print("\n" + "=" * 50)
    print("Done. Share the output and we proceed to step 2.")
    print("=" * 50)

if __name__ == "__main__":
    main()
