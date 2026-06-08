"""
Phase A — Step 2  (v12)
Fetch iframefrommycomputerdocument.js to find the real save endpoint.
Also try WsShiraUtils.asmx to see available methods.
"""
VERSION = "v12"

import os, re
import requests
from requests_negotiate_sspi import HttpNegotiateAuth

os.environ['NO_PROXY'] = 'shira2,prod-spfe,localhost,127.0.0.1'
os.environ['no_proxy'] = 'shira2,prod-spfe,localhost,127.0.0.1'

SHIRA   = "http://shira2"
FILE_ID = "2923739"

def make_session():
    s = requests.Session()
    s.auth      = HttpNegotiateAuth()
    s.trust_env = False
    s.proxies   = {}
    s.verify    = False
    return s

def main():
    print(f"=== Step 2 {VERSION} — discover real save endpoint ===")
    session = make_session()

    # ── 1: Fetch the JS file for the iframe form ───────────────────────────────
    js_url = f"{SHIRA}/classic/forms/documents/scan/iframefrommycomputerdocument.js"
    print(f"\n[1] Fetching JS: {js_url}")
    r = session.get(js_url, timeout=15)
    print(f"    Status: {r.status_code}  Length: {len(r.text)}")
    if r.status_code == 200:
        print("\n--- JS content ---")
        print(r.text[:8000])
        print("--- End JS ---")

    # ── 2: Try WsShiraUtils.asmx discovery ────────────────────────────────────
    ws_url = f"{SHIRA}/classic/WS/App/WsShiraUtils.asmx"
    print(f"\n[2] Fetching ASMX list: {ws_url}")
    r2 = session.get(ws_url, timeout=15)
    print(f"    Status: {r2.status_code}  Length: {len(r2.text)}")
    if r2.status_code == 200:
        # Find all method names
        methods = re.findall(r'<a href=[\'"](\w+)[\'"]', r2.text)
        print(f"    Methods: {methods[:30]}")
        print(r2.text[:3000])

    # ── 3: Also try WsShiraDocument.asmx ─────────────────────────────────────
    ws2_url = f"{SHIRA}/classic/WS/App/WsShiraDocument.asmx"
    print(f"\n[3] Trying WsShiraDocument.asmx: {ws2_url}")
    r3 = session.get(ws2_url, timeout=15)
    print(f"    Status: {r3.status_code}  Length: {len(r3.text)}")
    if r3.status_code == 200:
        methods3 = re.findall(r'<a href=[\'"](\w+)[\'"]', r3.text)
        print(f"    Methods: {methods3[:30]}")

    print("\n=== Done ===")

if __name__ == "__main__":
    main()
