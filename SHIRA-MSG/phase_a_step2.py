"""
Phase A — Step 2  (v7)
Discover how to create a document record in Shira.
Run AFTER step 1 passes.

Run:
    python phase_a_step2.py
"""

VERSION = "v8"

import os, re, io
import requests
from requests_negotiate_sspi import HttpNegotiateAuth
from bs4 import BeautifulSoup
from docx import Document

os.environ['NO_PROXY'] = 'shira2,prod-spfe,localhost,127.0.0.1'
os.environ['no_proxy'] = 'shira2,prod-spfe,localhost,127.0.0.1'

SHIRA   = "http://shira2"
SPFE    = "http://prod-spfe:1000"
FILE_ID = "2923739"

def make_session():
    """Session with NTLM auth and no proxy."""
    s = requests.Session()
    s.auth      = HttpNegotiateAuth()
    s.trust_env = False
    s.proxies   = {}
    s.verify    = False
    return s

def make_test_docx():
    """Create a minimal docx in memory."""
    doc = Document()
    doc.add_paragraph("Test message from ShiraAI - step 2 probe")
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

def main():
    print(f"=== Step 2 {VERSION} ===")

    session = make_session()

    # ── B: Load IframeFromMyComputerDocument.aspx to get VIEWSTATE ────────────
    print(f"\n[B] Loading IframeFromMyComputerDocument.aspx...")
    iframe_url = (
        f"{SHIRA}/classic/Forms/Documents/Scan/IframeFromMyComputerDocument.aspx"
        f"?FileID={FILE_ID}&EntityTypeID=6&EntityID={FILE_ID}&DocumentID=0"
    )
    viewstate = evval = form_data = None
    try:
        r = session.get(iframe_url, timeout=15)
        print(f"    Status  : {r.status_code}")
        soup = BeautifulSoup(r.text, "html.parser")
        hidden = {i["name"]: i.get("value","")
                  for i in soup.find_all("input", type="hidden") if i.get("name")}
        viewstate = hidden.get("__VIEWSTATE")
        evval     = hidden.get("__EVENTVALIDATION")
        form_data = hidden
        for k, v in hidden.items():
            print(f"      {k} = {(v[:60]+'...') if len(v)>60 else v}")
        if viewstate:
            print("    ✅ VIEWSTATE acquired")
    except Exception as e:
        print(f"    ❌ {e}")

    # ── B2: POST the test docx ─────────────────────────────────────────────────
    if viewstate:
        print(f"\n[B2] POSTing test docx to IframeFromMyComputerDocument.aspx...")
        try:
            post_data = {k: v for k, v in form_data.items()}
            post_data["__EVENTTARGET"]   = ""
            post_data["__EVENTARGUMENT"] = ""

            docx_buf = make_test_docx()
            files = {
                "fileUploadMyPcDoc": ("test_shira_msg.docx",
                                      docx_buf,
                                      "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            }
            r = session.post(iframe_url, data=post_data, files=files, timeout=30)
            print(f"    Status  : {r.status_code}")

            # Look for document ID in response — try many patterns
            doc_ids = re.findall(r'[Dd]ocumnet[Ii][Dd][=\s:\'\"]+(\d+)', r.text)
            doc_ids += re.findall(r'[Dd]ocument[Ii][Dd][=\s:\'\"]+(\d+)', r.text)
            doc_ids = [d for d in doc_ids if d != "0"]

            # Look for UNC path (contains the assigned doc ID as filename)
            unc_paths = re.findall(r'\\\\[^\'\"<>\s]+', r.text)
            # Look for UploadFileToDM redirect
            upload_dm = re.findall(r'UploadFileToDM[^\'"<>\s]*', r.text)
            # Look for any 7-8 digit numbers (doc IDs are large integers)
            big_nums = re.findall(r'\b(\d{7,9})\b', r.text)

            if doc_ids:
                print(f"    🎉 DocumentID found: {doc_ids[0]}")
                print(f"    Postal URL: {SHIRA}/classic/Forms/Postal/Postal.aspx?DocumentIDs={doc_ids[0]}&FileID={FILE_ID}")
            else:
                print(f"    ⚠️  No DocumentID — checking for other clues...")
                print(f"    UNC paths in response : {unc_paths[:3]}")
                print(f"    UploadFileToDM refs   : {upload_dm[:3]}")
                print(f"    Large numbers (7-9 digits): {list(dict.fromkeys(big_nums))[:10]}")
                print(f"\n    --- Full response (first 3000 chars) ---")
                print(r.text[:3000])
                print(f"    --- End ---")
        except Exception as e:
            print(f"    ❌ {e}")
    else:
        print("\n[B2] Skipped — no VIEWSTATE from [B]")

    # ── C: WsShiraUtils WSDL — list all operations ────────────────────────────
    print("\n[C] Checking WsShiraUtils WSDL...")
    try:
        r = session.get(f"{SHIRA}/classic/WS/App/WsShiraUtils.asmx?WSDL", timeout=15)
        print(f"    Status : {r.status_code}  ({len(r.text)} chars)")
        ops = re.findall(r'<(?:wsdl:)?operation\s+name="([^"]+)"', r.text)
        ops = list(dict.fromkeys(ops))  # deduplicate
        print(f"    Operations found: {len(ops)}")
        doc_ops = [o for o in ops if any(k in o.lower() for k in
                   ["doc", "creat", "add", "insert", "upload", "import", "scan"])]
        if doc_ops:
            print("    Document-related operations:")
            for op in doc_ops:
                print(f"      - {op}")
        print("    All operations:")
        for op in ops:
            print(f"      - {op}")
    except Exception as e:
        print(f"    ❌ {e}")

    # ── A: SPFE ImportDocument ────────────────────────────────────────────────
    print("\n[A] Testing SPFE ImportDocument endpoint...")
    try:
        r = session.post(
            f"{SPFE}/ShiraDocsMngWS.asmx/ImportDocument",
            data="{'fileUrl':'test', 'shiraDocId':'0', 'courtId':'5', 'isReadOnly':'false'}",
            headers={"Content-Type": "application/json"},
            timeout=15)
        print(f"    Status  : {r.status_code}")
        print(f"    Response: {r.text[:200]}")
        if r.status_code == 200:
            print("    ✅ SPFE ImportDocument reachable")
    except Exception as e:
        print(f"    ❌ {e}")

    print("\n=== Done — share this output ===")

if __name__ == "__main__":
    main()
