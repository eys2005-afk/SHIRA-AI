"""
Phase A — Step 5c
Broad search: find where JS_SubmitForm() and ACTION_* constants are DEFINED,
and how __FORM_ACTION / __FORM_SUBMIT_COUNTER are set before submit.

Run:
    python phase_a_step5.py > js2.txt 2>&1
    notepad js2.txt
"""
import os
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

def show(name, text, needles):
    print("\n" + "=" * 70)
    print(f"  {name}  (len={len(text)})")
    print("=" * 70)
    lines = text.splitlines()
    hit = False
    for i, line in enumerate(lines):
        for n in needles:
            if n in line:
                hit = True
                start = max(0, i - 1)
                end   = min(len(lines), i + 12)
                print(f"\n  --- '{n}' @ line {i} ---")
                for j in range(start, end):
                    print(f"  {lines[j]}")
                break
    if not hit:
        print("  (no matches)")

def main():
    s = make_session()

    # Definitions we hunt for
    needles = [
        "function JS_SubmitForm",
        "JS_SubmitForm =",
        "ACTION_SAVE",
        "ACTION_REFRESH =",
        "SAVE_STAY",
        "__FORM_ACTION",
        "__FORM_SUBMIT_COUNTER",
        "SubmitFormToServer",
        "var ACTION",
    ]

    files = {
        "globals.js":      f"{SHIRA}/classic/scripts/globals.js",
        "utils.js":        f"{SHIRA}/classic/scripts/utils.js",
        "screens.js":      f"{SHIRA}/classic/scripts/screens.js",
        "document.js":     f"{SHIRA}/classic/forms/documents/document.js",
        "formbase.js":     f"{SHIRA}/classic/scripts/formbase.js",
        "forms.js":        f"{SHIRA}/classic/scripts/forms.js",
        "shira.js":        f"{SHIRA}/classic/scripts/shira.js",
        "common.js":       f"{SHIRA}/classic/scripts/common.js",
    }
    for name, url in files.items():
        show(name, grab(s, url), needles)

if __name__ == "__main__":
    main()
