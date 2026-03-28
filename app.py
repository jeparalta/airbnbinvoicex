from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, send_file, session, redirect, url_for, abort, jsonify

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
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
import signal
import atexit
import sys

def get_user_data_dir():
    """Return ~/Documents/AirbnbInvoiceX, creating it if needed."""
    path = os.path.join(os.path.expanduser("~"), "Documents", "AirbnbInvoiceX")
    os.makedirs(path, exist_ok=True)
    return path

def check_chrome_installed():
    """Return path to Chrome binary, or None if not found."""
    return shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser") or \
        next((p for p in [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ] if os.path.isfile(p)), None)

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

# Track active resources for cleanup
ACTIVE_THREADS = []
ACTIVE_DRIVERS = []
ACTIVE_TIMERS = []
SHUTDOWN_REQUESTED = False
CLEANUP_LOCK = Lock()



def cleanup_all_resources():
    """Clean up all active resources (drivers, threads, timers)"""
    global SHUTDOWN_REQUESTED
    SHUTDOWN_REQUESTED = True
    
    logging.info("Starting graceful shutdown...")
    
    with CLEANUP_LOCK:
        # Cancel all active timers
        for timer in ACTIVE_TIMERS:
            try:
                timer.cancel()
            except Exception as e:
                logging.warning(f"Error canceling timer: {e}")
        ACTIVE_TIMERS.clear()
        
        # Close all active WebDriver instances
        for driver in ACTIVE_DRIVERS:
            try:
                if driver is not None:
                    driver.quit()
            except Exception as e:
                logging.warning(f"Error closing driver: {e}")
        ACTIVE_DRIVERS.clear()
        
        # Wait for threads to finish (with timeout)
        for thread in ACTIVE_THREADS:
            if thread.is_alive():
                try:
                    thread.join(timeout=5.0)  # Wait up to 5 seconds per thread
                    if thread.is_alive():
                        logging.warning(f"Thread {thread.name} did not finish in time")
                except Exception as e:
                    logging.warning(f"Error joining thread: {e}")
        ACTIVE_THREADS.clear()
    
    logging.info("Graceful shutdown completed.")


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logging.info(f"Received signal {signum}, initiating shutdown...")
    cleanup_all_resources()
    sys.exit(0)


def register_shutdown_handlers():
    """Register signal handlers and atexit handlers for graceful shutdown"""
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    atexit.register(cleanup_all_resources)


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

    # Use chromium if chrome is not available (for arm64 builds)
    chrome_binary = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
    if chrome_binary:
        chrome_options.binary_location = chrome_binary
    
    driver = webdriver.Chrome(options=chrome_options)
    
    # Track the driver for cleanup
    with CLEANUP_LOCK:
        ACTIVE_DRIVERS.append(driver)
    
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



def login_to_airbnb(driver):
    try:
        logging.info("Logging into Airbnb...")

        driver.get("https://www.airbnb.com/login")

        # Wait until we're no longer on the login page (up to 5 minutes).
        WebDriverWait(driver, 300).until(lambda d: 'login' not in d.current_url)
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

def find_reservation_row(driver, booking_number):
    """Navigate directly to the filtered reservations list and return the row element or None."""
    try:
        url = f"https://www.airbnb.com/hosting/reservations/all?confirmationCode={booking_number}"
        driver.get(url)
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        # Since we filtered by confirmationCode, just grab the first row with a "More options" button
        # No need to match booking number text — the URL filter already did that
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH,
                "//tr[.//button[@aria-label='Więcej opcji' or @aria-label='More options']]"
            ))
        )
        rows = driver.find_elements(By.XPATH,
            "//tr[.//button[@aria-label='Więcej opcji' or @aria-label='More options']]"
        )
        if rows:
            logging.info(f"Found reservation {booking_number}")
            return rows[0]
        logging.warning(f"Booking {booking_number} not found in filtered view")
        return None
    except Exception as e:
        logging.warning(f"Error finding reservation {booking_number}: {e}")
        return None


def open_more_options_menu(driver, row):
    """Click the 'More options' button via JS (bypasses overlays). Returns True if menu opened."""
    try:
        more_btn = row.find_element(
            By.XPATH, ".//button[@aria-label='Więcej opcji' or @aria-label='More options']"
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", more_btn)
        # JS click bypasses element-not-interactable and click-intercepted errors
        driver.execute_script("arguments[0].click();", more_btn)
        # Wait for the popup menu to appear (any menu link is fine)
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH,
                "//a[contains(@href, '/invoice/')] | "
                "//a[contains(@href, 'message')] | "
                "//a[contains(@href, 'reservation')]"
            ))
        )
        return True
    except Exception as e:
        logging.warning(f"Could not open more options menu: {e}")
        return False


def close_popup(driver):
    """Close any open popup by pressing Escape."""
    try:
        ActionChains(driver).send_keys('\ue00c').perform()  # Escape key
        time.sleep(0.1)
    except Exception:
        pass


def download_invoice(driver, booking_number, download_dir):
    downloaded_file_paths = []
    logging.info(f"Starting download for booking number {booking_number}")

    try:
        # Step 1: Find the reservation row (with pagination)
        row = find_reservation_row(driver, booking_number)
        if not row:
            logging.warning(f"Reservation {booking_number} not found in the list")
            return False, downloaded_file_paths

        # Step 2: Click "More options" (three dots) on that row
        if not open_more_options_menu(driver, row):
            return False, downloaded_file_paths

        # Step 3: Extract invoice links from the popup
        invoice_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/invoice/')]")
        if not invoice_links:
            logging.warning(f"No invoice links found for booking number {booking_number}")
            close_popup(driver)
            return True, downloaded_file_paths

        # Collect hrefs before closing popup (elements go stale after navigation)
        invoice_hrefs = []
        for link in invoice_links:
            href = link.get_attribute('href')
            if href:
                invoice_hrefs.append(href)
        logging.info(f"Found {len(invoice_hrefs)} invoice link(s) for {booking_number}")

        # Close the popup before navigating
        close_popup(driver)

        # Step 4: Open each invoice link and print to PDF
        for link_index, href in enumerate(invoice_hrefs):
            try:
                # Open invoice in new tab
                driver.execute_script("window.open(arguments[0], '_blank');", href)
                WebDriverWait(driver, 5).until(lambda d: len(d.window_handles) > 1)
                driver.switch_to.window(driver.window_handles[-1])

                # Wait for page load
                WebDriverWait(driver, 10).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )

                # Wait for content to be rendered
                WebDriverWait(driver, 10).until(
                    lambda d: len(d.find_element(By.TAG_NAME, "body").text) > 100 if d.find_elements(By.TAG_NAME, "body") else False
                )

                # Print to PDF
                print_options = {
                    "printBackground": False,
                    "pageRanges": "1",
                    "paperWidth": 8.27,
                    "paperHeight": 11.69,
                    "marginTop": 0,
                    "marginBottom": 0,
                    "marginLeft": 0,
                    "marginRight": 0,
                    "preferCSSPageSize": False,
                    "displayHeaderFooter": False,
                    "scale": 0.8
                }
                pdf = driver.execute_cdp_cmd("Page.printToPDF", print_options)
                pdf_content = base64.b64decode(pdf['data'])

                file_path = os.path.join(download_dir, f"invoice_{booking_number}_{link_index+1}.pdf")
                with open(file_path, 'wb') as file:
                    file.write(pdf_content)
                downloaded_file_paths.append(file_path)
                logging.info(f"Saved invoice PDF: {file_path}")

                # Close tab and switch back
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                time.sleep(0.2)

            except Exception as link_error:
                logging.error(f"Error processing invoice link {link_index + 1}: {link_error}")
                try:
                    while len(driver.window_handles) > 1:
                        driver.switch_to.window(driver.window_handles[-1])
                        driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                except Exception:
                    pass
                continue

        logging.info(f"Successfully downloaded {len(downloaded_file_paths)} invoice(s) for booking {booking_number}")
        return True, downloaded_file_paths

    except Exception as e:
        timestamp = int(time.time())
        screenshot_path = None
        html_path = None

        try:
            screenshot_path = os.path.join(download_dir, f"error_{booking_number}_{timestamp}.png")
            driver.save_screenshot(screenshot_path)
            logging.info(f"Saved error screenshot: {screenshot_path}")
        except Exception as screenshot_error:
            screenshot_path = "<screenshot failed>"
            logging.warning(f"Could not save screenshot: {screenshot_error}")

        try:
            html_path = os.path.join(download_dir, f"error_{booking_number}_{timestamp}.html")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            logging.info(f"Saved error HTML: {html_path}")
        except Exception as html_error:
            html_path = "<html save failed>"
            logging.warning(f"Could not save HTML: {html_error}")

        current_url = getattr(driver, 'current_url', 'n/a')
        page_title = getattr(driver, 'title', 'n/a')

        logging.exception(
            f"Error downloading invoice for booking number {booking_number}: {repr(e)} | "
            f"url={current_url} | title={page_title} | "
            f"screenshot={screenshot_path} | html={html_path}"
        )
        return False, downloaded_file_paths
    
    



def zip_invoices(invoice_paths, download_dir):
    zip_path = os.path.join(download_dir, 'invoices.zip')
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file_path in invoice_paths:
            zipf.write(file_path, os.path.basename(file_path))
    return zip_path



def scrape_airbnb_invoices(booking_numbers, manual_mfa=False, client_id=None):
    download_dir = os.path.join(get_user_data_dir(), 'invoice_downloads')
    os.makedirs(download_dir, exist_ok=True)

    total_bookings = len(booking_numbers)
    failed_downloads = []
    all_downloaded_files = []
    zip_path = None

    driver_visible = None
    driver_headless = None
    cookie_file_path = os.path.join(get_user_data_dir(), 'session_cookies.json')

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
            try:
                with CLEANUP_LOCK:
                    if driver_headless in ACTIVE_DRIVERS:
                        ACTIVE_DRIVERS.remove(driver_headless)
                driver_headless.quit()
            except Exception as e:
                logging.warning(f"Error closing headless driver during MFA: {e}")
            driver_headless = None
            
            # Update progress to show MFA needed
            if client_id:
                with PROGRESS_LOCK:
                    if client_id in PROGRESS:
                        PROGRESS[client_id]['status'] = 'mfa_needed'
                        PROGRESS[client_id]['stage'] = 'mfa'
                        PROGRESS[client_id]['stage_progress'] = 15
            
            driver_visible = initialize_driver(download_dir, headless=False)
            login_to_airbnb(driver_visible)
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
            try:
                with CLEANUP_LOCK:
                    if driver_visible in ACTIVE_DRIVERS:
                        ACTIVE_DRIVERS.remove(driver_visible)
                driver_visible.quit()
            except Exception as e:
                logging.warning(f"Error closing visible driver after MFA: {e}")
            driver_visible = None

        # Update progress to show we're ready to download
        if client_id:
            with PROGRESS_LOCK:
                if client_id in PROGRESS:
                    PROGRESS[client_id]['status'] = 'downloading'
                    PROGRESS[client_id]['stage'] = 'downloading'
                    PROGRESS[client_id]['stage_progress'] = 20

        all_downloaded_files = []

        for index, booking_number in enumerate(booking_numbers, start=1):
            # Check for shutdown request
            if SHUTDOWN_REQUESTED:
                logging.info(f"Shutdown requested, stopping at booking {index} of {total_bookings}")
                break
            
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

            time.sleep(1)  # Delay between bookings (respectful to Airbnb)

            # Update progress after processing each booking
            if client_id:
                with PROGRESS_LOCK:
                    PROGRESS[client_id]['current'] = index
                    # Calculate overall progress: 20% base + 70% for downloads + 10% for finalizing
                    download_progress = (index / total_bookings) * 70 if total_bookings > 0 else 0
                    PROGRESS[client_id]['stage_progress'] = 20 + download_progress

    except Exception as e:
        logging.exception(f"Error during invoice scraping: {e}")
        # If index is not defined (error before loop), mark all as failed
        if 'index' in locals():
            failed_downloads.extend(booking_numbers[index:])
        else:
            failed_downloads.extend(booking_numbers)
    finally:
        try:
            if driver_headless is not None:
                with CLEANUP_LOCK:
                    if driver_headless in ACTIVE_DRIVERS:
                        ACTIVE_DRIVERS.remove(driver_headless)
                driver_headless.quit()
        except Exception as e:
            logging.warning(f"Error closing headless driver: {e}")
        finally:
            if driver_visible is not None:
                try:
                    with CLEANUP_LOCK:
                        if driver_visible in ACTIVE_DRIVERS:
                            ACTIVE_DRIVERS.remove(driver_visible)
                    driver_visible.quit()
                except Exception as e:
                    logging.warning(f"Error closing visible driver: {e}")

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
        # Check for shutdown request
        if SHUTDOWN_REQUESTED:
            logging.info("Shutdown requested, skipping background scrape")
            return
        # Capture the returned values from scrape_airbnb_invoices function
        all_downloaded_files, download_dir, failed_downloads, zip_path = scrape_airbnb_invoices(booking_numbers, manual_mfa=True, client_id=client_id)

        # Trigger cleanup with a delay
        cleanup_delay = 30  # seconds, adjust as needed
        
        # Use a list to hold timer reference for closure
        timer_ref = [None]
        
        def cleanup_with_removal():
            try:
                cleanup_files(all_downloaded_files, download_dir)
            finally:
                # Remove timer from active list when done
                with CLEANUP_LOCK:
                    if timer_ref[0] and timer_ref[0] in ACTIVE_TIMERS:
                        ACTIVE_TIMERS.remove(timer_ref[0])
        
        timer = Timer(cleanup_delay, cleanup_with_removal)
        timer_ref[0] = timer
        with CLEANUP_LOCK:
            ACTIVE_TIMERS.append(timer)
        timer.start()
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
        with CLEANUP_LOCK:
            ACTIVE_THREADS.append(thread)
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
    safe_base = os.path.join(get_user_data_dir(), 'invoice_downloads')
    full_path = os.path.realpath(os.path.join(safe_base, filename))
    if not full_path.startswith(safe_base + os.sep):
        abort(400)
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




@app.route('/quit', methods=['POST'])
def quit_app():
    def shutdown():
        time.sleep(0.5)
        cleanup_all_resources()
        os.kill(os.getpid(), signal.SIGTERM)
    Thread(target=shutdown, daemon=True).start()
    return ('', 204)


@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


if not check_chrome_installed():
    print("\n" + "="*60)
    print("ERROR: Google Chrome not found.")
    print("Please install Chrome from https://www.google.com/chrome/")
    print("="*60 + "\n")
    sys.exit(1)

# Register shutdown handlers when the module is imported
register_shutdown_handlers()
