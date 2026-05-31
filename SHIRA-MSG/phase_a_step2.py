"""
Phase A — Step 2  (v10)
POST docx with __FORM_ACTION=UPLOAD_FILE to trigger document creation.
"""
VERSION = "v10"

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
    s = requests.Session()
    s.auth      = HttpNegotiateAuth()
    s.trust_env = False
    s.proxies   = {}
    s.verify    = False
    return s

def make_test_docx():
    doc = Document()
    doc.add_paragraph("Test message from ShiraAI - step 2 probe")
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

def main():
    print(f"=== Step 2 {VERSION} ===")
    session = make_session()

    iframe_url = (
        f"{SHIRA}/classic/Forms/Documents/Scan/IframeFromMyComputerDocument.aspx"
        f"?FileID={FILE_ID}&EntityTypeID=6&EntityID={FILE_ID}&DocumentID=0"
    )

    # ── Step 1: GET page to collect VIEWSTATE ─────────────────────────────────
    print(f"\n[1] Loading form...")
    try:
        r = session.get(iframe_url, timeout=15)
        print(f"    Status : {r.status_code}")
        soup = BeautifulSoup(r.text, "html.parser")
        hidden = {i["name"]: i.get("value","")
                  for i in soup.find_all("input", type="hidden") if i.get("name")}
        if not hidden.get("__VIEWSTATE"):
            print("    ❌ No VIEWSTATE — cannot proceed")
            return
        print("    ✅ VIEWSTATE acquired")
    except Exception as e:
        print(f"    ❌ {e}")
        return

    # ── Step 2: POST with __FORM_ACTION=UPLOAD_FILE ───────────────────────────
    print(f"\n[2] POSTing docx with __FORM_ACTION=UPLOAD_FILE...")
    try:
        post_data = dict(hidden)
        post_data["__FORM_ACTION"]   = "UPLOAD_FILE"   # ← the missing trigger
        post_data["__EVENTTARGET"]   = ""
        post_data["__EVENTARGUMENT"] = ""

        files = {
            "fileUploadMyPcDoc": (
                "test_shira_msg.docx",
                make_test_docx(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        }
        r = session.post(iframe_url, data=post_data, files=files, timeout=30)
        print(f"    Status  : {r.status_code}")
        print(f"    Response length: {len(r.text)}")

        # Look for DocumentID (Shira typos it as "DocumnetId" sometimes)
        ids = re.findall(r'[Dd]ocum(?:en|ne)t[Ii][Dd][^0-9]*(\d+)', r.text)
        ids = [d for d in ids if d != "0"]
        unc = re.findall(r'\\\\[^\'\"<>\s]+', r.text)
        upload_dm = re.findall(r'UploadFileToDM[^\'"<>\s]*', r.text)
        big_nums  = list(dict.fromkeys(re.findall(r'\b(\d{7,9})\b', r.text)))

        print(f"    DocumentIDs (non-zero) : {ids}")
        print(f"    UNC paths              : {unc[:5]}")
        print(f"    UploadFileToDM refs    : {upload_dm[:5]}")
        print(f"    Large numbers (7-9d)   : {big_nums[:10]}")

        if ids:
            doc_id = ids[0]
            print(f"\n    🎉 DocumentID = {doc_id}")
            print(f"    Postal URL: {SHIRA}/classic/Forms/Postal/Postal.aspx?DocumentIDs={doc_id}&FileID={FILE_ID}")
        else:
            print(f"\n    --- Full response ---")
            print(r.text[:5000])
            print(f"    --- End ---")

    except Exception as e:
        print(f"    ❌ {e}")

    print("\n=== Done ===")

if __name__ == "__main__":
    main()
