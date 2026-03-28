import threading
import time
import webbrowser
import sys
import os

# Ensure user data dir exists before app starts
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def open_browser():
    time.sleep(2)  # Wait for Flask to start
    webbrowser.open("http://127.0.0.1:5001")

if __name__ == '__main__':
    print("\n" + "="*60)
    print("  AirbnbInvoiceX")
    print("  Opening browser at http://127.0.0.1:5001 ...")
    print("  Keep this window open while using the app.")
    print("  Close this window to quit.")
    print("="*60 + "\n")

    threading.Thread(target=open_browser, daemon=True).start()

    # Import and run the Flask app
    import app as flask_app
    flask_app.app.run(host='127.0.0.1', port=5001)
