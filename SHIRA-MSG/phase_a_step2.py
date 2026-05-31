"""
Phase A — Step 2: Discover how to create a document record in Shira.
Run AFTER step 1 passes.

Run:
    python phase_a_step2.py
"""

import os
import requests
from requests_negotiate_sspi import HttpNegotiateAuth
from bs4 import BeautifulSoup
import re

os.environ['NO_PROXY'] = 'shira2,prod-spfe,localhost,127.0.0.1'
os.environ['no_proxy'] = 'shira2,prod-spfe,localhost,127.0.0.1'

SHIRA   = "http://shira2"
NO_PRXY = {}   # passed to every request to force no-proxy

FILE_ID = "2923739"   # test case FileID

def make_session():
    s = requests.Session()
    s.auth = HttpNegotiateAuth()
    s.headers.update({"Origin": SHIRA})
    s.trust_env = False
    s.proxies = {}
    s.verify = False
    return s

def get(session, url, **kwargs):
    """Wrapper that always passes proxies={} to bypass system proxy."""
    return session.get(url, proxies=NO_PRXY, timeout=15, **kwargs)

def main():
    print("=" * 50)
    print("Step 2 — Discovering document creation endpoint")
    print("=" * 50)

    session = make_session()

    # Test A: WsShiraUtils WSDL — look for document-creation methods
    print("\n[A] Searching WsShiraUtils for document-creation methods...")
    try:
        r = get(session, f"{SHIRA}/classic/WS/App/WsShiraUtils.asmx?WSDL")
        print(f"    Status: {r.status_code}")
        ops = re.findall(r'<operation name="([^"]+)"', r.text)
        print(f"    Total operations found: {len(ops)}")
        doc_ops = [o for o in ops if any(k in o.lower() for k in
                   ["doc", "create", "add", "insert", "upload", "import", "scan"])]
        if doc_ops:
            print("    Relevant operations:")
            for op in doc_ops:
                print(f"      - {op}")
        elif ops:
            print("    No doc-related ops — showing all:")
            for op in ops:
                print(f"      - {op}")
        else:
            print("    No operations found in WSDL")
    except Exception as e:
        print(f"    ❌ {e}")

    # Test B: Load UploadScanDocument.aspx and inspect its form fields
    print(f"\n[B] Loading UploadScanDocument.aspx for FileID={FILE_ID}...")
    upload_url = (
        f"{SHIRA}/classic/Forms/Documents/Scan/UploadScanDocument.aspx"
        f"?FileID={FILE_ID}&EntityTypeID=6&EntityID={FILE_ID}&DocumentID=0"
    )
    try:
        r = get(session, upload_url)
        print(f"    Status: {r.status_code}")
        soup = BeautifulSoup(r.text, "html.parser")

        hidden = {i["name"]: i.get("value","")
                  for i in soup.find_all("input", type="hidden") if i.get("name")}
        print("    Hidden fields:")
        for k, v in hidden.items():
            print(f"      {k} = {(v[:60]+'...') if len(v)>60 else v}")

        file_inputs = soup.find_all("input", type="file")
        print(f"    File inputs: {[f.get('name') for f in file_inputs]}")

        form = soup.find("form")
        if form:
            print(f"    Form action : {form.get('action','(none)')}")
            print(f"    Form method : {form.get('method','(none)')}")

        if hidden.get("__VIEWSTATE"):
            print("    ✅ Form loaded — has VIEWSTATE")
        else:
            print("    ⚠️  No VIEWSTATE")

    except Exception as e:
        print(f"    ❌ Failed: {e}")

    # Test C: Probe Shira REST API for document endpoints
    print("\n[C] Probing Shira REST API for document endpoints...")
    candidates = [
        "/api/api/Document/CreateDocument",
        "/api/api/Document/AddDocument",
        "/api/api/FileDocument/Create",
        "/api/api/Documents/Upload",
    ]
    for url in candidates:
        try:
            r = get(session, f"{SHIRA}{url}")
            print(f"    {url} → {r.status_code}")
        except Exception as e:
            print(f"    {url} → Error: {e}")

    print("\n" + "=" * 50)
    print("Done. Share the output and we move to step 3.")
    print("=" * 50)

if __name__ == "__main__":
    main()
