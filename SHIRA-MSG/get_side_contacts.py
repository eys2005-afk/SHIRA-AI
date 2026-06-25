"""
get_side_contacts.py — fetch party contact details (email, phone, ID) from Shira.
==================================================================================
Discovered flow (from Playwright network capture, 2026-06-25):

  Step 1 — GET FileSides.aspx  → HTML table with SideID, PersonID, name, type
  Step 2 — GET Person.aspx?PersonID=X&SideID=Y&FileID=Z  → HTML form with all
            contact fields: email, phone, mobile, ID number, address, etc.

Both pages use classic ASP.NET HTML — no JSON API, no ASMX.
Auth: Windows NTLM (requests_negotiate_sspi).

Usage:
    python get_side_contacts.py <fileId> [courtId]
    python get_side_contacts.py 2923739 5
"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import requests, urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings()

try:
    from requests_negotiate_sspi import HttpNegotiateAuth
    AUTH = HttpNegotiateAuth()
except ImportError:
    AUTH = None
    print("WARNING: requests_negotiate_sspi not installed")

import os
os.environ['NO_PROXY'] = 'shira2,prod-spfe,10.67.60.51,localhost,127.0.0.1'

SESSION = requests.Session()
if AUTH:
    SESSION.auth = AUTH
SESSION.verify = False
SESSION.proxies = {"http": None, "https": None}
SESSION.headers.update({"User-Agent": "Mozilla/5.0"})

SHIRA    = "http://shira2"
USER_ID  = 1438
COURT_ID = int(sys.argv[2]) if len(sys.argv) > 2 else 5
FILE_ID  = sys.argv[1] if len(sys.argv) > 1 else "2923739"


def get_sides(file_id):
    """Fetch FileSides.aspx and extract SideID, PersonID, name, type."""
    url = (f"{SHIRA}/classic/Forms/File/Contents/FileSides.aspx"
           f"?userid={USER_ID}&courtid={COURT_ID}"
           f"&FileID={file_id}&EntityId={file_id}&EntityTypeId=6")
    r = SESSION.get(url, timeout=15)
    if r.status_code != 200:
        print(f"[FAIL] FileSides.aspx → {r.status_code}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    sides = []

    # Each party row links to Person.aspx — extract params from the href
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "Person.aspx" not in href:
            continue
        params = dict(re.findall(r'([A-Za-z]+)=([^&]+)', href))
        person_id = params.get("PersonID", "")
        side_id   = params.get("SideID", "")
        side_type = params.get("SideTypeID", "")
        name      = a.get_text(strip=True)
        if person_id:
            sides.append({
                "personId": person_id,
                "sideId":   side_id,
                "sideTypeId": side_type,
                "name":     name,
                "href":     href,
            })

    # Fallback: look for PersonID in any onclick / JS
    if not sides:
        for tag in soup.find_all(attrs={"onclick": True}):
            m = re.search(r'PersonID=(\d+).*?SideID=(\d+)', tag["onclick"])
            if m:
                sides.append({
                    "personId": m.group(1),
                    "sideId":   m.group(2),
                    "name":     tag.get_text(strip=True),
                })

    return sides


def get_person_details(file_id, person_id, side_id, side_type_id="1"):
    """Fetch Person.aspx and extract contact fields."""
    url = (f"{SHIRA}/classic/Forms/General/Person/Person.aspx"
           f"?FileID={file_id}&PersonID={person_id}"
           f"&SideType=1&SideTypeID={side_type_id}&SideID={side_id}")
    r = SESSION.get(url, timeout=15)
    if r.status_code != 200:
        print(f"  [FAIL] Person.aspx → {r.status_code}")
        return {}

    soup = BeautifulSoup(r.text, "html.parser")

    def val(name):
        tag = soup.find("input", {"name": name}) or soup.find("select", {"name": name})
        if tag:
            return tag.get("value", "").strip()
        # also try textarea
        tag = soup.find("textarea", {"name": name})
        if tag:
            return tag.get_text(strip=True)
        return ""

    # Try to find email and phone by common input names
    contact = {
        "personId": person_id,
        "sideId":   side_id,
        "firstName":  val("txtFirstName") or val("txtPersonFirstName"),
        "lastName":   val("txtLastName")  or val("txtPersonLastName"),
        "idNum":      val("txtIDNumber")  or val("txtPersonIDNumber"),
        "email":      val("txtEmail")     or val("txtPersonEmail"),
        "phone":      val("txtPhone")     or val("txtPersonPhone"),
        "mobile":     val("txtMobile")    or val("txtPersonMobile"),
        "address":    val("txtAddress")   or val("txtPersonAddress"),
    }

    # If fields not found by name, dump all input names+values for inspection
    if not contact["email"] and not contact["phone"]:
        print("  [INFO] Known field names not found. All input fields:")
        for inp in soup.find_all(["input", "select", "textarea"]):
            n = inp.get("name", "")
            v = inp.get("value", inp.get_text(strip=True))[:60]
            if n:
                print(f"    {n} = {v!r}")

    return contact


def main():
    print("=" * 64)
    print(f"  Party contact lookup  fileId={FILE_ID}  courtId={COURT_ID}")
    print("=" * 64)

    sides = get_sides(FILE_ID)
    if not sides:
        print("  No party links found in FileSides.aspx")
        return

    print(f"\n  Found {len(sides)} party link(s):\n")
    for s in sides:
        print(f"  PersonID={s['personId']}  SideID={s['sideId']}  name={s['name']!r}")
        details = get_person_details(
            FILE_ID, s["personId"], s["sideId"], s.get("sideTypeId", "1"))
        for k, v in details.items():
            if v:
                print(f"    {k}: {v}")
        print()

    print("=" * 64)


if __name__ == "__main__":
    main()
