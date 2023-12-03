from flask import Flask, render_template, request, send_file
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from threading import Timer
import time
import zipfile
import os
import requests 
import shutil
import base64


app = Flask(__name__)


def initialize_driver(download_dir):
    chrome_options = Options()
    prefs = {"download.default_directory": download_dir}
    chrome_options.add_experimental_option("prefs", prefs)
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def cleanup_files(file_paths):
    for file_path in file_paths:
        if os.path.exists(file_path):
            os.remove(file_path)
    # Optionally, remove the directory if it's empty
    for dir_path in set(os.path.dirname(path) for path in file_paths):
        if os.path.exists(dir_path) and not os.listdir(dir_path):
            shutil.rmtree(dir_path)

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def login_to_airbnb(driver, username, password):
    try:
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
        print(f"Error during login: {e}")
        # Handle the error or rethrow to be caught by calling function



import base64
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

def download_invoice(driver, booking_number, download_dir):
    try:
        booking_url = f"https://www.airbnb.com/hosting/reservations/all?confirmationCode={booking_number}"
        driver.get(booking_url)

        # Wait for the download link in the modal to be clickable
        download_link = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/vat_invoices/')]"))
        )
        download_link.click()

        # Since the link opens in a new tab, switch to the new tab
        driver.switch_to.window(driver.window_handles[1])

        # Define the parameters for the print to PDF command
        print_options = {
            "printBackground": True,
            "pageRanges": "1",
            "paperWidth": 8.27,  # A4 size in inches
            "paperHeight": 11.69 # A4 size in inches
        }

        # Execute the print command
        pdf = driver.execute_cdp_cmd("Page.printToPDF", print_options)

        # Decode the result
        pdf_content = base64.b64decode(pdf['data'])

        # Save the PDF to a file
        file_path = os.path.join(download_dir, f"invoice_{booking_number}.pdf")
        with open(file_path, 'wb') as file:
            file.write(pdf_content)

        # Close the new tab and switch back to the original tab
        driver.close()
        driver.switch_to.window(driver.window_handles[0])

        return file_path
    except Exception as e:
        print(f"Error downloading invoice for booking number {booking_number}: {e}")
        # Handle the error or return None/raise an error



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

    try:
        driver = initialize_driver(download_dir)
        login_to_airbnb(driver, username, password)
        downloaded_files = []
        for number in booking_numbers:
            file_path = download_invoice(driver, number, download_dir)
            if file_path:
                downloaded_files.append(file_path)
            time.sleep(2)
        driver.quit()
        zip_path = zip_invoices(downloaded_files, download_dir)
        return zip_path
    except Exception as e:
        print(f"Error during invoice scraping: {e}")
        # Cleanup and handle the error
        driver.quit()


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        booking_numbers = request.form.get('booking_numbers').split(',')

        zip_path = scrape_airbnb_invoices(username, password, booking_numbers)

        # Schedule cleanup to occur after a delay
        cleanup_delay = 30  # seconds, adjust as needed
        Timer(cleanup_delay, cleanup_files, args=[[zip_path]]).start()

        return send_file(zip_path, as_attachment=True)

    return render_template('index.html')


