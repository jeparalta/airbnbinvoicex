from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, send_file, session, redirect, url_for, abort, jsonify

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC



from threading import Timer, Lock, Thread
import uuid
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

# Simple in-memory progress store keyed by client_id
PROGRESS = {}
PROGRESS_LOCK = Lock()



def initialize_driver(download_dir, headless=True):
    # Set the Selenium logger to only display critical errors
    selenium_logger.setLevel(logging.CRITICAL)

    chrome_options = Options()
    # Enable headless mode if requested
    if headless:
        chrome_options.add_argument("--headless")

    # Performance optimizations that are safe and won't trigger rate limiting
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-images")  # Block images for faster loading
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--memory-pressure-off")
    chrome_options.add_argument("--log-level=3")  # Reduce logging
    chrome_options.add_argument("--silent")

    prefs = {
        "download.default_directory": download_dir,
        "profile.default_content_setting_values": {
            "images": 2,  # Block images
            "plugins": 2,  # Block plugins
            "popups": 2,  # Block popups
            "geolocation": 2,  # Block geolocation
            "notifications": 2,  # Block notifications
            "media_stream": 2,  # Block media stream
        },
        "profile.managed_default_content_settings": {
            "images": 2
        }
    }
    chrome_options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=chrome_options)
    
    # Set timeouts for faster failure detection
    driver.set_page_load_timeout(30)
    driver.implicitly_wait(3)  # Reduced from default 10s
    
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
        logging.exception(f"Error during login: {repr(e)} | url={getattr(driver, 'current_url', 'n/a')}")
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
    logging.info(f"Starting download for booking number {booking_number}")

    try:
        booking_url = f"https://www.airbnb.com/hosting/reservations/all?confirmationCode={booking_number}"
        driver.get(booking_url)

        # Reduced wait time for page load (still safe, just faster)
        WebDriverWait(driver, 20).until(lambda d: d.execute_script('return document.readyState') == 'complete')

        # Reduced wait time for invoice links
        WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@href, '/vat_invoices/')]"))
        )

        # Optimized lazy loading trigger - faster scrolling
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.5)  # Reduced from 1 second
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)  # Reduced from 1 second
        except Exception:
            pass

        # Re-evaluate links after potential lazy load
        download_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/vat_invoices/')]")
        logging.info(f"Found {len(download_links)} invoice link(s) for booking {booking_number}")

        if not download_links:
            logging.info(f"No invoice links found for booking number {booking_number}")
            return True, downloaded_file_paths

        for link_index in range(len(download_links)):
            link_xpath = f"(//a[contains(@href, '/vat_invoices/')])[{link_index+1}]"
            WebDriverWait(driver, 20).until(  # Reduced from 40 seconds
                EC.element_to_be_clickable((By.XPATH, link_xpath))
            )
            link_el = driver.find_element(By.XPATH, link_xpath)
            
            # Optimized scrolling and clicking
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", link_el)
                time.sleep(0.2)  # Minimal delay for scroll
            except Exception:
                pass
            
            try:
                driver.execute_script("arguments[0].click();", link_el)
            except Exception:
                link_el.click()

            # Reduced wait for new tab
            WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) > 1)  # Reduced from 20
            driver.switch_to.window(driver.window_handles[-1])

            # Reduced wait for page load
            WebDriverWait(driver, 10).until(lambda d: d.execute_script('return document.readyState') == 'complete')  # Reduced from 20

            # Optimized print options for faster PDF generation
            print_options = {
                "printBackground": False,  # Disabled for faster rendering
                "pageRanges": "1",
                "paperWidth": 8.27,
                "paperHeight": 11.69,
                "marginTop": 0,
                "marginBottom": 0,
                "marginLeft": 0,
                "marginRight": 0,
                "preferCSSPageSize": False,  # Disabled for faster processing
                "displayHeaderFooter": False,  # Disabled for faster processing
                "scale": 0.8  # Smaller scale for faster processing
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

            # Reduced delay between downloads (still respectful to Airbnb)
            time.sleep(1)  # Reduced from 2 seconds
            # Reduced wait for window handles
            WebDriverWait(driver, 5).until(lambda d: len(d.window_handles) >= 1)  # Reduced from 20

        logging.info(f"Successfully downloaded invoices for booking {booking_number}")
        return True, downloaded_file_paths
    
    except Exception as e:
        # Capture more context and a screenshot to aid debugging
        try:
            timestamp = int(time.time())
            screenshot_path = os.path.join(download_dir, f"error_{booking_number}_{timestamp}.png")
            driver.save_screenshot(screenshot_path)
        except Exception:
            screenshot_path = "<screenshot failed>"
        logging.exception(
            f"Error downloading invoice for booking number {booking_number}: {repr(e)} | "
            f"url={getattr(driver, 'current_url', 'n/a')} | title={getattr(driver, 'title', 'n/a')} | "
            f"screenshot={screenshot_path}"
        )
        return False, downloaded_file_paths
    
    



def zip_invoices(invoice_paths, download_dir):
    zip_path = os.path.join(download_dir, 'invoices.zip')
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file_path in invoice_paths:
            zipf.write(file_path, os.path.basename(file_path))
    return zip_path



def scrape_airbnb_invoices(booking_numbers, manual_mfa=False, client_id=None):
    download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'invoice_downloads')
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    total_bookings = len(booking_numbers)
    failed_downloads = []

    driver_visible = None
    driver_headless = None
    cookie_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'session_cookies.json')

    try:
        # Initialize progress with stages
        if client_id:
            with PROGRESS_LOCK:
                PROGRESS[client_id] = { 
                    'total': total_bookings, 
                    'current': 0, 
                    'done': False, 
                    'status': 'started',
                    'stage': 'session_check',
                    'stage_progress': 5,
                    'total_stages': 4  # session_check, mfa (if needed), downloading, finalizing
                }
        
        # Try to use existing cookies with headless browser first
        driver_headless = initialize_driver(download_dir, headless=True)
        session_loaded = load_session_cookies(driver_headless, cookie_file_path)
        
        if not session_loaded:
            # Need MFA - close headless and open visible browser
            driver_headless.quit()
            driver_headless = None
            
            # Update progress to show MFA needed
            if client_id:
                with PROGRESS_LOCK:
                    if client_id in PROGRESS:
                        PROGRESS[client_id]['status'] = 'mfa_needed'
                        PROGRESS[client_id]['stage'] = 'mfa'
                        PROGRESS[client_id]['stage_progress'] = 15
            
            driver_visible = initialize_driver(download_dir, headless=False)
            login_to_airbnb(driver_visible, manual_mfa=True)
            save_session_cookies(driver_visible, cookie_file_path)
            
            # Transfer cookies to new headless browser
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
            
            # Close visible browser now that headless session is authenticated
            driver_visible.quit()
            driver_visible = None

        # Update progress to show we're ready to download
        if client_id:
            with PROGRESS_LOCK:
                if client_id in PROGRESS:
                    PROGRESS[client_id]['status'] = 'downloading'
                    PROGRESS[client_id]['stage'] = 'downloading'
                    PROGRESS[client_id]['stage_progress'] = 20

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

            time.sleep(1)  # Reduced delay between bookings (still respectful to Airbnb)

            # Update progress after processing each booking
            if client_id:
                with PROGRESS_LOCK:
                    PROGRESS[client_id]['current'] = index
                    # Calculate overall progress: 20% base + 70% for downloads + 10% for finalizing
                    download_progress = (index / total_bookings) * 70 if total_bookings > 0 else 0
                    PROGRESS[client_id]['stage_progress'] = 20 + download_progress

    except Exception as e:
        logging.info(f"Error during invoice scraping: {e}")
        failed_downloads.extend(booking_numbers[index:])
    finally:
        try:
            if driver_headless is not None:
                driver_headless.quit()
        finally:
            if driver_visible is not None:
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

    
    # Mark done in progress store
    if client_id:
        with PROGRESS_LOCK:
            if client_id in PROGRESS:
                PROGRESS[client_id]['done'] = True
                PROGRESS[client_id]['stage'] = 'finalizing'
                PROGRESS[client_id]['stage_progress'] = 90
    return all_downloaded_files, download_dir, failed_downloads, zip_path



def background_scrape(client_id, booking_numbers):
    """Run scraping in background thread"""
    try:
        # Capture the returned values from scrape_airbnb_invoices function
        all_downloaded_files, download_dir, failed_downloads, zip_path = scrape_airbnb_invoices(booking_numbers, manual_mfa=True, client_id=client_id)

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
        
        # Store results in progress data for completion check
        with PROGRESS_LOCK:
            if client_id in PROGRESS:
                PROGRESS[client_id]['zip_path'] = zip_path
                PROGRESS[client_id]['report'] = report
                PROGRESS[client_id]['done'] = True
                PROGRESS[client_id]['stage_progress'] = 100
                
    except Exception as e:
        logging.exception(f"Background scrape error: {e}")
        with PROGRESS_LOCK:
            if client_id in PROGRESS:
                PROGRESS[client_id]['error'] = str(e)
                PROGRESS[client_id]['done'] = True

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        booking_numbers = request.form.get('booking_numbers').split(',')

        # Filter out empty strings from booking_numbers
        booking_numbers = [number.strip() for number in booking_numbers if number.strip()]

        # Ensure we have a client_id to track progress
        if 'client_id' not in session:
            session['client_id'] = str(uuid.uuid4())
        client_id = session['client_id']

        # Start background scraping
        thread = Thread(target=background_scrape, args=(client_id, booking_numbers))
        thread.daemon = True
        thread.start()

        return render_template('progress.html', client_id=client_id)

    return render_template('index.html')

@app.route('/progress', methods=['GET'])
def progress():
    client_id = session.get('client_id')
    if not client_id:
        return jsonify({ 'total': 0, 'current': 0, 'done': False, 'status': 'no_session' })
    with PROGRESS_LOCK:
        data = PROGRESS.get(client_id, { 'total': 0, 'current': 0, 'done': False, 'status': 'not_started' })
    return jsonify(data)

@app.route('/complete_check', methods=['GET'])
def complete_check():
    client_id = session.get('client_id')
    if not client_id:
        return jsonify({ 'done': False })
    with PROGRESS_LOCK:
        data = PROGRESS.get(client_id, { 'done': False })
    if data.get('done') and 'zip_path' in data:
        # Store in session for the complete page
        session['zip_path'] = data['zip_path']
        session['report'] = data['report']
        return jsonify({ 'done': True, 'redirect': url_for('complete') })
    return jsonify({ 'done': data.get('done', False) })

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
