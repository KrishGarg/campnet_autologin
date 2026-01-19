import time
import threading
import requests
import sys
import signal
import logging
from logging.handlers import RotatingFileHandler
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
import urllib3
import json
import os

import tkinter as tk
from tkinter import messagebox



# ================= LOGGING =================
tk_root = None

LOG_FILE = "campnet_autologin.log"

logger = logging.getLogger("CampNetAutoLogin")
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=1_000_000 / 2,   # 0.5 MB
    backupCount=1         # keep last 1 file
)

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s"
)

handler.setFormatter(formatter)
logger.addHandler(handler)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ==========================================

BASE = "https://campnet.bits-goa.ac.in:8090"
CHECK_URL = "https://connectivitycheck.gstatic.com/generate_204"

HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,hi;q=0.6",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": BASE,
    "Referer": f"{BASE}/httpclient.html",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/143.0.0.0 Safari/537.36"
    ),
}

COOKIES = {
    "SF-UI-LANG": "en-US"
}

last_status = "Starting..."
auto_login_enabled = True
icon_ref = None

stop_event = threading.Event()

# ---------- Helpers ----------
def update_tooltip():
    if icon_ref:
        try:
            icon_ref.title = f"CampNet Auto Login\n{last_status}"
        except:
            pass

def now_ms():
    return int(time.time() * 1000)

def is_portal_available():
    """
    Returns True if the captive portal is reachable on this network.
    This identifies whether we are on a compatible Wi-Fi.
    """
    try:
        r = requests.get(
            f"{BASE}/httpclient.html",
            timeout=5,
            verify=False
        )
        return r.status_code == 200
    except Exception:
        return False


def is_logged_in():
    try:
        r = requests.get(
            CHECK_URL,
            allow_redirects=False,
            timeout=5,
            verify=False
        )
        return r.status_code == 204
    except Exception as e:
        logger.warning(f"Connectivity check failed: {e}")
        return False


def logout(session):
    logger.info("Sending logout request")
    return session.post(
        f"{BASE}/logout.xml",
        data={
            "mode": "193",
            "username": USERNAME,
            "a": now_ms(),
            "producttype": "0",
        },
        timeout=5,
    )


def login(session):
    logger.info("Sending login request")
    return session.post(
        f"{BASE}/login.xml",
        data={
            "mode": "191",
            "username": USERNAME,
            "password": PASSWORD,
            "a": now_ms(),
            "producttype": "0",
        },
        timeout=5,
    )

def prompt_for_config(config_path):
    """
    Opens a simple dialog to collect username and password,
    then writes config.json with default check_interval = 10.
    """
    root = tk.Tk()
    root.title("CampNet Auto Login – Setup")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    tk.Label(root, text="Username").grid(row=0, column=0, padx=10, pady=5, sticky="e")
    username_entry = tk.Entry(root, width=30)
    username_entry.grid(row=0, column=1, padx=10, pady=5)

    tk.Label(root, text="Password").grid(row=1, column=0, padx=10, pady=5, sticky="e")
    password_entry = tk.Entry(root, width=30, show="*")
    password_entry.grid(row=1, column=1, padx=10, pady=5)

    result = {}

    def submit():
        username = username_entry.get().strip()
        password = password_entry.get().strip()

        if not username or not password:
            messagebox.showerror("Error", "Both fields are required")
            return

        result["username"] = username
        result["password"] = password
        root.destroy()

    def cancel():
        root.destroy()

    btn_frame = tk.Frame(root)
    btn_frame.grid(row=2, column=0, columnspan=2, pady=10)

    tk.Button(btn_frame, text="Save", width=10, command=submit).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Cancel", width=10, command=cancel).pack(side="right", padx=5)

    username_entry.focus()
    root.mainloop()

    if not result:
        sys.exit("Setup cancelled by user")

    config = {
        "username": result["username"],
        "password": result["password"],
        "check_interval": 10
    }

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    logger.info("config.json created via setup dialog")

    return config



# ---------- Core Logic ----------

def load_config():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    config_path = os.path.join(base_dir, "config.json")

    # If config does not exist, prompt user
    if not os.path.exists(config_path):
        logger.info("config.json not found, launching setup dialog")
        cfg = prompt_for_config(config_path)
        return cfg["username"], cfg["password"], cfg["check_interval"]

    # Load existing config
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        username = cfg["username"]
        password = cfg["password"]
        check_interval = cfg.get("check_interval", 10)

        if not username or not password:
            raise ValueError("Invalid credentials in config")

        logger.info("Config loaded successfully")
        return username, password, check_interval

    except Exception as e:
        logger.exception("Invalid config.json")
        sys.exit(f"Invalid config.json: {e}")

USERNAME, PASSWORD, CHECK_INTERVAL = load_config()

def open_settings_window():
    global USERNAME, PASSWORD, CHECK_INTERVAL

    # Load latest config
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    config_path = os.path.join(base_dir, "config.json")

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    root = tk.Toplevel(tk_root)
    root.title("CampNet Auto Login – Settings")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    tk.Label(root, text="Username").grid(row=0, column=0, padx=10, pady=5, sticky="e")
    username_entry = tk.Entry(root, width=30)
    username_entry.insert(0, cfg.get("username", ""))
    username_entry.grid(row=0, column=1, padx=10, pady=5)

    tk.Label(root, text="Password").grid(row=1, column=0, padx=10, pady=5, sticky="e")
    password_entry = tk.Entry(root, width=30, show="*")
    password_entry.insert(0, cfg.get("password", ""))
    password_entry.grid(row=1, column=1, padx=10, pady=5)

    tk.Label(root, text="Check interval (seconds)").grid(row=2, column=0, padx=10, pady=5, sticky="e")
    interval_entry = tk.Entry(root, width=10)
    interval_entry.insert(0, str(cfg.get("check_interval", 10)))
    interval_entry.grid(row=2, column=1, padx=10, pady=5, sticky="w")

    startup_var = tk.BooleanVar(value=cfg.get("startup_enabled", False))
    tk.Checkbutton(
        root,
        text="Start automatically on system startup (coming soon)",
        variable=startup_var
    ).grid(row=3, column=0, columnspan=2, pady=5)

    def save():
        nonlocal cfg
        global USERNAME, PASSWORD, CHECK_INTERVAL
        try:
            new_username = username_entry.get().strip()
            new_password = password_entry.get().strip()
            new_interval = int(interval_entry.get())

            if not new_username or not new_password:
                raise ValueError("Username and password cannot be empty")

            cfg["username"] = new_username
            cfg["password"] = new_password
            cfg["check_interval"] = new_interval
            cfg["startup_enabled"] = startup_var.get()

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)

            # Apply immediately
            USERNAME = new_username
            PASSWORD = new_password
            CHECK_INTERVAL = new_interval

            root.destroy()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    btns = tk.Frame(root)
    btns.grid(row=4, column=0, columnspan=2, pady=10)

    tk.Button(btns, text="Save", width=10, command=save).pack(side="left", padx=5)
    tk.Button(btns, text="Cancel", width=10, command=root.destroy).pack(side="right", padx=5)

    root.mainloop()


def captive_login():
    global last_status

    if is_logged_in():
        last_status = "Already logged in"
        logger.info("Already logged in")
        return

    try:
        with requests.Session() as s:
            s.headers.update(HEADERS)
            s.cookies.update(COOKIES)
            login(s)

        if is_logged_in():
            last_status = "Logged in successfully"
            logger.info("Login successful")
            return

        logger.warning("Login did not stick, retrying with logout")

        with requests.Session() as s:
            s.headers.update(HEADERS)
            s.cookies.update(COOKIES)
            logout(s)
            login(s)


        if is_logged_in():
            last_status = "Logged in after reset"
            logger.info("Login successful after reset")
        else:
            last_status = "Login failed"
            logger.error("Login failed after retry")

    except Exception as e:
        last_status = f"Error: {e}"
        logger.exception("Exception during login flow")


def force_login():
    global auto_login_enabled, last_status
    auto_login_enabled = True
    last_status = "Manual login requested"
    logger.info("Manual login triggered (auto-login enabled)")
    update_tooltip()
    captive_login()



def force_logout():
    global auto_login_enabled, last_status
    auto_login_enabled = False
    last_status = "Logged out (auto-login paused)"
    logger.info("Manual logout triggered (auto-login paused)")
    update_tooltip()

    try:
        with requests.Session() as s:
            s.headers.update(HEADERS)
            s.cookies.update(COOKIES)
            logout(s)
        logger.info("Logout successful")
    except Exception as e:
        last_status = f"Logout error"
        logger.exception("Logout failed")
        update_tooltip()



def worker_loop():
    global last_status

    logger.info("Worker loop started")

    while not stop_event.is_set():

        # Respect manual pause
        if not auto_login_enabled:
            last_status = "Auto-login paused"
            update_tooltip()
            stop_event.wait(CHECK_INTERVAL)
            continue

        # Check if this network supports the captive portal
        if not is_portal_available():
            last_status = "Not on campus network"
            update_tooltip()
            stop_event.wait(CHECK_INTERVAL)
            continue

        # We are on a compatible network
        if not is_logged_in():
            last_status = "Campus network detected – logging in"
            logger.info("Campus network detected -> attempting login")
            captive_login()
        else:
            last_status = "Connected"

        update_tooltip()
        stop_event.wait(CHECK_INTERVAL)



# ================= TRAY UI =================

def create_image():
    img = Image.new("RGB", (64, 64), "white")
    d = ImageDraw.Draw(img)
    d.ellipse((8, 8, 56, 56), fill="blue")
    return img


def force_login_action(icon, item):
    force_login()


def force_logout_action(icon, item):
    force_logout()


def show_status(icon, item):
    logger.info(f"Status requested: {last_status}, auto_login={auto_login_enabled}")

def open_settings_action(icon, item):
    # Schedule UI creation on Tk main thread
    tk_root.after(0, open_settings_window)


def shutdown(reason=""):
    logger.info(f"Shutting down ({reason})")

    # Stop worker loop
    stop_event.set()

    # Stop tray icon
    if icon_ref:
        try:
            icon_ref.stop()
        except:
            pass

    # Stop Tk mainloop
    if tk_root:
        try:
            tk_root.after(0, tk_root.quit)
        except:
            pass

    # Final hard exit
    sys.exit(0)



def exit_app(icon, item):
    shutdown("Tray exit")


# ---------- Signal Handling ----------

def signal_handler(sig, frame):
    shutdown("Ctrl+C / signal")


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


# ---------- Main ----------

def main():
    global icon_ref, tk_root

    logger.info("CampNet Auto Login starting")

    # --- Start hidden Tk root on MAIN thread ---
    tk_root = tk.Tk()
    tk_root.withdraw()   # hide main window

    # --- Start worker thread ---
    t = threading.Thread(target=worker_loop, daemon=True)
    t.start()

    # --- Tray icon runs in background thread ---
    def tray_thread():
        global icon_ref

        menu = Menu(
            MenuItem("Settings", open_settings_action),
            MenuItem("Force Login", force_login_action),
            MenuItem("Force Logout (Pause Auto Login)", force_logout_action),
            MenuItem("Log Status (debug)", show_status),
            MenuItem("Exit", exit_app),
        )

        icon_ref = Icon(
            "CampNet Auto Login",
            create_image(),
            "CampNet Auto Login\nStarting...",
            menu
        )

        icon_ref.run()

    threading.Thread(target=tray_thread, daemon=True).start()

    # --- Tk event loop (blocks main thread correctly) ---
    tk_root.mainloop()



if __name__ == "__main__":
    main()
