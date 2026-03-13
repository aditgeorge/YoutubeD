To package your app with everything included (Python, `yt-dlp`, and `ffmpeg`), you need to create a "truly standalone" executable.

Before we start, here is the golden rule of PyInstaller: **You cannot cross-compile.** To make a Windows `.exe`, you must run these steps on a Windows machine. To make a Mac app, you must run them on a Mac.

Here is your complete guide to building both.

---

### Step 1: Update Your Python Script (Do this first)

Because Windows uses `ffmpeg.exe` and Mac uses `ffmpeg` (no extension), we need to update your script to be smart enough to find the right bundled file regardless of which OS it is running on.

**1. Add this helper function near the top of your script (under your imports):**

```python
def get_ffmpeg_path():
    """Get absolute path to bundled ffmpeg based on the operating system."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    # Windows uses .exe, Mac/Linux do not
    ffmpeg_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    return os.path.join(base_path, ffmpeg_name)

```

**2. Update the `opts` dictionary in your `_download` method:**
Find the `opts = { ... }` block in your `_download` function and add the `ffmpeg_location` line like this:

```python
        opts = {
            "format": fmt,
            "outtmpl": os.path.join(folder, "%(title)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [self._progress_hook],
            "postprocessors": postprocessors,
            "ffmpeg_location": get_ffmpeg_path(),  # <--- ADD THIS LINE
        }

```

---

### Step 2: Build the Windows Executable (`.exe`)

*You must do this on a Windows computer.*

1. **Download Static FFmpeg for Windows:**
* Go to [gyan.dev/ffmpeg/builds/](https://www.gyan.dev/ffmpeg/builds/).
* Download the `ffmpeg-release-essentials.zip`.
* Open the zip, go into the `bin` folder, and extract **`ffmpeg.exe`**.
* Place `ffmpeg.exe` in the exact same folder as your `youtube_downloader.py` script.


2. **Install PyInstaller:**
* Open Command Prompt or PowerShell and run: `pip install pyinstaller`


3. **Run the Build Command:**
* Navigate to your project folder in the terminal and run this exact command:


```cmd
pyinstaller --noconfirm --onefile --windowed --add-binary "ffmpeg.exe;." --name "YouTube Downloader" youtube_downloader.py

```


*(Note: Windows uses a semicolon `;` in the `--add-binary` flag).*
4. **Get Your App:**
* Go into the newly created `dist` folder. Your standalone `YouTube Downloader.exe` is ready to be shared with any Windows user.



---

### Step 3: Build the Mac Executable

*You must do this on a Mac computer.*

1. **Download Static FFmpeg for Mac:**
* Go to [evermeet.cx/ffmpeg/](https://evermeet.cx/ffmpeg/).
* Download the zip file for `ffmpeg` (the green button).
* Unzip it, and you will get a single file named **`ffmpeg`** (no extension).
* Place `ffmpeg` in the exact same folder as your `youtube_downloader.py` script.


2. **Install PyInstaller:**
* Open Terminal and run: `pip3 install pyinstaller`


3. **Run the Build Command:**
* Navigate to your project folder in the terminal and run this exact command:


```bash
pyinstaller --noconfirm --onefile --windowed --add-binary "ffmpeg:." --name "YouTube Downloader" youtube_downloader.py

```


*(Note: Mac uses a colon `:` in the `--add-binary` flag).*
4. **Get Your App:**
* Go into the newly created `dist` folder. Your standalone `YouTube Downloader` app is ready to be shared with any Mac user.



Would you like me to show you how to add a custom `.ico` (Windows) and `.icns` (Mac) file to your PyInstaller commands so your app has a professional icon instead of the default generic one?

---

### macOS certificate error fix (YouTube validation)

If your friend sees an SSL/TLS error like `certificate verify failed` when validating a video:

1. Install project dependencies from `requirements.txt` (this includes `certifi`).
2. Rebuild the Mac app on macOS (PyInstaller cannot cross-compile from Windows).
3. If running from a local Python install (not bundled app), run Python's `Install Certificates.command` once.

The app now sets `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE` to `certifi` automatically when available, which fixes most macOS CA trust issues.