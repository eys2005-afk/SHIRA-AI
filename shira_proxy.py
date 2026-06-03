"""
shira_proxy.py — v8 final
pip install flask requests requests-negotiate-sspi beautifulsoup4 lxml python-docx pdfminer.six flask-cors
"""

import os, sys, ssl, urllib3, re, io, json, xml.etree.ElementTree as ET

BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))

# Suppress PyInstaller temp directory cleanup warning
if getattr(sys, 'frozen', False):
    import warnings
    warnings.filterwarnings("ignore")

VERSION = "2.4"

os.environ['NO_PROXY'] = 'shira2,prod-spfe,10.67.60.51,localhost,127.0.0.1'
urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context

from flask import Flask, request, jsonify, Response, stream_with_context, send_file
from flask_cors import CORS
import requests
from requests_negotiate_sspi import HttpNegotiateAuth
from bs4 import BeautifulSoup
from pdfminer.high_level import extract_text as pdf_extract_text
import docx as docx_lib

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
CORS(app)

SHIRA = "http://shira2"
SPFE  = "http://prod-spfe:1000"
PROXY_URL = "http://192.168.174.80:8080"

# ↓↓↓ PUT YOUR GEMINI API KEY HERE ↓↓↓
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE"
# ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑

SUMMONS_KW = ['זימון','הזמנה לדיון','הזמנה לישיבה','הודעה על דיון','הזמנת עדים','מועד דיון','נדחה ל','notice','summon']

def is_summons(name):
    n = (name or '').lower()
    return any(k in n for k in SUMMONS_KW)

def make_session():
    s = requests.Session()
    s.auth = HttpNegotiateAuth()
    s.headers.update({"Content-Type": "application/json; charset=UTF-8", "Origin": SHIRA, "Referer": f"{SHIRA}/App/main/files/files-list"})
    s.proxies = {"http": None, "https": None}
    return s

SESSION = make_session()

def anonymize(text):
    text = re.sub(r'\b\d{9}\b', '[תז]', text)
    text = re.sub(r'\b0\d{1,2}[-\s]?\d{3}[-\s]?\d{4}\b', '[טלפון]', text)
    text = re.sub(r'[\w.+\-]+@[\w\-]+\.\w+', '[מייל]', text)
    return text

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return Response(HTML_PAGE, mimetype="text/html; charset=utf-8")

@app.route("/app.js")
def js_file():
    return Response(JS_CODE, mimetype="application/javascript; charset=utf-8")

@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/api/me")
def me():
    COURTS = {1:"ירושלים",2:"תל אביב",3:"חיפה",4:"פתח תקוה",5:"רחובות",6:"באר שבע",7:"טבריה",8:"צפת",9:"אשדוד",10:"אשקלון",11:"נתניה",12:"בית הדין הגדול",13:"אריאל"}
    try:
        r = SESSION.get(f"{SHIRA}/api/api/userController/GetUser", timeout=10)
        r.raise_for_status()
        d  = r.json()
        cl = d.get("courtList", [])
        if cl:
            cid = cl[0]["courtId"]
            courts = [{"courtId": c["courtId"], "courtName": c.get("courtName") or COURTS.get(c["courtId"], str(c["courtId"]))} for c in cl]
            return jsonify({"courtId": cid, "courtName": cl[0].get("courtName") or COURTS.get(cid, str(cid)), "userName": d.get("userName",""), "firstName": d.get("firstName",""), "lastName": d.get("lastName",""), "courtList": courts})
        return jsonify({"error": "no court"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/search", methods=["POST"])
def search():
    id_num = (request.json or {}).get("idNum", "").strip()
    if not id_num: return jsonify({"error": "idNum required"}), 400
    p = {"courtID":None,"assemblyId":None,"fileNumber":None,"fileMainID":None,"subjectID":None,"subjectSubID":None,"Composition":None,"FileStatusOpen":"-1","FirstName":None,"IdNum1":id_num,"IdType1":1,"IsOnlineFile":False,"LastName":None,"OldFileNum":"","currentPage":1,"fileStatusID":None,"insertDateFrom":None,"insertDateTo":None,"isCorrectName":False,"isPriority":False,"meetingDateFrom":None,"meetingDateTo":None,"rowsPerPage":100}
    try:
        r = SESSION.post(f"{SHIRA}/api/api/FileSearch/GetAdvancedFileSearch", json=p, timeout=15)
        r.raise_for_status()
        data = r.json()
        for f in data: f["sideB"] = f.get("sideB") or ""
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/search-case", methods=["POST"])
def search_case():
    b    = request.json or {}
    fmid = b.get("fileMainId", "").strip()
    fn   = b.get("fileNumber")
    if not fmid: return jsonify({"error": "fileMainId required"}), 400
    p = {"courtID":None,"assemblyId":None,"fileNumber":int(fn) if fn else None,"fileMainID":int(fmid),"subjectID":None,"subjectSubID":None,"Composition":None,"FileStatusOpen":"-1","FirstName":None,"IdNum1":None,"IdType1":1,"IsOnlineFile":False,"LastName":None,"OldFileNum":"","currentPage":1,"fileStatusID":None,"insertDateFrom":None,"insertDateTo":None,"isCorrectName":False,"isPriority":False,"meetingDateFrom":None,"meetingDateTo":None,"rowsPerPage":100}
    try:
        r = SESSION.post(f"{SHIRA}/api/api/FileSearch/GetAdvancedFileSearch", json=p, timeout=15)
        r.raise_for_status()
        data = r.json()
        for f in data: f["sideB"] = f.get("sideB") or ""
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/search-name", methods=["POST"])
def search_name():
    b  = request.json or {}
    ln = b.get("lastName", "").strip()
    fn = b.get("firstName", "").strip()
    if not ln and not fn: return jsonify({"error": "name required"}), 400
    def do(last, first):
        p = {"courtID":None,"assemblyId":None,"fileNumber":None,"fileMainID":None,"subjectID":None,"subjectSubID":None,"Composition":None,"FileStatusOpen":"-1","FirstName":first or None,"LastName":last or None,"IdNum1":None,"IdType1":1,"IsOnlineFile":False,"OldFileNum":"","currentPage":1,"fileStatusID":None,"insertDateFrom":None,"insertDateTo":None,"isCorrectName":False,"isPriority":False,"meetingDateFrom":None,"meetingDateTo":None,"rowsPerPage":100}
        r = SESSION.post(f"{SHIRA}/api/api/FileSearch/GetAdvancedFileSearch", json=p, timeout=15)
        r.raise_for_status()
        return r.json()
    try:
        results = {}
        for f in do(ln, fn):
            f["sideB"] = f.get("sideB") or ""
            results[f.get("fileId", f.get("fileNumber",""))] = f
        if ln and fn:
            for f in do(fn, ln):
                f["sideB"] = f.get("sideB") or ""
                k = f.get("fileId", f.get("fileNumber",""))
                if k not in results: results[k] = f
        return jsonify(list(results.values()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/documents/<int:file_id>")
def documents(file_id):
    url = f"{SHIRA}/classic/Forms/File/Contents/FileDocs.aspx?userid=0&courtid=0&FileID={file_id}&EntityId={file_id}&EntityTypeId=6"
    try:
        r    = SESSION.get(url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        docs = []
        table = soup.find("table", id="grdFileDocs")
        if not table:
            for t in soup.find_all("table"):
                if "OpenDocument" in str(t): table = t; break
        if table:
            for tr in table.find_all("tr"):
                m = re.search(r"OpenDocument\((\d+)\)", str(tr))
                if not m: continue
                did  = m.group(1)
                link = tr.find("a", onclick=True) or tr.find("a")
                name = (link.get_text(strip=True) if link else "") or f"מסמך {did}"
                rt   = tr.get_text(" ", strip=True)
                dm   = re.search(r"\d{2}/\d{2}/\d{4}", rt)
                date = dm.group(0) if dm else ""
                ext  = name.rsplit(".", 1)[-1].lower() if "." in name else ""
                docs.append({"docId": did, "name": name, "date": date, "type": "pdf" if ext == "pdf" else "docx", "openUrl": f"{SHIRA}/classic/Forms/Documents/DM/DMOpenDocument.aspx?DocIDs={did}&Action=1"})
        return jsonify(docs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/doctext/<doc_id>")
def doc_text(doc_id):
    try:
        xml = f"<XmlData><DocumentID>{doc_id}</DocumentID></XmlData>"
        r1  = SESSION.post(f"{SHIRA}/classic/WS/App/WsShiraUtils.asmx/GetDocumentDetails", data=xml.encode("utf-8"), headers={"Content-Type": "application/xml"}, timeout=10)
        root = ET.fromstring(r1.text)
        dn   = root.find("DocNumber")
        if dn is None or not dn.text: return jsonify({"text": "", "error": "DocNumber not found"})
        r2   = SESSION.post(f"{SPFE}/ShiraDocsMngWS.asmx/GetDocumentUrlAndStatus", data=f"{{'docNumber':'{dn.text.strip()}','isCopy':'true'}}", headers={"Content-Type": "application/json"}, timeout=10)
        res  = r2.json().get("d", "")
        furl = res.split("|")[0] if "|" in res else res
        if not furl or furl == "-1": return jsonify({"text": "", "error": "URL not found"})
        r3   = SESSION.get(furl, timeout=20)
        r3.raise_for_status()
        buf  = io.BytesIO(r3.content)
        ext  = furl.rsplit(".", 1)[-1].lower()
        text = ""
        if ext == "pdf":
            raw = pdf_extract_text(buf) or ""
            # fix visual-order RTL PDFs: reverse each line
            lines = raw.splitlines()
            fixed = []
            for line in lines:
                stripped = line.strip()
                if stripped and any('֐' <= c <= '׿' for c in stripped):
                    # line contains Hebrew — check if it looks reversed
                    rev = stripped[::-1]
                    fixed.append(rev)
                else:
                    fixed.append(line)
            text = "\n".join(fixed)
        elif ext in ("docx", "doc"):
            text = "\n".join(p.text for p in docx_lib.Document(buf).paragraphs)
        else:
            text = r3.content.decode("utf-8", errors="ignore")[:50000]
        return jsonify({"text": text[:30000]})
    except Exception as e:
        return jsonify({"text": "", "error": str(e)})

@app.route("/api/hearings/<int:file_id>")
def hearings(file_id):
    url = f"{SHIRA}/classic/Forms/File/Contents/FileMeetings.aspx?userid=0&courtid=0&FileID={file_id}&EntityId={file_id}&EntityTypeId=6"
    try:
        r    = SESSION.get(url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        tbl  = soup.find("table", id="grdMeetings") or soup.find("table")
        if not tbl: return jsonify([])
        rows = []
        for tr in tbl.find_all("tr")[1:]:
            tds   = tr.find_all("td")
            cells = [td.get_text(strip=True) for td in tds]
            if len(cells) < 3: continue
            # Extract protocol doc ID from OpenDocument link in this row
            proto_match = re.search(r"OpenDocument\((\d+)\)", str(tr))
            proto_id    = proto_match.group(1) if proto_match else None
            rows.append({
                "hebrewDate":     cells[0] if len(cells) > 0 else "",
                "date":           cells[1] if len(cells) > 1 else "",
                "purpose":        cells[2] if len(cells) > 2 else "",
                "status":         cells[3] if len(cells) > 3 else "",
                "timeFrom":       cells[4] if len(cells) > 4 else "",
                "timeTo":         cells[5] if len(cells) > 5 else "",
                "panel":          cells[6] if len(cells) > 6 else "",
                "protoStatus":    cells[8] if len(cells) > 8 else "",
                "protocolDocId":  proto_id,
            })
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/ai", methods=["POST"])
def ai_proxy():
    b       = request.json or {}
    msg     = b.get("messages", [{}])[0].get("content", "")
    sys_    = b.get("system", "אתה עוזר משפטי לבית הדין הרבני. ענה בעברית בלבד. ללא markdown.")
    side_a  = (b.get("sideA") or "").strip()
    side_b  = (b.get("sideB") or "").strip()
    case_no = (b.get("caseNumber") or "").strip()
    msg     = msg[:200000]

    def extract_name_parts(side):
        # sideA/sideB format: "תובע/ת, שם משפחה שם פרטי, מספר ת.ז"
        parts = [p.strip() for p in side.split(",") if p.strip()]
        name_parts = []
        for p in parts:
            if re.match(r'^\d+$', p) or '/' in p:
                continue
            # add full name and each individual word
            name_parts.append(p)
            for word in p.split():
                if len(word) >= 3:
                    name_parts.append(word)
        return name_parts

    def replace_names(text, name_parts, label):
        for name in name_parts:
            text = text.replace(name, label)
            text = text.replace(name[::-1], label)  # reversed (visual-order PDFs)
        return text

    msg = replace_names(msg, extract_name_parts(side_a), "צד א")
    msg = replace_names(msg, extract_name_parts(side_b), "צד ב")
    if case_no:
        msg = msg.replace(case_no, "[תיק]")
        msg = msg.replace(case_no.split("/")[0], "[תיק]")  # also replace base number
    msg = anonymize(msg)
    url  = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:streamGenerateContent?alt=sse&key={GEMINI_API_KEY}"
    print(f"[ai] sending {len(msg)} chars to Gemini | sideA={side_a!r} sideB={side_b!r} case={case_no!r}")
    try:
        preview_html = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head><meta charset="utf-8"><title>Gemini Preview</title>
<style>body{{font-family:Arial;font-size:14px;padding:20px;direction:rtl}}
.label{{color:#888;font-size:12px;margin-bottom:4px}}
.val{{background:#f5f5f5;padding:8px;border-radius:4px;margin-bottom:12px;white-space:pre-wrap}}
.ok{{color:green;font-weight:bold}} .warn{{color:red;font-weight:bold}}</style></head>
<body>
<h2>מה נשלח ל-Gemini</h2>
<div class="label">צד א (מקורי):</div><div class="val">{side_a}</div>
<div class="label">צד ב (מקורי):</div><div class="val">{side_b}</div>
<div class="label">מספר תיק (מקורי):</div><div class="val">{case_no}</div>
<hr>
<div class="label">500 התווים הראשונים שנשלחים ל-Gemini (אחרי סינון):</div>
<div class="val">{msg[:500].replace('<','&lt;').replace('>','&gt;')}</div>
<hr>
<p>{"<span class='ok'>✓ השמות הוחלפו בהצלחה</span>" if side_a.split(",")[1].strip() not in msg[:5000] else "<span class='warn'>⚠ ייתכן שעדיין יש שמות בטקסט</span>"}</p>
</body></html>"""
        with open("C:/SHIRA AI/gemini_preview.html", "w", encoding="utf-8") as _f:
            _f.write(preview_html)
    except Exception: pass

    @stream_with_context
    def gen():
        try:
            with requests.post(url, json={"contents": [{"parts": [{"text": msg}]}], "systemInstruction": {"parts": [{"text": sys_}]}}, proxies={"https": None, "http": None}, verify=False, timeout=180, stream=True) as resp:
                print(f"[ai] status={resp.status_code}")
                for line in resp.iter_lines():
                    if not line: continue
                    if isinstance(line, bytes): line = line.decode("utf-8")
                    if not line.startswith("data:"): continue
                    cs = line[5:].strip()
                    if cs == "[DONE]": break
                    try:
                        cd = json.loads(cs)
                        # debug
                        cands = cd.get("candidates", [])
                        if cands and cands[0].get("finishReason"):
                            print(f"[ai] finishReason={cands[0]['finishReason']}")
                        all_parts = cd.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                        if all_parts:
                            print(f"[ai] parts={[(p.get('thought',False), len(p.get('text',''))) for p in all_parts]}")
                        for p in all_parts:
                            if p.get("thought", False):
                                continue
                            t = p.get("text", "")
                            if t:
                                t = t.replace("**","").replace("*","").replace("##","").replace("#","")
                                yield f"data: {json.dumps({'text': t}, ensure_ascii=False)}\n\n"
                        u = cd.get("usageMetadata")
                        if u:
                            inp = u.get("promptTokenCount", 0)
                            out = u.get("candidatesTokenCount", 0)
                            thi = u.get("thoughtsTokenCount", 0)
                            cost = (inp/1e6)*0.15 + (out/1e6)*0.60 + (thi/1e6)*3.50
                            import datetime
                            entry = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), "input": inp, "output": out, "thinking": thi, "total": u.get("totalTokenCount",0), "usd": round(cost,6), "ils": round(cost*3.7,4)}
                            try:
                                lp = os.path.join(BASE_DIR, "usage_log.jsonl")
                                open(lp, "a", encoding="utf-8").write(json.dumps(entry, ensure_ascii=False) + "\n")
                            except: pass
                            yield f"data: {json.dumps({'usage': entry})}\n\n"
                    except json.JSONDecodeError: continue
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(gen(), mimetype="text/event-stream", headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no","Connection":"keep-alive"})

@app.route("/api/export-docx", methods=["POST"])
def export_docx():
    import datetime, docx as _docx
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    b = request.json or {}
    text = b.get("text", "").strip()
    if not text: return jsonify({"error": "no text"}), 400
    case_number = b.get("caseNumber", "")
    case_title  = b.get("caseTitle", "")
    court_name  = b.get("courtName", "בית הדין הרבני")
    doc = _docx.Document()
    sec = doc.sections[0]
    sec.page_width=7560310; sec.page_height=10692130; sec.left_margin=900430; sec.right_margin=1141095; sec.top_margin=331470; sec.bottom_margin=810260
    doc.element.body.get_or_add_sectPr().append(OxmlElement('w:bidi'))
    def ap(txt, bold=False, center=False, sb=4, sa=4, fs=None, color=None):
        p  = doc.add_paragraph()
        pf = p.paragraph_format; pf.space_before=Pt(sb); pf.space_after=Pt(sa)
        pf.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.JUSTIFY
        pp = p._p.get_or_add_pPr(); pp.append(OxmlElement('w:bidi'))
        jc = OxmlElement('w:jc'); jc.set(qn('w:val'), 'center' if center else 'both'); pp.append(jc)
        run = p.add_run(txt); run.font.name='FrankRuehl'; run.font.size=Pt(fs or 14); run.font.bold=bold
        if color: run.font.color.rgb = RGBColor(*color)
        rp = run._r.get_or_add_rPr(); rp.append(OxmlElement('w:rtl'))
        lg = OxmlElement('w:lang'); lg.set(qn('w:bidi'), 'he-IL'); rp.append(lg)
    ap("בבית הדין הרבני האזורי", bold=True, center=True, sb=6, sa=2)
    ap(court_name, bold=True, center=True, sa=6)
    if case_number: ap(f"תיק מס' {case_number}", center=True, sa=2)
    if case_title:  ap(case_title, center=True, sa=6)
    ap("סיכום AI", bold=True, center=True, sb=6, sa=10)
    for para in [p.strip() for p in text.split('\n') if p.strip()]:
        is_h = len(para) < 60 and not para.endswith(('.', ',', ':', ')')) and not para[0].isdigit()
        ap(para, bold=is_h, sb=8 if is_h else 3, sa=4 if is_h else 3)
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    ap(f"הופק על ידי מערכת שירה AI  |  {now}", fs=9, center=True, color=(150,150,150))
    buf = io.BytesIO(); doc.save(buf); buf.seek(0)
    fn  = f"סיכום_AI_{case_number or 'תיק'}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.docx"
    return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document", as_attachment=True, download_name=fn)

STYLE_FILE      = os.path.join(BASE_DIR, "style_example.txt")
UPDATE_URL_FILE = os.path.join(BASE_DIR, "update_url.txt")

def get_update_url():
    try:
        if os.path.exists(UPDATE_URL_FILE):
            return open(UPDATE_URL_FILE, encoding="utf-8").read().strip().rstrip('/')
    except: pass
    return None

@app.route("/api/check-update")
def check_update():
    base = get_update_url()
    if not base:
        return jsonify({"current": VERSION, "latest": VERSION, "hasUpdate": False})
    try:
        r = requests.get(f"{base}/version.txt", timeout=5, proxies={"http":None,"https":None})
        latest = r.text.strip()
        has = latest != VERSION
        return jsonify({"current": VERSION, "latest": latest, "hasUpdate": has,
                        "downloadUrl": f"{base}/ShiraAI.exe" if has else None})
    except Exception as e:
        return jsonify({"current": VERSION, "latest": VERSION, "hasUpdate": False, "error": str(e)})

@app.route("/api/do-update", methods=["POST"])
def do_update():
    base = get_update_url()
    if not base:
        return jsonify({"error": "no update URL configured"}), 400
    try:
        r = requests.get(f"{base}/ShiraAI.exe", timeout=120, stream=True, proxies={"http":None,"https":None})
        r.raise_for_status()
        new_exe  = os.path.join(BASE_DIR, "ShiraAI_update.exe")
        curr_exe = sys.executable if getattr(sys, 'frozen', False) else None
        with open(new_exe, "wb") as f:
            for chunk in r.iter_content(65536): f.write(chunk)
        if curr_exe:
            bat = os.path.join(BASE_DIR, "_updater.bat")
            open(bat, "w", encoding="ascii").write(
                f'@echo off\n'
                f'timeout /t 4 /nobreak >nul\n'
                f'taskkill /f /im ShiraAI.exe >nul 2>&1\n'
                f'timeout /t 2 /nobreak >nul\n'
                f'copy /y "{new_exe}" "{curr_exe}" >nul\n'
                f'if errorlevel 1 (\n'
                f'  timeout /t 3 /nobreak >nul\n'
                f'  copy /y "{new_exe}" "{curr_exe}" >nul\n'
                f')\n'
                f'del /f /q "{new_exe}" >nul 2>&1\n'
                f'start "" "{curr_exe}"\n'
                f'del "%~0"\n'
            )
            import subprocess, threading
            subprocess.Popen(['cmd', '/c', bat], creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW)
            threading.Timer(3.0, lambda: os._exit(0)).start()
            return jsonify({"ok": True, "restart": True})
        return jsonify({"ok": True, "restart": False, "msg": "Downloaded to ShiraAI_update.exe"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/style-example", methods=["GET"])
def get_style_example():
    try:
        if os.path.exists(STYLE_FILE):
            return jsonify({"text": open(STYLE_FILE, encoding="utf-8").read()})
        return jsonify({"text": ""})
    except Exception as e:
        return jsonify({"text": "", "error": str(e)})

@app.route("/api/style-example", methods=["POST"])
def save_style_example():
    try:
        text = (request.json or {}).get("text", "")
        open(STYLE_FILE, "w", encoding="utf-8").write(text)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/usage")
def usage():
    lp = os.path.join(BASE_DIR, "usage_log.jsonl")
    if not os.path.exists(lp): return jsonify({"queries":0,"total_tokens":0,"total_usd":0,"total_ils":0,"last_queries":[]})
    entries = []
    try:
        for line in open(lp, encoding="utf-8"):
            line = line.strip()
            if line: entries.append(json.loads(line))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"queries":len(entries),"total_tokens":sum(e.get("total",0) for e in entries),"total_usd":round(sum(e.get("usd",0) for e in entries),4),"total_ils":round(sum(e.get("ils",0) for e in entries),3),"avg_usd":round(sum(e.get("usd",0) for e in entries)/len(entries),4) if entries else 0,"last_queries":entries[-10:]})


# ── HTML & JS as raw strings (no escaping issues) ────────────────────────────

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>מערכת שירה</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',Arial,sans-serif;direction:rtl;background:#f4f5f7;color:#1a1a2e;font-size:14px}
header{background:#1a3a5c;color:#fff;padding:12px 24px;display:flex;align-items:center;gap:12px}
header h1{font-size:17px;font-weight:500}
.sub{font-size:12px;opacity:.7;margin-top:2px}
.status-dot{width:10px;height:10px;border-radius:50%;background:#ccc;margin-right:auto;margin-left:8px}
.status-dot.ok{background:#4caf50}.status-dot.err{background:#f44336}
.status-label{font-size:12px;opacity:.8}
.user-chip{font-size:12px;background:rgba(255,255,255,.15);border-radius:20px;padding:4px 12px}
.container{max-width:1100px;margin:0 auto;padding:20px 16px}
.card{background:#fff;border:1px solid #e0e4ea;border-radius:10px;padding:20px;margin-bottom:16px}
.card-title{font-size:13px;font-weight:600;color:#555;margin-bottom:14px;text-transform:uppercase;letter-spacing:.5px}
.row{display:flex;gap:8px;align-items:center;margin-bottom:12px}
input[type=text]{flex:1;height:38px;border:1px solid #d0d5dd;border-radius:7px;padding:0 12px;font-size:14px;direction:rtl;outline:none}
input[type=text]:focus{border-color:#1a3a5c}
button{height:38px;padding:0 18px;border:1px solid #d0d5dd;border-radius:7px;background:#fff;color:#1a1a2e;font-size:14px;cursor:pointer;white-space:nowrap}
button.primary{background:#1a3a5c;color:#fff;border-color:#1a3a5c}
button.primary:hover{background:#14304d}
button.sm{height:30px;padding:0 12px;font-size:12px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:right;padding:9px 12px;background:#f8f9fb;color:#555;font-weight:600;border-bottom:1px solid #e0e4ea}
td{padding:9px 12px;border-bottom:1px solid #f0f2f5;vertical-align:middle}
tr.clickable:hover{background:#f0f6ff;cursor:pointer}
tr.selected{background:#e8f0fe!important}
.badge{display:inline-block;padding:2px 9px;border-radius:20px;font-size:11px;font-weight:600}
.b-open{background:#e6f4ea;color:#2e7d32}.b-closed{background:#f3f4f6;color:#555}.b-pending{background:#fff8e1;color:#e65100}
.tabs{display:flex;gap:4px;margin-bottom:16px;border-bottom:1px solid #e0e4ea}
.tab{padding:8px 16px;border-radius:7px 7px 0 0;font-size:13px;cursor:pointer;border:1px solid transparent;background:transparent;color:#666;border-bottom:none;position:relative;bottom:-1px}
.tab.active{background:#fff;border-color:#e0e4ea;border-bottom-color:#fff;color:#1a3a5c;font-weight:600}
.empty{color:#aaa;text-align:center;padding:28px;font-size:13px}
.spinner{display:inline-block;width:16px;height:16px;border:2px solid #ddd;border-top-color:#1a3a5c;border-radius:50%;animation:spin .7s linear infinite;vertical-align:middle}
@keyframes spin{to{transform:rotate(360deg)}}
.ai-box{background:#f8f9fb;border:1px solid #e0e4ea;border-radius:8px;padding:14px 16px;font-size:13px;line-height:1.75;white-space:pre-wrap;min-height:80px}
.ai-cursor{display:inline-block;width:2px;height:14px;background:#1a3a5c;animation:blink .8s step-end infinite;vertical-align:middle}
@keyframes blink{50%{opacity:0}}
.doc-row{display:flex;align-items:center;gap:10px;padding:9px 4px;border-bottom:1px solid #f0f2f5}
.doc-row:hover{background:#f8f9fb}
.error-msg{color:#c62828;background:#ffebee;border-radius:6px;padding:8px 12px;font-size:13px}
.stat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:16px}
.stat{background:#f8f9fb;border-radius:8px;padding:12px 14px;text-align:center}
.stat-val{font-size:20px;font-weight:600;color:#1a3a5c}
.stat-lbl{font-size:11px;color:#888;margin-top:3px}
.hearing-row{padding:8px 4px;border-bottom:1px solid #f0f2f5;font-size:13px;display:flex;gap:12px;align-items:center}
.hearing-date{font-weight:600;color:#1a3a5c;min-width:90px}
mark{background:#fff176;border-radius:2px;padding:0 1px}
</style>
</head>
<body>
<header>
  <div><h1 id="header-title">מערכת שירה — חיפוש חכם וסיכומי AI</h1><div class="sub">בתי הדין הרבניים</div></div>
  <div style="margin-right:auto;display:flex;align-items:center;gap:10px;"><span class="user-chip" id="user-chip"></span></div>
  <div class="status-dot" id="dot"></div>
  <div class="status-label" id="status-label">מתחבר...</div>
</header>

<div id="update-banner" style="display:none;background:#e65100;color:#fff;padding:10px 24px;font-size:13px;align-items:center;gap:12px;justify-content:center">
  <span>🔔 קיים עדכון גרסה</span>
  <span id="update-version-info" style="opacity:.85"></span>
  <button onclick="doUpdate()" style="background:#fff;color:#e65100;border:none;border-radius:6px;padding:5px 16px;font-size:13px;cursor:pointer;font-weight:600">התקן עכשיו</button>
  <button onclick="document.getElementById('update-banner').style.display='none'" style="background:transparent;color:rgba(255,255,255,.7);border:none;cursor:pointer;font-size:16px">✕</button>
</div>

<!-- Court selection modal -->
<div id="court-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.35);z-index:2000;display:flex;align-items:center;justify-content:center">
  <div style="background:#fff;border-radius:14px;padding:32px 36px;min-width:340px;box-shadow:0 8px 40px rgba(0,0,0,.18);text-align:center">
    <div style="font-size:15px;font-weight:600;color:#1a3a5c;margin-bottom:6px">כניסה למערכת שירה AI</div>
    <div id="court-modal-user" style="font-size:13px;color:#888;margin-bottom:20px"></div>
    <div style="font-size:13px;color:#555;margin-bottom:10px;text-align:right">בחר בית דין</div>
    <div id="court-modal-list" style="display:flex;flex-direction:column;gap:8px;margin-bottom:20px"></div>
    <button class="primary" style="width:100%;height:42px;font-size:14px" onclick="confirmCourtSelection()">כניסה</button>
  </div>
</div>

<button id="dev-btn" onclick="toggleDevMode()" style="position:fixed;bottom:16px;left:16px;z-index:999;background:rgba(0,0,0,.06);border:1px solid rgba(0,0,0,.1);color:#aaa;font-size:11px;padding:5px 10px;border-radius:20px;cursor:pointer;height:auto;opacity:.4" onmouseenter="this.style.opacity=1" onmouseleave="this.style.opacity=.4">⚙</button>
<button id="usage-btn" onclick="showUsage()" style="display:none;position:fixed;bottom:16px;left:80px;z-index:999;background:rgba(0,0,0,.06);border:1px solid rgba(0,0,0,.1);color:#aaa;font-size:11px;padding:5px 10px;border-radius:20px;cursor:pointer;height:auto;opacity:.4" onmouseenter="this.style.opacity=1" onmouseleave="this.style.opacity=.4">📊</button>

<div id="usage-popup" style="display:none;position:fixed;bottom:50px;left:16px;z-index:1000;background:#fff;border:1px solid #e0e4ea;border-radius:12px;padding:20px;min-width:300px;box-shadow:0 4px 24px rgba(0,0,0,.12)">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
    <strong style="font-size:13px;color:#1a3a5c">📊 סטטיסטיקות שימוש</strong>
    <button onclick="document.getElementById('usage-popup').style.display='none'" style="height:24px;padding:0 8px;font-size:12px">✕</button>
  </div>
  <div id="usage-content" style="font-size:13px;color:#444;line-height:2">טוען...</div>
</div>

<div id="open-doc-msg" style="display:none;position:fixed;bottom:60px;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:8px 20px;border-radius:20px;font-size:13px;z-index:999;white-space:nowrap"></div>

<div class="container">
  <div class="card">
    <div class="card-title">🔍 חיפוש תיקים</div>
    <div style="display:flex;gap:4px;margin-bottom:14px;border-bottom:1px solid #e0e4ea">
      <button class="tab active" id="stab-id"   onclick="switchSearchTab('id')">לפי ת"ז</button>
      <button class="tab"        id="stab-case" onclick="switchSearchTab('case')">לפי מס' תיק</button>
      <button class="tab"        id="stab-name" onclick="switchSearchTab('name')">לפי שם</button>
    </div>
    <div id="search-id-panel">
      <div class="row"><input type="text" id="id-input" placeholder='הכנס ת"ז (9 ספרות)' maxlength="9"/><button class="primary" onclick="doSearch()">חפש</button><button onclick="clearSearch()">נקה</button></div>
    </div>
    <div id="search-case-panel" style="display:none">
      <div class="row"><input type="text" id="case-input" placeholder="מס' תיק"/><button class="primary" onclick="doCaseSearch()">חפש</button><button onclick="clearSearch()">נקה</button></div>
    </div>
    <div id="search-name-panel" style="display:none">
      <div class="row"><input type="text" id="name-first" placeholder="שם פרטי"/><input type="text" id="name-last" placeholder="שם משפחה"/><button class="primary" onclick="doNameSearch()">חפש</button><button onclick="clearSearch()">נקה</button></div>
    </div>
    <div id="results-area"></div>
  </div>

  <div class="card" id="case-panel" style="display:none">
    <div class="card-title" id="case-heading">📁 תיק נבחר</div>
    <div class="stat-grid" id="case-stats"></div>
    <div class="tabs">
      <button class="tab active" onclick="switchTab('docs')">📄 מסמכים</button>
      <button class="tab" onclick="switchTab('hearings')">📅 דיונים</button>
      <button class="tab" onclick="switchTab('search')">🔎 חיפוש בתיק</button>
      <button class="tab" onclick="switchTab('ai')">✨ סיכום AI</button>
    </div>
    <div id="tab-docs"></div>
    <div id="tab-hearings" style="display:none"></div>
    <div id="tab-search"   style="display:none"></div>
    <div id="tab-ai"       style="display:none"></div>
  </div>
</div>

<script src="/app.js"></script>
</body>
</html>"""


JS_CODE = r"""
const PROXY = 'http://localhost:5050';
const COURT_NAMES = {1:'ירושלים',2:'תל אביב',3:'חיפה',4:'פתח תקוה',5:'רחובות',6:'באר שבע',7:'טבריה',8:'צפת',9:'אשדוד',10:'אשקלון',11:'נתניה',12:'בית הדין הגדול',13:'אריאל'};

let userCourtId=null, userCourtName=null, userName=null, devMode=false;
let caseDocs=[], docTexts={}, selectedCase=null, summonsHidden=false;
let allCaseDocs={}, searchRunning=false, searchAborted=false;

async function boot() {
  checkHealth();
  setInterval(checkHealth, 30000);
  checkForUpdate();
  // Hide modal initially via JS (it has display:flex in HTML for layout purposes)
  document.getElementById('court-modal').style.display = 'none';
  try {
    const r = await fetch(PROXY + '/api/me');
    const d = await r.json();
    if (d.courtId) {
      userName = d.firstName ? d.firstName + ' ' + d.lastName : d.userName || '';
      const courts = d.courtList || [{ courtId: d.courtId, courtName: d.courtName }];
      if (courts.length > 1) {
        showCourtModal(courts, userName, d);
      } else {
        applyCourtUser(d.courtId, d.courtName || COURT_NAMES[d.courtId] || String(d.courtId), userName);
      }
    }
  } catch(e) { console.log('me error:', e); }
}

function showCourtModal(courts, name, meData) {
  document.getElementById('court-modal-user').textContent = name || '';
  const list = document.getElementById('court-modal-list');
  list.innerHTML = courts.map((c, i) =>
    '<label style="display:flex;align-items:center;gap:10px;background:#f8f9fb;border:2px solid ' + (i===0?'#1a3a5c':'#e0e4ea') + ';border-radius:8px;padding:12px 14px;cursor:pointer;font-size:14px;font-weight:' + (i===0?'600':'400') + '" onclick="selectCourtOption(this,' + c.courtId + ',\'' + (c.courtName||'') + '\')">' +
    '<span style="font-size:20px">🏛</span>' + (c.courtName || COURT_NAMES[c.courtId] || String(c.courtId)) +
    '</label>'
  ).join('');
  list.dataset.selectedId   = courts[0].courtId;
  list.dataset.selectedName = courts[0].courtName || COURT_NAMES[courts[0].courtId] || String(courts[0].courtId);
  document.getElementById('court-modal').style.display = 'flex';
}

function selectCourtOption(el, courtId, courtName) {
  document.querySelectorAll('#court-modal-list label').forEach(l => {
    l.style.borderColor  = '#e0e4ea';
    l.style.fontWeight   = '400';
  });
  el.style.borderColor = '#1a3a5c';
  el.style.fontWeight  = '600';
  document.getElementById('court-modal-list').dataset.selectedId   = courtId;
  document.getElementById('court-modal-list').dataset.selectedName = courtName;
}

function confirmCourtSelection() {
  const list = document.getElementById('court-modal-list');
  const cid  = parseInt(list.dataset.selectedId);
  const name = list.dataset.selectedName;
  document.getElementById('court-modal').style.display = 'none';
  applyCourtUser(cid, name, userName);
}

function applyCourtUser(courtId, courtName, name) {
  userCourtId   = courtId;
  userCourtName = courtName;
  document.getElementById('header-title').textContent = 'חיפוש חכם וסיכומי AI — ' + courtName;
  document.title = 'שירה AI — ' + courtName;
  document.getElementById('user-chip').textContent = name ? '👤 ' + name : '';
}

function toggleDevMode() {
  if (!devMode) {
    const pwd = prompt('סיסמת מפתח:');
    if (pwd !== 'ELCH2026') { alert('סיסמה שגויה'); return; }
  }
  devMode = !devMode;
  document.getElementById('dev-btn').textContent  = devMode ? '⚙ מצב מפתח' : '⚙';
  document.getElementById('usage-btn').style.display = devMode ? 'block' : 'none';
}

async function checkForUpdate() {
  try {
    const r = await fetch(PROXY + '/api/check-update');
    const d = await r.json();
    if (d.hasUpdate) {
      const b = document.getElementById('update-banner');
      document.getElementById('update-version-info').textContent = 'גרסה ' + d.latest + ' זמינה (נוכחית: ' + d.current + ')';
      b.style.display = 'flex';
    }
  } catch(e) {}
}

async function doUpdate() {
  const b = document.getElementById('update-banner');
  b.innerHTML = '<span class="spinner"></span> <span>מוריד עדכון...</span>';
  try {
    const r = await fetch(PROXY + '/api/do-update', {method:'POST'});
    const d = await r.json();
    if (d.error) { b.innerHTML = '<span style="color:#ffcdd2">שגיאה: ' + d.error + '</span>'; return; }
    if (d.restart) {
      b.innerHTML = '<span>✓ העדכון הותקן — המערכת תופעל מחדש...</span>';
      setTimeout(() => window.close(), 2000);
    } else {
      b.innerHTML = '<span>✓ הקובץ הורד. החלף את ShiraAI.exe ידנית.</span>';
    }
  } catch(e) { b.innerHTML = '<span style="color:#ffcdd2">שגיאה: ' + e.message + '</span>'; }
}

async function checkHealth() {
  try {
    const r = await fetch(PROXY + '/api/health');
    document.getElementById('dot').className        = r.ok ? 'status-dot ok' : 'status-dot err';
    document.getElementById('status-label').textContent = r.ok ? 'מחובר לשרת' : 'שגיאה';
  } catch {
    document.getElementById('dot').className        = 'status-dot err';
    document.getElementById('status-label').textContent = 'שגיאה — הפעל שרת';
  }
}

function applyCourtFilter(data) {
  if (devMode || !userCourtId) return data;
  return data.filter(c => c.courtId === userCourtId);
}

function clearSearch() {
  ['id-input','case-input','name-first','name-last'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  document.getElementById('results-area').innerHTML = '';
  document.getElementById('case-panel').style.display = 'none';
  // Focus the visible input
  const panels = {id:'id-input', case:'case-input', name:'name-first'};
  const active = document.querySelector('.tab.active')?.id?.replace('stab-','');
  if (active && panels[active]) document.getElementById(panels[active])?.focus();
}

function switchSearchTab(tab) {
  ['id','case','name'].forEach(t => {
    document.getElementById('search-' + t + '-panel').style.display = t === tab ? 'block' : 'none';
    document.getElementById('stab-' + t).classList.toggle('active', t === tab);
  });
  document.getElementById('results-area').innerHTML = '';
}

async function doSearch() {
  const idNum = document.getElementById('id-input').value.trim();
  const area  = document.getElementById('results-area');
  if (!idNum || idNum.length < 5) { area.innerHTML = '<p class="empty">נא להכניס ת"ז תקינה</p>'; return; }
  area.innerHTML = '<p class="empty"><span class="spinner"></span> מחפש...</p>';
  document.getElementById('case-panel').style.display = 'none';
  try {
    const r    = await fetch(PROXY + '/api/search', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({idNum})});
    const data = await r.json();
    if (data.error) { area.innerHTML = '<div class="error-msg">שגיאה: ' + data.error + '</div>'; return; }
    renderResults(Array.isArray(data) ? data : [], area);
  } catch { area.innerHTML = '<div class="error-msg">לא ניתן להתחבר לשרת.</div>'; }
}

async function doCaseSearch() {
  const raw  = document.getElementById('case-input').value.trim();
  const area = document.getElementById('results-area');
  if (!raw) { area.innerHTML = '<p class="empty">נא להכניס מספר תיק</p>'; return; }
  const parts      = raw.split('/');
  const fileMainId = parts[0].replace(/[^0-9]/g, '');
  const fileNumber = parts[1] ? parts[1].replace(/[^0-9]/g, '') : null;
  if (!fileMainId) { area.innerHTML = '<p class="empty">מספר תיק לא תקין</p>'; return; }
  area.innerHTML = '<p class="empty"><span class="spinner"></span> מחפש...</p>';
  document.getElementById('case-panel').style.display = 'none';
  try {
    const r    = await fetch(PROXY + '/api/search-case', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fileMainId,fileNumber})});
    const data = await r.json();
    if (data.error) { area.innerHTML = '<div class="error-msg">שגיאה: ' + data.error + '</div>'; return; }
    renderResults(Array.isArray(data) ? data : (data ? [data] : []), area);
  } catch { area.innerHTML = '<div class="error-msg">לא ניתן להתחבר לשרת.</div>'; }
}

async function doNameSearch() {
  const firstName = document.getElementById('name-first').value.trim();
  const lastName  = document.getElementById('name-last').value.trim();
  const area      = document.getElementById('results-area');
  if (!lastName && !firstName) { area.innerHTML = '<p class="empty">נא להכניס שם</p>'; return; }
  area.innerHTML = '<p class="empty"><span class="spinner"></span> מחפש...</p>';
  document.getElementById('case-panel').style.display = 'none';
  try {
    const r    = await fetch(PROXY + '/api/search-name', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lastName,firstName})});
    const data = await r.json();
    if (data.error) { area.innerHTML = '<div class="error-msg">שגיאה: ' + data.error + '</div>'; return; }
    renderResults(Array.isArray(data) ? data : [], area);
  } catch { area.innerHTML = '<div class="error-msg">לא ניתן להתחבר לשרת.</div>'; }
}

function renderResults(data, area) {
  const filtered = applyCourtFilter(data);
  if (!filtered.length) { area.innerHTML = '<p class="empty">לא נמצאו תיקים</p>'; return; }
  window._cases = filtered;
  let html = '<p style="font-size:12px;color:#888;margin-bottom:8px;">נמצאו ' + filtered.length + ' תיקים</p>';
  html += '<table><thead><tr><th>מס תיק</th><th>בית דין</th><th>נושא</th><th>צד א</th><th>צד ב</th><th>סטטוס</th></tr></thead><tbody>';
  filtered.forEach((c, i) => {
    const cls    = c.fileStatusID === 2 ? 'b-closed' : c.fileStatusID === 5 ? 'b-pending' : 'b-open';
    const status = c.fileStatusName || (c.isClosed ? 'סגור' : 'פתוח');
    html += '<tr class="clickable" onclick="selectCase(' + i + ')" data-idx="' + i + '">';
    html += '<td>' + (c.fullFileMainNumber||c.fileNumber||'') + '</td><td>' + (c.courtName||'') + '</td><td>' + (c.subjectSubName||'') + '</td>';
    html += '<td>' + (c.sideA||'').substring(0,25) + '</td><td>' + (c.sideB||'').substring(0,25) + '</td>';
    html += '<td><span class="badge ' + cls + '">' + status + '</span></td></tr>';
  });
  html += '</tbody></table>';
  area.innerHTML = html;
}

async function selectCase(idx) {
  selectedCase    = window._cases[idx];
  caseDocs        = []; docTexts = {}; summonsHidden = false;
  document.getElementById('tab-ai').innerHTML = '';
  document.querySelectorAll('tr[data-idx]').forEach(r => r.classList.remove('selected'));
  const row = document.querySelector('tr[data-idx="' + idx + '"]');
  if (row) row.classList.add('selected');
  document.getElementById('case-heading').textContent = '📁 תיק ' + (selectedCase.fullFileMainNumber||selectedCase.fileNumber) + ' — ' + (selectedCase.sideA||'') + ' / ' + (selectedCase.sideB||'');
  document.getElementById('case-stats').innerHTML =
    '<div class="stat"><div class="stat-val">' + (selectedCase.courtName||'—') + '</div><div class="stat-lbl">בית דין</div></div>' +
    '<div class="stat"><div class="stat-val">' + (selectedCase.subjectSubName||'—') + '</div><div class="stat-lbl">נושא</div></div>' +
    '<div class="stat"><div class="stat-val">' + (selectedCase.isClosed?'סגור':'פתוח') + '</div><div class="stat-lbl">סטטוס</div></div>';
  document.getElementById('case-panel').style.display = 'block';
  switchTab('docs');
  document.getElementById('case-panel').scrollIntoView({behavior:'smooth'});
  loadDocs();
}

async function loadDocs() {
  const fileId = selectedCase.fileId || selectedCase.fileMainId;
  try {
    const r    = await fetch(PROXY + '/api/documents/' + fileId);
    const data = await r.json();
    caseDocs   = data.error ? [] : data;
    allCaseDocs[fileId] = caseDocs;
    if (document.getElementById('tab-docs').style.display !== 'none') renderDocs('');
    renderDocChecklist();
  } catch { caseDocs = []; }
}

function switchTab(tab) {
  document.querySelectorAll('.tab').forEach((t, i) =>
    t.classList.toggle('active', ['docs','hearings','search','ai'][i] === tab));
  ['docs','hearings','search','ai'].forEach(t =>
    document.getElementById('tab-' + t).style.display = t === tab ? 'block' : 'none');
  if (tab === 'docs')     renderDocs('');
  if (tab === 'hearings') loadHearings();
  if (tab === 'search')   renderSearchTab();
  if (tab === 'ai')       renderAITab();
}

function renderDocs(highlight) {
  const el = document.getElementById('tab-docs');
  if (!caseDocs.length) { el.innerHTML = '<p class="empty"><span class="spinner"></span> טוען...</p>'; return; }
  let html = '';
  caseDocs.forEach(d => {
    const nm = highlight ? d.name.replace(new RegExp(highlight,'g'), '<mark>' + highlight + '</mark>') : d.name;
    html += '<div class="doc-row">';
    html += '<span style="font-size:18px">' + (d.type==='pdf'?'📕':'📄') + '</span>';
    html += '<span style="flex:1;font-size:13px">' + nm + '</span>';
    html += '<span style="font-size:11px;color:#888;background:#f0f2f5;padding:1px 7px;border-radius:10px">' + d.type.toUpperCase() + '</span>';
    html += '<span style="color:#888;font-size:12px">' + d.date + '</span>';
    html += '<button class="sm primary" onclick="openDoc(\'' + encodeURIComponent(d.openUrl) + '\')">פתח</button>';
    html += '</div>';
  });
  el.innerHTML = html || '<p class="empty">אין מסמכים</p>';
}

let _lastSearchTerm = '';
function openDoc(u, searchTerm) {
  window.open(decodeURIComponent(u), '_blank');
  if (searchTerm) {
    try { navigator.clipboard.writeText(searchTerm); } catch(e) {}
    const msg = document.getElementById('open-doc-msg');
    if (msg) {
      msg.textContent = '📋 "' + searchTerm + '" הועתק ללוח — לחץ Ctrl+F במסמך שנפתח';
      msg.style.display = 'block';
      clearTimeout(msg._t);
      msg._t = setTimeout(() => msg.style.display = 'none', 5000);
    }
  }
}

async function loadHearings() {
  const el = document.getElementById('tab-hearings');
  el.innerHTML = '<p class="empty"><span class="spinner"></span> טוען דיונים...</p>';
  const fileId = selectedCase.fileId || selectedCase.fileMainId;
  try {
    const r    = await fetch(PROXY + '/api/hearings/' + fileId);
    const data = await r.json();
    if (data.error || !data.length) { el.innerHTML = '<p class="empty">לא נמצאו דיונים</p>'; return; }
    const today = new Date();
    // Decision panel (hidden by default)
    let html =
      '<div id="decision-panel" style="display:none;background:#f8f9fb;border:1px solid #e0e4ea;border-radius:10px;padding:16px;margin-bottom:16px">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">' +
      '<strong style="font-size:13px;color:#1a3a5c">✍ הכן החלטה מהדיון</strong>' +
      '<button onclick="document.getElementById(\'decision-panel\').style.display=\'none\'" style="height:26px;padding:0 10px;border:1px solid #e0e4ea;border-radius:6px;background:#fff;font-size:12px;cursor:pointer;color:#aaa">✕</button>' +
      '</div>' +
      '<p style="font-size:12px;color:#888;margin-bottom:6px" id="decision-context-label"></p>' +
      '<textarea id="decision-prompt" rows="4" style="width:100%;border:1px solid #d0d5dd;border-radius:7px;padding:10px 12px;font-size:13px;direction:rtl;resize:vertical;font-family:inherit;line-height:1.7;margin-bottom:10px">על בסיס פרוטוקולי הדיון וכל מסמכי התיק, נסח החלטה מפורטת ומנומקת של בית הדין. ההחלטה תכלול: רקע עובדתי, סיכום טענות הצדדים, דיון והכרעה, וסעד. כתוב בסגנון רשמי של בית דין רבני.</textarea>' +
      '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">' +
      '<button class="primary" id="decision-go-btn" onclick="generateDecision()">✨ הכן החלטה</button>' +
      '<button id="decision-stop-btn" onclick="decisionAborted=true" style="display:none;background:#c62828;color:#fff;border-color:#c62828;height:38px;padding:0 18px;border-radius:7px;font-size:14px;cursor:pointer">⏹ עצור</button>' +
      '<button onclick="exportDecisionDocx()" style="height:38px;padding:0 14px;border:1px solid #d0d5dd;border-radius:7px;background:#fff;font-size:13px;cursor:pointer">📄 ייצא Word</button>' +
      '</div>' +
      '<div id="decision-log" style="margin-top:8px;font-size:11px;color:#aaa"></div>' +
      '<div id="decision-ans" class="ai-box" style="margin-top:12px;display:none;min-height:100px"></div>' +
      '</div>';
    // Table
    html += '<div style="overflow-x:auto"><table style="font-size:12px">' +
      '<thead><tr>' +
      '<th>תאריך</th><th>תאריך עברי</th><th>מטרת דיון</th><th>סטטוס</th><th>משעה</th><th>עד שעה</th><th>הרכב</th><th>פרוטוקול</th><th>פעולה</th>' +
      '</tr></thead><tbody>';
    data.forEach((row, i) => {
      const d    = new Date((row.date||'').split('/').reverse().join('-'));
      const diff = Math.ceil((d - today) / 86400000);
      const soon = diff >= 0 && diff <= 7
        ? '<br><span style="background:#fff3e0;color:#e65100;padding:1px 6px;border-radius:8px;font-size:10px">בעוד ' + diff + ' ימים</span>' : '';
      const protoCell = row.protocolDocId
        ? '<a href="' + PROXY.replace('http://','http://') + '" onclick="openDoc(\'' + encodeURIComponent('http://shira2/classic/Forms/Documents/DM/DMOpenDocument.aspx?DocIDs=' + row.protocolDocId + '&Action=1') + '\');return false" style="color:#1a3a5c;font-size:18px" title="פתח פרוטוקול">📋</a>'
        : '<span style="color:#ddd;font-size:18px">📋</span>';
      const rowData = encodeURIComponent(JSON.stringify({date: row.date, purpose: row.purpose, protocolDocId: row.protocolDocId}));
      html += '<tr>' +
        '<td style="white-space:nowrap;font-weight:600;color:#1a3a5c">' + (row.date||'') + soon + '</td>' +
        '<td style="white-space:nowrap;color:#888">' + (row.hebrewDate||'') + '</td>' +
        '<td>' + (row.purpose||row.type||'') + '</td>' +
        '<td><span class="badge ' + (row.status==='נקבע'?'b-open':row.status==='נדחה'?'b-pending':'b-closed') + '">' + (row.status||'') + '</span></td>' +
        '<td style="color:#555">' + (row.timeFrom||'') + '</td>' +
        '<td style="color:#555">' + (row.timeTo||'') + '</td>' +
        '<td style="font-size:11px;color:#555;max-width:120px">' + (row.panel||'') + '</td>' +
        '<td style="text-align:center">' + protoCell + ' <span style="font-size:10px;color:#aaa">' + (row.protoStatus||'') + '</span></td>' +
        '<td><button class="sm primary" style="font-size:11px;white-space:nowrap" onclick="openDecisionPanel(' + "'" + rowData + "'" + ')">✍ החלטה</button></td>' +
        '</tr>';
    });
    html += '</tbody></table></div>';
    el.innerHTML = html;
  } catch(e) { el.innerHTML = '<div class="error-msg">שגיאה בטעינת דיונים: ' + e.message + '</div>'; }
}

function openDecisionPanel(rowDataEncoded) {
  const row = JSON.parse(decodeURIComponent(rowDataEncoded));
  const panel = document.getElementById('decision-panel');
  const label = document.getElementById('decision-context-label');
  if (!panel) return;
  if (label) label.textContent = 'דיון מתאריך: ' + (row.date||'') + (row.purpose ? ' — ' + row.purpose : '');
  const prompt = document.getElementById('decision-prompt');
  if (prompt && row.date) {
    prompt.value = 'על בסיס פרוטוקול הדיון מתאריך ' + row.date + ' וכל מסמכי התיק, נסח החלטה מפורטת ומנומקת של בית הדין. ההחלטה תכלול: רקע עובדתי, סיכום טענות הצדדים, דיון והכרעה, וסעד. כתוב בסגנון רשמי של בית דין רבני.';
  }
  // Store protocol doc id for generateDecision to prioritize
  panel.dataset.protocolDocId = row.protocolDocId || '';
  panel.style.display = 'block';
  panel.scrollIntoView({behavior:'smooth'});
}

function showDecisionPanel() {
  const p = document.getElementById('decision-panel');
  if (p) p.style.display = p.style.display === 'none' ? 'block' : 'none';
}

let decisionAborted = false;

async function generateDecision() {
  const prompt  = document.getElementById('decision-prompt')?.value.trim();
  const ansEl   = document.getElementById('decision-ans');
  const logEl   = document.getElementById('decision-log');
  const goBtn   = document.getElementById('decision-go-btn');
  const stopBtn = document.getElementById('decision-stop-btn');
  if (!prompt || !ansEl) return;
  decisionAborted = false;
  goBtn.style.display  = 'none';
  stopBtn.style.display = 'block';
  ansEl.style.display  = 'block';
  ansEl.style.color    = '#999';
  ansEl.style.fontStyle = 'italic';
  ansEl.innerHTML      = '<span class="spinner"></span> טוען מסמכים...';
  logEl.textContent    = '';

  // Use only the specific protocol document for this hearing
  const panel = document.getElementById('decision-panel');
  const protoId = panel?.dataset?.protocolDocId;
  let combined = '';
  if (protoId) {
    logEl.textContent = 'טוען פרוטוקול...';
    if (!docTexts[protoId]) {
      try {
        const r = await fetch(PROXY + '/api/doctext/' + protoId);
        const d = await r.json();
        docTexts[protoId] = d.text || '';
      } catch { docTexts[protoId] = ''; }
    }
    combined = docTexts[protoId] || '';
    logEl.textContent = combined ? '✓ פרוטוקול נטען (' + combined.length + ' תווים)' : '⚠ הפרוטוקול ריק';
  } else {
    logEl.textContent = '⚠ אין פרוטוקול לדיון זה — שולח ללא תוכן';
  }
  if (decisionAborted) { ansEl.textContent = 'הופסק'; goBtn.style.display='block'; stopBtn.style.display='none'; return; }

  logEl.textContent = 'שולח ל-Gemini (' + combined.length + ' תווים)...';

  const styleEx = (await fetch(PROXY + '/api/style-example').then(r=>r.json()).catch(()=>({text:''}))).text || '';
  const sysPrompt = styleEx
    ? 'אתה דיין בבית הדין הרבני. כתוב בעברית בלבד. ללא markdown ללא כוכביות. השאר שורה ריקה בין כל פסקה.\n\nכתוב בדיוק באותו סגנון ומבנה כמו הדוגמה:\n---\n' + styleEx + '\n---'
    : 'אתה דיין בבית הדין הרבני. כתוב בעברית בלבד. ללא markdown ללא כוכביות. השאר שורה ריקה בין כל פסקה. כתוב בסגנון רשמי של פסיקה רבנית. פרט ככל האפשר.';

  try {
    await streamAI(sysPrompt, 'מסמכי תיק:\n\n' + combined + '\n\n---\n' + prompt, ansEl);
    logEl.textContent = '✓ הסתיים';
  } catch(e) {
    ansEl.textContent = 'שגיאה: ' + e.message;
    logEl.textContent = '';
  } finally {
    goBtn.style.display  = 'block';
    stopBtn.style.display = 'none';
  }
}

async function exportDecisionDocx() {
  const ans = document.getElementById('decision-ans');
  if (!ans || !ans.textContent || ans.style.display === 'none') { alert('אין החלטה לייצוא'); return; }
  try {
    const resp = await fetch(PROXY + '/api/export-docx', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({text:ans.textContent, caseNumber:selectedCase?.fullFileMainNumber||selectedCase?.fileNumber||'', caseTitle:(selectedCase?.sideA||'')+' נגד '+(selectedCase?.sideB||''), courtName:userCourtName||'בית הדין הרבני'})
    });
    if (!resp.ok) { alert('שגיאה בייצוא'); return; }
    const blob = await resp.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    const cd   = resp.headers.get('Content-Disposition') || '';
    const m    = cd.match(/filename[*]?=(?:UTF-8'')?([^;]+)/i);
    a.download = m ? decodeURIComponent(m[1].replace('סיכום_AI','החלטה')) : 'החלטה.docx';
    a.href = url; a.click(); URL.revokeObjectURL(url);
  } catch(e) { alert('שגיאה: ' + e.message); }
}

function renderSearchTab() {
  const total = window._cases ? window._cases.length : 1;
  document.getElementById('tab-search').innerHTML =
    '<div style="margin-bottom:10px;display:flex;gap:16px;align-items:center;flex-wrap:wrap">' +
    '<label style="display:flex;align-items:center;gap:5px;font-size:13px;cursor:pointer"><input type="radio" name="search-scope" value="case" checked onchange="updateSearchPlaceholder()"> תיק נוכחי בלבד</label>' +
    '<label style="display:flex;align-items:center;gap:5px;font-size:13px;cursor:pointer"><input type="radio" name="search-scope" value="all" onchange="updateSearchPlaceholder()"> כל ' + total + ' התיקים שנמצאו</label>' +
    '</div>' +
    '<div class="row">' +
    '<input type="text" id="content-q" placeholder="חפש מילה בכל מסמכי התיק..."/>' +
    '<button id="search-go-btn" class="primary" onclick="doContentSearch()">🔎 חפש</button>' +
    '<button id="search-stop-btn" onclick="stopSearch()" style="display:none;background:#c62828;color:#fff;border-color:#c62828">⏹ עצור</button>' +
    '</div>' +
    '<div id="search-progress" style="display:none;font-size:12px;color:#888;margin-bottom:8px;padding:4px 0"></div>' +
    '<div id="content-results"></div>';
}

function updateSearchPlaceholder() {
  const scope = document.querySelector('input[name="search-scope"]:checked')?.value;
  const inp = document.getElementById('content-q');
  if (inp) inp.placeholder = scope === 'all' ? 'חפש בכל התיקים שנמצאו...' : 'חפש מילה בכל מסמכי התיק...';
}

function stopSearch() { searchAborted = true; }

async function doContentSearch() {
  const q    = document.getElementById('content-q').value.trim();
  const area = document.getElementById('content-results');
  const prog = document.getElementById('search-progress');
  if (!q || searchRunning) return;
  const scope = document.querySelector('input[name="search-scope"]:checked')?.value || 'case';
  const cases = scope === 'all' && window._cases ? window._cases : [selectedCase];
  searchRunning = true; searchAborted = false;
  document.getElementById('search-go-btn').style.display  = 'none';
  document.getElementById('search-stop-btn').style.display = 'block';
  prog.style.display = 'block';
  area.innerHTML = '<p class="empty"><span class="spinner"></span> מחפש...</p>';
  try {
    const allHits = [];
    for (let ci = 0; ci < cases.length; ci++) {
      if (searchAborted) break;
      const c      = cases[ci];
      const fileId = c.fileId || c.fileMainId;
      prog.textContent = 'תיק ' + (ci+1) + '/' + cases.length + ': ' + (c.fullFileMainNumber||c.fileNumber||'');
      if (!allCaseDocs[fileId]) {
        try {
          const r = await fetch(PROXY + '/api/documents/' + fileId);
          const d = await r.json();
          allCaseDocs[fileId] = d.error ? [] : d;
        } catch { allCaseDocs[fileId] = []; }
      }
      const docs = allCaseDocs[fileId];
      for (let di = 0; di < docs.length; di++) {
        if (searchAborted) break;
        const doc = docs[di];
        prog.textContent = 'תיק ' + (ci+1) + '/' + cases.length + ' — מסמך ' + (di+1) + '/' + docs.length + ': ' + doc.name;
        if (!docTexts[doc.docId]) {
          try {
            const r = await fetch(PROXY + '/api/doctext/' + doc.docId);
            const d = await r.json();
            docTexts[doc.docId] = d.text || '';
          } catch { docTexts[doc.docId] = ''; }
        }
        if (doc.name.includes(q) || (docTexts[doc.docId]||'').includes(q))
          allHits.push({c, doc, text: docTexts[doc.docId]||''});
      }
    }
    if (!allHits.length) { area.innerHTML = '<p class="empty">' + (searchAborted?'החיפוש הופסק':'לא נמצאו תוצאות') + '</p>'; return; }
    let html = '<p style="font-size:12px;color:#888;margin-bottom:8px;">נמצאו ' + allHits.length + ' תוצאות' + (searchAborted?' (הופסק)':'') + ':</p>';
    const byCase = {};
    allHits.forEach(h => { const k = h.c.fullFileMainNumber||h.c.fileNumber; if(!byCase[k]) byCase[k]={c:h.c,hits:[]}; byCase[k].hits.push(h); });
    Object.values(byCase).forEach(({c, hits}) => {
      if (cases.length > 1) html += '<div style="background:#f0f6ff;border-radius:6px;padding:6px 10px;margin:8px 0 4px;font-size:12px;font-weight:600;color:#1a3a5c">📁 תיק ' + (c.fullFileMainNumber||c.fileNumber) + ' — ' + (c.sideA||'') + ' / ' + (c.sideB||'') + '</div>';
      hits.forEach(({doc, text}) => {
        const idx  = text.indexOf(q);
        const snip = idx >= 0 ? '...' + text.substring(Math.max(0,idx-40), idx+q.length+80).replace(new RegExp(q,'g'),'<mark>'+q+'</mark>') + '...' : '';
        html += '<div class="doc-row" style="flex-direction:column;align-items:flex-start;gap:4px">';
        const btnId = 'obtn_' + doc.docId;
        html += '<div style="display:flex;gap:8px;align-items:center;width:100%"><span>'+(doc.type==='pdf'?'📕':'📄')+'</span><strong style="font-size:13px">'+doc.name+'</strong><span style="color:#888;font-size:12px">'+doc.date+'</span><button id="'+btnId+'" class="sm primary" style="margin-right:auto">פתח</button></div>';
        window._searchBtns = window._searchBtns || {};
        window._searchBtns[btnId] = {url: doc.openUrl, q};
        if (snip) html += '<p style="font-size:12px;color:#555;padding-right:24px;line-height:1.7">'+snip+'</p>';
        html += '</div>';
      });
    });
    area.innerHTML = html;
    // Wire up open buttons with search term
    if (window._searchBtns) {
      Object.entries(window._searchBtns).forEach(([id, {url, q}]) => {
        const btn = document.getElementById(id);
        if (btn) btn.onclick = () => openDoc(encodeURIComponent(url), q);
      });
      window._searchBtns = {};
    }
  } finally {
    searchRunning = false; searchAborted = false;
    document.getElementById('search-go-btn').style.display  = 'block';
    document.getElementById('search-stop-btn').style.display = 'none';
    prog.style.display = 'none';
  }
}

function isSummons(name) {
  const n  = (name||'').toLowerCase();
  const kw = ['זימון','הזמנה לדיון','הזמנה לישיבה','הודעה על דיון','הזמנת עדים','מועד דיון','נדחה ל','notice','summon'];
  return kw.some(k => n.includes(k));
}

function renderAITab() {
  const el = document.getElementById('tab-ai');
  if (el.innerHTML) return;
  const caseKey = 'ai_' + (selectedCase.fullFileMainNumber || selectedCase.fileNumber);
  el.innerHTML = [
    '<div style="margin-bottom:16px">',
    '  <p style="font-size:12px;color:#888;margin-bottom:8px">שאלה על התיק</p>',
    '  <div class="row"><input type="text" id="ai-q" placeholder="מה הסוגיות המרכזיות?"/><button class="primary" onclick="askAI()">✨ שאל</button></div>',
    '</div>',
    '<div style="margin-bottom:16px">',
    '  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">',
    '    <p style="font-size:12px;color:#888">📋 דוגמה לסגנון הפלט <span style="color:#bbb;font-weight:normal">(הדבק קטע מהחלטה אמיתית — גמיני ילמד ממנה)</span></p>',
    '    <div style="display:flex;gap:6px">',
    '      <button class="sm" onclick="saveStyleExample()" style="font-size:11px;background:#e8f5e9;color:#2e7d32;border-color:#a5d6a7">💾 שמור</button>',
    '      <button class="sm" onclick="clearStyleExample()" style="font-size:11px;color:#aaa">🗑 נקה</button>',
    '    </div>',
    '  </div>',
    '  <textarea id="style-example" rows="5" placeholder="הדבק כאן קטע מהחלטת דיין לדוגמה — גמיני ישתמש בסגנון, הרווחים והמבנה שלה..." style="width:100%;border:1px solid #d0d5dd;border-radius:7px;padding:10px 12px;font-size:12px;direction:rtl;resize:vertical;font-family:inherit;color:#444;line-height:1.7"></textarea>',
    '  <p id="style-saved-msg" style="font-size:11px;color:#2e7d32;display:none;margin-top:4px">✓ הדוגמה נשמרה</p>',
    '</div>',
    '<div style="margin-bottom:16px">',
    '  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">',
    '    <p style="font-size:12px;color:#888">מסמכים לשליחה ל-AI</p>',
    '    <div style="display:flex;gap:6px">',
    '      <button class="sm" onclick="toggleAllDocs(true)"  style="font-size:11px">✓ בחר הכל</button>',
    '      <button class="sm" onclick="toggleAllDocs(false)" style="font-size:11px">✗ בטל הכל</button>',
    '    </div>',
    '  </div>',
    '  <div style="margin-bottom:6px;display:flex;gap:6px;align-items:center">',
    '    <button class="sm" id="btn-filter-summons" onclick="filterSummons()" style="font-size:11px;background:#fff3e0;color:#e65100;border-color:#ffcc80">🚫 הסתר זימונים</button>',
    '    <span id="summons-status" style="font-size:11px;color:#aaa"></span>',
    '  </div>',
    '  <div id="doc-checklist" style="background:#f8f9fb;border:1px solid #e0e4ea;border-radius:8px;padding:8px;max-height:180px;overflow-y:auto">',
    '    <p style="font-size:12px;color:#aaa;text-align:center;padding:8px">טוען מסמכים...</p>',
    '  </div>',
    '</div>',
    '<div style="margin-bottom:12px">',
    '  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">',
    '    <p style="font-size:12px;color:#888">לוג פעילות</p>',
    '    <button class="sm" onclick="clearLog()" style="font-size:11px;color:#aaa">נקה</button>',
    '  </div>',
    '  <div id="ai-log" style="background:#1a1a2e;color:#7ec8e3;font-size:11px;font-family:monospace;border-radius:6px;padding:8px;max-height:100px;overflow-y:auto;direction:ltr"></div>',
    '</div>',
    '<div style="margin-top:14px">',
    '  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">',
    '    <p style="font-size:12px;color:#888">תשובה</p>',
    '    <div style="display:flex;gap:8px;align-items:center">',
    '      <span id="ai-cost" style="font-size:11px;color:#bbb;display:none"></span>',
    '      <button class="sm" onclick="exportDocx()" style="font-size:11px;background:#1a3a5c;color:#fff;border-color:#1a3a5c">📄 ייצא Word</button>',
    '      <button class="sm" onclick="clearAI(\'' + caseKey + '\')" style="font-size:11px;color:#aaa;border-color:#e0e4ea">🗑 נקה</button>',
    '    </div>',
    '  </div>',
    '  <div class="ai-box" id="ai-ans" style="min-height:120px;color:#aaa;font-style:italic">התשובה תופיע כאן...</div>',
    '</div>'
  ].join('\n');
  const saved = sessionStorage.getItem(caseKey);
  if (saved) { const a=document.getElementById('ai-ans'); a.style.color='#222'; a.style.fontStyle='normal'; a.textContent=saved; }
  if (devMode) { const c=document.getElementById('ai-cost'); if(c) c.style.display='inline'; }
  fetch(PROXY + '/api/style-example').then(r=>r.json()).then(d=>{ const t=document.getElementById('style-example'); if(t&&d.text) t.value=d.text; }).catch(()=>{});
  renderDocChecklist();
}

async function saveStyleExample() {
  const t = document.getElementById('style-example');
  if (!t) return;
  try {
    await fetch(PROXY + '/api/style-example', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text: t.value})});
    const msg = document.getElementById('style-saved-msg');
    if (msg) { msg.style.display='block'; setTimeout(()=>msg.style.display='none', 2000); }
  } catch(e) { alert('שגיאה בשמירה: ' + e.message); }
}

async function clearStyleExample() {
  try {
    await fetch(PROXY + '/api/style-example', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text: ''})});
    const t = document.getElementById('style-example');
    if (t) t.value = '';
  } catch(e) {}
}

function renderDocChecklist() {
  const el = document.getElementById('doc-checklist');
  if (!el) return;
  if (!caseDocs.length) { el.innerHTML = '<p style="font-size:12px;color:#aaa;text-align:center;padding:8px">אין מסמכים</p>'; return; }
  el.innerHTML = caseDocs.map((d,i) =>
    '<label style="display:flex;align-items:center;gap:8px;padding:4px 6px;border-radius:4px;cursor:pointer;font-size:12px" onmouseover="this.style.background=\'#f0f4f8\'" onmouseout="this.style.background=\'\'">' +
    '<input type="checkbox" id="doc-chk-' + i + '" checked style="cursor:pointer"/>' +
    '<span style="flex:1">' + d.name + '</span>' +
    '<span style="color:#aaa;font-size:11px">' + d.date + '</span></label>'
  ).join('');
}

function filterSummons() {
  summonsHidden = !summonsHidden;
  const btn = document.getElementById('btn-filter-summons');
  const st  = document.getElementById('summons-status');
  if (!summonsHidden) {
    caseDocs.forEach((_,i) => { const l=document.getElementById('doc-chk-'+i)?.closest('label'); if(l) l.style.display=''; });
    btn.style.background='#fff3e0'; btn.style.color='#e65100'; btn.textContent='🚫 הסתר זימונים'; st.textContent='';
    return;
  }
  btn.textContent='✓ הצג הכל'; btn.style.background='#e8f5e9'; btn.style.color='#2e7d32';
  let hidden=0;
  caseDocs.forEach((doc,i) => {
    const label = document.getElementById('doc-chk-'+i)?.closest('label');
    if (label) {
      const s = isSummons(doc.name);
      label.style.display = s ? 'none' : '';
      if (s) { document.getElementById('doc-chk-'+i).checked=false; hidden++; }
    }
  });
  st.textContent = hidden > 0 ? 'הוסתרו ' + hidden + ' זימונים' : 'לא נמצאו זימונים';
}

function toggleAllDocs(checked) {
  caseDocs.forEach((_,i) => { const c=document.getElementById('doc-chk-'+i); if(c) c.checked=checked; });
}

function getSelectedDocs() {
  return caseDocs.filter((_,i) => { const c=document.getElementById('doc-chk-'+i); return c&&c.checked; });
}

function addLog(msg) {
  const log = document.getElementById('ai-log');
  if (!log) return;
  log.innerHTML += '<div>[' + new Date().toLocaleTimeString('he-IL') + '] ' + msg + '</div>';
  log.scrollTop  = log.scrollHeight;
}

function clearLog() { const l=document.getElementById('ai-log'); if(l) l.innerHTML=''; }

async function loadDocTexts() {
  const sel = getSelectedDocs();
  addLog('טוען ' + sel.length + ' מסמכים...');
  for (const doc of sel) {
    if (!docTexts[doc.docId]) {
      addLog('טוען: ' + doc.name);
      try {
        const r = await fetch(PROXY + '/api/doctext/' + doc.docId);
        const d = await r.json();
        docTexts[doc.docId] = d.text || '';
        addLog('✓ ' + doc.name + ' (' + docTexts[doc.docId].length + ' תווים)');
      } catch { docTexts[doc.docId]=''; addLog('✗ שגיאה: ' + doc.name); }
    } else { addLog('✓ ' + doc.name + ' (כבר נטען)'); }
  }
}

async function streamAI(system, userMessage, targetEl) {
  targetEl.className = 'ai-box';
  targetEl.innerHTML = '<span class="ai-cursor"></span>';
  const resp = await fetch(PROXY + '/api/ai', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
      system,
      messages:[{role:'user',content:userMessage}],
      sideA: selectedCase?.sideA || '',
      sideB: selectedCase?.sideB || '',
      caseNumber: selectedCase?.fullFileMainNumber || selectedCase?.fileNumber || ''
    })
  });
  if (!resp.ok) throw new Error('HTTP ' + resp.status);
  const reader  = resp.body.getReader();
  const decoder = new TextDecoder();
  let text = '';
  while (true) {
    const {done,value} = await reader.read();
    if (done) break;
    const raw   = decoder.decode(value, {stream:true});
    const lines = raw.split('\n');
    for (const line of lines) {
      if (!line.startsWith('data:')) continue;
      const s = line.slice(5).trim();
      if (!s || s === '[DONE]') continue;
      try {
        const chunk = JSON.parse(s);
        if (chunk.error) throw new Error(chunk.error);
        if (chunk.text) {
          text += chunk.text;
          targetEl.innerHTML = text + '<span class="ai-cursor"></span>';
        }
        if (chunk.usage) {
          const u = chunk.usage;
          const costEl = document.getElementById('ai-cost');
          if (costEl && devMode) costEl.textContent = 'טוקנים: ' + u.total.toLocaleString() + ' | $' + u.usd + ' / ₪' + u.ils;
          addLog('טוקנים: ' + u.total.toLocaleString() + ' | $' + u.usd);
        }
      } catch(e) { console.log('chunk err', e); }
    }
  }
  targetEl.style.color = '#222';
  targetEl.style.fontStyle = 'normal';
  targetEl.textContent = text || 'לא ניתן לענות';
  if (selectedCase) {
    const ck = 'ai_' + (selectedCase.fullFileMainNumber || selectedCase.fileNumber);
    try { sessionStorage.setItem(ck, text); } catch(e) {}
  }
  return text;
}

function clearAI(caseKey) {
  sessionStorage.removeItem(caseKey);
  const ans = document.getElementById('ai-ans');
  if (ans) { ans.style.color='#aaa'; ans.style.fontStyle='italic'; ans.textContent='התשובה תופיע כאן...'; }
}

async function exportDocx() {
  const ans = document.getElementById('ai-ans');
  if (!ans || !ans.textContent || ans.textContent === 'התשובה תופיע כאן...') { alert('אין תשובה לייצוא'); return; }
  try {
    const resp = await fetch(PROXY + '/api/export-docx', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({text:ans.textContent, caseNumber:selectedCase?.fullFileMainNumber||selectedCase?.fileNumber||'', caseTitle:(selectedCase?.sideA||'')+' נגד '+(selectedCase?.sideB||''), courtName:userCourtName||'בית הדין הרבני'})
    });
    if (!resp.ok) { alert('שגיאה בייצוא'); return; }
    const blob = await resp.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    const cd   = resp.headers.get('Content-Disposition') || '';
    const m    = cd.match(/filename[*]?=(?:UTF-8'')?([^;]+)/i);
    a.download = m ? decodeURIComponent(m[1]) : 'סיכום_AI.docx';
    a.href = url; a.click(); URL.revokeObjectURL(url);
  } catch(e) { alert('שגיאה: ' + e.message); }
}

async function askAI() {
  const q = document.getElementById('ai-q').value.trim();
  if (!q) return;
  const selected = getSelectedDocs();
  if (!selected.length) { alert('נא לבחור לפחות מסמך אחד'); return; }
  const ans = document.getElementById('ai-ans');
  ans.className='ai-box'; ans.style.color='#999'; ans.style.fontStyle='italic'; ans.textContent='טוען מסמכים...';
  addLog('--- שאילתה חדשה ---');
  addLog('שאלה: ' + q);
  addLog('מסמכים: ' + selected.length);
  await loadDocTexts();
  const MAX_DOC = 30000, MAX_TOT = 200000;
  const combined = selected
    .map(d => '[' + d.name + ']:\n' + (docTexts[d.docId]||'').substring(0, MAX_DOC))
    .join('\n\n')
    .substring(0, MAX_TOT);
  addLog('טקסט: ' + combined.length + ' תווים');
  addLog('שולח ל-Gemini...');
  const ctx = combined || 'תיק ' + selectedCase.subjectSubName;
  const styleEx = (document.getElementById('style-example')?.value || '').trim();
  const sysPrompt = styleEx
    ? 'אתה עוזר משפטי לבית הדין הרבני. ענה בעברית בלבד. ענה על בסיס המסמכים בלבד. ללא markdown ללא כוכביות.\n\nחשוב מאוד: כתוב בדיוק באותו סגנון, מבנה ורווחים כמו הדוגמה הבאה. השאר שורות ריקות בין פסקאות. כל נושא בפסקה נפרדת. פרט ככל האפשר.\n\nדוגמה לסגנון הנדרש:\n---\n' + styleEx + '\n---'
    : 'אתה עוזר משפטי לבית הדין הרבני. ענה בעברית בלבד. ענה על בסיס המסמכים בלבד. ללא markdown ללא כוכביות. השאר שורה ריקה בין כל פסקה. פרט ככל האפשר.';
  try {
    await streamAI(
      sysPrompt,
      'מסמכי תיק:\n\n' + ctx + '\n\n---\nשאלה: ' + q,
      ans
    );
    addLog('✓ תשובה התקבלה');
  } catch(e) {
    ans.className='ai-box'; ans.textContent='שגיאה: ' + e.message;
    addLog('✗ שגיאה: ' + e.message);
  }
}

async function showUsage() {
  const popup   = document.getElementById('usage-popup');
  const content = document.getElementById('usage-content');
  popup.style.display = popup.style.display === 'none' ? 'block' : 'none';
  if (popup.style.display === 'none') return;
  content.textContent = 'טוען...';
  try {
    const r = await fetch(PROXY + '/api/usage');
    const d = await r.json();
    if (d.error) { content.textContent = 'שגיאה: ' + d.error; return; }
    content.innerHTML =
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px">' +
      '<div style="background:#f8f9fb;border-radius:8px;padding:10px;text-align:center"><div style="font-size:20px;font-weight:600;color:#1a3a5c">' + d.queries + '</div><div style="font-size:11px;color:#888">שאילתות</div></div>' +
      '<div style="background:#f8f9fb;border-radius:8px;padding:10px;text-align:center"><div style="font-size:20px;font-weight:600;color:#1a3a5c">' + d.total_tokens.toLocaleString() + '</div><div style="font-size:11px;color:#888">טוקנים</div></div>' +
      '<div style="background:#e8f5e9;border-radius:8px;padding:10px;text-align:center"><div style="font-size:20px;font-weight:600;color:#2e7d32">$' + d.total_usd + '</div><div style="font-size:11px;color:#888">עלות</div></div>' +
      '<div style="background:#e8f5e9;border-radius:8px;padding:10px;text-align:center"><div style="font-size:20px;font-weight:600;color:#2e7d32">&#8362;' + d.total_ils + '</div><div style="font-size:11px;color:#888">שקלים</div></div>' +
      '</div><div style="font-size:11px;color:#888">ממוצע: $' + d.avg_usd + '</div>';
  } catch(e) { content.textContent = 'שגיאה'; }
}

document.addEventListener('keydown', e => {
  if (e.key !== 'Enter') return;
  const id = document.activeElement.id;
  if (id === 'id-input')    doSearch();
  if (id === 'case-input')  doCaseSearch();
  if (id === 'name-last' || id === 'name-first') doNameSearch();
  if (id === 'content-q')   doContentSearch();
  if (id === 'ai-q')        askAI();
});

boot();
"""


if __name__ == "__main__":
    import time, webbrowser, threading
    PORT = 5050
    if sys.platform == "win32":
        import ctypes
        try: ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
        except: pass
        os.system(f'for /f "tokens=5" %a in (\'netstat -aon ^| findstr :{PORT} ^| findstr LISTENING\') do taskkill /f /pid %a >nul 2>&1')
        time.sleep(0.5)
    print(f"ShiraAI running at http://localhost:{PORT}")
    threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
