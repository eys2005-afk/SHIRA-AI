"""
Phase A — Step 4
Fetch the JavaScript behind UploadScanDocument so we can see exactly how
DocumnetId is generated and how UploadFileToDM is called.
No browser needed — just the proven SESSION pattern.

Run:
    python phase_a_step4.py > js_dump.txt 2>&1
    notepad js_dump.txt
"""
import os
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

def dump(session, url, label):
    print("\n" + "=" * 70)
    print(f"  {label}")
    print(f"  {url}")
    print("=" * 70)
    try:
        r = session.get(url, timeout=20)
        print(f"  Status: {r.status_code}  Length: {len(r.text)}\n")
        print(r.text)
    except Exception as e:
        print(f"  ERROR: {e}")

def main():
    s = make_session()

    # 1. The JS that drives UploadScanDocument
    dump(s, f"{SHIRA}/classic/Forms/Documents/Scan/uploadscandocument.js",
         "uploadscandocument.js")

    # 2. The JS that drives UploadFileToDM
    dump(s, f"{SHIRA}/classic/Forms/Documents/Scan/uploadfiletodm.js",
         "uploadfiletodm.js")

    # 3. The UploadScanDocument page itself (to see hidden fields / form action)
    dump(s, f"{SHIRA}/classic/Forms/Documents/Scan/UploadScanDocument.aspx"
            f"?FileID={FILE_ID}&EntityTypeID=1&EntityID={FILE_ID}&DocumentID=0",
         "UploadScanDocument.aspx (page HTML)")

if __name__ == "__main__":
    main()
