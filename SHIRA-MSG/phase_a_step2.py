"""
Phase A — Step 2  (v9)
Read the JS file that handles the actual file upload logic.
"""
VERSION = "v9"

import os, re
import requests
from requests_negotiate_sspi import HttpNegotiateAuth

os.environ['NO_PROXY'] = 'shira2,prod-spfe,localhost,127.0.0.1'
os.environ['no_proxy'] = 'shira2,prod-spfe,localhost,127.0.0.1'

SHIRA = "http://shira2"

def make_session():
    s = requests.Session()
    s.auth      = HttpNegotiateAuth()
    s.trust_env = False
    s.proxies   = {}
    s.verify    = False
    return s

def main():
    print(f"=== Step 2 {VERSION} ===")
    session = make_session()

    # Fetch the JS file that handles the upload
    js_url = f"{SHIRA}/classic/forms/documents/scan/iframefrommycomputerdocument.js"
    print(f"\n[JS] Fetching {js_url}...")
    try:
        r = session.get(js_url, timeout=15)
        print(f"    Status : {r.status_code}  ({len(r.text)} chars)")
        if r.status_code == 200:
            print(f"\n--- Full JS content ---")
            print(r.text)
            print(f"--- End ---")
        else:
            print(r.text[:500])
    except Exception as e:
        print(f"    ❌ {e}")

    print("\n=== Done ===")

if __name__ == "__main__":
    main()
