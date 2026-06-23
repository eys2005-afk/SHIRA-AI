"""
find_side_email_playwright.py — use Playwright to intercept the network call
that returns party contact details (email, phone, ID) in Shira.

Navigates to a case, clicks on a party row, and prints every XHR/Fetch
request+response so we can identify the endpoint to use in ShiraAI.

Usage:
    python find_side_email_playwright.py [fileId] [courtId]
    python find_side_email_playwright.py 2923739 5
"""
import sys, io, asyncio, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright

FILE_ID  = sys.argv[1] if len(sys.argv) > 1 else "2923739"
COURT_ID = sys.argv[2] if len(sys.argv) > 2 else "5"
SHIRA    = "http://shira2"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--auth-server-allowlist=*shira2*",
                "--auth-negotiate-delegate-allowlist=*shira2*",
            ],
        )
        ctx = await browser.new_context()
        page = await ctx.new_page()

        captured = []

        async def on_response(response):
            url = response.url
            if any(x in url.lower() for x in ["side", "person", "contact", "party",
                                                "צד", "ws", "asmx", "api", "json",
                                                "getside", "getperson"]):
                try:
                    body = await response.text()
                except Exception:
                    body = "(binary)"
                captured.append({
                    "url": url,
                    "status": response.status,
                    "body_preview": body[:500],
                })
                print(f"\n>>> CAPTURED: {url}  [{response.status}]")
                print(f"    {body[:300]}")

        page.on("response", on_response)

        # ---- Step 1: open case page ----
        case_url = f"{SHIRA}/classic/Forms/FileMain/FileMain.aspx?FileID={FILE_ID}&CourtID={COURT_ID}"
        print(f"Opening case: {case_url}")
        await page.goto(case_url, timeout=30000, wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # ---- Step 2: try clicking on "Sides" tab / party rows ----
        # Try common tab names for parties
        for selector in [
            "text=צדדים",
            "text=בעלי דין",
            "a[href*='Side']",
            "a[href*='side']",
            "#tabSides",
            "#lnkSides",
            "li:has-text('צדדים')",
        ]:
            try:
                el = page.locator(selector).first
                if await el.count() > 0:
                    print(f"\nClicking sides tab: {selector}")
                    await el.click()
                    await page.wait_for_timeout(2000)
                    break
            except Exception:
                pass

        # ---- Step 3: click first party row to open details ----
        for selector in [
            "table.grid tr:nth-child(2)",
            "tr.grid-row",
            "a[href*='SideID']",
            "a[href*='PersonID']",
            "td.grid-cell:first-child",
        ]:
            try:
                el = page.locator(selector).first
                if await el.count() > 0:
                    print(f"\nClicking party row: {selector}")
                    await el.click()
                    await page.wait_for_timeout(3000)
                    break
            except Exception:
                pass

        # ---- Step 4: also intercept ALL requests for 10 sec ----
        print("\n\nWaiting 10s — please manually click on a party row in the browser...")
        await page.wait_for_timeout(10000)

        # ---- Step 5: dump everything captured ----
        print("\n" + "="*60)
        print(f"  Total requests captured: {len(captured)}")
        print("="*60)
        for c in captured:
            print(f"\nURL   : {c['url']}")
            print(f"Status: {c['status']}")
            print(f"Body  : {c['body_preview']}")
            print("-"*60)

        # Also dump ALL network requests (not filtered)
        all_requests = []
        async def on_req(req):
            if req.resource_type in ("xhr", "fetch"):
                all_requests.append(req.url)
        page.on("request", on_req)

        print("\nCapturing ALL XHR/Fetch for another 15s — click around the party details...")
        await page.wait_for_timeout(15000)

        print("\n" + "="*60)
        print("  ALL XHR/Fetch requests seen:")
        print("="*60)
        for u in all_requests:
            print(f"  {u}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
