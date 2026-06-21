"""
phase_a_record.py
=================
Uses Playwright's OWN bundled Chromium (not your enterprise Chrome),
launched with integrated Windows auth so it logs into shira2 seamlessly
with your domain credentials — no password prompt, no debug-port policy.

Run:
    python phase_a_record.py

A browser opens. Navigate to a Shira case → add a document → upload a .docx →
save it all the way through. Then close the browser window.
Every shira2 network request is printed below.
"""

import asyncio, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from playwright.async_api import async_playwright

SHIRA       = "http://shira2"
TARGET_HOST = "shira2"
START_URL   = f"{SHIRA}/classic/"

async def main():
    print("=" * 60)
    print("  Shira recorder (Playwright bundled Chromium + Windows auth)")
    print("=" * 60)

    captured = []

    async with async_playwright() as p:
        # Integrated Windows auth: let Chromium auto-send domain creds to shira2
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--auth-server-allowlist=*shira2*",
                "--auth-negotiate-delegate-allowlist=*shira2*",
            ],
        )
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        async def on_request(request):
            if TARGET_HOST in request.url:
                captured.append({
                    "type": "request",
                    "method": request.method,
                    "url": request.url,
                    "post_data": (request.post_data or "")[:1200],
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

        context.on("request", on_request)
        context.on("response", on_response)

        await page.goto(START_URL)
        print("\nBrowser open. Do the full document upload on a case.")
        print("CLOSE the browser window when done.\n")

        try:
            await page.wait_for_event("close", timeout=600_000)
        except Exception:
            pass

    # ── Print results ───────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  Captured shira2 traffic")
    print("=" * 60)

    requests_list = [c for c in captured if c["type"] == "request"]
    response_map  = {c["url"]: c for c in captured if c["type"] == "response"}

    printed = set()
    for req in requests_list:
        url = req["url"]
        if any(url.endswith(e) for e in (".js", ".css", ".png", ".gif", ".ico", ".woff", ".woff2")):
            continue
        if "WebResource.axd" in url or "ScriptResource" in url:
            continue
        key = req["method"] + url
        if key in printed:
            continue
        printed.add(key)

        resp   = response_map.get(url, {})
        body   = resp.get("body", "")
        status = resp.get("status", "?")

        print(f"\n{'-'*55}")
        print(f"  {req['method']}  {url}")
        print(f"  Status: {status}")
        if req.get("post_data"):
            print(f"  POST: {req['post_data'][:800]}")
        if body and req["method"] != "GET":
            print(f"  Response: {body[:800]}")
        nums = re.findall(r'\b(\d{7,10})\b', body)
        if nums:
            print(f"\n  *** Numbers in response: {nums[:10]} ***")

    print("\n" + "=" * 60)
    print("  Done — look at POST requests and '*** Numbers ***' lines")
    print("=" * 60)

asyncio.run(main())
