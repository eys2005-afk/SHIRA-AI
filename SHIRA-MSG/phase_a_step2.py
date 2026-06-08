"""
Phase A — Step 2  (v11)
3-step chain:
  1. GET form → collect VIEWSTATE
  2. POST UPLOAD_FILE with docx → server saves to UNC, returns new VIEWSTATE + hdnDestinationDirDoc
  3. POST SAVE_DOCUMENT with that path → Shira creates document record, returns DocumentID
"""
VERSION = "v11"

import os, re, io
import requests
from requests_negotiate_sspi import HttpNegotiateAuth
from bs4 import BeautifulSoup
from docx import Document

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

def make_test_docx():
    doc = Document()
    doc.add_paragraph("Test message from ShiraAI - step 2 v11")
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

def extract_hidden(html):
    soup = BeautifulSoup(html, "html.parser")
    return {i["name"]: i.get("value", "")
            for i in soup.find_all("input", type="hidden") if i.get("name")}

def main():
    print(f"=== Step 2 {VERSION} ===")
    session = make_session()

    iframe_url = (
        f"{SHIRA}/classic/Forms/Documents/Scan/IframeFromMyComputerDocument.aspx"
        f"?FileID={FILE_ID}&EntityTypeID=6&EntityID={FILE_ID}&DocumentID=0"
    )

    # ── Step 1: GET page ───────────────────────────────────────────────────────
    print(f"\n[1] Loading form...")
    r1 = session.get(iframe_url, timeout=15)
    print(f"    Status: {r1.status_code}")
    hidden1 = extract_hidden(r1.text)
    if not hidden1.get("__VIEWSTATE"):
        print("    ❌ No VIEWSTATE"); return
    print("    ✅ VIEWSTATE acquired")

    # ── Step 2: POST UPLOAD_FILE ───────────────────────────────────────────────
    print(f"\n[2] POSTing UPLOAD_FILE...")
    post2 = dict(hidden1)
    post2["__FORM_ACTION"]   = "UPLOAD_FILE"
    post2["__EVENTTARGET"]   = ""
    post2["__EVENTARGUMENT"] = ""

    r2 = session.post(
        iframe_url,
        data=post2,
        files={"fileUploadMyPcDoc": ("shiramsg_test.docx", make_test_docx(),
               "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        timeout=30,
    )
    print(f"    Status: {r2.status_code}")
    hidden2 = extract_hidden(r2.text)
    unc_path = hidden2.get("hdnDestinationDirDoc", "")
    print(f"    hdnDestinationDirDoc: {unc_path}")
    if not unc_path:
        print("    ❌ No UNC path returned — cannot proceed")
        print(r2.text[:3000]); return
    print("    ✅ File saved to UNC")

    # ── Step 3: POST SAVE_DOCUMENT ─────────────────────────────────────────────
    print(f"\n[3] POSTing SAVE_DOCUMENT to create Shira document record...")
    post3 = dict(hidden2)
    post3["__FORM_ACTION"]   = "SAVE_DOCUMENT"
    post3["__EVENTTARGET"]   = ""
    post3["__EVENTARGUMENT"] = ""

    r3 = session.post(iframe_url, data=post3, timeout=30)
    print(f"    Status : {r3.status_code}")
    print(f"    Length : {len(r3.text)}")

    ids = re.findall(r'[Dd]ocum(?:en|ne)t[Ii][Dd][^0-9]*(\d+)', r3.text)
    ids = [d for d in ids if d != "0"]
    big_nums = list(dict.fromkeys(re.findall(r'\b(\d{7,10})\b', r3.text)))
    big_nums = [n for n in big_nums if n != FILE_ID]

    print(f"    DocumentIDs found: {ids}")
    print(f"    Large numbers    : {big_nums[:10]}")

    if ids:
        doc_id = ids[0]
        print(f"\n    ✅ DocumentID = {doc_id}")
        print(f"    Postal URL: {SHIRA}/classic/Forms/Postal/Postal.aspx?DocumentIDs={doc_id}&FileID={FILE_ID}")
    elif big_nums:
        print(f"\n    ⚠️  No labeled DocumentID — possible ID in big numbers above")
        print(f"    Try: {SHIRA}/classic/Forms/Postal/Postal.aspx?DocumentIDs={big_nums[0]}&FileID={FILE_ID}")
    else:
        print(f"\n    ❌ No DocumentID found")
        print("\n    --- Response ---")
        print(r3.text[:5000])

    print("\n=== Done ===")

if __name__ == "__main__":
    main()
