# Airbnb Invoice Downloader

## Overview
The Airbnb Invoice Downloader is a Flask-based web application designed to automate the process of downloading Airbnb invoices. Users can input their Airbnb credentials along with booking numbers, and the application will scrape the necessary data to provide a ZIP file containing PDF invoices.

## Features
- User-friendly web interface.
- Secure entry of Airbnb credentials.
- Supports multiple invoice downloads.
- Automated login and invoice scraping from Airbnb.
- Outputs a ZIP file containing all requested invoices.

## Prerequisites
- Python 3.x
- Flask
- Selenium
- Chrome WebDriver (must be installed on your server)

### Chrome WebDriver Setup
The application requires Chrome WebDriver to interact with the Chrome browser for web scraping. Ensure Chrome WebDriver is installed and its version is compatible with your Chrome browser.

- **Download Chrome WebDriver**: Visit [ChromeDriver - WebDriver for Chrome](https://sites.google.com/chromium.org/driver/) and download the version that matches your Chrome browser.
- **Setting WebDriver Path**:
  - *Option 1*: Place the `chromedriver` executable in a directory that's in your system's PATH.
  - *Option 2*: Specify the path to `chromedriver` in the `initialize_driver` function within the script.

## Quickstart

```bash
cd airbnbinvoicex
./run.sh
```

The script will create a virtualenv, install dependencies from `requirements.txt`, and start Flask.

If `./run.sh` isn't executable, run:

```bash
chmod +x run.sh
./run.sh
```

## Manual setup (alternative)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=app.py
flask run
```

## Usage

- Paste booking numbers (whitespace separated; we format them automatically).
- Click "Download Invoices".
- A browser opens for manual login/MFA; complete it. It closes automatically once scraping starts.
- The app prepares a ZIP for download on completion.

## Security Note

- Credentials are no longer collected; login is manual in your own browser session.

## Legal Disclaimer

- This tool is intended for personal use only. Ensure you are compliant with Airbnb's Terms of Service regarding automated data scraping.

## Contributing

- Contributions to this project are welcome. Please fork the repository and submit a pull request.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
