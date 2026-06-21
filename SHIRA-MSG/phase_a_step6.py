"""
Phase A — Step 6
Try different __FORM_ACTION values against UploadScanDocument.aspx.
We already know the full form fields from the HTML dump (step 4).
For each candidate action we POST and look for a non-zero hdnDocumentID in the response.

Run:
    python phase_a_step6.py > step6.txt 2>&1
    notepad step6.txt
"""
import os, re, time
import requests
from requests_negotiate_sspi import HttpNegotiateAuth

os.environ['NO_PROXY'] = 'shira2,prod-spfe,localhost,127.0.0.1'
os.environ['no_proxy'] = 'shira2,prod-spfe,localhost,127.0.0.1'

SHIRA   = "http://shira2"
FILE_ID = "2923739"   # real file
ENTITY_ID = "1936401" # entity from recorded network tab

# The UNC temp dir shown in the HTML (hdnDestinationTempDir)
UNC_TEMP = r"\\Prod-nas1\filer$\Root\Data\Users\elchanans\ScanDocuments\Temp"

# ── Candidate ACTION values ───────────────────────────────────────────────────
# In Shira the pattern is usually SAVE_STAY, SAVE, SAVE_AND_STAY, etc.
# uploadscandocument.js calls JS_SubmitForm(ACTION_SAVE_STAY).
# We'll also try the integer 4 (common pattern in Shira's globals).
CANDIDATES = [
    "SAVE_STAY",
    "ACTION_SAVE_STAY",
    "SAVE",
    "SAVE_AND_STAY",
    "4",
    "3",
    "1",
    "2",
    "5",
    "0",
]

def make_session():
    s = requests.Session()
    s.auth      = HttpNegotiateAuth()
    s.trust_env = False
    s.proxies   = {}
    s.verify    = False
    return s

def get_viewstate(session):
    """Fetch the page first to get VIEWSTATE / EVENTVALIDATION."""
    url = (f"{SHIRA}/classic/Forms/Documents/Scan/UploadScanDocument.aspx"
           f"?FileID={FILE_ID}&EntityTypeID=1&EntityID={ENTITY_ID}&DocumentID=0")
    r = session.get(url, timeout=20)
    vs  = re.search(r'id="__VIEWSTATE"\s+value="([^"]*)"', r.text)
    ev  = re.search(r'id="__EVENTVALIDATION"\s+value="([^"]*)"', r.text)
    vsg = re.search(r'id="__VIEWSTATEGENERATOR"\s+value="([^"]*)"', r.text)
    return {
        "__VIEWSTATE":          vs.group(1)  if vs  else "",
        "__EVENTVALIDATION":    ev.group(1)  if ev  else "",
        "__VIEWSTATEGENERATOR": vsg.group(1) if vsg else "",
        "raw": r.text,
    }

def extract_doc_id(html):
    m = re.search(r'id="hdnDocumentID"\s+value="(\d+)"', html)
    return int(m.group(1)) if m else None

def try_action(session, vs_data, action):
    url = f"{SHIRA}/classic/Forms/Documents/Scan/UploadScanDocument.aspx"
    form = {
        "__VIEWSTATE":          vs_data["__VIEWSTATE"],
        "__VIEWSTATEGENERATOR": vs_data["__VIEWSTATEGENERATOR"],
        "__EVENTVALIDATION":    vs_data["__EVENTVALIDATION"],
        "__FORM_ACTION":        action,
        "__FORM_SUBMIT_COUNTER": "1",
        "__SHIRA_USER_ID":      "1438",
        "__SHIRA_COURT_ID":     "5",
        "__SHIRA_FORMBASE_SCREEN_ID": "47",
        "hdnFileID":            FILE_ID,
        "hdnEntityTypeID":      "1",
        "hdnEntityID":          ENTITY_ID,
        "hdnDocumentID":        "0",
        "hdnDestinationTempDir": UNC_TEMP,
        "cboFileSide":          "0",   # neutral — no party side
        "cboScanType":          "1",   # כתב
        "cboScanSource":        "5",   # דוא"ל
    }
    try:
        r = session.post(url, data=form,
                         headers={"Referer": url},
                         timeout=25)
        doc_id = extract_doc_id(r.text)
        # Also check for any error/success indicators
        has_error = "שגיאה" in r.text or "error" in r.text.lower()
        return r.status_code, doc_id, len(r.text), has_error
    except Exception as e:
        return 0, None, 0, str(e)

def main():
    print("=== Phase A Step 6 — ACTION_SAVE_STAY discovery ===\n")
    session = make_session()

    print("[+] Fetching VIEWSTATE from UploadScanDocument.aspx...")
    vs_data = get_viewstate(session)
    print(f"    VIEWSTATE length  : {len(vs_data['__VIEWSTATE'])}")
    print(f"    EVENTVALIDATION   : {len(vs_data['__EVENTVALIDATION'])} chars")
    print()

    # Also dump a snippet of the raw page to find any __FORM_ACTION hints
    raw = vs_data["raw"]
    # Look for ACTION_ constants or JS_SubmitForm calls
    for needle in ["ACTION_SAVE_STAY", "JS_SubmitForm", "__FORM_ACTION", "SAVE_STAY", "SubmitFormToServer"]:
        idx = raw.find(needle)
        if idx >= 0:
            print(f"  FOUND '{needle}' at pos {idx}:")
            print(f"    {raw[max(0,idx-40):idx+120]!r}")
            print()

    print("-" * 60)
    print(f"{'Action':<25}  {'HTTP':>5}  {'DocID':>12}  {'Len':>7}  Note")
    print("-" * 60)

    for action in CANDIDATES:
        status, doc_id, length, has_err = try_action(session, vs_data, action)
        note = "ERROR" if isinstance(has_err, str) else ("has_error" if has_err else "ok")
        star = " *** HIT ***" if doc_id and doc_id > 0 else ""
        print(f"{action:<25}  {status:>5}  {str(doc_id):>12}  {length:>7}  {note}{star}")
        time.sleep(0.5)   # be polite to the server

    print("-" * 60)
    print("\nDone. Look for '*** HIT ***' rows.")

if __name__ == "__main__":
    main()
