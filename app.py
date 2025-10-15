from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, send_file, session, redirect, url_for, abort

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC



from threading import Timer
import time
import zipfile
import os
import shutil
import base64
import json

import logging
from selenium.webdriver.remote.remote_connection import LOGGER as selenium_logger

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


app = Flask(__name__)
# Get the secret key from environment variables (default empty)
SECRET_KEY = os.environ.get('SECRET_KEY', '')

# If missing/empty, generate a transient key so the app can run locally
if not SECRET_KEY:
    SECRET_KEY = os.urandom(24).hex()

# Set the Flask app's secret key
app.secret_key = SECRET_KEY



def initialize_driver(download_dir, headless=True):
    # Set the Selenium logger to only display critical errors
    selenium_logger.setLevel(logging.CRITICAL)

    chrome_options = Options()
    # Enable headless mode if requested
    if headless:
        chrome_options.add_argument("--headless")

    prefs = {"download.default_directory": download_dir}
    chrome_options.add_experimental_option("prefs", prefs)
    
    # Optionally, set the window size for headless mode
    chrome_options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=chrome_options)
    return driver


def cleanup_files(file_paths, download_dir):
    # Logging the start of the cleanup process
    logging.info("Starting cleanup process.")

    for file_path in file_paths:
        # Check if the file is in the download directory and is a PDF (as an example)
        if file_path.startswith(download_dir) and file_path.endswith(".pdf"):
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logging.info(f"Deleted file: {file_path}")
            except Exception as e:
                logging.error(f"Error deleting file {file_path}: {str(e)}")

    # Optionally, remove the directory if it's empty
    if os.path.exists(download_dir) and not os.listdir(download_dir):
        try:
            shutil.rmtree(download_dir)
            logging.info(f"Deleted directory: {download_dir}")
        except Exception as e:
            logging.error(f"Error deleting directory {download_dir}: {str(e)}")

    logging.info("Cleanup process completed.")



def login_to_airbnb(driver, manual_mfa=False):
    try:
        logging.info("Logging into Airbnb...")

        driver.get("https://www.airbnb.com/login")

        if manual_mfa:
            # Let the user complete the entire login (including MFA) manually in the visible browser.
            # Wait until we're no longer on the login page (up to 5 minutes).
            WebDriverWait(driver, 300).until(lambda d: 'login' not in d.current_url)
        else:
            # Automated (non-MFA) fallback
            continue_with_email_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Continue with email']"))
            )
            continue_with_email_button.click()

            email_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "user[email]"))
            )
            # Credentials removed. This path is not used in enforced MFA mode.

            continue_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@data-testid='signup-login-submit-btn']"))
            )
            continue_button.click()

            password_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "user[password]"))
            )
            # Credentials removed. This path is not used in enforced MFA mode.

            login_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@data-testid='signup-login-submit-btn']"))
            )
            login_button.click()

            time.sleep(5)
    except Exception as e:
       logging.info(f"Error during login: {e}")
        # Handle the error or rethrow to be caught by calling function




def save_session_cookies(driver, cookie_file_path):
    try:
        cookies = driver.get_cookies()
        with open(cookie_file_path, 'w') as f:
            json.dump(cookies, f)
        logging.info(f"Saved session cookies to {cookie_file_path}")
    except Exception as e:
        logging.info(f"Failed to save cookies: {e}")


def load_session_cookies(driver, cookie_file_path):
    try:
        if not os.path.isfile(cookie_file_path):
            return False
        with open(cookie_file_path, 'r') as f:
            cookies = json.load(f)
        # Must be on the domain before adding cookies
        driver.get("https://www.airbnb.com/")
        for cookie in cookies:
            sanitized = {
                'name': cookie.get('name'),
                'value': cookie.get('value'),
                'domain': cookie.get('domain'),
                'path': cookie.get('path', '/'),
                'secure': cookie.get('secure', False),
            }
            if 'expiry' in cookie:
                sanitized['expiry'] = cookie['expiry']
            try:
                driver.add_cookie(sanitized)
            except Exception as e:
                logging.info(f"Skipping cookie add error for {sanitized.get('name')}: {e}")
        # Verify by navigating to an authenticated page
        driver.get("https://www.airbnb.com/hosting/reservations/all")
        if 'login' in driver.current_url:
            return False
        return True
    except Exception as e:
        logging.info(f"Failed to load cookies: {e}")
        return False

def download_invoice(driver, booking_number, download_dir):
    downloaded_file_paths = []
    logging.info(f"Starting download for booking number {booking_number}")  # Debugging print

    try:
        booking_url = f"https://www.airbnb.com/hosting/reservations/all?confirmationCode={booking_number}"
        driver.get(booking_url)

        WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@href, '/vat_invoices/')]"))
        )

        download_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/vat_invoices/')]")

        if not download_links:
            logging.info(f"No invoice links found for booking number {booking_number}")

        for link_index, link in enumerate(download_links):
            # Wait until the link is visible and clickable
            WebDriverWait(driver, 10).until(EC.visibility_of(link))
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable(link))

            # Then click the link
            link.click()

            # Since the link opens in a new tab, switch to the new tab
            driver.switch_to.window(driver.window_handles[-1])

            # Ensure page fully loaded before printing
            WebDriverWait(driver, 20).until(lambda d: d.execute_script('return document.readyState') == 'complete')

            # Define the parameters for the print to PDF command
            print_options = {
                "printBackground": True,
                "pageRanges": "1",
                "paperWidth": 8.27,   # A4 size in inches
                "paperHeight": 11.69, # A4 size in inches
                "marginTop": 0,       # Setting the top margin to 0
                "marginBottom": 0,    # Setting the bottom margin to 0
                "marginLeft": 0,      # Setting the left margin to 0
                "marginRight": 0,
                "preferCSSPageSize": True
            }

            # Execute the print command
            pdf = driver.execute_cdp_cmd("Page.printToPDF", print_options)

            # Decode the result
            pdf_content = base64.b64decode(pdf['data'])

            # Save the PDF to a file
            file_path = os.path.join(download_dir, f"invoice_{booking_number}_{link_index+1}.pdf")
            with open(file_path, 'wb') as file:
                file.write(pdf_content)
            downloaded_file_paths.append(file_path)

            # Close the new tab and switch back to the original tab
            driver.close()
            driver.switch_to.window(driver.window_handles[0])

            # Brief delay to allow the page to stabilize before the next interaction
            time.sleep(2)

        logging.info(f"Successfully downloaded invoices for booking {booking_number}")
        return True, downloaded_file_paths
    
    except Exception as e:
        logging.info(f"Error downloading invoice for booking number {booking_number}: {str(e)}")
        return False, downloaded_file_paths
    
    



def zip_invoices(invoice_paths, download_dir):
    zip_path = os.path.join(download_dir, 'invoices.zip')
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file_path in invoice_paths:
            zipf.write(file_path, os.path.basename(file_path))
    return zip_path



def scrape_airbnb_invoices(booking_numbers, manual_mfa=False):
    download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'invoice_downloads')
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    total_bookings = len(booking_numbers)
    failed_downloads = []

    # Visible browser for MFA login (or using persisted cookies)
    driver_visible = initialize_driver(download_dir, headless=False)
    driver_headless = None
    cookie_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'session_cookies.json')

    try:
        # Try to reuse existing session cookies first
        session_loaded = load_session_cookies(driver_visible, cookie_file_path)
        if not session_loaded:
            # Fall back to manual MFA login
            login_to_airbnb(driver_visible, manual_mfa=True)
            # Save fresh cookies after successful login
            save_session_cookies(driver_visible, cookie_file_path)

        # Transfer cookies to headless browser to ensure printToPDF produces full content
        cookies = driver_visible.get_cookies()
        driver_headless = initialize_driver(download_dir, headless=True)
        driver_headless.get("https://www.airbnb.com/")
        for cookie in cookies:
            sanitized = {
                'name': cookie.get('name'),
                'value': cookie.get('value'),
                'domain': cookie.get('domain'),
                'path': cookie.get('path', '/'),
                'secure': cookie.get('secure', False),
            }
            if 'expiry' in cookie:
                sanitized['expiry'] = cookie['expiry']
            try:
                driver_headless.add_cookie(sanitized)
            except Exception as e:
                logging.info(f"Cookie add failed for {sanitized.get('name')}: {e}")

        driver_headless.get("https://www.airbnb.com/hosting/reservations/all")

        all_downloaded_files = []

        for index, booking_number in enumerate(booking_numbers, start=1):
            logging.info(f"Downloading invoices for booking {booking_number} ({index} of {total_bookings})")

            success, file_paths = download_invoice(driver_headless, booking_number, download_dir)

            retry_count = 0
            while not success and retry_count < 5:
                logging.info(f"Retrying download for booking {booking_number} (Attempt {retry_count + 1})")
                success, file_paths = download_invoice(driver_headless, booking_number, download_dir)
                retry_count += 1

            if not success:
                logging.info(f"Failed to download invoices for booking {booking_number} after 5 attempts")
                failed_downloads.append(booking_number)
            else:
                all_downloaded_files.extend(file_paths)

            time.sleep(2)

    except Exception as e:
        logging.info(f"Error during invoice scraping: {e}")
        failed_downloads.extend(booking_numbers[index:])
    finally:
        try:
            if driver_headless is not None:
                driver_headless.quit()
        finally:
            driver_visible.quit()

    # zip the downloaded invoices here using zip_invoices function
    zip_path = zip_invoices(all_downloaded_files, download_dir)
    logging.info(f"zip path: {zip_path}")

    # Final report
    if failed_downloads:
        logging.info("Failed to download invoices for the following bookings:")
        for booking in failed_downloads:
            logging.info(booking)
    else:
        logging.info("All invoices downloaded successfully.")

    
    return all_downloaded_files, download_dir, failed_downloads, zip_path



@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        booking_numbers = request.form.get('booking_numbers').split(',')

        # Filter out empty strings from booking_numbers
        booking_numbers = [number.strip() for number in booking_numbers if number.strip()]

        # Capture the returned values from scrape_airbnb_invoices function
        all_downloaded_files, download_dir, failed_downloads, zip_path = scrape_airbnb_invoices(booking_numbers, manual_mfa=True)

        # Trigger cleanup with a delay
        cleanup_delay = 30  # seconds, adjust as needed
        Timer(cleanup_delay, cleanup_files, args=[all_downloaded_files, download_dir]).start()
        # Create a summary report
        report = {
            'total_bookings': len(booking_numbers),
            'successful_downloads': len(all_downloaded_files),
            'failed_downloads': len(failed_downloads),
            'failed_booking_numbers': failed_downloads
        }

        logging.info(f"Original zip path: {zip_path}")
        # Store the file path and report in the session
        zip_path = os.path.basename(zip_path)
        logging.info(f"filename: {zip_path}")
        session['zip_path'] = zip_path
        session['report'] = report

        return redirect(url_for('complete'))

    return render_template('index.html')

@app.route('/download_zip/<filename>')
def download_zip(filename):
    full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'invoice_downloads', filename)
    if not os.path.isfile(full_path):
        abort(404)
    return send_file(full_path, as_attachment=True)



@app.route('/complete', methods=['GET'])
def complete():
    if 'report' in session:
        report = session['report']
        return render_template('complete.html', report=report, zip_path=session.get('zip_path'))
    else:
        return redirect(url_for('index'))




@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404
