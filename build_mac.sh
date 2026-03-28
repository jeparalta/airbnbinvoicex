#!/bin/bash
set -e
echo "Building AirbnbInvoiceX for macOS..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pyinstaller
pyinstaller airbnbinvoicex.spec --clean
cd dist
zip -r AirbnbInvoiceX-mac.zip AirbnbInvoiceX.app
echo "Done: dist/AirbnbInvoiceX-mac.zip"
