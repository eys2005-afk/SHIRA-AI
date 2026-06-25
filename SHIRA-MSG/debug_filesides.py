"""
debug_filesides.py — dump the raw HTML of FileSides.aspx to find PersonID links.
"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import requests, urllib3
urllib3.disable_warnings()
from bs4 import BeautifulSoup

try:
    from requests_negotiate_sspi import HttpNegotiateAuth
    AUTH = HttpNegotiateAuth()
except ImportError:
    AUTH = None

os.environ['NO_PROXY'] = 'shira2,prod-spfe,10.67.60.51,localhost,127.0.0.1'

SESSION = requests.Session()
if AUTH:
    SESSION.auth = AUTH
SESSION.verify = False
SESSION.proxies = {"http": None, "https": None}

SHIRA   = "http://shira2"
FILE_ID = sys.argv[1] if len(sys.argv) > 1 else "2923739"
COURT_ID = sys.argv[2] if len(sys.argv) > 2 else "5"
USER_ID = 1438

url = (f"{SHIRA}/classic/Forms/File/Contents/FileSides.aspx"
       f"?userid={USER_ID}&courtid={COURT_ID}"
       f"&FileID={FILE_ID}&EntityId={FILE_ID}&EntityTypeId=6")

print(f"Fetching: {url}")
r = SESSION.get(url, timeout=15)
print(f"Status: {r.status_code}")

# Save full HTML
with open("filesides_debug.html", "w", encoding="utf-8") as f:
    f.write(r.text)
print("Saved to filesides_debug.html")

soup = BeautifulSoup(r.text, "html.parser")

# Print all <a> tags
print("\n--- All <a> tags ---")
for a in soup.find_all("a", href=True)[:30]:
    print(f"  href={a['href'][:100]!r}  text={a.get_text(strip=True)[:40]!r}")

# Print all onclick attributes
print("\n--- All onclick attrs (first 30) ---")
for tag in soup.find_all(attrs={"onclick": True})[:30]:
    print(f"  <{tag.name}> onclick={tag['onclick'][:120]!r}")

# Print lines containing PersonID
print("\n--- Lines containing 'Person' ---")
for line in r.text.splitlines():
    if "Person" in line or "person" in line:
        print(" ", line.strip()[:150])
