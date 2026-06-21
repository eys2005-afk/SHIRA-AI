"""
discover_dispatch.py — find Shira's send/dispatch web-services.
Goal: is there a way to send SMS/email that is NOT bound to a case document?

It enumerates the methods of the known ASMX service(s) and looks for any
method whose name suggests send / sms / mail / dispatch (דיוור) that does
NOT require a DocumentID.

Run:
    python discover_dispatch.py > dispatch.txt 2>&1
    type dispatch.txt
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

# ASMX services to probe (the ones seen in traffic + likely siblings)
ASMX = [
    "/classic/WS/App/WsShiraUtils.asmx",
    "/classic/WS/App/WsShiraDocument.asmx",
    "/classic/WS/App/WsShiraPostal.asmx",
    "/classic/WS/App/WsShiraDiur.asmx",
    "/classic/WS/App/WsShiraSms.asmx",
    "/classic/WS/App/WsShiraMail.asmx",
    "/classic/WS/App/WsShiraMessage.asmx",
    "/classic/WS/App/WsShiraNotification.asmx",
]

# Newer Web-API controllers (the /api/api/* style seen in traffic)
API_GUESSES = [
    "/api/api/postal/",
    "/api/api/diur/",
    "/api/api/sms/",
    "/api/api/mail/",
    "/api/api/message/",
    "/api/api/notification/",
]

SEND_HINT = re.compile(r'(send|sms|mail|email|dispatch|diur|דיוור|הודע|notif|postal|message)', re.I)
DOC_HINT  = re.compile(r'(document|docid|מסמך)', re.I)

def probe_asmx(s, path):
    url = SHIRA + path
    try:
        r = s.get(url, timeout=15)
    except Exception as e:
        print(f"  {path}: ERROR {e}"); return
    if r.status_code != 200:
        print(f"  {path}: HTTP {r.status_code}")
        return
    # method names appear as <a href="ServiceName.asmx?op=Method">
    methods = re.findall(r'\?op=(\w+)', r.text)
    methods = sorted(set(methods))
    print(f"\n  === {path}  ({len(methods)} methods) ===")
    for m in methods:
        flag = ""
        if SEND_HINT.search(m):
            flag = "  <<< SEND-RELATED"
        print(f"    {m}{flag}")
    # For each send-related method, fetch its op page to see params
    for m in methods:
        if SEND_HINT.search(m):
            op_url = f"{url}?op={m}"
            try:
                rr = s.get(op_url, timeout=15)
                params = re.findall(r'<b>(\w+)</b>', rr.text)
                needs_doc = any(DOC_HINT.search(p) for p in params)
                print(f"      -> {m} params={params[:12]}  needsDoc={needs_doc}")
            except Exception as e:
                print(f"      -> {m} (param probe error {e})")

def probe_api(s, path):
    url = SHIRA + path
    try:
        r = s.get(url, timeout=10)
        print(f"  {path}: HTTP {r.status_code}  len={len(r.text)}")
        if r.status_code in (200, 400, 405):
            print(f"      {r.text[:200]}")
    except Exception as e:
        print(f"  {path}: ERROR {e}")

def main():
    s = make_session()
    print("=" * 60)
    print("  Discover Shira dispatch services (document-free send?)")
    print("=" * 60)

    print("\n[ASMX services]")
    for p in ASMX:
        probe_asmx(s, p)

    print("\n[Web-API controller guesses]")
    for p in API_GUESSES:
        probe_api(s, p)

    print("\nDone. Look for '<<< SEND-RELATED' methods with needsDoc=False.")

if __name__ == "__main__":
    main()
