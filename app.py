from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, send_file, session, redirect, url_for

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

import logging
from selenium.webdriver.remote.remote_connection import LOGGER as selenium_logger

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


app = Flask(__name__)
# Get the secret key from environment variables
SECRET_KEY = os.environ.get('SECRET_KEY')

# Set the Flask app's secret key
app.secret_key = SECRET_KEY



def initialize_driver(download_dir):
    # Set the Selenium logger to only display critical errors
    selenium_logger.setLevel(logging.CRITICAL)

    chrome_options = Options()
    # Enable headless mode
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



def login_to_airbnb(driver, username, password):
    try:
        logging.info("Logging into Airbnb...")
        logging.info(f"secret key: {SECRET_KEY}")

        driver.get("https://www.airbnb.com/login")

        # Click the "Continue with email" button
        continue_with_email_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Continue with email']"))
        )
        continue_with_email_button.click()

        # Wait for the email input field to be present
        email_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "user[email]"))
        )
        email_field.send_keys(username)

        # Click the "Continue" button after entering email
        continue_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@data-testid='signup-login-submit-btn']"))
        )
        continue_button.click()

        # Wait for the password input field to be present
        password_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "user[password]"))
        )
        password_field.send_keys(password)

        # Click the "Log in" button after entering password
        login_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@data-testid='signup-login-submit-btn']"))
        )
        login_button.click()

        
        time.sleep(5)  # Wait for the login process to complete
    except Exception as e:
       logging.info(f"Error during login: {e}")
        # Handle the error or rethrow to be caught by calling function




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

            # Define the parameters for the print to PDF command
            print_options = {
                "printBackground": True,
                "pageRanges": "1",
                "paperWidth": 8.27,   # A4 size in inches
                "paperHeight": 11.69, # A4 size in inches
                "marginTop": 0,       # Setting the top margin to 0
                "marginBottom": 0,    # Setting the bottom margin to 0
                "marginLeft": 0,      # Setting the left margin to 0
                "marginRight": 0      # Setting the right margin to 0
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



def scrape_airbnb_invoices(username, password, booking_numbers):
    download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'invoice_downloads')
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    total_bookings = len(booking_numbers)
    failed_downloads = []
    driver = initialize_driver(download_dir)

    try:
        login_to_airbnb(driver, username, password)

        all_downloaded_files = []  # Store all successfully downloaded invoice file paths

        for index, booking_number in enumerate(booking_numbers, start=1):
            logging.info(f"Downloading invoices for booking {booking_number} ({index} of {total_bookings})")

            success, file_paths = download_invoice(driver, booking_number, download_dir)

            retry_count = 0
            while not success and retry_count < 5:
                logging.info(f"Retrying download for booking {booking_number} (Attempt {retry_count + 1})")
                success, file_paths = download_invoice(driver, booking_number, download_dir)
                retry_count += 1

            if not success:
                logging.info(f"Failed to download invoices for booking {booking_number} after 5 attempts")
                failed_downloads.append(booking_number)
            else:
                all_downloaded_files.extend(file_paths)  # Add successful downloads to the list

            time.sleep(2)  # Brief delay between bookings

    except Exception as e:
        logging.info(f"Error during invoice scraping: {e}")
        failed_downloads.extend(booking_numbers[index:])  # Add remaining bookings to failed list
    finally:
        driver.quit()

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
        username = request.form['username']
        password = request.form['password']
        booking_numbers = request.form.get('booking_numbers').split(',')

        # Filter out empty strings from booking_numbers
        booking_numbers = [number.strip() for number in booking_numbers if number.strip()]

        # Capture the returned values from scrape_airbnb_invoices function
        all_downloaded_files, download_dir, failed_downloads, zip_path = scrape_airbnb_invoices(username, password, booking_numbers)

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
    full_path = os.path.join('/Users/joseparalta/Projects/JepProjects/airbnbinvoicex/invoice_downloads', filename)
    return send_file(full_path, as_attachment=True)



@app.route('/complete', methods=['GET'])
def complete():
    if 'report' in session:
        report = session['report']
        return render_template('complete.html', report=report, zip_path=session.get('zip_path'))
    else:
        return redirect(url_for('index'))



