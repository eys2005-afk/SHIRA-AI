"""
find_side_email_playwright.py — use Playwright to intercept the network call
that returns party contact details (email, phone, ID) in Shira.

Uses the permanent Chrome profile (C:\\SHIRA AI\\browser_profile\\) that
already has Windows SSO — same approach as the batch case-closure tool (app.py).

Usage:
    python find_side_email_playwright.py [fileId] [courtId]
    python find_side_email_playwright.py 2923739 5
"""
import sys, io, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright

FILE_ID   = sys.argv[1] if len(sys.argv) > 1 else "2923739"
COURT_ID  = sys.argv[2] if len(sys.argv) > 2 else "5"
SHIRA     = "http://shira2"
PROFILE   = r"C:\SHIRA AI\browser_profile"


async def main():
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE,
            headless=False,
            args=[
                "--auth-server-allowlist=*shira2*",
                "--auth-negotiate-delegate-allowlist=*shira2*",
            ],
            no_viewport=True,
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        all_requests = []
        captured = []

        async def on_response(response):
            url = response.url
            if any(x in url.lower() for x in [
                "side", "person", "contact", "party", "ws", "asmx",
                "/api/", "getside", "getperson", "postal",
            ]):
                try:
                    body = await response.text()
                except Exception:
                    body = "(binary)"
                captured.append({"url": url, "status": response.status, "body": body[:600]})
                print(f"\n>>> [{response.status}] {url}")
                print(f"    {body[:400]}")

        async def on_request(req):
            if req.resource_type in ("xhr", "fetch", "document"):
                all_requests.append(f"[{req.resource_type}] {req.url}")

        page.on("response", on_response)
        page.on("request", on_request)

        # Navigate to the case
        print(f"Opening login: {SHIRA}/App/login")
        await page.goto(f"{SHIRA}/App/login", timeout=30000, wait_until="networkidle")
        await page.wait_for_timeout(2000)

        case_url = (f"{SHIRA}/classic/Forms/FileMain/FileMain.aspx"
                    f"?FileID={FILE_ID}&CourtID={COURT_ID}")
        print(f"Opening case: {case_url}")
        await page.goto(case_url, timeout=30000, wait_until="networkidle")

        print("\n" + "="*60)
        print("  Browser is open — you have 90 seconds.")
        print("  Click on a party card / party details to open")
        print("  the screen that shows email + phone.")
        print("="*60)
        await page.wait_for_timeout(90000)

        print("\n" + "="*60)
        print(f"  Captured (filtered) requests: {len(captured)}")
        print("="*60)
        for c in captured:
            print(f"\nURL   : {c['url']}")
            print(f"Status: {c['status']}")
            print(f"Body  : {c['body']}")
            print("-"*60)

        print("\n  ALL XHR/Fetch/Document requests seen:")
        for r in all_requests:
            print(f"  {r}")

        await ctx.close()


if __name__ == "__main__":
    asyncio.run(main())
