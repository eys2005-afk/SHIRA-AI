"""
record_full.py — capture the COMPLETE Shira send (and delete) flow.
===================================================================
Unlike phase_a_record.py, this does NOT de-duplicate. It prints every
non-static request in the exact order it happened, with full POST bodies,
and highlights the __FORM_ACTION of each POST — so we can see the real
SEND trigger and, if you delete the test document, the DELETE call too.

Run:
    python record_full.py > full.txt 2>&1

In the browser that opens:
  1. Go to a case (enter the case number as usual)
  2. Send a message to a party (email or SMS) all the way through
  3. (optional) Delete that document from the case
  4. CLOSE the browser window
Then:  type full.txt   and paste it here.
"""
import asyncio, re, sys, io, urllib.parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from playwright.async_api import async_playwright

SHIRA       = "http://shira2"
TARGET_HOST = "shira2"
START_URL   = f"{SHIRA}/classic/"

STATIC = (".js", ".css", ".png", ".gif", ".ico", ".woff", ".woff2", ".jpg", ".jpeg", ".svg")

def form_action(post_data):
    if not post_data:
        return None
    m = re.search(r'__FORM_ACTION=([^&]*)', post_data)
    if m:
        return urllib.parse.unquote(m.group(1))
    return None

async def main():
    print("=" * 60)
    print("  Shira FULL recorder (no de-dup, ordered, full bodies)")
    print("=" * 60)

    events = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--auth-server-allowlist=*shira2*",
                  "--auth-negotiate-delegate-allowlist=*shira2*"],
        )
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        async def on_request(request):
            if TARGET_HOST not in request.url:
                return
            url = request.url
            if any(url.lower().split("?")[0].endswith(e) for e in STATIC):
                return
            if "WebResource.axd" in url or "ScriptResource" in url:
                return
            events.append({
                "method": request.method,
                "url": url,
                "post": request.post_data or "",
            })

        context.on("request", on_request)

        await page.goto(START_URL)
        print("\nBrowser open. Do ONE full send (and optional delete). Then close it.\n")

        try:
            await page.wait_for_event("close", timeout=900_000)
        except Exception:
            pass

    print("\n" + "=" * 60)
    print("  ORDERED traffic")
    print("=" * 60)
    for i, e in enumerate(events, 1):
        fa = form_action(e["post"])
        print(f"\n[{i}] {e['method']}  {e['url']}")
        if fa:
            print(f"     __FORM_ACTION = {fa}")
        if e["post"]:
            print(f"     POST: {e['post'][:1500]}")

    print("\n" + "=" * 60)
    print("  POSTs only, with their __FORM_ACTION (the send/delete trail)")
    print("=" * 60)
    for i, e in enumerate(events, 1):
        if e["method"] == "POST":
            fa = form_action(e["post"]) or "(none)"
            short = e["url"].replace(SHIRA, "")
            print(f"  [{i}] {short}   __FORM_ACTION={fa}")

asyncio.run(main())
