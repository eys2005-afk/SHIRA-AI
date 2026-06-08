"""
phase_a_record.py
=================
Opens Shira's document upload form in a real browser (Playwright).
Records ALL network requests so we can see exactly which endpoint
creates the document record and what it returns.

Run:
    pip install playwright
    playwright install chromium
    python phase_a_record.py

Then manually upload any .docx file in the browser window that opens.
After you close the browser, this script prints every POST/XHR request
that was captured — especially any that return a DocumentID.
"""

import asyncio, json, re
from pathlib import Path
from playwright.async_api import async_playwright

SHIRA   = "http://shira2"
FILE_ID = "2923739"

UPLOAD_URL = (
    f"{SHIRA}/classic/Forms/Documents/Scan/IframeFromMyComputerDocument.aspx"
    f"?FileID={FILE_ID}&EntityTypeID=6&EntityID={FILE_ID}&DocumentID=0"
)

async def main():
    print("=" * 60)
    print("  Shira upload recorder")
    print("=" * 60)
    print(f"\nOpening: {UPLOAD_URL}")
    print("\nInstructions:")
    print("  1. The browser will open the Shira upload form")
    print("  2. Choose any .docx file and upload it normally")
    print("  3. Close the browser window when done")
    print("\nAll network requests will be printed below.\n")

    captured = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, channel="chrome")
        context = await browser.new_context(
            ignore_https_errors=True,
        )
        page = await context.new_page()

        # Capture every request+response
        async def on_request(request):
            captured.append({
                "type": "request",
                "method": request.method,
                "url": request.url,
                "post_data": request.post_data,
            })

        async def on_response(response):
            try:
                body = await response.text()
            except Exception:
                body = "(binary)"
            captured.append({
                "type": "response",
                "status": response.status,
                "url": response.url,
                "body": body[:2000],
            })

        page.on("request", on_request)
        page.on("response", on_response)

        await page.goto(UPLOAD_URL)
        print("Browser opened. Waiting for you to upload a file and close...")

        # Wait until browser is closed
        await browser.wait_for_event("disconnected")

    # ── Print results ─────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  Captured requests")
    print("=" * 60)

    requests_only = [c for c in captured if c["type"] == "request"]
    responses_only = {c["url"]: c for c in captured if c["type"] == "response"}

    for req in requests_only:
        if req["method"] in ("GET",) and ".js" in req["url"]:
            continue  # skip static JS files
        if req["method"] in ("GET",) and ".css" in req["url"]:
            continue

        resp = responses_only.get(req["url"], {})
        body = resp.get("body", "")
        status = resp.get("status", "?")

        print(f"\n{'─'*50}")
        print(f"  {req['method']}  {req['url']}")
        print(f"  Status: {status}")
        if req.get("post_data"):
            print(f"  POST data: {req['post_data'][:500]}")
        if body:
            print(f"  Response: {body[:500]}")

        # Highlight anything that looks like a DocumentID
        nums = re.findall(r'\b(\d{7,10})\b', body)
        nums = [n for n in nums if n != FILE_ID]
        if nums:
            print(f"\n  *** Possible DocumentIDs: {nums} ***")

    print("\n" + "=" * 60)
    print("  Done — check '*** Possible DocumentIDs ***' lines above")
    print("=" * 60)

asyncio.run(main())
