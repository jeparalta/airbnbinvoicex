# Airbnb Invoice Downloader

## Overview
Flask web app that automates downloading Airbnb invoices. Enter booking confirmation codes, complete login/MFA manually in a browser window, and the app downloads all invoices as a ZIP file.

## Features
- User-friendly web interface
- Manual login/MFA in your own browser — no credentials stored
- Supports multiple bookings in one run
- Outputs a ZIP file containing all requested invoices as PDFs

## Prerequisites
- Python 3.x
- Chrome or Chromium browser (ChromeDriver is managed automatically by Selenium)

## Download (recommended)

1. Go to [Releases](https://github.com/sienioApius/airbnbinvoicex/releases/latest)
2. Download `AirbnbInvoiceX-mac.zip` (Mac) or `AirbnbInvoiceX-win.zip` (Windows)
3. Unzip and double-click `AirbnbInvoiceX`
4. Browser opens automatically at `http://localhost:5001`

**Requirement:** Google Chrome must be installed.

## Quickstart

```bash
cd airbnbinvoicex
./run.sh
```

The script creates a virtualenv, installs dependencies, and opens the app in your browser.

If `./run.sh` isn't executable:

```bash
chmod +x run.sh
./run.sh
```

## Manual setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=app.py
flask run --port 5001
```

## Usage

1. Paste booking confirmation codes (comma or whitespace separated — formatted automatically)
2. Click **Download Invoices**
3. A browser window opens to Airbnb — complete login and MFA there
4. The window closes automatically and the app downloads the invoices
5. Download the ZIP when ready

## Legal Disclaimer

This tool is intended for personal use only. Ensure you are compliant with Airbnb's Terms of Service regarding automated data scraping.

## License
MIT — see [LICENSE](LICENSE).
