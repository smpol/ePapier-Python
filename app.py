import sys
import os
import time
import logging
import logging.handlers 
import socket
import requests
from threading import Lock, Thread, Event
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from PIL import Image
from io import BytesIO
from flask import Flask
from dotenv import load_dotenv
from lib.waveshare_epd import epd7in5_V2
from selenium.common.exceptions import WebDriverException, TimeoutException  
import signal
import psutil
from waitress import serve
import tempfile
import urllib3

# Disable SSL warnings for requests for localhost
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load environment variables
load_dotenv()

# Configure logging to file and console, default level set to INFO
log_file_handler = logging.handlers.RotatingFileHandler(
    "app.log", maxBytes=5*1024*1024, backupCount=5)  # 5 MB per file, keep 5 backups
log_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        log_file_handler,
                        logging.StreamHandler(sys.stdout)
                    ])

app = Flask(__name__)
shutdown_event = Event()  # Event to signal shutdown across threads
browser = None  # Persistent browser instance to keep it open continuously

def log_open_fds(context=""):
    """Log the current number of open file descriptors with a context."""
    try:
        process = psutil.Process(os.getpid())
        if hasattr(process, 'num_fds'):
            num_fds = process.num_fds()
            logging.info(f"[{context}] Number of open file descriptors: {num_fds}")
        else:
            logging.info(f"[{context}] Cannot determine number of open file descriptors on this OS.")
    except Exception as e:
        logging.error(f"[{context}] Failed to log open file descriptors: {e}")

try:
    epd = epd7in5_V2.EPD()
    logging.info("E-paper display initialized successfully")
except Exception as e:
    logging.error("Failed to initialize e-paper display object: %s", e)
    sys.exit(1)

display_initialized = True
cleared_screen = True
use_second_flag = False
update_lock = Lock()

# Update intervals in seconds
quick_update_interval = 15  # 15 seconds
full_update_interval = 30 * 60  # 20 minutes (1200 seconds)
last_quick_update = time.time()
last_full_update = time.time()
second_screen_view = time.time()

# Cloudflare API credentials
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_ZONE_ID = os.getenv("CLOUDFLARE_ZONE_ID")
CLOUDFLARE_RECORD_ID = os.getenv("CLOUDFLARE_RECORD_ID")
CLOUDFLARE_DOMAIN = os.getenv("CLOUDFLARE_DOMAIN")

# Initialize a single requests session
session = requests.Session()
session.headers.update({
    "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
    "Content-Type": "application/json"
})

def initialize_epaper():
    """Initialize and clear the e-paper display."""
    global display_initialized
    logging.info("Initializing e-paper display")
    log_open_fds("initialize_epaper - start")
    try:
        epd.init()
        epd.Clear()
        display_initialized = True
    except Exception as e:
        logging.error("Failed to initialize e-paper display: %s", e)
        display_initialized = False
    finally:
        log_open_fds("initialize_epaper - end")

initialize_epaper()

def cleanup():
    """Perform cleanup operations: clear and power down the display, close browser and session."""
    logging.info("Performing cleanup")
    log_open_fds("cleanup - start")
    try:
        epd.init()
        epd.Clear()
        epd.sleep()
        epd7in5_V2.epdconfig.module_exit()
    except Exception as e:
        logging.error("Error during display cleanup: %s", e)
    finally:
        global browser
        # Zamknij przeglądarkę jeśli istnieje
        if browser is not None:
            try:
                logging.info("Closing browser during cleanup")
                browser.quit()
            except Exception as e:
                logging.warning("Error closing browser: %s", e)
            finally:
                browser = None  # Zresetuj przeglądarkę
        # Zamknij sesję requests
        try:
            session.close()
            logging.info("Requests session closed")
        except Exception as e:
            logging.error("Error closing requests session: %s", e)
    log_open_fds("cleanup - end")

def clear_screen():
    """Clear the e-paper display."""
    logging.info("Clearing screen")
    log_open_fds("clear_screen - start")
    try:
        epd.init()
        epd.Clear()
        epd.sleep()
    except Exception as e:
        logging.error("Error clearing screen: %s", e)
    finally:
        log_open_fds("clear_screen - end")

def check_website():
    """Check if the website is accessible and return the status code."""
    try:
        response = requests.get("https://localhost/screen", timeout=60, verify=False)
        logging.info("Website status code: %s", response.status_code)
        return response.status_code == 200
    except requests.RequestException as e:
        return False

def get_browser():
    """Initialize and return a singleton instance of the Selenium WebDriver."""
    global browser
    if browser is not None:
        try:
            # Sprawdź czy przeglądarka jest jeszcze aktywna
            browser.current_url  # Proste sprawdzenie statusu
            return browser
        except Exception as e:
            logging.warning("Browser session invalid, reinitializing: %s", e)
            browser = None

    logging.info("Initializing browser")
    log_open_fds("get_browser - start")
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--window-size=800,525")
        chrome_options.add_argument("--ignore-certificate-errors")
        service = Service('/usr/bin/chromedriver')
        browser = webdriver.Chrome(service=service, options=chrome_options)
        browser.set_page_load_timeout(30)  # Ustaw timeout
        logging.info("Browser initialized successfully")
    except WebDriverException as e:
        logging.error("Failed to initialize browser: %s", e)
        browser = None
    log_open_fds("get_browser - end")
    return browser

# Initialize browser once at startup
browser = get_browser()

def get_local_ip():
    """Retrieve the local IP address of the machine."""
    logging.info("Getting local IP")
    log_open_fds("get_local_ip - start")
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception as e:
        logging.error("Error getting local IP: %s", e)
        ip = "127.0.0.1"
    finally:
        s.close()
    log_open_fds("get_local_ip - end")
    return ip

def get_cloudflare_ip():
    """Retrieve the current IP address from Cloudflare DNS record."""
    logging.info("Retrieving IP from Cloudflare")
    log_open_fds("get_cloudflare_ip - start")
    url = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records/{CLOUDFLARE_RECORD_ID}"
    
    with requests.Session() as temp_session:
        temp_session.headers.update({
            "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
            "Content-Type": "application/json"
        })
        try:
            response = temp_session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            current_ip = data.get("result", {}).get("content")
            logging.info("Retrieved IP from Cloudflare: %s", current_ip)
        except requests.RequestException as e:
            logging.error("Request exception while retrieving IP from Cloudflare: %s", e)
            current_ip = None
    log_open_fds("get_cloudflare_ip - end")
    return current_ip

def update_cloudflare_dns(ip):
    """Update Cloudflare DNS record with the given IP address, unless IP is 127.0.0.1."""
    logging.info("Updating Cloudflare DNS")
    log_open_fds("update_cloudflare_dns - start")
    if ip == "127.0.0.1":
        logging.info("Local IP is 127.0.0.1; skipping Cloudflare update.")
        return

    url = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records/{CLOUDFLARE_RECORD_ID}"
    data = {
        "type": "A",
        "name": CLOUDFLARE_DOMAIN,
        "content": ip,
        "ttl": 120,
        "comment": f"Updated by Python script on {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "proxied": False
    }

    try:
        response = session.put(url, json=data, timeout=10)
        response.raise_for_status()
        logging.info("Cloudflare DNS record updated successfully with IP: %s", ip)
    except requests.RequestException as e:
        logging.error("Request exception while updating Cloudflare DNS: %s", e)
    log_open_fds("update_cloudflare_dns - end")

def periodic_cloudflare_update():
    """Periodically check and update Cloudflare DNS record if IP changes."""
    logging.info("Starting periodic Cloudflare update")
    log_open_fds("periodic_cloudflare_update - start")
    while not shutdown_event.is_set():
        local_ip = get_local_ip()
        cloudflare_ip = get_cloudflare_ip()

        if local_ip != "127.0.0.1" and local_ip != cloudflare_ip:
            logging.info("IP mismatch or scheduled update, updating Cloudflare.")
            update_cloudflare_dns(local_ip)

        # Wait for the next update interval (10 minutes)
        for _ in range(600):
            if shutdown_event.is_set():
                break
            time.sleep(1)
    log_open_fds("periodic_cloudflare_update - end")

def capture_and_display(full_refresh=False):
    global display_initialized, second_screen_view, use_second_flag, browser
    if shutdown_event.is_set():
        return

    logging.info("Capturing and displaying")
    log_open_fds("capture_and_display - start")
    current_ip = get_local_ip()

    # Logic to toggle between second=true and normal view every 5 minutes
    if use_second_flag and (time.time() - second_screen_view > 300):
        second_screen_view = time.time()
        use_second_flag = False
    elif not use_second_flag and (time.time() - second_screen_view > 300):
        second_screen_view = time.time()
        use_second_flag = True

    url = f"https://localhost/screen?ip={current_ip}"
    if use_second_flag:
        url += "&second=true"

    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        screenshot_io = None  # Inicjalizacja zmiennej
        image = None  # Inicjalizacja zmiennej
        try:
            logging.info("Refreshing page content for screenshot capture")
            
            # Sprawdź i zainicjuj przeglądarkę jeśli potrzebna
            if browser is None:
                browser = get_browser()
                if browser is None:
                    raise RuntimeError("Browser initialization failed")
            
            browser.set_page_load_timeout(30)  # Ustaw timeout na 30 sekund
            browser.get(url)

            screenshot = browser.get_screenshot_as_png()
            screenshot_io = BytesIO(screenshot)
            image = Image.open(screenshot_io).convert('L')
            image = image.resize((epd.width, epd.height))

            if full_refresh:
                epd.init()
                epd.Clear()
                epd.display(epd.getbuffer(image))
                epd.sleep()
            else:
                epd.init_part()
                epd.display_Partial(epd.getbuffer(image), 0, 0, epd.width, epd.height)
                epd.sleep()

            logging.info("Display updated with %s refresh", "full" if full_refresh else "partial")
            break  # Sukces - wyjdź z pętli

        except TimeoutException as e:
            logging.error("Page load timeout: %s", e)
            retry_count += 1
            logging.info("Restarting browser due to timeout (attempt %d/%d)", retry_count, max_retries)
            try:
                if browser:
                    browser.quit()
            except Exception as e:
                logging.warning("Error closing browser: %s", e)
            browser = None

        except Exception as e:
            logging.error("Error capturing and displaying: %s", e)
            retry_count += 1
            logging.info("Restarting browser due to error (attempt %d/%d)", retry_count, max_retries)
            try:
                if browser:
                    browser.quit()
            except Exception as e:
                logging.warning("Error closing browser: %s", e)
            browser = None

        finally:
            # Bezpieczne zamykanie zasobów
            if image is not None:
                image.close()
            if screenshot_io is not None:
                screenshot_io.close()
            
        time.sleep(5)  # Odczekaj przed ponowną próbą

    log_open_fds("capture_and_display - end")

@app.route('/updatescreen', methods=['GET'])
def update_screen():
    logging.info("Received request to update screen")
    with update_lock:
        if not display_initialized:
            logging.info("Reinitializing display as it was not initialized")
            initialize_epaper()
        capture_and_display(full_refresh=True)
        return "Screen updated successfully", 200

def main_loop():
    """Main loop that handles periodic screen updates."""
    global last_quick_update, last_full_update, display_initialized, cleared_screen
    logging.info("Entering main loop")
    log_open_fds("main_loop - start")
    try:
        while not shutdown_event.is_set():
            try:
                if check_website():
                    cleared_screen = False
                    current_time = time.time()
                    if update_lock.locked():
                        logging.debug("Update lock is active, sleeping for 0.5 seconds")
                        time.sleep(0.5)
                        continue
                    with update_lock:
                        if current_time - last_full_update >= full_update_interval:
                            capture_and_display(full_refresh=True)
                            last_full_update = current_time
                        elif current_time - last_quick_update >= quick_update_interval:
                            capture_and_display(full_refresh=False)
                            last_quick_update = current_time
                else:
                    logging.warning("Website is not accessible, waiting 10 seconds")
                    if not cleared_screen:
                        logging.info("Clearing screen as website is not accessible")
                        clear_screen()
                        cleared_screen = True
                    time.sleep(10)
            except Exception as e:
                logging.error("Unhandled exception in main loop: %s", e)
                time.sleep(5)
    except Exception as e:
        logging.error("Critical error in main loop: %s", e)
    finally:
        cleanup()
    log_open_fds("main_loop - end")

def start_flask_server():
    """Start the Flask server using Waitress in a separate daemon thread."""
    logging.info("Starting Flask server with Waitress")
    log_open_fds("start_flask_server - start")
    server = Thread(target=lambda: serve(app, host='0.0.0.0', port=5002), daemon=True)
    server.start()
    log_open_fds("start_flask_server - end")
    return server

if __name__ == "__main__":
    def signal_handler(sig, frame):
        logging.info("Received termination signal, shutting down...")
        shutdown_event.set()
        cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    start_flask_server()

    cloudflare_thread = Thread(target=periodic_cloudflare_update, daemon=True)
    cloudflare_thread.start()

    main_loop()