# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AirbnbInvoiceX is a Flask web application that automates downloading invoices from Airbnb using Selenium browser automation. Users enter booking confirmation codes, the app logs into Airbnb (with manual MFA support), scrapes invoice PDFs via Chrome DevTools Protocol, and delivers them as a zip file.

## Commands

```bash
# Start the app (creates venv, installs deps, opens browser)
./run.sh

# Manual setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run Flask directly
FLASK_APP=app.py flask run --host=0.0.0.0 --port=5001
```

There are no tests, linter, or CI/CD configured.

## Architecture

**Single-file app** — all server logic lives in `app.py` (~784 lines).

### Core Flow
1. User submits comma-separated booking codes via `templates/index.html`
2. `POST /` spawns a daemon thread running `background_scrape()` → `scrape_airbnb_invoices()`
3. Progress page (`templates/progress.html`) polls `GET /progress` every 750ms
4. For each booking code, `download_invoice()` navigates to the reservation page, finds invoice links, and uses `Page.printToPDF` (CDP command) to generate PDFs
5. Results are zipped; `GET /download_zip/<filename>` serves the file; cleanup runs after 30s

### Key Mechanisms
- **Session reuse**: Cookies saved to `session_cookies.json` to avoid repeated MFA. If cookies are stale, falls back to visible browser for manual MFA (5-min timeout).
- **Chrome setup**: `initialize_driver()` configures headless Chrome with aggressive performance opts (images disabled, no extensions). Auto-detects Chrome/Chromium binary.
- **Concurrency**: In-memory `progress` dict guarded by `PROGRESS_LOCK`. Global tracking of `ACTIVE_THREADS`, `ACTIVE_DRIVERS`, `ACTIVE_TIMERS` for graceful shutdown via signal handlers.
- **Retry logic**: Each invoice download retries up to 5 times. On failure, captures screenshot + HTML dump for debugging.

### Routes
| Route | Purpose |
|-------|---------|
| `GET/POST /` | Main form |
| `GET /progress` | JSON progress polling |
| `GET /complete_check` | Completion status check |
| `GET /download_zip/<filename>` | Zip file download |
| `GET /complete` | Results summary page |

### Dependencies
- Flask 3.0.0 — web framework
- Selenium 4.15.2 — browser automation
- python-dotenv 1.0.0 — env var loading
- Chrome/Chromium + ChromeDriver — required on the system

## Security Notes

Snyk security scanning is configured via Cursor rules (`.cursor/rules/snyk_rules.mdc`). Always scan new code for vulnerabilities.
