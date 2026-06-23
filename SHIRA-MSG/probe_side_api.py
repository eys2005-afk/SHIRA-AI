"""
probe_side_api.py — probe the Shira REST API for party contact details.
=======================================================================
We know from network capture that Shira uses:
    http://shira2/api/api/FileSearch/GetFileDetailsFileId?fileId=...

So the base is http://shira2/api/api/ — try all likely endpoints for
party details (email, phone, ID number).

Known party ID from scrape_postal_grid.py: 1682244
Known fileMainId: 1295887

Usage:
    python probe_side_api.py
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    from requests_negotiate_sspi import HttpNegotiateAuth
    AUTH = HttpNegotiateAuth()
except ImportError:
    AUTH = None
    print("WARNING: requests_negotiate_sspi not installed — trying without auth")

import requests
SESSION = requests.Session()
if AUTH:
    SESSION.auth = AUTH
SESSION.headers.update({"Accept": "application/json"})

SHIRA     = "http://shira2"
API       = f"{SHIRA}/api/api"
SIDE_ID   = 1682244
FILE_ID   = 2923739
FILE_MAIN = 1295887

ENDPOINTS = [
    # Side / party
    f"{API}/Side/GetSideDetails?sideId={SIDE_ID}",
    f"{API}/Side/GetSide?sideId={SIDE_ID}",
    f"{API}/Side/GetSideById?id={SIDE_ID}",
    f"{API}/Side/{SIDE_ID}",
    f"{API}/FileSide/GetSideDetails?sideId={SIDE_ID}",
    f"{API}/FileSide/GetFileSides?fileId={FILE_ID}",
    f"{API}/FileSide/GetFileSides?fileMainId={FILE_MAIN}",
    f"{API}/FileSide/GetSides?fileId={FILE_ID}",
    # Person
    f"{API}/Person/GetPersonDetails?personId={SIDE_ID}",
    f"{API}/Person/GetPerson?personId={SIDE_ID}",
    f"{API}/Person/{SIDE_ID}",
    # Contact
    f"{API}/Contact/GetContacts?sideId={SIDE_ID}",
    f"{API}/Contact/GetSideContacts?sideId={SIDE_ID}",
    f"{API}/SideContact/GetSideContacts?sideId={SIDE_ID}",
    # File sides list
    f"{API}/FileSearch/GetFileSides?fileId={FILE_ID}",
    f"{API}/FileSearch/GetFileSides?fileMainId={FILE_MAIN}",
    f"{API}/FileSideList/GetFileSides?fileId={FILE_ID}",
]

def probe(url):
    try:
        r = SESSION.get(url, timeout=10)
        short = r.text[:300].replace("\n", " ")
        return r.status_code, short
    except Exception as e:
        return 0, str(e)[:100]

print("=" * 70)
print("  Probing Shira REST API for party contact details")
print("=" * 70)
for url in ENDPOINTS:
    status, body = probe(url)
    marker = ">>>" if status == 200 else "   "
    print(f"{marker} [{status}] {url}")
    if status == 200:
        print(f"         {body}")
print("=" * 70)
