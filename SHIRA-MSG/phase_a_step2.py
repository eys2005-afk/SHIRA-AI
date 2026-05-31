"""
Phase A — Step 2  (v6)
Discover how to create a document record in Shira.
Run AFTER step 1 passes.

Run:
    python phase_a_step2.py
"""

VERSION = "v6"

import os, re
import requests
from requests_negotiate_sspi import HttpNegotiateAuth
from bs4 import BeautifulSoup

os.environ['NO_PROXY'] = 'shira2,prod-spfe,localhost,127.0.0.1'
os.environ['no_proxy'] = 'shira2,prod-spfe,localhost,127.0.0.1'

SHIRA   = "http://shira2"
SPFE    = "http://prod-spfe:1000"
FILE_ID = "2923739"

def make_shira_session():
    """Session for shira2 — NTLM auth, no proxy. Do NOT pass proxies= per-request (breaks NTLM handshake)."""
    s = requests.Session()
    s.auth      = HttpNegotiateAuth()
    s.trust_env = False
    s.proxies   = {}
    s.verify    = False
    return s

def make_spfe_session():
    """Session for SPFE — no auth needed, no proxy."""
    s = requests.Session()
    s.trust_env = False
    s.proxies   = {}
    s.verify    = False
    return s

def main():
    print(f"=== Step 2 {VERSION} ===")

    shira = make_shira_session()
    spfe  = make_spfe_session()

    # ── B: Load IframeFromMyComputerDocument.aspx ─────────────────────────────
    print(f"\n[B] Loading IframeFromMyComputerDocument.aspx...")
    iframe_url = (
        f"{SHIRA}/classic/Forms/Documents/Scan/IframeFromMyComputerDocument.aspx"
        f"?FileID={FILE_ID}&EntityTypeID=6&EntityID={FILE_ID}&DocumentID=0"
    )
    try:
        r = shira.get(iframe_url, timeout=15)
        print(f"    Status  : {r.status_code}")
        soup = BeautifulSoup(r.text, "html.parser")

        hidden = {i["name"]: i.get("value","")
                  for i in soup.find_all("input", type="hidden") if i.get("name")}
        print("    Hidden fields:")
        for k, v in hidden.items():
            print(f"      {k} = {(v[:70]+'...') if len(v)>70 else v}")

        file_inputs = soup.find_all("input", type="file")
        print(f"    File inputs : {[f.get('name') for f in file_inputs]}")

        form = soup.find("form")
        if form:
            print(f"    Form action : {form.get('action','(none)')}")

        doc_ids = re.findall(r'DocumentID[=\s:\'\"]+(\d+)', r.text)
        print(f"    DocumentIDs in page: {doc_ids}")

        if hidden.get("__VIEWSTATE"):
            print("    ✅ Page loaded with VIEWSTATE — can POST file here")
        else:
            print("    ⚠️  No VIEWSTATE")
    except Exception as e:
        print(f"    ❌ {e}")

    # ── C: WsShiraUtils WSDL ──────────────────────────────────────────────────
    print("\n[C] Checking WsShiraUtils WSDL...")
    try:
        r = shira.get(f"{SHIRA}/classic/WS/App/WsShiraUtils.asmx?WSDL", timeout=15)
        print(f"    Status : {r.status_code}")
        print(f"    Length : {len(r.text)} chars")
        ops = re.findall(r'<operation name="([^"]+)"', r.text)
        print(f"    Operations found: {len(ops)}")
        if ops:
            for op in ops:
                print(f"      - {op}")
        else:
            print(f"    First 500 chars:\n    {r.text[:500]}")
    except Exception as e:
        print(f"    ❌ {e}")

    # ── A: SPFE ImportDocument ────────────────────────────────────────────────
    print("\n[A] Testing SPFE ImportDocument endpoint...")
    try:
        r = spfe.post(
            f"{SPFE}/ShiraDocsMngWS.asmx/ImportDocument",
            data="{'fileUrl':'test', 'shiraDocId':'0', 'courtId':'5', 'isReadOnly':'false'}",
            headers={"Content-Type": "application/json"},
            timeout=15)
        print(f"    Status  : {r.status_code}")
        print(f"    Response: {r.text[:200]}")
        if r.status_code == 200:
            print("    ✅ SPFE ImportDocument endpoint reachable")
        else:
            print("    ⚠️  Check response above")
    except Exception as e:
        print(f"    ❌ {e}")

    print("\n=== Done — share this output ===")

if __name__ == "__main__":
    main()
