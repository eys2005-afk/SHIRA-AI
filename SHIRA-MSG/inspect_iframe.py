"""
inspect_iframe.py — read the source of truth, no guessing.
Fetches the iframe upload page HTML + its JS in full, then extracts:
  - every <input> name/id/type  (so we know the EXACT file field name)
  - every <form> action + enctype
  - every function definition in the JS
  - every reference to upload / DocumentID / submit
Run:
    python inspect_iframe.py > iframe.txt 2>&1
    notepad iframe.txt
"""
import os, re, sys, io
# Force UTF-8 stdout so Hebrew/symbols never crash the cp1255 console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
import requests
from requests_negotiate_sspi import HttpNegotiateAuth

os.environ['NO_PROXY'] = 'shira2,prod-spfe,localhost,127.0.0.1'
os.environ['no_proxy'] = 'shira2,prod-spfe,localhost,127.0.0.1'

SHIRA     = "http://shira2"
FILE_ID   = "2923739"
ENTITY_ID = "1936401"
COURT_ID  = "5"

def make_session():
    s = requests.Session()
    s.auth = HttpNegotiateAuth(); s.trust_env = False; s.proxies = {}; s.verify = False
    return s

def get(s, url):
    try:
        r = s.get(url, timeout=20)
        return r.status_code, r.text
    except Exception as e:
        return 0, f"(ERROR {e})"

def section(title):
    print("\n" + "=" * 70 + f"\n  {title}\n" + "=" * 70)

def main():
    s = make_session()

    # The candidate iframe URLs (we print which one actually returns a form)
    iframe_urls = [
        f"{SHIRA}/classic/Forms/Documents/Scan/IframeFromMyComputerDocument.aspx"
        f"?FileID={FILE_ID}&EntityTypeID=1&EntityID={ENTITY_ID}&DocumentID=0&CourtID={COURT_ID}",
        f"{SHIRA}/classic/Forms/Documents/Scan/UploadScanDocument.aspx"
        f"?FileID={FILE_ID}&EntityTypeID=1&EntityID={ENTITY_ID}&DocumentID=0",
    ]

    for url in iframe_urls:
        status, html = get(s, url)
        section(f"PAGE  ({status})  {url}")
        if status != 200:
            print(html[:500]); continue

        # --- every <form ...> tag ---
        print("\n-- <form> tags --")
        for m in re.finditer(r'<form[^>]*>', html, re.I):
            print("  " + m.group(0))

        # --- every <input ...> tag (name/id/type/value-trimmed) ---
        print("\n-- <input> tags --")
        for m in re.finditer(r'<input[^>]*>', html, re.I):
            tag = m.group(0)
            # trim long viewstate values
            tag = re.sub(r'value="[^"]{60,}"', 'value="...(long)..."', tag)
            print("  " + tag)

        # --- every <iframe ...> tag (find the nested upload iframe) ---
        print("\n-- <iframe> tags --")
        for m in re.finditer(r'<iframe[^>]*>', html, re.I):
            print("  " + m.group(0))

        # --- script src references ---
        print("\n-- <script src> --")
        for m in re.finditer(r'<script[^>]*src="([^"]+)"', html, re.I):
            print("  " + m.group(1))

        # --- inline JS lines that mention upload/submit/DocumentID ---
        print("\n-- inline JS hints --")
        for line in html.splitlines():
            if re.search(r'(upload|submit|DocumentID|DocumnetId|__doPostBack|filUpload|FileUpload)', line, re.I):
                print("  " + line.strip()[:200])

    # --- JS files, full function listing ---
    js_files = [
        f"{SHIRA}/classic/Forms/Documents/Scan/iframefrommycomputerdocument.js",
        f"{SHIRA}/classic/Forms/Documents/Scan/uploadscandocument.js",
    ]
    for url in js_files:
        status, js = get(s, url)
        section(f"JS  ({status}, len={len(js)})  {url}")
        if status != 200:
            print(js[:300]); continue
        print("\n-- function definitions --")
        for m in re.finditer(r'function\s+(\w+)\s*\([^)]*\)', js):
            print("  " + m.group(0))
        print("\n-- lines mentioning upload/submit/DocumentID/postback --")
        for line in js.splitlines():
            if re.search(r'(upload|submit|DocumentID|DocumnetId|doPostBack|FormAction|__FORM)', line, re.I):
                print("  " + line.strip()[:200])

if __name__ == "__main__":
    main()
