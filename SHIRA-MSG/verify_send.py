"""
verify_send.py — Did it actually succeed?
=========================================
Checks two things for a document we created in a case:
  1. The document exists in the case  (proven by its DocumentID)
  2. Whether it was SENT via Postal — by opening Postal.aspx for that
     document and reading its real on-screen status + a screenshot.

Run:
    python verify_send.py
A browser opens, loads the Postal screen for the document, saves a
screenshot (verify_postal.png), and prints the visible status text.
"""
import sys, io, os, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

SHIRA   = "http://shira2"
DOC_ID  = "14732119"     # the document we created
FILE_ID = "2923739"

def main():
    postal_url = f"{SHIRA}/classic/Forms/Postal/Postal.aspx?DocumentIDs={DOC_ID}&FileID={FILE_ID}"
    print("=" * 60)
    print("  Verify: was the message sent?")
    print("=" * 60)
    print(f"  DocumentID: {DOC_ID}")
    print(f"  Postal URL: {postal_url}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--auth-server-allowlist=*shira2*",
                  "--auth-negotiate-delegate-allowlist=*shira2*"],
        )
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()

        print("[1] Opening Postal screen for the document…")
        page.goto(postal_url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # screenshot proof
        shot = os.path.abspath("verify_postal.png")
        page.screenshot(path=shot, full_page=True)
        print(f"[2] Screenshot saved: {shot}")

        # dump visible text and look for status keywords
        try:
            text = page.inner_text("body")
        except Exception:
            text = ""
        print("\n[3] Status keywords found on the page:")
        keywords = ["נשלח", "נשלחה", "נשלחו", "ממתין", "טרם", "תאריך שליחה",
                    "נמען", "נמענים", "סטטוס", "דואר", "שגיאה", "הצלחה"]
        any_hit = False
        for kw in keywords:
            if kw in text:
                any_hit = True
                # print the surrounding context for each hit
                idx = text.find(kw)
                snippet = text[max(0, idx-30):idx+60].replace("\n", " ")
                print(f"   • '{kw}': …{snippet}…")
        if not any_hit:
            print("   (no status keywords matched — see the screenshot)")

        # also dump any grid rows that look like sent records (dates / recipients)
        print("\n[4] First 1500 chars of visible page text:")
        print("-" * 60)
        print(text[:1500])
        print("-" * 60)

        print("\nBrowser stays open 60s so you can look directly.")
        try:
            page.wait_for_timeout(60000)
        except Exception:
            pass
        browser.close()

    print("\nDone. Open verify_postal.png to see the exact screen.")

if __name__ == "__main__":
    main()
