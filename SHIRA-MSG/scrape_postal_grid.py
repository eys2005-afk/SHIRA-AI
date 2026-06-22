"""
scrape_postal_grid.py — read the Postal.aspx recipient grid for a case.
========================================================================
Opens Postal.aspx in a real browser (Playwright, Windows auth), waits for
the grid to render, then extracts all visible party names + contact info
(email, phone, secured-mail address) from the grdSidePostals table.

Also probes WsShiraUtils.asmx with correct Content-Type: application/xml
to find a party-contact method.

Run:
    python scrape_postal_grid.py > grid.txt 2>&1
    type grid.txt
"""
import sys, io, os, asyncio, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

os.environ['NO_PROXY'] = 'shira2,prod-spfe,localhost,127.0.0.1'
os.environ['no_proxy'] = 'shira2,prod-spfe,localhost,127.0.0.1'

import requests
from requests_negotiate_sspi import HttpNegotiateAuth

SHIRA   = "http://shira2"
FILE_ID = 2923739
DOC_ID  = "14732119"   # a real doc from the test case — used only to open Postal

def make_session():
    s = requests.Session()
    s.auth = HttpNegotiateAuth()
    s.trust_env = False
    s.proxies = {}
    s.verify = False
    return s

# ── Part 1: probe ASMX with correct XML content-type ─────────────────────────

CANDIDATE_METHODS = [
    "GetFileParties",
    "GetFilePartyList",
    "GetFileContacts",
    "GetPostalRecipients",
    "GetPartiesDetails",
    "GetFileSides",
    "GetFileDetails",
    "GetFileSideContacts",
    "GetPartySideContacts",
]

def probe_asmx_xml(s):
    print("\n[Part 1] WsShiraUtils.asmx with application/xml")
    base = f"{SHIRA}/classic/WS/App/WsShiraUtils.asmx"
    for method in CANDIDATE_METHODS:
        xml = f"<XmlData><FileID>{FILE_ID}</FileID></XmlData>"
        try:
            r = s.post(f"{base}/{method}",
                       data=xml.encode("utf-8"),
                       headers={"Content-Type": "application/xml"},
                       timeout=10)
            short = r.text[:300].replace("\n", " ")
            print(f"  {method}: {r.status_code}  {short}")
        except Exception as e:
            print(f"  {method}: ERROR {e}")

# ── Part 2: Playwright — render Postal.aspx and read the grid ─────────────────

async def scrape_postal():
    from playwright.async_api import async_playwright

    postal_url = f"{SHIRA}/classic/Forms/Postal/Postal.aspx?DocumentIDs={DOC_ID}&FileID={FILE_ID}"
    print(f"\n[Part 2] Playwright scrape of Postal.aspx")
    print(f"  URL: {postal_url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--auth-server-allowlist=*shira2*",
                  "--auth-negotiate-delegate-allowlist=*shira2*"],
        )
        ctx  = browser.new_context(ignore_https_errors=True)
        page = await ctx.new_page()
        await page.goto(postal_url, wait_until="networkidle", timeout=30000)

        # Dump full page text
        text = await page.inner_text("body")
        print("\n  === Visible page text ===")
        print(text[:4000])

        # Try to find the grid table
        print("\n  === grdSidePostals table HTML ===")
        try:
            html = await page.inner_html("#grdSidePostals")
            print(html[:3000])
        except Exception:
            print("  (grid not found by id)")

        # Look for email/phone patterns in the page source
        src = await page.content()
        emails = list(set(re.findall(r'[\w.+-]+@[\w.-]+\.\w+', src)))
        phones = list(set(re.findall(r'0\d[-\s]?\d{7,8}', src)))
        print(f"\n  Emails in page source: {emails[:20]}")
        print(f"  Phones in page source: {phones[:20]}")

        # Also dump all input values (hidden fields carry party IDs)
        inputs = await page.query_selector_all("input[type=hidden]")
        print("\n  === Hidden input values ===")
        for inp in inputs[:40]:
            name  = await inp.get_attribute("name")  or ""
            value = await inp.get_attribute("value") or ""
            if name and value and len(value) < 200:
                print(f"    {name} = {value}")

        # Intercept the AJAX calls that populate the grid
        print("\n  Done.")
        await browser.close()

def main():
    s = make_session()
    probe_asmx_xml(s)
    asyncio.run(scrape_postal())

if __name__ == "__main__":
    main()
