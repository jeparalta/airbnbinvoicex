# PyInstaller Packaging Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Package the Flask+Selenium app as a standalone double-click executable for Mac and Windows, distributed via GitHub Releases.

**Architecture:** PyInstaller bundles Python + all dependencies into a single directory bundle. A launcher script starts the Flask server and opens the browser. GitHub Actions builds on both platforms on every git tag and uploads artifacts to a GitHub Release.

**Tech Stack:** PyInstaller, Flask, Selenium, GitHub Actions (macos-latest + windows-latest runners)

---

### Task 1: Fix file paths for read-only bundle environment

PyInstaller bundles run from a temp directory that is read-only. All writable files must go to a user-owned location.

**Files:**
- Modify: `app.py`

**Step 1: Replace hardcoded paths with user data dir helper**

Find these two lines in `app.py` (inside `scrape_airbnb_invoices`):
```python
download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'invoice_downloads')
cookie_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'session_cookies.json')
```

Add a helper function near the top of `app.py` (after imports):
```python
def get_user_data_dir():
    """Return ~/Documents/AirbnbInvoiceX, creating it if needed."""
    path = os.path.join(os.path.expanduser("~"), "Documents", "AirbnbInvoiceX")
    os.makedirs(path, exist_ok=True)
    return path
```

Replace the two lines with:
```python
download_dir = os.path.join(get_user_data_dir(), 'invoice_downloads')
cookie_file_path = os.path.join(get_user_data_dir(), 'session_cookies.json')
```

**Step 2: Also fix the download_zip route**

In `download_zip` route, the `safe_base` must match:
```python
safe_base = os.path.join(get_user_data_dir(), 'invoice_downloads')
```

**Step 3: Verify app still works normally**

Run `./run.sh`, submit a booking. Check that files appear in `~/Documents/AirbnbInvoiceX/`.

**Step 4: Commit**
```bash
git add app.py
git commit -m "feat: move writable files to ~/Documents/AirbnbInvoiceX for bundle compatibility"
```

---

### Task 2: Chrome detection at startup

Show a clear error to non-tech users if Chrome is not found, instead of a cryptic Selenium crash.

**Files:**
- Modify: `app.py`

**Step 1: Add Chrome check function after `get_user_data_dir`**

```python
def check_chrome_installed():
    """Return path to Chrome binary, or None if not found."""
    return shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser") or \
        next((p for p in [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ] if os.path.isfile(p)), None)
```

**Step 2: Call it at app startup (bottom of file, before `register_shutdown_handlers()`)**

```python
if not check_chrome_installed():
    print("\n" + "="*60)
    print("ERROR: Google Chrome not found.")
    print("Please install Chrome from https://www.google.com/chrome/")
    print("="*60 + "\n")
    sys.exit(1)
```

**Step 3: Verify manually**

Temporarily rename Chrome binary, run app, confirm error message appears.

**Step 4: Commit**
```bash
git add app.py
git commit -m "feat: check Chrome is installed at startup with friendly error"
```

---

### Task 3: Create PyInstaller spec file

**Files:**
- Create: `airbnbinvoicex.spec`

**Step 1: Install PyInstaller in venv**
```bash
source venv/bin/activate
pip install pyinstaller
pip freeze > requirements.txt
```

**Step 2: Create `airbnbinvoicex.spec`**

```python
# airbnbinvoicex.spec
import sys
block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),  # include if exists
    ],
    hiddenimports=[
        'flask',
        'flask.templating',
        'jinja2',
        'jinja2.ext',
        'werkzeug',
        'werkzeug.serving',
        'werkzeug.debug',
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.chrome',
        'selenium.webdriver.chrome.options',
        'selenium.webdriver.chrome.service',
        'selenium.webdriver.common.by',
        'selenium.webdriver.support',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'dotenv',
        'engineio',
        'pkg_resources',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AirbnbInvoiceX',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # keep console for MFA instructions visibility
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AirbnbInvoiceX',
)

# Mac .app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='AirbnbInvoiceX.app',
        icon=None,
        bundle_identifier='com.airbnbinvoicex.app',
        info_plist={
            'NSHighResolutionCapable': True,
        },
    )
```

**Step 3: Test build locally on Mac**
```bash
source venv/bin/activate
pyinstaller airbnbinvoicex.spec --clean
```

Expected: `dist/AirbnbInvoiceX/` directory created, and `dist/AirbnbInvoiceX.app` on Mac.

**Step 4: Test the built app**
```bash
./dist/AirbnbInvoiceX/AirbnbInvoiceX
```

Browser should open at localhost:5001.

**Step 5: Add dist/ to .gitignore**
```bash
echo "dist/" >> .gitignore
echo "build/" >> .gitignore
echo "*.spec.bak" >> .gitignore
```

**Step 6: Commit**
```bash
git add airbnbinvoicex.spec .gitignore
git commit -m "feat: add PyInstaller spec file for Mac/Windows bundling"
```

---

### Task 4: Create a launcher script

The app needs to auto-open the browser and show instructions in the console window.

**Files:**
- Create: `launcher.py`
- Modify: `airbnbinvoicex.spec` (change entry point from `app.py` to `launcher.py`)

**Step 1: Create `launcher.py`**

```python
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
```

**Step 2: Update spec to use launcher.py**

Change `['app.py']` to `['launcher.py']` in the `Analysis` call.

**Step 3: Rebuild and test**
```bash
pyinstaller airbnbinvoicex.spec --clean
./dist/AirbnbInvoiceX/AirbnbInvoiceX
```

**Step 4: Commit**
```bash
git add launcher.py airbnbinvoicex.spec
git commit -m "feat: add launcher script with auto browser open and user instructions"
```

---

### Task 5: Create build scripts

**Files:**
- Create: `build_mac.sh`
- Create: `build_win.bat`

**Step 1: Create `build_mac.sh`**
```bash
#!/bin/bash
set -e
echo "Building AirbnbInvoiceX for macOS..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pyinstaller
pyinstaller airbnbinvoicex.spec --clean
cd dist
zip -r AirbnbInvoiceX-mac.zip AirbnbInvoiceX.app
echo "Done: dist/AirbnbInvoiceX-mac.zip"
```

**Step 2: Create `build_win.bat`**
```bat
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
```

**Step 3: Make build_mac.sh executable**
```bash
chmod +x build_mac.sh
```

**Step 4: Commit**
```bash
git add build_mac.sh build_win.bat
git commit -m "feat: add build scripts for Mac and Windows"
```

---

### Task 6: GitHub Actions workflow

Automatically build and publish to GitHub Releases when a tag like `v1.0.0` is pushed.

**Files:**
- Create: `.github/workflows/build.yml`

**Step 1: Create `.github/workflows/build.yml`**

```yaml
name: Build and Release

on:
  push:
    tags:
      - 'v*'

jobs:
  build-mac:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pyinstaller
      - name: Build
        run: pyinstaller airbnbinvoicex.spec --clean
      - name: Zip
        run: cd dist && zip -r AirbnbInvoiceX-mac.zip AirbnbInvoiceX.app
      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: mac-build
          path: dist/AirbnbInvoiceX-mac.zip

  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pyinstaller
      - name: Build
        run: pyinstaller airbnbinvoicex.spec --clean
      - name: Zip
        run: Compress-Archive -Path dist\AirbnbInvoiceX -DestinationPath dist\AirbnbInvoiceX-win.zip
        shell: powershell
      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: windows-build
          path: dist\AirbnbInvoiceX-win.zip

  release:
    needs: [build-mac, build-windows]
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - name: Download Mac build
        uses: actions/download-artifact@v4
        with:
          name: mac-build
      - name: Download Windows build
        uses: actions/download-artifact@v4
        with:
          name: windows-build
      - name: Create Release
        uses: softprops/action-gh-release@v2
        with:
          files: |
            AirbnbInvoiceX-mac.zip
            AirbnbInvoiceX-win.zip
          generate_release_notes: true
```

**Step 2: Commit**
```bash
git add .github/workflows/build.yml
git commit -m "feat: add GitHub Actions workflow for Mac and Windows builds"
```

**Step 3: Test by pushing a tag**
```bash
git tag v1.0.0
git push origin v1.0.0
```

Go to GitHub → Actions tab → verify both builds succeed.
Go to GitHub → Releases → verify zips are attached.

---

### Task 7: Update README with download instructions

**Files:**
- Modify: `README.md`

**Step 1: Add Installation section**

Add before "Quickstart":
```markdown
## Download (recommended)

1. Go to [Releases](https://github.com/sienioApius/airbnbinvoicex/releases/latest)
2. Download `AirbnbInvoiceX-mac.zip` (Mac) or `AirbnbInvoiceX-win.zip` (Windows)
3. Unzip and double-click `AirbnbInvoiceX`
4. **Mac only:** First time — right-click → Open → Open (bypasses Gatekeeper)
5. Browser opens automatically at `http://localhost:5001`

**Requirement:** Google Chrome must be installed.
```

**Step 2: Commit and push**
```bash
git add README.md
git commit -m "docs: add download instructions for packaged app"
git push
```

---

## Summary

| Task | What it does |
|------|-------------|
| 1 | Fix file paths to work in read-only bundle |
| 2 | Chrome check at startup with friendly error |
| 3 | PyInstaller spec file |
| 4 | Launcher script (auto-open browser) |
| 5 | Build scripts for local builds |
| 6 | GitHub Actions — auto-build + release on tag |
| 7 | README download instructions |
