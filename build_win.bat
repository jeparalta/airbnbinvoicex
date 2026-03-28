@echo off
echo Building AirbnbInvoiceX for Windows...
python -m venv venv
call venv\Scripts\activate.bat
pip install -r requirements.txt
pip install pyinstaller
pyinstaller airbnbinvoicex.spec --clean
cd dist
powershell Compress-Archive -Path AirbnbInvoiceX -DestinationPath AirbnbInvoiceX-win.zip
echo Done: dist\AirbnbInvoiceX-win.zip
