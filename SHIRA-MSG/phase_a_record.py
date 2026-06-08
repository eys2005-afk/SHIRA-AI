"""
phase_a_record.py
=================
Connects to your existing Chrome browser (already logged in to Shira)
and records all network requests while you do the document upload manually.

STEP 1 — Close Chrome completely, then relaunch it with remote debugging:
    "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222

STEP 2 — Run this script:
    python phase_a_record.py

STEP 3 — In Chrome: navigate to a Shira case → Documents tab → upload a .docx → save
STEP 4 — Press ENTER in this CMD window when done
"""

import asyncio, re, sys
from playwright.async_api import async_playwright

TARGET_HOST = "shira2"

async def main():
    print("=" * 60)
    print("  Shira network recorder  (connecting to your Chrome)")
    print("=" * 60)
    print("\nMake sure Chrome was launched with:")
    print('  chrome.exe --remote-debugging-port=9222\n')
    print("Connecting to Chrome on localhost:9222 ...")

    captured = []

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        except Exception as e:
            print(f"\n❌ Could not connect: {e}")
            print("\nMake sure you launched Chrome with --remote-debugging-port=9222")
            return

        print("✅ Connected to Chrome!\n")

        # Use the first existing context/page
        contexts = browser.contexts
        if not contexts:
            context = await browser.new_context()
        else:
            context = contexts[0]

        pages = context.pages
        if not pages:
            page = await context.new_page()
        else:
            page = pages[0]

        # Capture every request+response on shira2
        async def on_request(request):
            if TARGET_HOST in request.url:
                captured.append({
                    "type": "request",
                    "method": request.method,
                    "url": request.url,
                    "post_data": (request.post_data or "")[:1000],
                })

        async def on_response(response):
            if TARGET_HOST in response.url:
                try:
                    body = await response.text()
                except Exception:
                    body = "(binary)"
                captured.append({
                    "type": "response",
                    "status": response.status,
                    "url": response.url,
                    "body": body[:3000],
                })

        # Listen on all pages in the context
        context.on("request", on_request)
        context.on("response", on_response)

        print("Recording started. Go do the document upload in Chrome now.")
        print("Press ENTER here when you're done...")
        await asyncio.get_event_loop().run_in_executor(None, input)

    # ── Print results ─────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  Captured network traffic")
    print("=" * 60)

    requests_list  = [c for c in captured if c["type"] == "request"]
    response_map   = {}
    for c in captured:
        if c["type"] == "response":
            response_map[c["url"]] = c

    printed = set()
    for req in requests_list:
        key = req["method"] + req["url"]
        if key in printed:
            continue
        printed.add(key)

        # Skip static assets
        url = req["url"]
        if any(url.endswith(ext) for ext in (".js", ".css", ".png", ".gif", ".ico")):
            continue
        if "WebResource.axd" in url or "ScriptResource" in url:
            continue

        resp  = response_map.get(url, {})
        body  = resp.get("body", "")
        status = resp.get("status", "?")

        print(f"\n{'─'*55}")
        print(f"  {req['method']}  {url}")
        print(f"  Status: {status}")
        if req.get("post_data"):
            print(f"  POST: {req['post_data'][:600]}")
        if body and req["method"] != "GET":
            print(f"  Response: {body[:600]}")

        # Flag possible DocumentIDs
        nums = re.findall(r'\b(\d{7,10})\b', body)
        if nums:
            print(f"\n  *** Numbers in response: {nums[:10]} ***")

    print("\n" + "=" * 60)
    print("  Done — look for POST requests and '*** Numbers ***' lines")
    print("=" * 60)

asyncio.run(main())
