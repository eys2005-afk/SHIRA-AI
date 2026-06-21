"""
Phase A — Step 5
Dump the JS that defines:
  - ACTION_SAVE / ACTION_SAVE_STAY constants (document.js / globals.js / sendtoserver.js)
  - Screens_UploadFileToDM() URL building (screens.js)
  - JS_SubmitForm() (sendtoserver.js)

Run:
    python phase_a_step5.py > js2.txt 2>&1
    notepad js2.txt
"""
import os, re
import requests
from requests_negotiate_sspi import HttpNegotiateAuth

os.environ['NO_PROXY'] = 'shira2,prod-spfe,localhost,127.0.0.1'
os.environ['no_proxy'] = 'shira2,prod-spfe,localhost,127.0.0.1'

SHIRA = "http://shira2"

def make_session():
    s = requests.Session()
    s.auth      = HttpNegotiateAuth()
    s.trust_env = False
    s.proxies   = {}
    s.verify    = False
    return s

def grab(s, url):
    try:
        r = s.get(url, timeout=20)
        return r.text if r.status_code == 200 else f"(HTTP {r.status_code})"
    except Exception as e:
        return f"(ERROR {e})"

def show_relevant(name, text, patterns):
    print("\n" + "=" * 70)
    print(f"  {name}  (len={len(text)})")
    print("=" * 70)
    lines = text.splitlines()
    for i, line in enumerate(lines):
        for pat in patterns:
            if pat.lower() in line.lower():
                # print a small window of context
                start = max(0, i - 1)
                end   = min(len(lines), i + 8)
                print(f"\n  --- match '{pat}' @ line {i} ---")
                for j in range(start, end):
                    print(f"  {lines[j]}")
                break

def main():
    s = make_session()
    files = {
        "globals.js":      f"{SHIRA}/classic/scripts/globals.js",
        "sendtoserver.js": f"{SHIRA}/classic/scripts/sendtoserver.js",
        "screens.js":      f"{SHIRA}/classic/scripts/screens.js",
        "document.js":     f"{SHIRA}/classic/forms/documents/document.js",
    }
    patterns = ["ACTION_SAVE", "ACTION_", "JS_SubmitForm", "Screens_UploadFileToDM",
                "UploadFileToDM", "DOC_TYPE", "function JS_SubmitForm",
                "__FORM_ACTION", "SubmitFormToServer"]
    for name, url in files.items():
        text = grab(s, url)
        show_relevant(name, text, patterns)

if __name__ == "__main__":
    main()
