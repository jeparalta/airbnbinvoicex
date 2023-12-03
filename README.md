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

## Installation
1. **Clone the repository:**
   ```bash
   git clone https://github.com/jeparalta/airbnbinvoicex.git
   cd airbnbinvoicex

2. **Set up a Virtual Environment (Optional but Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`

3. **Install required Python packages:**
    ```bash
    pip install flask selenium


## Running the Application

1. **Start the Flask application, run one of the following commands in your terminal:**
    ```bash
    flask run   # Or python -m flask run
    
2. **Open a web browser and navigate to:** 
    http://localhost:5000

## Usage

- Enter your Airbnb username and password.
- Enter the booking numbers separated spaces (for pasting multiple numbers).
- Click the "Download Invoices" button.
- The application will process the request and provide a ZIP file for download containing the invoices.
- Make sure your computer doesnt go to sleep or process will get interrupted and fail!

## Security Note

- Ensure that you protect your Airbnb credentials. This application does not store your credentials but uses them for scraping purposes only.

## Legal Disclaimer

- This tool is intended for personal use only. Ensure you are compliant with Airbnb's Terms of Service regarding automated data scraping.

## Contributing

- Contributions to this project are welcome. Please fork the repository and submit a pull request.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
