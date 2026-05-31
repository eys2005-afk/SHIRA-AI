"""
Phase A — Step 2: Discover how to create a document record in Shira.
This script probes UploadScanDocument.aspx to understand the upload flow,
and checks if WsShiraUtils has a CreateDocument method.

Run AFTER step 1 passes.

Run:
    python phase_a_step2.py
"""

import requests
from requests_negotiate_sspi import HttpNegotiateAuth
from bs4 import BeautifulSoup
import re

SHIRA   = "http://shira2"

# ── Fill these in from the case you want to test ──────────────────────────────
FILE_ID = "2923739"   # Shira FileID of the test case
# ─────────────────────────────────────────────────────────────────────────────

def make_session():
    s = requests.Session()
    s.auth = HttpNegotiateAuth()
    s.headers.update({"Origin": SHIRA})
    s.proxies = {"http": None, "https": None}
    s.verify = False
    return s

def main():
    print("=" * 50)
    print("Step 2 — Discovering document creation endpoint")
    print("=" * 50)

    session = make_session()

    # Test A: Check if WsShiraUtils has a CreateDocument or AddDocument method
    print("\n[A] Searching WsShiraUtils for document-creation methods...")
    try:
        r = session.get(
            f"{SHIRA}/classic/WS/App/WsShiraUtils.asmx?WSDL",
            timeout=10,
            headers={"Content-Type": "text/html"}
        )
        ops = re.findall(r'<operation name="([^"]+)"', r.text)
        doc_ops = [o for o in ops if any(k in o.lower() for k in
                   ["doc", "create", "add", "insert", "upload", "import", "scan"])]
        if doc_ops:
            print(f"    Potentially relevant operations:")
            for op in doc_ops:
                print(f"      - {op}")
        else:
            print("    No obvious document-creation methods found")
    except Exception as e:
        print(f"    ❌ {e}")

    # Test B: Load UploadScanDocument.aspx and inspect its form
    print(f"\n[B] Loading UploadScanDocument.aspx for FileID={FILE_ID}...")
    upload_url = (
        f"{SHIRA}/classic/Forms/Documents/Scan/UploadScanDocument.aspx"
        f"?FileID={FILE_ID}&EntityTypeID=6&EntityID={FILE_ID}&DocumentID=0"
    )
    try:
        r = session.get(upload_url, timeout=15, headers={"Content-Type": "text/html"})
        print(f"    Status: {r.status_code}")
        soup = BeautifulSoup(r.text, "html.parser")

        # Extract hidden fields
        hidden = {i["name"]: i.get("value","") for i in soup.find_all("input", type="hidden") if i.get("name")}
        print(f"    Hidden fields found:")
        for k, v in hidden.items():
            display_v = v[:60] + "..." if len(v) > 60 else v
            print(f"      {k} = {display_v}")

        # Extract file input names
        file_inputs = soup.find_all("input", type="file")
        print(f"    File inputs: {[f.get('name') for f in file_inputs]}")

        # Extract form action
        form = soup.find("form")
        if form:
            print(f"    Form action: {form.get('action', '(none)')}")
            print(f"    Form method: {form.get('method', '(none)')}")

        if hidden.get("__VIEWSTATE"):
            print("    ✅ Form loaded successfully — ready for Step 3")
        else:
            print("    ⚠️  No VIEWSTATE found — may not be a standard ASP.NET form")

    except Exception as e:
        print(f"    ❌ Failed: {e}")

    # Test C: Check if there's a JSON API endpoint for document creation
    print(f"\n[C] Probing Shira REST API for document endpoints...")
    candidates = [
        "/api/api/Document/CreateDocument",
        "/api/api/Document/AddDocument",
        "/api/api/FileDocument/Create",
        "/api/api/Documents/Upload",
    ]
    for url in candidates:
        try:
            r = session.get(f"{SHIRA}{url}", timeout=5)
            print(f"    {url} → {r.status_code}")
        except Exception as e:
            print(f"    {url} → Error: {e}")

    print("\n" + "=" * 50)
    print("Done. Share the output — it tells us the exact upload approach.")
    print("=" * 50)

if __name__ == "__main__":
    main()
