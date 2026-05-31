"""
Phase A — Step 3
1. Write docx directly to UNC Temp path
2. Call SPFE ImportDocument with that path and shiraDocId=0
3. If response is a positive number → that IS the DocumentID, done!

Run:
    python phase_a_step3.py
"""
VERSION = "v1"

import os, io, time
import requests
from requests_negotiate_sspi import HttpNegotiateAuth
from docx import Document

os.environ['NO_PROXY'] = 'shira2,prod-spfe,localhost,127.0.0.1'
os.environ['no_proxy'] = 'shira2,prod-spfe,localhost,127.0.0.1'

SHIRA    = "http://shira2"
SPFE     = "http://prod-spfe:1000"
FILE_ID  = "2923739"
COURT_ID = "5"
UNC_TEMP = r"\\Prod-nas1\filer$\Root\Data\Users\elchanans\ScanDocuments\Temp"

def make_session():
    s = requests.Session()
    s.auth      = HttpNegotiateAuth()
    s.trust_env = False
    s.proxies   = {}
    s.verify    = False
    return s

def make_test_docx():
    doc = Document()
    doc.add_paragraph("Test message from ShiraAI — phase A step 3")
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()

def main():
    print(f"=== Step 3 {VERSION} ===")
    session = make_session()

    # ── 1: Write docx to UNC Temp path ────────────────────────────────────────
    filename = f"shiramsg_test_{int(time.time())}.docx"
    unc_path = os.path.join(UNC_TEMP, filename)
    # Also build the double-backslash version for the JSON body
    unc_path_escaped = unc_path.replace("\\", "\\\\")

    print(f"\n[1] Writing test docx to UNC path...")
    print(f"    Path: {unc_path}")
    try:
        docx_bytes = make_test_docx()
        with open(unc_path, "wb") as f:
            f.write(docx_bytes)
        print(f"    ✅ File written ({len(docx_bytes)} bytes)")
    except Exception as e:
        print(f"    ❌ {e}")
        return

    # ── 2: Call SPFE ImportDocument with shiraDocId=0 ─────────────────────────
    print(f"\n[2] Calling SPFE ImportDocument with shiraDocId=0...")
    print(f"    fileUrl  : {unc_path}")
    try:
        body = (
            f"{{'fileUrl':'{unc_path_escaped}', "
            f"'shiraDocId':'0', "
            f"'courtId':'{COURT_ID}', "
            f"'isReadOnly':'false'}}"
        )
        r = session.post(
            f"{SPFE}/ShiraDocsMngWS.asmx/ImportDocument",
            data=body,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        print(f"    Status  : {r.status_code}")
        print(f"    Response: {r.text[:500]}")

        import re, json
        # Try to parse {"d": <number>}
        m = re.search(r'"d"\s*:\s*(-?\d+)', r.text)
        if m:
            doc_id = int(m.group(1))
            if doc_id > 0:
                print(f"\n    🎉 DocumentID = {doc_id}")
                print(f"    Postal URL: {SHIRA}/classic/Forms/Postal/Postal.aspx?DocumentIDs={doc_id}&FileID={FILE_ID}")
            else:
                print(f"\n    ⚠️  Got {doc_id} — need to try with a real shiraDocId or different approach")
    except Exception as e:
        print(f"    ❌ {e}")

    # ── 3: Also try with FileID as shiraDocId (some systems use this) ─────────
    print(f"\n[3] Trying again with shiraDocId=FileID ({FILE_ID})...")
    try:
        body2 = (
            f"{{'fileUrl':'{unc_path_escaped}', "
            f"'shiraDocId':'{FILE_ID}', "
            f"'courtId':'{COURT_ID}', "
            f"'isReadOnly':'false'}}"
        )
        r2 = session.post(
            f"{SPFE}/ShiraDocsMngWS.asmx/ImportDocument",
            data=body2,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        print(f"    Status  : {r2.status_code}")
        print(f"    Response: {r2.text[:300]}")
        m2 = re.search(r'"d"\s*:\s*(-?\d+)', r2.text)
        if m2:
            doc_id2 = int(m2.group(1))
            if doc_id2 > 0:
                print(f"\n    🎉 DocumentID = {doc_id2}")
                print(f"    Postal URL: {SHIRA}/classic/Forms/Postal/Postal.aspx?DocumentIDs={doc_id2}&FileID={FILE_ID}")
            else:
                print(f"    Result: {doc_id2}")
    except Exception as e:
        print(f"    ❌ {e}")

    print("\n=== Done ===")

if __name__ == "__main__":
    main()
