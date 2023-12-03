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

## Installation
1. **Clone the repository:**
   ```bash
   git clone [repository-url]
   cd [repository-name]

## Set up a Virtual Environment (Optional but Recommended)
```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`