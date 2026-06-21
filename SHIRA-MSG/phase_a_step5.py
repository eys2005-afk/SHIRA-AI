"""
Phase A — Step 5b
Dump sendtoserver.js fully + search utils.js / document.js for ACTION constants
and JS_SubmitForm definition.

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

def show_relevant(name, text, patterns):
    print("\n" + "=" * 70)
    print(f"  {name}  (len={len(text)})")
    print("=" * 70)
    lines = text.splitlines()
    for i, line in enumerate(lines):
        for pat in patterns:
            if pat.lower() in line.lower():
                start = max(0, i - 1)
                end   = min(len(lines), i + 10)
                print(f"\n  --- match '{pat}' @ line {i} ---")
                for j in range(start, end):
                    print(f"  {lines[j]}")
                break

def main():
    s = make_session()

    # Full dump of sendtoserver.js (small file)
    print("\n" + "=" * 70)
    print("  FULL sendtoserver.js")
    print("=" * 70)
    print(grab(s, f"{SHIRA}/classic/scripts/sendtoserver.js"))

    # Search utils.js and document.js for the ACTION constants + JS_SubmitForm
    patterns = ["ACTION_SAVE", "ACTION_REFRESH", "ACTION_NEW", "= 'SAVE",
                '= "SAVE', "JS_SubmitForm", "var ACTION", "FORM_ACTION"]
    for name, url in [
        ("utils.js",    f"{SHIRA}/classic/scripts/utils.js"),
        ("globals.js",  f"{SHIRA}/classic/scripts/globals.js"),
        ("document.js", f"{SHIRA}/classic/forms/documents/document.js"),
    ]:
        show_relevant(name, grab(s, url), patterns)

if __name__ == "__main__":
    main()
