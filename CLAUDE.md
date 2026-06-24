# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Shira AI is a local proxy server for Israeli Rabbinical Courts (בתי הדין הרבניים). It bridges the internal Shira case management system (`http://shira2`) with a Hebrew-language web UI that lets court staff search cases, view documents/hearings, and ask AI questions about case files. The entire application lives in a single file: `shira_proxy.py`.

## Running the Server

```bash
# Install dependencies (Windows only for full NTLM auth support)
pip install flask requests requests-negotiate-sspi beautifulsoup4 lxml python-docx pdfplumber flask-cors httpx

# Run the server (starts on port 5050 and opens the browser automatically)
python shira_proxy.py
```

On Windows, `START.bat` is used to launch the server. The script kills any existing process on port 5050 before starting.

## Architecture

Everything is in `shira_proxy.py` — a single Flask app (~2100 lines) that:

1. **Embeds the frontend** as `_HTML` (a Python string). The JS makes all requests to `http://localhost:5050` (the `PROXY` constant). There is no separate HTML file to edit; the frontend lives inside the Python file.

2. **Authenticates to Shira** using Windows NTLM (`HttpNegotiateAuth` from `requests-negotiate-sspi`). A single `SESSION` object is created at startup and reused for all backend requests to `http://shira2` and `http://prod-spfe:1000`.

3. **Streams AI responses** via Server-Sent Events (SSE). The `/api/ai` endpoint forwards requests to Google Gemini 2.5 Flash, anonymizes PII before sending, strips markdown symbols from the response, and logs token usage/costs to `usage_log.jsonl`.

### Key Backend Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/me` | Identifies the logged-in user and their court |
| `POST /api/search` | Search cases by ID number (ת"ז) |
| `POST /api/search-case` | Search by case number |
| `POST /api/search-name` | Search by party name |
| `GET /api/documents/<file_id>` | List documents for a case (scrapes FileDocs.aspx) |
| `GET /api/doctext/<doc_id>` | Extract text from a PDF or DOCX document |
| `GET /api/hearings/<file_id>` | List scheduled hearings for a case |
| `POST /api/ai` | Stream AI response (SSE) via Gemini |
| `POST /api/export-docx` | Export AI summary as a formatted Word document |
| `GET /api/usage` | Return token usage stats from `usage_log.jsonl` |

### Document Text Extraction Flow (`/api/doctext`)

1. POST to `WsShiraUtils.asmx/GetDocumentDetails` with XML to get the internal `DocNumber`
2. POST to `prod-spfe` (`ShiraDocsMngWS.asmx/GetDocumentUrlAndStatus`) to get the file URL
3. Fetch the file, then extract text with `pdfplumber` (PDF) or `python-docx` (DOCX)
4. Text is capped at 30,000 characters before returning

### PII Anonymization

`anonymize_text()` runs on all document content before it reaches Gemini. It strips Israeli ID numbers, phone numbers, emails, bank accounts, addresses, zip codes, passport numbers, and names following legal titles (עו"ד, שופט, etc.).

### Court Filter

By default, the frontend filters search results to only show cases from the logged-in user's own court (`userCourtId`). Dev mode (password: `ELCH2026`) disables this filter and shows all courts.

### Word Export

`/api/export-docx` generates RTL Hebrew `.docx` files using `python-docx` with FrankRuehl font (standard rabbinical court font), correct A4-like page dimensions, and a divider line.

## Configuration

The Gemini API key is hardcoded near line 1410:
```python
GEMINI_API_KEY = "..."
```

Backend URLs are hardcoded:
- `SHIRA = "http://shira2"` — the internal Shira application server
- `SPFE = "http://prod-spfe:1000"` — the document storage service
- `PROXY = "http://192.168.174.80:8080"` — a local HTTP proxy (not currently used by the Flask server itself)

## Conventions

- The app is designed to run on a Windows workstation with domain authentication. On Linux, `requests-negotiate-sspi` is unavailable, so NTLM auth is skipped (SSPI check at module level).
- Shira API responses use `courtId` integers (1=Jerusalem, 2=Tel Aviv, 3=Haifa, 4=Petah Tikva, 5=Rehovot, etc.).
- All user-facing text is in Hebrew (RTL). The UI enforces `direction: rtl`.
- The AI is instructed to respond only in Hebrew, with plain text (no markdown).
