"""
inspect_logic.py — print the EXACT function bodies and constant values
that drive the upload+save flow. No guessing: we read Shira's own code.

Run:
    python inspect_logic.py > logic.txt 2>&1
    notepad logic.txt
"""
import os, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
import requests
from requests_negotiate_sspi import HttpNegotiateAuth

os.environ['NO_PROXY'] = 'shira2,prod-spfe,localhost,127.0.0.1'
os.environ['no_proxy'] = 'shira2,prod-spfe,localhost,127.0.0.1'

SHIRA = "http://shira2"

def make_session():
    s = requests.Session()
    s.auth = HttpNegotiateAuth(); s.trust_env = False; s.proxies = {}; s.verify = False
    return s

def get(s, url):
    try:
        r = s.get(url, timeout=20)
        return r.text if r.status_code == 200 else f"(HTTP {r.status_code})"
    except Exception as e:
        return f"(ERROR {e})"

def extract_function(js, name):
    """Return the full body of `function name(...) { ... }` with brace matching."""
    # find 'function name(' OR 'async function name(' OR 'name = function('
    patterns = [
        rf'(async\s+)?function\s+{re.escape(name)}\s*\(',
        rf'{re.escape(name)}\s*=\s*(async\s+)?function\s*\(',
        rf'{re.escape(name)}\s*:\s*(async\s+)?function\s*\(',
    ]
    start = -1
    for pat in patterns:
        m = re.search(pat, js)
        if m:
            start = m.start()
            break
    if start < 0:
        return None
    # find first { after start
    brace = js.find('{', start)
    if brace < 0:
        return None
    depth = 0
    i = brace
    while i < len(js):
        c = js[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return js[start:i+1]
        i += 1
    return js[start:start+2000]

def show_function(js, name):
    print("\n" + "-" * 70)
    print(f"  function: {name}")
    print("-" * 70)
    body = extract_function(js, name)
    print(body if body else f"  (not found in this file)")

def show_constants(js, names):
    print("\n" + "-" * 70)
    print("  constant definitions")
    print("-" * 70)
    for n in names:
        # var NAME = "...";  OR  NAME = 123;  OR  const NAME = ...
        for m in re.finditer(rf'(var|const|let)?\s*{re.escape(n)}\s*=\s*([^;\n]+);', js):
            print(f"  {n} = {m.group(2).strip()}")
        # also object-style:  NAME : "..."
        for m in re.finditer(rf'\b{re.escape(n)}\s*:\s*([^,\n}}]+)', js):
            print(f"  {n} : {m.group(1).strip()}")

def main():
    s = make_session()

    files = {
        "uploadscandocument.js": f"{SHIRA}/classic/forms/documents/scan/uploadscandocument.js",
        "iframefrommycomputerdocument.js": f"{SHIRA}/classic/forms/documents/scan/iframefrommycomputerdocument.js",
        "globals.js": f"{SHIRA}/classic/scripts/globals.js",
        "sendtoserver.js": f"{SHIRA}/classic/scripts/sendtoserver.js",
        "screens.js": f"{SHIRA}/classic/scripts/screens.js",
    }
    js = {name: get(s, url) for name, url in files.items()}

    print("=" * 70)
    print("  PARENT: uploadscandocument.js")
    print("=" * 70)
    for fn in ["Save", "CompleteSave", "OpenUploadFileToDM", "GetDocumentID",
               "checkFileAvailability", "OnPageLoadInit"]:
        show_function(js["uploadscandocument.js"], fn)

    print("\n" + "=" * 70)
    print("  CHILD: iframefrommycomputerdocument.js")
    print("=" * 70)
    for fn in ["StartUploadFile", "UploadFileDone", "GetSelectedFileDetails",
               "OnSaveValidation", "copyFile", "checkFileExistence", "removeFileAttributes"]:
        show_function(js["iframefrommycomputerdocument.js"], fn)

    print("\n" + "=" * 70)
    print("  CORE: JS_SubmitForm + Screens_UploadFileToDM")
    print("=" * 70)
    for src in ["sendtoserver.js", "globals.js", "screens.js", "uploadscandocument.js"]:
        b = extract_function(js[src], "JS_SubmitForm")
        if b:
            print(f"\n  [JS_SubmitForm found in {src}]")
            print(b)
            break
    for src in ["screens.js", "sendtoserver.js"]:
        b = extract_function(js[src], "Screens_UploadFileToDM")
        if b:
            print(f"\n  [Screens_UploadFileToDM found in {src}]")
            print(b)
            break

    print("\n" + "=" * 70)
    print("  CONSTANT VALUES")
    print("=" * 70)
    const_names = ["ACTION_SAVE_STAY", "ACTION_SAVE", "ACTION_REFRESH",
                   "UPLOAD_FILE", "DOC_TYPE", "DOC_SOURCE_OPTION"]
    for src in ["globals.js", "uploadscandocument.js", "iframefrommycomputerdocument.js", "sendtoserver.js"]:
        print(f"\n  --- in {src} ---")
        show_constants(js[src], const_names)

if __name__ == "__main__":
    main()
