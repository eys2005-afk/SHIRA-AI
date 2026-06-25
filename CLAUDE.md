# מערכת שיר"ה — מסמך אב טכני מקצה לקצה / Shira System — End-to-End Master Reference

> מסמך זה מרכז את כל מה שנאסף על מערכת שיר"ה (Taldor) לאורך כל השיחות, לצורך בנייה מחדש מאפס.
> This document consolidates everything gathered about the Shira system across all sessions, for a from-scratch rebuild.
>
> **שימוש מומלץ / Recommended use:** שמור כ-`CLAUDE.md` בשורש הפרויקט, או הזן ל-Claude Code כקובץ הקשר.
> Save as `CLAUDE.md` in the project root, or feed to Claude Code as context.

---

## 0. הקשר וזהות / Context & Identity

| שדה / Field | ערך / Value |
|---|---|
| Username | `elchanans` |
| User ID | `1438` |
| Court | בית הדין הרבני רחובות / Beit Din Rehovot |
| Court ID | `5` |
| Domain | `rbc` / `BETDIN` (`rbc.gov.il`) |
| System vendor | Taldor |
| GitHub | `eys2005-afk` |

**הרכבים (רחובות) / Assemblies (Rehovot):**

| הרכב / Assembly | assemblyID |
|---|---|
| א / A | `15` |
| ב / B | `96` |
| ג / C | `107` |
| בי | `16` |
| פט | `17` |

**מיפוי בתי דין / Court ID map:**
1=ירושלים, 2=תל אביב, 3=חיפה, 4=פתח תקוה, **5=רחובות**, 6=באר שבע, 7=טבריה, 8=צפת, 9=אשדוד, 10=אשקלון, 11=נתניה, 12=בית הדין הגדול, 13=אריאל.

---

## 1. תשתית רשת — קבועים קריטיים / Network Infrastructure — Critical Constants

אלו הקבועים שחוזרים בכל פרויקט. בלעדיהם שום קריאה פנימית לא עובדת.
These constants recur in every project. Without them, no internal call works.

| רכיב / Component | ערך / Value |
|---|---|
| Corporate proxy | `192.168.174.80:8080` |
| Shira main host | `http://shira2` (IP `10.67.60.51:80`, ASP.NET / IIS) |
| Document SOAP service | `http://prod-spfe:1000/ShiraDocsMngWS.asmx` |
| SSL inspection | BlueCoat, `CN=TehilaRootCA`, thumbprint `2BDE3B42A945610134C5D2EC0E169241A7C837E5` |
| External tunneling | ngrok / localhost.run — **חסומים / blocked** by firewall |

### כללי זהב / Golden rules

1. **`session.trust_env = False`** — חובה לכל קריאה פנימית ל-shira2. בלי זה הבקשה עוברת דרך ה-proxy הארגוני לאינטרנט ומחזירה 404 מהרשות הדיגיטלית. / Mandatory for all internal shira2 calls. Without it, the request routes through the corporate proxy to the internet and returns a 404 from the national digital authority.
2. **NTLM auth** דרך `requests_negotiate_sspi` — `HttpNegotiateAuth()`. משתמש ב-token של ה-Windows session הנוכחי (אין צורך בסיסמה). / Uses the current Windows session token (no password needed).
3. **קריאות AI חיצוניות** (Gemini) — דווקא **כן** דרך ה-proxy הארגוני. / External AI calls (Gemini) **do** go through the corporate proxy.
4. **`urllib3.disable_warnings()`** + `session.verify = False` — בגלל BlueCoat. / Because of BlueCoat SSL interception.

### תבנית session בסיסית / Base session template

```python
import requests
from requests_negotiate_sspi import HttpNegotiateAuth
import urllib3
urllib3.disable_warnings()

session = requests.Session()
session.auth = HttpNegotiateAuth()        # current Windows token
session.verify = False                    # BlueCoat
session.trust_env = False                 # CRITICAL — bypass corporate proxy for internal calls
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin": "http://shira2",
})
```

🆕 **Production session template (from actual shira_proxy.py, 2026-06-10):** the live code uses `proxies={"http": None, "https": None}` instead of `trust_env=False`, plus sets `NO_PROXY` env var at module load:
```python
os.environ['NO_PROXY'] = 'shira2,prod-spfe,10.67.60.51,localhost,127.0.0.1'
ssl._create_default_https_context = ssl._create_unverified_context  # global BlueCoat bypass

def make_session():
    s = requests.Session()
    s.auth = HttpNegotiateAuth()
    s.headers.update({"Content-Type": "application/json; charset=UTF-8",
                       "Origin": SHIRA, "Referer": f"{SHIRA}/App/main/files/files-list"})
    s.proxies = {"http": None, "https": None}  # ← used instead of trust_env=False
    return s
```
> ⚠️ Both approaches work; `proxies=None` + `NO_PROXY` env var is what the current EXE actually runs.

🆕 **Dashboard proxy (old, port 3000)** uses `requests_ntlm.HttpNtlmAuth('', '', send_cbt=False)` (NOT `requests_negotiate_sspi`!) with blank credentials and `proxies={'http':'','https':''}`. (from Claude Code, 2026-06-10)

**pip behind proxy:** `pip install <pkg> --proxy http://192.168.174.80:8080`

---

## 2. ה-API של שיר"ה — מיפוי מלא / The Shira API — Full Map

### 2.1 חיפוש תיקים / File Search (POST)

```
POST http://shira2/api/api/FileSearch/GetAdvancedFileSearch
Content-Type: application/json
Auth: Windows SSPI (Negotiate)
```

**Payload עובד / Working payload:**

```json
{
  "courtID": 5,
  "assemblyId": null,
  "fileNumber": null,
  "fileMainID": null,
  "subjectID": null,
  "subjectSubID": null,
  "Composition": null,
  "FileStatusOpen": "-1",
  "FirstName": null,
  "IdNum1": "<<ID_HERE>>",
  "IdType1": 1,
  "IsOnlineFile": false,
  "LastName": null,
  "OldFileNum": "",
  "currentPage": 1,
  "fileStatusID": null,
  "insertDateFrom": null,
  "insertDateTo": null,
  "isCorrectName": false,
  "isPriority": false,
  "meetingDateFrom": null,
  "meetingDateTo": null,
  "rowsPerPage": 100
}
```

**אזהרות קריטיות / Critical caveats:**
- ⚠️ **תאריכים חובה / Dates mandatory:** אם `insertDateFrom`/`insertDateTo` הם `null`, סינון לפי `assemblyId` **מתעלם** ומחזיר מערך ריק. כדי לסנן לפי הרכב — חובה לספק טווח תאריכים. / If dates are null, `assemblyId` filtering is **ignored** and returns an empty array. To filter by assembly you must supply a date range.
- **מקסימום 500 שורות לעמוד / Max 500 rows per page.** Pagination: increment `currentPage` with fixed `rowsPerPage: 500` until a batch returns fewer than 500 rows.
- **דה-דופליקציה / Dedup:** combine results across date ranges and dedup by `fileId` (regex on ID numbers for unique couples).

**שדות בתשובה / Response fields:** `fileId`, `fileMainId`, `fileNumber`, `fullFileMainNumber` (עדיף על fileNumber — מחזיר "812804/13" ולא רק "13"), `subjectSubName`, `fileStatusID`, `isClosed`, `fileString`, `openDate` (`insertDate`), `sideA`, `sideB`, `courtName`, `courtId` (⚠️ **lowercase `d`** — שגיאה נפוצה בסינון / common filtering bug), `totalRows`, **`meetingStart`** (`"DD/MM/YYYY HH:MM"` — תאריך הדיון הבא; `"22:00"` = sentinel לשעה לא נקבעה), **`meetingTarget`** (סוג הטיפול: `"רגיל "` / `"החלטה"` / `"עיון"` / `"ישיבת פישור"` — לסנן `"עיון"` בהצגת יומן).

> ⚠️ **אין שדה תאריך סגירה ב-API.** `FileNumberCloseDate` קיים רק במודל ה-Power BI (`FactFile`), מאחורי gateway, לא נגיש מהדפדפן. קירוב מעשי: תיקים סגורים (`FileStatusOpen:"-1"`) מסוננים לפי `insertDate` ב-12 החודשים האחרונים. / No close-date field in the API. It lives only in the Power BI model behind a gateway. Practical workaround: closed files filtered by `insertDate` within last 12 months.

### 2.2 פרטי תיק / File Details (GET)

```
GET http://shira2/App/main/files/GetFileDetailsFileId?fileId=XXX
```

מחזיר / Returns:
```json
{
  "fileId": 2740575, "fileMainId": 1488524, "fileNumber": 1,
  "subjectSubId": 7, "subjectSubName": "גירושין",
  "fullFileMainNumber": "1488524/1", "fileStatusID": 5,
  "isClosed": false,
  "fileString": "1488524/1, גירושין, <side A>, <side B>",
  "openDate": "2024-07-18T09:00:00"
}
```

### 2.3 רשימת הרכבים / Assembly dropdown
```
GetFileDropdownList   (requires courtID → returns assemblyId + courtId)
```

### 2.4 משתמש / User
```
GET http://shira2/api/api/userController/GetUser
```

### 2.5 דיונים / Hearings
```
GET http://shira2/classic/Forms/File/Contents/FileMeetings.aspx?userid=0&courtid=0&FileID=XXX&EntityId=XXX&EntityTypeId=6
```
> הערה / Note: ה-endpoint הישן `XmlTableValues.aspx` היה **שגוי** לדיונים; השתמש ב-`FileMeetings.aspx`. / The old `XmlTableValues.aspx` endpoint was **wrong** for hearings; use `FileMeetings.aspx`.

🆕 **Hearings response fields** (parsed from `table#grdMeetings`, from production code, 2026-06-10):
- `hebrewDate` (col 0), `date` (col 1, DD/MM/YYYY), `purpose` (col 2), `status` (col 3: נקבע/נדחה/etc), `timeFrom` (col 4), `timeTo` (col 5), `panel` (col 6), `protoStatus` (col 8)
- 🆕 `protocolDocId` — extracted via `re.search(r"OpenDocument\((\d+)\)", str(tr))` — link to the hearing's protocol document

🆕 **Search by case number:**
```
POST http://shira2/api/api/FileSearch/GetAdvancedFileSearch
Payload: {"fileMainID": 1488524, "fileNumber": 1, "courtID": null, ...rest null}
```
(from `/api/search-case` route, 2026-06-10)

🆕 **Search by name:**
```
POST http://shira2/api/api/FileSearch/GetAdvancedFileSearch
Payload: {"FirstName": "...", "LastName": "...", "courtID": null, ...rest null}
```
Production code tries both (first=A last=B) and (first=B last=A) to catch reversed name order, deduplicates by `fileId`. (from Claude Code, 2026-06-10)

### 2.6 החלטות / Decisions
```
FileDecisions.aspx   → parse HTML for table id #grdDecision
```

🆕 **Documents table ID** — production code looks for `table#grdFileDocs` first, falls back to any table containing `OpenDocument`. Names come from the `<a>` tag text (not `onclick`); dates from regex `\d{2}/\d{2}/\d{4}` in the row text. (from Claude Code, 2026-06-10)

---

## 3. זרימת מסמכים / Document Flow

הזרימה המלאה לפתיחת/קריאת מסמך / Full flow to open & read a document:

```
DocumentID
  → http://shira2/classic/WS/App/WsShiraUtils.asmx/GetDocumentDetails   → DocNumber
  → http://prod-spfe:1000/ShiraDocsMngWS.asmx/GetDocumentUrlAndStatus   → file URL
  → http://shira2/TempGoogleDocs/{DocID}-{hash}-readOnly.docx           → actual file
```

**פתיחה ישירה / Direct open:**
```
GET http://shira2/classic/Forms/Documents/DM/DMOpenDocument.aspx?DocIDs=XXX&Action=1&FileID=YYY
```
`Action`: `0=ReadOnly`, `1=Edit`, `2=Print` (from `DM_OPEN_ACTION`). Virtual dir is `/classic`.

**רשימת מסמכים / Document list:**
```
GET http://shira2/classic/Forms/File/Contents/FileDocs.aspx?userid=0&courtid=0&FileID=XXX&EntityId=XXX&EntityTypeId=6
```
פרסור / Parse: extract via `OpenDocument(\d+)` for IDs; parse `href="javascript:OpenDocument()"` for names (not onclick). Use BeautifulSoup for text extraction.

**תיקיות cache / Cache folders:**
- `\\Prod-nas1\filer$\Root\Data\Users\elchanans\DMDocuments\Temp` — naming: `{DocumentID}-{hash}-readOnly.{ext}`
- `\\prod-tlv-b\filer$\Root\ShiraServers\TempGoogleDocs\` — cache only.

> 💡 DocIDs הם **גלובליים** וחוצי-בתי-דין — אין הגבלת גישה בין בתי דין. / DocIDs are global and cross-court; no access restriction between courts.

**קריאת תוכן בפועל / Reading content:** PDF via `pdfplumber`, DOCX via `python-docx`. Cap extracted text (~30,000 chars) before sending to AI.

🆕 **CONTRADICTION — PDF library:** CLAUDE.md says `pdfplumber`. The canonical `C:\SHIRA AI\shira_proxy.py` (v2.4, latest) switched to **`pdfminer.six`** (`from pdfminer.high_level import extract_text as pdf_extract_text`) to reduce EXE size (~280MB → ~60MB). The SHIRA1 copy (v2.1) still uses `pdfplumber`. Use `pdfminer.six` for new builds. (from git log + code, 2026-06-10)

🆕 **Scanned PDF (image-based) fallback:** if extracted text < 50 chars and file < 20MB, fall back to **Gemini OCR** — send PDF as base64 `inline_data` to `gemini-2.5-flash`. Prompt: `"חלץ את כל הטקסט מהמסמך. החזר רק את תוכן הטקסט בעברית, שמור על מבנה הפסקאות. ללא markdown."` (from shira_proxy.py, 2026-06-10)

🆕 **Reversed-PDF fix:** visual-order PDFs (some Shira scans) have RTL lines stored reversed. Production code reverses each line before sending to AI. (from git commit `ca59e58`, 2026-06-10)

🆕 **Content-type detection priority:** extension is stripped of query-string/fragment first (`furl.split("?")[0]`), then MIME type from `Content-Type` header takes precedence over extension. (from shira_proxy.py doctext route, 2026-06-10)

🆕 **`GetDocumentDetails` call format:** uses `application/xml` Content-Type with XML body: `<XmlData><DocumentID>{doc_id}</DocumentID></XmlData>`. `GetDocumentUrlAndStatus` called with JSON string body `{'docNumber':'...','isCopy':'true'}`. (from shira_proxy.py, 2026-06-10)

---

## 4. זרימת דוחות SSRS / SSRS Report Flow (יומן דיונים / Hearing Diary)

הדוחות בשיר"ה הם **SSRS** (SQL Server Reporting Services) דרך `ReportViewerWebControl.axd`.
Shira reports are SSRS via `ReportViewerWebControl.axd`. Three sequential requests:

**Step 1 — GET the form**, extract `__VIEWSTATE`, `__VIEWSTATEGENERATOR`, `__EVENTVALIDATION`:
```
GET http://shira2/classic/Forms/Reports/Rep001.aspx?userid=1438&courtid=5&FileID=2870728
```
(`FileID=2870728` = הדוח עצמו, לא תיק / the report ID itself, not a case. Rep001 = יומן הרכב; Rep008 = פעילות בבית הדין.)

**Step 2 — POST** with tokens + form fields (200 OK, ~44KB):
```python
data = {
    '__VIEWSTATE': viewstate, '__VIEWSTATEGENERATOR': viewstategen,
    '__EVENTVALIDATION': eventvalidation,
    '__FORM_ACTION': 'SHOW_REPORT',
    '__SHIRA_USER_ID': '1438', '__SHIRA_COURT_ID': '5',
    '__SHIRA_ALLOW_FILE_SEARCH': '0', '__SHIRA_FORMBASE_SCREEN_ID': '89',
    '__CLIENT_IP': '10.67.4.32', '__FORM_SUBMIT_COUNTER': '1',
    'cboCourt': '5',
    'cboAssembly': '-1',                  # -1 = all assemblies
    'txtFromDate': '07/06/2026',          # DD/MM/YYYY
    'txtToDate': '07/06/2026',            # DD/MM/YYYY
    'cboReportType': '1', 'cmdSearch': 'הצג דוח',
    'hdnCurrentReportId': '-1', 'hdnDefaultAssembly': '107',
}
```

**Step 3 — GET** the rendered report. Extract `ReportSession` + `ControlID` from the POST response, then:
```
GET http://shira2/classic/Reserved.ReportViewerWebControl.axd
    ?ReportSession={session}&ControlID={controlId}
    &Culture=1037&UICulture=1037&ReportStack=1
    &OpType=ReportArea&ZoomMode=FullPage          # ZoomMode REQUIRED, else 500
```

**Regex לחילוץ / Extraction regex:**
```
ReportSession=([a-zA-Z0-9]+)&ControlID=([a-zA-Z0-9]+).*?OpType=ReportArea
```
> ⚠️ ללא `ZoomMode=FullPage` → שגיאת 500 "Missing URL parameter: ZoomMode". / Without it → 500 error.
> התגובה היא HTML מלא עם כל הדיונים (שעה, הרכב, מספר תיק, צדדים, נושא). / Response is full HTML with all hearings.

**קובץ פרויקט / Project file:** `C:\Users\elchanans\Documents\AI\HEARINGS\test_hearing.py` (standalone, separate from shira_proxy).

🆕 **CSV export alternative** (in addition to HTML): the SSRS report also supports CSV export — same session/ControlID, just change the Step 3 URL:
```
GET http://shira2/classic/Reserved.ReportViewerWebControl.axd
    ?ReportSession={session}&ControlID={controlId}
    &Culture=1037&UICulture=1037&ReportStack=1
    &OpType=Export&FileName=Rep001
    &ContentDisposition=OnlyHtmlInline&Format=CSV
```
CSV columns: `AssemblyNameAndHall`, `AssemblyName`, `MeetingStartDate1`, `MeetingStartHour2`, `SubjectSubDesc`, `SideA_FullName`, `SideB_FullName`, `FileNumber`. Hall extracted via regex `r'אולם:\s*(\d+)'` from `AssemblyNameAndHall`. (from fetcher.py, 2026-06-10)

🆕 **`hdnDefaultAssembly` must be read from the live form**, not hardcoded — value varies by court. Use `soup.find('input', {'name': 'hdnDefaultAssembly'})['value']`. Similarly, `cboCourt` and `cboAssembly` values should be read from the rendered `<select>` elements, not hardcoded. (from fetcher.py, 2026-06-10)

🆕 **SSRS is court-scoped by NTLM identity — confirmed (2026-06-24):** requesting `Rep001.aspx?userid=1438&courtid=12` with court 5 NTLM credentials returns an HTML page with `form id="NotAllowed"` and the message "אין הרשאה לגשת לדוח זה". The URL parameters `userid` and `courtid` are display metadata only — the server grants access based solely on the authenticated NTLM token. To get another court's SSRS diary, the script **must run on a machine where that court's user is logged in**.

🆕 **`__SHIRA_FORMBASE_SCREEN_ID`** = `'89'` for Rep001 but read from form dynamically (`_val('__SHIRA_FORMBASE_SCREEN_ID') or '89'`). (from fetcher.py, 2026-06-10)

---

## 5. הגשת בקשות ציבורית / Public Submission Flow

מטרה / Goal: לאפשר לצדדים להגיש בקשות ישירות לשיר"ה. / Let parties submit requests directly into Shira.

- **Step 1 — יצירת בקשה / Create request:** `FileRequest.aspx` — **פתור / solved**.
- **Step 2 — צירוף מסמך / Attach document:** the harder part.

**זרימת ImportDocument המתוקנת / Correct ImportDocument flow:**
1. Copy file to `\\Prod-nas1\filer$\Root\Data\Users\elchanans\ScanDocuments\Temp\` with any name.
2. Call `ImportDocument` with the file path → returns a **real Shira document ID** (the filename **becomes** the doc ID).
3. Call `UploadFileToDM.aspx` / `UploadScanDocument.aspx` with that real document ID.

```
POST http://prod-spfe:1000/ShiraDocsMngWS.asmx/ImportDocument
Payload: {'fileUrl': '\\\\Prod-nas1\\filer$\\...\\Temp\\14656917.docx',
          'shiraDocId': '14656917', 'courtId': '5', 'isReadOnly': 'false'}
```

**סקריפטים / Scripts:** `shira_full_submit.py`, `test_upload_dm.py` (Desktop).
**אופציה / Option:** Playwright to bypass VIEWSTATE complexity.

---

## 6. מודול הודעות / Messaging Module

פרוטוטיפ HTML+JS עצמאי לשליחת התראות רשמיות מתוך תיק. / Standalone HTML+JS prototype to send official notifications from within a case.

- מעטפה אוטומטית / Auto-envelope: court name, case number, subject, side A, side B.
- תבניות מערכת / System templates: hearing invitation, postponement, document request, decision notification.
- תבניות משתמש / User templates: managed via `localStorage`.
- צ'קבוקסים לנמענים, תצוגה מקדימה, toast on send.
- יעד / Target: InfoBay (נקרא **server-side** מ-shira2, לא מהדפדפן / called server-side from shira2, not the browser).

**Endpoints relevant (under `/classic/WS/App/WsShiraUtils.asmx/`):** `GetPostalAddressDetails`, `CheckDocumentHasHistory`, `IsDocInvalidForPostal`.

**הצעד הבא / Next step:** capture the exact network request fired when "send" is clicked in the existing Shira mailing screen, then replicate it.

---

## 7. ShiraAI — הפרויקט הדגל / The Flagship Project

כלי web פנימי מבוסס Flask. / Flask-based internal web tool.

| שדה / Field | ערך / Value |
|---|---|
| Path | **Canonical:** `C:\SHIRA AI\shira_proxy.py` (v2.4) 🆕 (from Claude Code, 2026-06-10) |
| Path (build/dist) | `C:\Users\elchanans\Documents\AI\AI\SHIRA1\` (v2.1 — used for EXE builds) 🆕 |
| Old path (CLAUDE.md) | `C:\Users\elchanans\Documents\AI\AI1\shira-proxy\` — ⚠️ this copy is outdated (last modified 2026-06-04) |
| GitHub | `eys2005-afk/SHIRA-AI` |
| Port | `localhost:5050` |
| Files | `shira_proxy.py` (single-file — HTML and JS are embedded as Python strings, no separate static dir) 🆕 |
| Launch (dev) | `launch.vbs` — opens cmd silently, starts server, opens browser. (from Claude Code, 2026-06-10) 🆕 |
| Dev mode password | `ELCH2026` |
| AI | Google Gemini `gemini-2.5-flash` (external calls: `proxies={"https":None,"http":None}`, NOT via corporate proxy) 🆕 |
| Export | Word, FrankRuehl 14pt |
| Current version | v2.1 (SHIRA1) / v2.4 (C:\SHIRA AI) 🆕 |

**מה עובד / What works:**
- חיפוש תיק לפי ת"ז / מספר תיק / שם → רשימת תיקים → רשימת מסמכים עם צ'קבוקסים.
- בורר מסמכים ידני / Manual selector: filter by name; quick-select "5 last / 10 last / 20 last / entire case".
- Progress bar "loading document X of Y", 8-second timeout per document, stop button.
- סיכום תיק מלא ללא תקרת 20 מסמכים / Full-case summarization, no 20-doc cap.
- חיפוש טקסט חופשי במסמכים (PDF + DOCX) עם הדגשה.
- שאלות AI חופשיות + ייצוא תשובה ל-Word.
- אנונימיזציה של PII לפני שליחה ל-API חיצוני / PII anonymization before external API.
- Streaming via SSE; token usage tracking (large case ~149K tokens ≈ $0.023; small ~19K ≈ $0.003).
- סינון לפי בית דין של המשתמש / Court filter (13 קבצי HTML ייעודיים עם `USER_COURTS` קשיח / 13 court-specific HTML files with hardcoded `USER_COURTS`).

**הפצה / Distribution:** single `ShiraAI.exe` via PyInstaller (`--hidden-import win32timezone`). 🆕 **Exclude list** (keeps EXE ~60MB with `pdfminer.six`): `--exclude-module torch,scipy,numpy,pandas,pyarrow,numba,PIL,matplotlib,sklearn,tensorflow`. Console hidden via `ctypes.windll.user32.ShowWindow(..., 0)` when frozen. (from build.bat + ShiraAI.spec, 2026-06-10)

🆕 **Build workflow** (from `C:\SHIRA AI\`, 2026-06-10):
1. `BUILD.bat` — runs PyInstaller, produces `dist\ShiraAI.exe`
2. `PUBLISH.bat` — copies EXE + version to `C:\Users\elchanans\Documents\AI\AI\SHIRA1\update_files\`, then serves via `python -m http.server 8081`
3. Client machines read `update_url.txt` → currently `http://10.67.4.32:8081`

**🟡 עדכון אוטומטי — SOLVED (בחלקו) / Auto-update PARTIALLY SOLVED:**
~~בעיה לא פתורה~~ The approach shifted from GitHub to an **internal HTTP server**:
- `update_url.txt` contains the update server URL (currently `http://10.67.4.32:8081`)
- Routes: `GET /version.txt` (current version), `GET /ShiraAI.exe` (download)
- On update: `os.rename(curr_exe, curr_exe+'.old')` → `shutil.copy2(new_exe, curr_exe)` → `subprocess.Popen([curr_exe], creationflags=DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP)` → `os._exit(0)` (from `/api/do-update` route, 2026-06-10) 🆕
- ⚠️ GitHub raw URL approach was **abandoned** in favor of internal server (git commit `28a93fb`)
- ⚠️ The `shira_launcher.py` infinite-loop issue is moot — current EXE is self-contained and updates itself in-place

🆕 **Flask API routes (complete list, v2.1/v2.4, 2026-06-10):**
- `GET /` — embedded HTML page
- `GET /app.js` — embedded JavaScript
- `GET /api/health` → `{"status":"ok"}`
- `GET /api/me` → user + court info (with multi-court selection modal if user belongs to multiple courts)
- `POST /api/search` — search by `idNum`
- `POST /api/search-case` — search by `fileMainId` + optional `fileNumber`
- `POST /api/search-name` — search by `lastName` + `firstName`
- `GET /api/documents/<file_id>`
- `GET /api/doctext/<doc_id>` — extracts text (PDF/DOCX/OCR fallback)
- `GET /api/hearings/<file_id>`
- `POST /api/ai` — SSE streaming to Gemini (system prompt + messages + sideA/sideB for anonymization)
- `POST /api/export-docx` — generate Word summary
- `GET/POST /api/templates` — style examples per template key (`psak_din`, `hachlata`, `free`, `hearing`) — saved to `templates.json`
- `GET /api/check-update` — reads `update_url.txt`, fetches `/version.txt`
- `POST /api/do-update` — downloads and hot-swaps EXE
- `GET/POST /api/style-example` — saved to `style_example.txt`
- `GET /api/usage` — reads `usage_log.jsonl`
- 🆕 **Missing in v2.4 (C:\SHIRA AI):** `/api/templates` routes — present in SHIRA1 v2.1 only

🆕 **Gemini token cost formula** (from usage logging, 2026-06-10):
```python
cost = (input_tokens/1e6)*0.15 + (output_tokens/1e6)*0.60 + (thinking_tokens/1e6)*3.50
```
Exchange rate: `cost * 3.7` for ILS.

🆕 **Anonymization** (from `anonymize()` function, 2026-06-10): removes 9-digit ID numbers (`\b\d{9}\b` → `[תז]`), then replaces individual Hebrew words (≥2 chars) from `sideA` / `sideB` with `[שם]`. Applied to the AI message payload before sending to Gemini.

🆕 **Debug log:** all `print()` calls are tee'd to `shira_debug.log` in `BASE_DIR` (alongside the EXE). Useful for diagnosing frozen EXE issues. (from shira_proxy.py __main__, 2026-06-10)

**כללי עבודה על הקובץ / Working rules:**
1. גיבוי לפני כל שינוי / **Always back up before changes.**
2. שינויים ממוקדים, לא כתיבה מחדש / **Targeted fixes, not full rewrites** (use fix scripts).
3. **לעולם אל תיגע בקונפיג של ה-Flask backend / Never modify Flask backend config** (changing `host` or adding filtering broke the file repeatedly).
4. שנה רק את `askAI()` בתוך ה-HTML המוטמע / Only modify `askAI()` in the embedded HTML.
5. אל תשתמש בקוד מ-Gemini — הוא נתן גרסה ישנה שדרסה שיפורים / Don't use Gemini's code — it gave a stale version that overwrote improvements.

---

## 8. Shira Dashboard — פרויקט נפרד / Separate Project

ניטור תיקים פתוחים לפי הרכב. / Monitor open cases per assembly.

| שדה / Field | ערך / Value |
|---|---|
| Path | `C:\Users\elchanans\Documents\AI\AI1\shira-proxy\` (`proxy.py` + `dashboard.html`) |
| Alt path | `Z:\פרוייקטים במחשוב\shira-py\` |
| Port | `localhost:3000` |
| Assemblies | א=15, ב=96, ג=107 |

**תכונות / Features:** pagination; case-type filtering; unique-couples dedup (regex on ID numbers); claims-only filter; Excel export; last-decision-date column (from `FileDecisions.aspx`); batch decision loading with modal for 5 most recent decisions.

**הערות טכניות / Technical notes:**
- חובה להגיש את `dashboard.html` דרך ה-proxy (route `/`), לא כ-`file://` (דפדפנים חוסמים fetch ל-localhost מ-file protocol). / Must serve `dashboard.html` through the proxy, not as `file://`.
- persistent `requests.Session()` with auth set once, reused for all requests. Node.js `httpntlm` proved unreliable for sequential requests — use Python.
- בעיה פתוחה / Open issue: closures tab `Failed to fetch` (proxy not forwarding Shira session cookie → 401).

---

## 9. כלי תמלול דיונים / Hearing Transcription Tool

| שדה / Field | ערך / Value |
|---|---|
| Path | `C:\python_packages\app\app.py` |
| Stack | Streamlit, local Whisper (`base.pt`), Python 3.14 |
| Pipeline | microphone → Gemini (transcription + diarization) → Claude (format into protocol) → review UI |

**בעיה פתוחה / Open issue:** text doesn't appear during/after recording (threading issue).
**רקע / Background:** earlier explored Verbit Live Booking API integration (Power Automate); blocked by Premium license, proxy, and `"is_test": true` JWT. Contact: Arik Weiss.

🆕 **Standalone protocol server (working replacement)** — `protocol_server.py` at `C:\Users\elchanans\Documents\AI\AI\SHIRA PROTOCOL\` and canonical at `C:\SHIRA AI\protocol_server.py`. (from Claude Code, 2026-06-10)

| שדה / Field | ערך / Value |
|---|---|
| Port | `5051` |
| Stack | Flask + MediaRecorder (browser) + Gemini `gemini-2.5-flash` |
| Launch | `START_PROTOCOL.BAT` → runs `C:\SHIRA AI\protocol_server.py` |
| Pipeline | browser mic → 45-second audio chunks (audio/webm) → Gemini transcription + diarization → structured protocol lines → Word export |

**Protocol line format** (Gemini output + parse): `SPEAKER_KEY|speaker_name|text` — one line per utterance.
Speaker keys: `judge` / `husband` / `wife` / `atty_h` / `atty_w` / `other` / `interruption`.

**Features:** real-time display with color-coded speakers (purple=judge, blue=husband, pink=wife); edit mode (contenteditable); manual send-chunk button; Word export (FrankRuehl, speaker colors in DOCX); min chunk size 4000 bytes. Routes: `/api/transcribe` (POST multipart), `/api/export` (POST JSON → DOCX).

---

## 9b. 🆕 יומן דיונים / Hearing Calendar (GitHub + Render) (updated 2026-06-24)

פרויקט נפרד לתצוגת יומן דיונים חיצוני (לשותפים / קולגות). / Separate project for external hearing calendar display.

> ⚠️ **Supabase נזנח לחלוטין** — חסום בחומת האש של בתי הדין (404 מסונן). כל האחסון עבר ל-GitHub.
> Supabase fully abandoned — firewall-blocked from court network. All storage moved to GitHub.

| שדה / Field | ערך / Value |
|---|---|
| Path | `C:\Users\elchanans\Documents\AI\HEARINGS\` |
| GitHub repo | `eys2005-afk/hearing-calendar` — **פרטי / private** (contains litigants' names) |
| Stack | Flask (`app.py`) + GitHub storage + Render.com deployment |
| Procfile | `web: gunicorn app:app` |
| Requirements | `flask`, `requests`, `gunicorn`, `beautifulsoup4` |
| Render env vars | `GH_TOKEN`, `GH_REPO`, `NOTES_BRANCH`, `SITE_PASSWORD`, `SECRET_KEY` |

### אחסון נתונים / Data Storage

**יומן דיונים** — `data/hearings.json` מחויב ל-`main` branch. מבנה:
```json
{"updated_at": "2026-06-24T07:24:20", "hearings": [...]}
```
כל hearing: `{court_id, assembly, hall, date (DD/MM/YYYY), time (HH:MM or ""), subject, side_a, side_b, file_number, meeting_type}`

**הערות יומן** — `notes.json` ב-branch נפרד `notes`. כתיבה לענף זה **לא מפעילה** redeploy ב-Render (שמאזין רק ל-`main`). מפתח הערה: `"{court_id}|{DD/MM/YYYY}"`.

### pipeline סנכרון / Sync Pipeline

**`fetch_all.py`** — מודול אחיד לשתי בתי הדין:
- **Court 5 (רחובות):** SSRS Rep001 CSV ← יומן אמיתי, כולל אולם ושעה מדויקת
- **Court 12 (בית הדין הגדול):** `GetAdvancedFileSearch` ← **קירוב בלבד**, לא יומן אמיתי (ראה סעיף 16)

סינונים קריטיים ב-`fetch_court_search()`:
- `meetingTarget == "עיון"` → **מסנן החוצה** (סקירה פנימית, אין ישיבה פיזית — כל ימי שישי היו מסוג זה)
- `time >= "20:00"` → מנרמל ל-`""` (שיר"ה משתמש ב-"22:00" כ-sentinel ל"שעה לא נקבעה")

**`sync_github.py`** — מריץ `fetch_all()`, כותב `data/hearings.json`, עושה `git commit + push`. משתנים חשובים:
```python
os.environ['GIT_TERMINAL_PROMPT'] = '0'   # מונע popup של git
os.environ['GCM_INTERACTIVE'] = 'never'   # מונע popup של credential manager
```

**`setup_daily_sync.ps1`** — יוצר Task Scheduler "HearingCalendarSync" ב-17:00 יומי. `LogonType=Interactive` (נדרש — NTLM דורש Windows session פעיל).

### `meetingTarget` — ערכים ידועים מ-GetAdvancedFileSearch
| ערך | משמעות | להציג? |
|---|---|---|
| `"רגיל "` (עם רווח) | דיון רגיל | ✅ כן |
| `"החלטה"` | ישיבת החלטה | ✅ כן |
| `"ישיבת פישור"` | גישור | ✅ כן |
| `"עיון"` | סקירה פנימית — אין ישיבה | ❌ לסנן |

### אבטחה / Security
- **Login screen** (`/login`) עם סיסמה משותפת לכולם — `SITE_PASSWORD` env var ב-Render
- **`/robots.txt`** מחזיר `Disallow: /`
- `<meta name="robots" content="noindex,nofollow">` בכל הדפים
- ה-repo **חייב להישאר פרטי** — מכיל שמות בעלי דין

### Users
```python
USERS = {
    'elchanan': {'name': 'אלחנן שמריה', 'court_id': '5',  'court_name': 'רחובות'},
    'avi':      {'name': 'אבי אושרי',   'court_id': '12', 'court_name': 'בית הדין הגדול'},
}
```

**Dedup logic:** `_dedup_by_couple()` — for same (couple, date), keeps the hearing with highest-priority subject (גירושין > מזונות > רכוש > שהות > other).

### צבעי הרכב / Assembly Colors (template)
```
א/ד/ז/י → --ha (כחול navy)
ב/ה/ח   → --hb (אדום)
ג/ו/ט   → --hg (ירוק)
```
CSS classes: `pill-X`, `hh-X`, `asm-btn-X` — all follow this pattern.

### Git config — HEARINGS repo (חובה לאחר clone)

⚠️ **חובה להגדיר בכל clone חדש** — מונע אזהרות CRLF שקופצות בכל commit:
```
git -C "C:\Users\elchanans\Documents\AI\HEARINGS" config core.autocrlf true
git -C "C:\Users\elchanans\Documents\AI\HEARINGS" config core.safecrlf false
```
כבר מוגדר בעותק הנוכחי. אם האזהרות חוזרות — הרץ שוב את שתי הפקודות.

---

## 10. ארכיטקטורת בנייה מחדש מומלצת / Recommended Rebuild Architecture

לבנייה מקצה לקצה, שכבות מוצעות / For an end-to-end build, suggested layers:

1. **שכבת חיבור / Connectivity layer** — מודול Python יחיד (`shira_client.py`) שמכיל את ה-session template (סעיף 1), ועוטף את כל ה-endpoints (סעיפים 2–4) כפונקציות. בסיס לכל שאר הפרויקטים. / Single Python module wrapping all endpoints as functions; the base for everything else.
2. **שכבת נתונים / Data layer** — חיפוש תיקים, פרטים, מסמכים, דיונים, החלטות, דוחות SSRS. / File search, details, documents, hearings, decisions, SSRS reports.
3. **שכבת AI** — Gemini דרך proxy, אנונימיזציית PII, סיכום וחיפוש. / Gemini via proxy, PII anonymization, summarize & search.
4. **שכבת UI** — Flask + HTML מוטמע (כמו ShiraAI) או dashboard נפרד. / Flask + embedded HTML, or separate dashboard.
5. **שכבת הפצה / Distribution layer** — EXE עם עדכון אוטומטי דו-קבצי (סעיף 7). / EXE with two-file auto-update.

**העדפות טכניות לאורך כל הדרך / Technical preferences throughout:**
- תשובות באנגלית; קוד בעברית טבעי בהערות בסדר. / English responses.
- החלפת קבצים מלאה על פני עריכות חלקיות, אך שינויים ממוקדים על פני rewrites רחבים. / Complete file replacements over partial edits, but minimal targeted changes over broad rewrites.
- גיבוי לפני כל שינוי; בדיקה אינקרמנטלית לפני שילוב שלבים. / Backup before every change; incremental testing before combining steps.
- Cursor IDE + Claude Code; `CLAUDE.md` בשורש לפרסיסטנטיות. / `CLAUDE.md` in project root for persistence.

---

## 11. הוצאה ל-Claude Code — הנחיות / Exporting to Claude Code

כדי להמשיך בבנייה ב-Claude Code: / To continue building in Claude Code:

1. **הגדר proxy לפני הפעלה / Set proxy before launch:**
   ```
   setx HTTPS_PROXY http://192.168.174.80:8080
   ```
   (אז סגור ופתח מחדש את הטרמינל. / Then reopen the terminal.)
2. **שמור מסמך זה כ-`CLAUDE.md`** בשורש הפרויקט. Claude Code יקרא אותו אוטומטית כהקשר. / Save this doc as `CLAUDE.md` in project root; Claude Code auto-reads it.
3. תצוגת עברית בטרמינל משובשת — קוסמטי בלבד, מתעלמים. / Hebrew terminal display garbled — cosmetic only, ignore.
4. בקשה ראשונה מומלצת / Suggested first prompt to Claude Code:
   > "Read CLAUDE.md. Build `shira_client.py` — a single module wrapping the session template and all endpoints in sections 2–4. Back up before any change, English responses, targeted edits only."

---

---

## 12. 🆕 מפת קבצים נוכחית / Current File Map (updated 2026-06-15)

### 4 פרויקטים פעילים / 4 Active Projects

| # | שם / Name | קובץ ראשי / Main File | פורט / Port | הערות |
|---|---|---|---|---|
| 1 | **ShiraAI עצמאי** | `C:\SHIRA AI\shira_proxy.py` | 5050 | הבסיס — לשמור! v2.6, git repo |
| 2 | **שרת פרוטוקול** | `C:\SHIRA AI\protocol_server.py` | 5051 | תמלול דיונים בזמן אמת |
| 3 | **דשבורד הרכבים** | `C:\Users\elchanans\Documents\AI\AI1\shira-proxy\proxy.py` | 3000 | ניטור תיקים פתוחים |
| 4 | **Shira System** (חדש) | `C:\Users\elchanans\Documents\AI\shira-system\app.py` | 5055 | פרויקט מקיף — תחת פיתוח |

### קבצים נוספים / Additional Files

| נתיב / Path | תיאור |
|---|---|
| `C:\Users\elchanans\Documents\AI\AI\SHIRA PROTOCOL\shira_proxy.py` | גרסה ישנה של shira_proxy (port 5050) — ארכיון |
| `C:\SHIRA AI\API_BET_DIN\shiraai-beit-din-83107d7ac5c1.json` | **Vertex AI Service Account key** |
| `C:\SHIRA AI\BUILD.bat` / `PUBLISH.bat` | בנייה והפצת EXE |
| `C:\SHIRA AI\dist\ShiraAI.exe` | קובץ ההפצה הנוכחי |
| `C:\Users\elchanans\Documents\AI\HEARINGS\` | יומן דיונים — Flask+GitHub, deployed to Render (Supabase נזנח) |

### 🔐 Vertex AI Migration Status (2026-06-15)

מעבר מ-AI Studio API (מפתח חשוף) ל-Vertex AI Enterprise (Service Account).

| קובץ | סטטוס |
|---|---|
| `C:\SHIRA AI\shira_proxy.py` | ✅ מועבר |
| `C:\SHIRA AI\protocol_server.py` | ✅ מועבר |
| `C:\Users\elchanans\Documents\AI\shira-system\app.py` | ✅ מועבר (2026-06-15) |
| `C:\Users\elchanans\Documents\AI\AI\SHIRA PROTOCOL\shira_proxy.py` | ⚠️ גרסה ישנה, לא בשימוש פעיל |

**Vertex AI פרטים:**
- Project: `shiraai-beit-din`
- Location: `us-central1`
- Model: `gemini-2.5-flash`
- Service account: `shiraai-server@shiraai-beit-din.iam.gserviceaccount.com`
- Key file: `C:\SHIRA AI\API_BET_DIN\shiraai-beit-din-83107d7ac5c1.json`

**תבנית auth לכל קובץ:**
```python
from google.oauth2 import service_account
from google.auth.transport.requests import Request as _GoogleAuthReq

VERTEX_KEY_PATH = r"C:\SHIRA AI\API_BET_DIN\shiraai-beit-din-83107d7ac5c1.json"
VERTEX_PROJECT  = "shiraai-beit-din"
VERTEX_LOCATION = "us-central1"
VERTEX_MODEL    = "gemini-2.5-flash"

_vertex_creds = None

def _get_vertex_token():
    global _vertex_creds
    if _vertex_creds is None:
        _vertex_creds = service_account.Credentials.from_service_account_file(
            VERTEX_KEY_PATH, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
    if not _vertex_creds.valid:
        _s = requests.Session(); _s.verify = False; _s.proxies = {"https": None, "http": None}
        _vertex_creds.refresh(_GoogleAuthReq(session=_s))
    return _vertex_creds.token
```

**שימוש (generateContent):**
```python
url = (f"https://{VERTEX_LOCATION}-aiplatform.googleapis.com/v1/projects/"
       f"{VERTEX_PROJECT}/locations/{VERTEX_LOCATION}/publishers/google/models/"
       f"{VERTEX_MODEL}:generateContent")
resp = requests.post(url, json=payload,
    headers={"Authorization": f"Bearer {_get_vertex_token()}"},
    proxies={"https": None, "http": None}, verify=False, timeout=120)
```

---

## 13. 🆕 Shira System — פרויקט מקיף (2026-06-15)

פרויקט חדש המאחד את כל הפונקציות: חיפוש, סיכום AI, פרוטוקול, תמלול ועוד.
תוכנן עם Claude Fable 5, הפיתוח הופסק עקב בעיית זמינות מודל.

| שדה | ערך |
|---|---|
| Path | `C:\Users\elchanans\Documents\AI\shira-system\app.py` |
| Port | `5055` |
| Launch | `C:\Users\elchanans\Documents\AI\shira-system\launch.bat` |
| Config | `config.json` (Gemini API key, `use_proxy_for_ai`) |

**Routes קיימים:**
- `GET /api/me` — פרטי משתמש
- `POST /api/search` — חיפוש לפי ת"ז
- `POST /api/search-name` — חיפוש לפי שם (עם היפוך)
- `GET /api/case/<file_id>` — פרטי תיק
- `GET /api/documents/<file_id>` — רשימת מסמכים
- `GET /api/doctext/<doc_id>` — חילוץ טקסט (PDF/DOCX + OCR fallback)
- `GET /api/hearings/<file_id>` — רשימת דיונים
- `POST /api/calendar/hearings` — יומן הרכב (SSRS 3-step)
- `POST /api/ai/chat` — SSE streaming לגמיני
- `POST /api/transcribe` — תמלול אודיו
- `POST /api/export-docx` — ייצוא Word
- `GET/POST /api/config` — ניהול הגדרות

**מה עוד מתוכנן (מהפגישה עם Fable 5):** ← להשלים כשמתחדש הפיתוח

> ⛔ **Claude Fable 5 אינו זמין נכון ל-2026-06-15.** מאושר גם ברשת. כל תכנון ה-Shira System נעשה עם Fable 5 ונעצר כשהמודל הורד. לחדש עם Opus 4.8 (`claude-opus-4-8`) או Sonnet 4.6 (`claude-sonnet-4-6`) עד שיחזור.

**⚠️ Vertex AI migration נדרש:** כל קריאות ה-AI ב-app.py עדיין משתמשות ב-`generativelanguage.googleapis.com` עם מפתח מ-`config.json`. יש להחיל את תבנית ה-auth מסעיף 12 על: OCR fallback, `/api/ai/chat`, `/api/transcribe`.

---

---

## 14. 🆕 סיכום דיונים מחר במייל / Tomorrow's Hearing Digest by Email (2026-06-17)

פיצ'ר חדש ב-ShiraAI: כפתור "✉ סיכום מחר" בהדר שפותח מודל להגדרות ושליחה.

**קבצים:**
- Backend: `C:\SHIRA AI\shira_proxy.py` — routes חדשים + helpers
- Config: `C:\SHIRA AI\user_config.json` — email + assemblyId (נשמר פעם אחת)

**Routes חדשים:**
- `GET /api/user-config` — מחזיר config + רשימת הרכבים
- `POST /api/user-config` — שומר email + assemblyId
- `POST /api/send-digest` — מייצר ושולח; עם `{"preview":true}` מחזיר JSON עם שדה `html`

**זרימה:**
1. `_fetch_hearings_ssrs_csv(date_str, assembly_id, court_id)` — SSRS 3-step (כמו סעיף 4 עם CSV export)
2. לכל תיק ייחודי: `_file_id_for_number()` → `_get_docs_for_digest()` → `_read_doc_text_for_digest()` → `_ai_summary_for_hearing()` (Vertex AI non-streaming, maxOutputTokens=400)
3. `_build_digest_html()` → HTML email
4. שליחה דרך `win32com.client.Dispatch("Outlook.Application")`

**הרכבים (רחובות):** א=15, ב=96, ג=107, בי=16, פט=17. נשמרים ב-`ASSEMBLY_LIST` + `user_config.json`.

**הגדרות UI:** המשתמש מגדיר מייל + הרכב פעם אחת בדיאלוג; הערכים נשמרים ב-`user_config.json`.

---

*עודכן 2026-06-17 — הוספת פיצ'ר סיכום דיונים מחר.*

---

## 15. 🆕 הצעת החלטות לבקשות — AI Decision Proposals (2026-06-17)

פיצ'ר חדש ב-ShiraAI המאפשר לסופר הדיינים להכין טיוטת החלטה AI לדיינים עבור בקשות פתוחות.

### ארכיטקטורה

**Permission gate:** רק מי שיכול לגשת ל-`TasksForManager.aspx` (בקרה למנהלים, screen_id=66) רואה את הלשונית. הגישה לעמוד זה מוגבלת בשירה לסופרי דיינים / מנהלים. אין צורך בבדיקה נוספת.

**Task discovery:** `POST /api/api/task/GetTaskSearch` עם `currentUserId=X, taskStatus=1`. משימות מסוג `"מתן החלטה בבקשה"` הן הבקשות הממתינות.

**Document ID resolution:** ל-task יש `fileId` אבל `documentId=0`. מסמך הבקשה מאותר ב-`FileDocs.aspx` ע"י התאמת `req_type` (שם הבקשה לאחר הסרת "מתן החלטה בבקשה") לטקסט השורה.

### UI — שתי לשוניות ראשיות

```
[🔍 חיפוש תיקים]  [⚖️ הצעת החלטות לבקשות]   ← nav bar מתחת ל-header
```

- לשונית החלטות מוסתרת עד שהמערכת מזהה שיש דיינים עם משימות פתוחות
- `switchMainTab('search'|'decisions')` — מחליפה בין `#main-search` ו-`#main-decisions`

### זרימת שימוש

1. סופר הדיינים נכנס → המערכת קוראת `assembly-users` → בודקת pending tasks לכל דיין
2. אם נמצאו → לשונית "⚖️ הצעת החלטות" מופיעה
3. בוחרים דיין מהרשימה → לוחצים "הצג בקשות פתוחות" → רשימת task cards
4. לכל task: כפתור **"📋 מסמכים ▼"** → טוען checkboxes של מסמכי התיק (מסמך הבקשה מסומן מראש)
5. בוחרים מסמכים → **"⚖️ הצע החלטה"** → SSE streaming של טיוטת החלטה
6. ייצוא ל-Word או העתקה

### Routes Python החדשים

| Route | תיאור |
|---|---|
| `GET /api/assembly-users` | פרסור `cboTargetUser` מ-`TasksForManager.aspx` |
| `GET /api/pending-decisions?userId=X` | `GetTaskSearch` + סינון "החלטה בבקשה" |
| `POST /api/propose-decision` | SSE — קורא מסמכים → Vertex AI → streaming |

**`/api/propose-decision` payload:**
```json
{"fileId": 123456, "taskKindName": "מתן החלטה בבקשה — שהות", "fileNumber": "1524520/6",
 "hint": "לדחות את הבקשה", "docIds": ["12345", "67890"]}
```
- אם `docIds` מסופק: קורא רק אותם (ראשון = בקשה, שאר = הקשר)
- אם `docIds` לא מסופק: autodetect מ-`FileDocs.aspx` לפי `req_type`

### פרטי JS החדשים

```js
switchMainTab(tab)      // מחליפה בין שתי הלשוניות
initDecisions()         // נקראת מ-applyCourtUser() בכניסה
loadDecisionTasks()     // טוענת task cards לדיין נבחר
toggleDocPicker(taskId) // מרחיבה/מכווצת את רשימת המסמכים per-task
proposeDecision(taskId) // אוספת docIds מ-checkboxes → POST → SSE
exportDecisionDocx(taskId)
window._dtTasks = {}    // מאגר נתוני tasks לפי taskId (למניעת JSON-in-onclick)
```

### גיבוי

`C:\SHIRA AI\shira_proxy.py.bak_20260616` — גרסה לפני הפיצ'ר (v2.7)

### GitHub

Remote: `https://github.com/eys2005-afk/SHIRA-AI.git`
סטטוס: commit `5920ad2` עשוי אך לא נדחף — GitHub חסם בגלל GCP API key בהיסטוריית ה-commits הישנים.
פתרון נדרש: allow secret דרך GitHub security URL, או ניקוי היסטוריה + force push.

---

*עודכן 2026-06-17 — הוספת סעיף 15 — הצעת החלטות לבקשות.*

---

## 16. 🆕 חיבור נתונים מחוץ לשירה — ממצאים קריטיים (2026-06-24)

### גישה חוצה בתי דין — מה עובד ומה לא

| מקור נתונים | חוצה בתי דין? | הערות |
|---|---|---|
| `GetAdvancedFileSearch` | ✅ כן | כל בית דין נגיש; `meetingStart` = תאריך דיון הבא ברשומת התיק — **לא יומן** |
| `SSRS Rep001` (יומן הרכב) | ❌ לא | מוגבל לבית הדין של המשתמש המחובר לפי NTLM |
| `FileMeetings.aspx` | ❌ לא | 404 עבור תיקים של בית דין אחר |
| `FileDocs.aspx` | ❌ לא | court-scoped |
| DocIDs | ✅ כן | גלובליים, ניתן לקרוא מסמכים מכל בית דין |

### ⚠️ SSRS — אבטחה מבוססת NTLM, לא URL

**נבדק בפועל (2026-06-24):** בקשה ל-`Rep001.aspx?userid=1438&courtid=12` עם NTLM credentials של court 5 → מחזירה דף "אין הרשאה לגשת לדוח זה" (form id="NotAllowed").

**המסקנה:** הפרמטרים `userid` ו-`courtid` ב-URL הם **מטא-דאטה לתצוגה בלבד**. השרת מאמת על פי ה-NTLM token בלבד. אי-אפשר לזייף גישה לבית דין אחר על ידי שינוי URL בלבד.

### חומת אש — מה עובר ומה חסום

| שירות | סטטוס | הערה |
|---|---|---|
| **Supabase** (`*.supabase.co`) | ❌ חסום | מחזיר 404 מסונן ("הגישה לדף אינה מורשית") |
| **GitHub** (`github.com`, `api.github.com`) | ✅ עובר | דרך proxy ארגוני `192.168.174.80:8080` |
| **Vertex AI / Gemini** | ✅ עובר | דרך proxy ארגוני |
| **ngrok / localhost.run** | ❌ חסום | tunneling חסום |

### אסטרטגיה לנתוני בית דין אחר (יומן אמיתי)

כדי לקבל נתוני Rep001 של בית דין אחר, **חובה** שהקוד ירוץ על מחשב שבו מחובר משתמש מאותו בית דין. אפשרויות מעשיות:

1. **EXE על מחשב של קולגה** — EXE עצמאי שמריץ sync חד-פעמי או יומי. לא דורש התקנת Python. משתמש ב-Windows session הנוכחי (NTLM אוטומטי). הקולגה לוחץ פעמיים.
2. **ביקור פיזי** — לשבת ליד מחשב של קולגה, להריץ script פעם אחת.
3. **שכבת ShiraAI** — אם ShiraAI מותקן אצל הקולגה, להוסיף sync module שרץ לצידו.

**EXE מה שצריך לכלול:**
- `requests`, `requests_negotiate_sspi`, `beautifulsoup4` (NTLM + SSRS parsing)
- GitHub token לדחיפה ל-`eys2005-afk/hearing-calendar`
- auto-detect court from `GetUser` API → fetch Rep001 for that court → push

### `GetAdvancedFileSearch` — שדות נוספים חשובים

שדות שלא תועדו קודם לכן:
- **`meetingTarget`** — סוג הטיפול: `"רגיל "` / `"החלטה"` / `"עיון"` / `"ישיבת פישור"` (ראה סעיף 9b לטבלה מלאה)
- **`fullFileMainNumber`** — מספר תיק מלא (`"812804/13"`) — עדיף על `fileNumber` שמחזיר רק את תת-המספר
- **`meetingStart`** — פורמט `"DD/MM/YYYY HH:MM"`. שעה `"22:00"` = sentinel ל"שעה לא נקבעה". **זהו שדה ברמת התיק, לא רשומת יומן מאושרת.**

*עודכן 2026-06-24 — ממצאי cross-court access, חומת אש, SSRS security model.*

---

## 17. 🆕 סגירת תיקים אוטומטית / Batch Case Closure Tool (2026-06-25)

כלי לסגירת תיקים לא פעילים בצובר — מכניס החלטת "סג" (סגירת תיק, DecisionTypeId=58) לכל תיק ברשימה.
כל סגירה מחשבת כ-bonus metric לבית הדין.

### קבצים

| קובץ | תפקיד |
|------|---------|
| `C:\SHIRA AI\app.py` | אפליקציית GUI (tkinter) |
| `C:\SHIRA AI\close_app.bat` | מפעיל — לחיצה כפולה |
| `C:\SHIRA AI\browser_profile\` | פרופיל Chrome קבוע (שומר session שירה 2) |
| `C:\SHIRA AI\openpyxl\` | חבילה מקומית (מועתקת לכאן כדי שה-bat ימצא אותה) |
| `C:\SHIRA AI\et_xmlfile\` | תלות של openpyxl |

**הפעלה:** לחיצה כפולה על `C:\SHIRA AI\close_app.bat`

### קובץ קלט — Rep007.xlsx

- דוח תיקים לא פעילים, מיוצא ידנית מ-Shira 2
- מספרי תיקים בפורמט `XXXXXX/X` נמצאים בעמודה האחרונה של כל שורה
- נתונים מתחילים משורה 9
- ~682 תיקים לדוח

### זרימת הכנסת החלטה (Playwright — Classic ASP.NET)

1. **ניווט ישיר ל-FileDecisions.aspx:**
   ```
   /classic/Forms/File/Contents/FileDecisions.aspx
     ?userid={userId}&courtid=5&MenuFileNumber={fileNumber}
     &EntityTypeId=6&EntityId={fileId}&FileID={fileId}
   ```

2. **לחיצה על כפתור הוספה** — `input[value*='הוסף']`

3. **מציאת iframe QuickSearch** — URL מכיל `AddDecisionQuickSearch`

4. **בתוך iframe QuickSearch:**
   - מילוי `input[name="txtDecisionCode"]` עם `"סג"`
   - לחיצה על `input[name="btnSearch"]`
   - סימון `input[name*="chkSelectDecision_58"]` (DecisionTypeId=58)
   - לחיצה על `input[name="btnChoose"]` → מפעיל `parent.postMessage()` לחלון האב

5. **מציאת frame AddDecision** — URL מכיל `AddDecision.aspx` (לא QuickSearch)

6. ⚠️ **"השלם דייני הרכב"** — `input[name="CtlButton1"]` — **שלב קריטי!**
   בלי זה השמירה נכשלת בשקט.

7. **שמירה** — `input[name="cmdSave"]`

8. **טיפול בחלון-קופץ** — `MessageBox.aspx` נפתח כדף חדש; סגירה עם `ctx.wait_for_event("page")`

### אילוצים ארכיטקטוניים

- **postMessage:** QuickSearch חייב לרוץ בתוך היררכיית iframe נכונה — לא כניווט עצמאי
- **פרופיל Chrome קבוע:** נדרש ל-Windows SSO אוטומטי
- **court ID:** 5 (רחובות)
- **userId:** 1438 (ברירת מחדל; מתעדכן מ-`/api/api/userController/GetUser`)

### בעיות ופתרונות

| בעיה | פתרון |
|------|--------|
| שם קובץ עברית ב-bat | שם קובץ ASCII (`app.py`) |
| openpyxl לא נמצא מ-bat | העתקת החבילה ישירות ל-`C:\SHIRA AI\` |
| כפתורים נחתכים בתחתית | pack של bottom bar עם `side="bottom"` **לפני** הגוף |
| חלון נפתח מאחורי חלונות | `self.attributes("-topmost", True)` בהפעלה |
| החלטה לא נשמרת | חובה ללחוץ "השלם דייני הרכב" (CtlButton1) לפני cmdSave |
| חלון-קופץ אחרי שמירה | `ctx.wait_for_event("page")` + `popup.close()` |

### תכונות ה-GUI

- בחירת קובץ Rep007.xlsx
- טעינה אוטומטית של כל מספרי התיקים + lookup של fileId מה-API
- טבלת תיקים עם סטטוס בזמן אמת
- כפתורי **הפעל / עצור / המשך** (השהיה בין תיקים)
- ספירת הצליחו / שגיאות / נותרו
- ייצוא תוצאות ל-Excel

*עודכן 2026-06-25 — הוספת כלי סגירת תיקים אוטומטית.*
