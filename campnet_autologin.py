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


# ================= LOGGING =================

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

def load_config():
    if getattr(sys, 'frozen', False):
        # Running as .exe
        base_dir = os.path.dirname(sys.executable)
    else:
        # Running as .py
        base_dir = os.path.dirname(os.path.abspath(__file__))

    config_path = os.path.join(base_dir, "config.json")

    if not os.path.exists(config_path):
        logger.error(f"config.json not found at {config_path}")
        sys.exit("config.json missing")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        username = cfg["username"]
        password = cfg["password"]
        check_interval = cfg["check_interval"]

        logger.info("Config loaded successfully")

        return username, password

    except Exception as e:
        logger.exception("Invalid config.json")
        sys.exit(f"Invalid config.json: {e}")


# ==========================================

BASE = "https://campnet.bits-goa.ac.in:8090"
CHECK_URL = "https://connectivitycheck.gstatic.com/generate_204"

USERNAME, PASSWORD, CHECK_INTERVAL = load_config()

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


# ---------- Core Logic ----------

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

        time.sleep(1)

        if is_logged_in():
            last_status = "Logged in successfully"
            logger.info("Login successful")
            return

        logger.warning("Login did not stick, retrying with logout")

        with requests.Session() as s:
            s.headers.update(HEADERS)
            s.cookies.update(COOKIES)
            logout(s)
            time.sleep(0.5)
            login(s)

        time.sleep(1)

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
            last_status = "Connected (campus network)"

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


def shutdown(reason=""):
    logger.info(f"Shutting down ({reason})")
    stop_event.set()
    if icon_ref:
        try:
            icon_ref.stop()
        except:
            pass
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
    global icon_ref

    logger.info("CampNet Auto Login starting")

    t = threading.Thread(target=worker_loop, daemon=True)
    t.start()
    update_tooltip()


    menu = Menu(
        MenuItem("Force Login", force_login_action),
        MenuItem("Force Logout (Pause Auto Login)", force_logout_action),
        MenuItem("Show Status (console)", show_status),
        MenuItem("Exit", exit_app),
    )

    icon_ref = Icon(
        "CampNet Auto Login",
        create_image(),
        "CampNet Auto Login\nStarting...",
        menu
    )

    icon_ref.run()


if __name__ == "__main__":
    main()
