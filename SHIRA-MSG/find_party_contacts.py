"""
find_party_contacts.py — discover how Shira exposes case party email/phone.
===========================================================================
We need to send Option B emails to the right address. This script probes
Shira's known API endpoints to find how to get a party's email + mobile
for a given file (case).

Run:
    python find_party_contacts.py > contacts.txt 2>&1
    type contacts.txt
"""
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import requests
from requests_negotiate_sspi import HttpNegotiateAuth

os.environ['NO_PROXY'] = 'shira2,prod-spfe,localhost,127.0.0.1'
os.environ['no_proxy'] = 'shira2,prod-spfe,localhost,127.0.0.1'

SHIRA   = "http://shira2"
FILE_ID = 2923739   # test case — change if needed

def make_session():
    s = requests.Session()
    s.auth = HttpNegotiateAuth()
    s.trust_env = False
    s.proxies = {}
    s.verify = False
    return s

def try_post(s, url, body, label):
    print(f"\n--- {label} ---")
    print(f"  POST {url}")
    print(f"  body: {json.dumps(body)[:200]}")
    try:
        r = s.post(url, json=body, timeout=15)
        print(f"  status: {r.status_code}  len={len(r.text)}")
        print(f"  response: {r.text[:600]}")
    except Exception as e:
        print(f"  ERROR: {e}")

def try_get(s, url, label):
    print(f"\n--- {label} ---")
    print(f"  GET {url}")
    try:
        r = s.get(url, timeout=15)
        print(f"  status: {r.status_code}  len={len(r.text)}")
        print(f"  response: {r.text[:600]}")
    except Exception as e:
        print(f"  ERROR: {e}")

def main():
    s = make_session()
    print("=" * 60)
    print("  Shira — find party contact endpoints")
    print("=" * 60)

    # 1. api/api style endpoints (newer REST)
    rest_guesses = [
        f"/api/api/fileParties/GetFileParties?fileId={FILE_ID}",
        f"/api/api/fileParties/GetParties?fileId={FILE_ID}",
        f"/api/api/parties/GetParties?fileId={FILE_ID}",
        f"/api/api/postal/GetPostalAddressDetails?fileId={FILE_ID}",
        f"/api/api/postal/GetAddressDetails?fileId={FILE_ID}",
        f"/api/api/diur/GetRecipients?fileId={FILE_ID}",
        f"/api/api/fileContact/GetFileContacts?fileId={FILE_ID}",
        f"/api/api/contacts/GetContacts?fileId={FILE_ID}",
        f"/api/api/FileParty/GetFileParties?fileId={FILE_ID}",
        f"/api/api/FileParty/GetFilePartiesData?fileId={FILE_ID}",
    ]
    for path in rest_guesses:
        try_get(s, SHIRA + path, path)

    # 2. WsShiraUtils methods that might return party data
    asmx = f"{SHIRA}/classic/WS/App/WsShiraUtils.asmx"
    utils_bodies = [
        ({"XmlData": f"<XmlData><FileID>{FILE_ID}</FileID></XmlData>"}, "GetFileParties"),
        ({"XmlData": f"<XmlData><FileID>{FILE_ID}</FileID></XmlData>"}, "GetFileContacts"),
        ({"XmlData": f"<XmlData><FileID>{FILE_ID}</FileID></XmlData>"}, "GetPostalRecipients"),
        ({"XmlData": f"<XmlData><FileID>{FILE_ID}</FileID></XmlData>"}, "GetPartiesDetails"),
    ]
    for body, method in utils_bodies:
        try_post(s, f"{asmx}/{method}", body, f"WsShiraUtils/{method}")

    # 3. GetFilePartyList (seen in some Shira versions)
    try_post(s, f"{asmx}/GetFilePartyList",
             {"XmlData": f"<XmlData><FileID>{FILE_ID}</FileID></XmlData>"},
             "WsShiraUtils/GetFilePartyList")

    # 4. Postal.aspx itself loads the recipient grid — grab its HTML
    print(f"\n--- Postal.aspx HTML (first 3000 chars) ---")
    postal_url = f"{SHIRA}/classic/Forms/Postal/Postal.aspx?DocumentIDs=14732119&FileID={FILE_ID}"
    try:
        r = s.get(postal_url, timeout=15)
        print(f"  status: {r.status_code}  len={len(r.text)}")
        # look for email/phone in the HTML
        import re
        emails = re.findall(r'[\w.+-]+@[\w.-]+\.\w+', r.text)
        phones = re.findall(r'\b05\d[-\s]?\d{7}\b', r.text)
        print(f"  emails found: {list(set(emails))[:10]}")
        print(f"  phones found: {list(set(phones))[:10]}")
        print(f"  HTML: {r.text[:3000]}")
    except Exception as e:
        print(f"  ERROR: {e}")

    # 5. Check the Postal ASMX
    print(f"\n--- WsShiraPostal.asmx ---")
    postal_asmx = f"{SHIRA}/classic/WS/App/WsShiraPostal.asmx"
    try:
        r = s.get(postal_asmx, timeout=15)
        print(f"  status: {r.status_code}  len={len(r.text)}")
        import re
        methods = re.findall(r'\?op=(\w+)', r.text)
        print(f"  methods: {methods}")
        if r.status_code == 200:
            print(f"  HTML: {r.text[:500]}")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n" + "=" * 60)
    print("  Done. Look for email/phone fields in any 200 response.")
    print("=" * 60)

if __name__ == "__main__":
    main()
