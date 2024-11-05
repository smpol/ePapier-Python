import sys
import os
import time
import logging
import socket
import requests
from threading import Lock, Thread, Timer
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from PIL import Image
from io import BytesIO
from flask import Flask
from dotenv import load_dotenv
from lib.waveshare_epd import epd7in5_V2
from selenium.common.exceptions import WebDriverException

# Load environment variables
load_dotenv()

# Configure logging to file and console, default level set to INFO
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler("app.log"),
                        logging.StreamHandler(sys.stdout)
                    ])

app = Flask(__name__)
try:
    epd = epd7in5_V2.EPD()
    logging.info("E-paper display initialized successfully")
except Exception as e:
    logging.error("Failed to initialize e-paper display object: %s", e)
    sys.exit(1)

display_initialized = True
update_lock = Lock()

quick_update_interval = 10  # seconds
full_update_interval = 10 * 60  # seconds (10 minutes)
last_quick_update = time.time()
last_full_update = time.time()

# Cloudflare API credentials
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_ZONE_ID = os.getenv("CLOUDFLARE_ZONE_ID")
CLOUDFLARE_RECORD_ID = os.getenv("CLOUDFLARE_RECORD_ID")
CLOUDFLARE_DOMAIN = os.getenv("CLOUDFLARE_DOMAIN")

def initialize_epaper():
    global display_initialized
    try:
        logging.info("Initializing and clearing e-paper display")
        epd.init_4Gray()
        epd.Clear()
        display_initialized = True
    except Exception as e:
        logging.error("Failed to initialize e-paper display: %s", e)
        display_initialized = False

initialize_epaper()

def cleanup():
    logging.info("Performing cleanup: clearing and powering down the display.")
    try:
        epd.init_4Gray()
        epd.Clear()
        epd.sleep()
        epd7in5_V2.epdconfig.module_exit()
    except Exception as e:
        logging.error("Error during cleanup: %s", e)

def get_browser():
    try:
        logging.info("Starting browser initialization")
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--window-size=800,525")
        chrome_options.add_argument("--ignore-certificate-errors")
        service = Service('/usr/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logging.info("Browser initialized successfully")
        return driver
    except WebDriverException as e:
        logging.error("Failed to initialize browser: %s", e)
        return None

browser = get_browser()  # Persistent browser instance

def restart_browser():
    global browser
    logging.info("Restarting browser")
    if browser:
        browser.quit()
    browser = get_browser()

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception as e:
        logging.error("Error getting local IP: %s", e)
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def get_cloudflare_ip():
    """Retrieve the current IP address from Cloudflare DNS record."""
    url = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records/{CLOUDFLARE_RECORD_ID}"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        current_ip = response.json().get("result", {}).get("content")
        logging.info("Retrieved IP from Cloudflare: %s", current_ip)
        return current_ip
    else:
        logging.error("Failed to retrieve IP from Cloudflare: %s", response.text)
        return None

def update_cloudflare_dns(ip):
    """Update Cloudflare DNS record with the given IP address, unless IP is 127.0.0.1."""
    if ip == "127.0.0.1":
        logging.info("Local IP is 127.0.0.1; skipping Cloudflare update.")
        return

    url = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records/{CLOUDFLARE_RECORD_ID}"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "type": "A",
        "name": CLOUDFLARE_DOMAIN,
        "content": ip,
        "ttl": 120,  # Time-to-live
        "comment": f"Updated by Python script on {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "proxied": False
    }

    response = requests.put(url, headers=headers, json=data)
    if response.status_code == 200:
        logging.info("Cloudflare DNS record updated successfully with IP: %s", ip)
    else:
        logging.error("Failed to update Cloudflare DNS record: %s", response.text)

def periodic_cloudflare_update():
    """Periodically check and update Cloudflare DNS record if IP changes."""
    local_ip = get_local_ip()
    cloudflare_ip = get_cloudflare_ip()

    # Update if IPs do not match or force update every 10 minutes
    if local_ip != "127.0.0.1" and local_ip != cloudflare_ip:
        logging.info("IP mismatch or scheduled update, updating Cloudflare.")
        update_cloudflare_dns(local_ip)

    # Schedule the next update in 10 minutes
    Timer(600, periodic_cloudflare_update).start()

# Start the periodic Cloudflare DNS update
initial_ip = get_local_ip()
if initial_ip != "127.0.0.1":
    update_cloudflare_dns(initial_ip)  # Initial update on program start if IP is not 127.0.0.1
periodic_cloudflare_update()  # Start periodic check and update every 10 minutes

def capture_and_display(full_refresh=False):
    global display_initialized
    if not browser:
        restart_browser()
        if not browser:
            logging.error("Browser could not be reinitialized.")
            return

    current_ip = get_local_ip()
    url = f"https://localhost/?ip={current_ip}"

    try:
        logging.info("Navigating to URL")
        browser.get(url)
        screenshot = browser.get_screenshot_as_png()
        image = Image.open(BytesIO(screenshot)).convert('L')
        image = image.resize((epd.width, epd.height))

        if full_refresh:
            epd.init_4Gray()
            epd.Clear()
            epd.display(epd.getbuffer(image))
            epd.sleep()
        else:
            epd.init_part()
            epd.display_Partial(epd.getbuffer(image), 0, 0, epd.width, epd.height)

        logging.info("Display updated with %s refresh", "full" if full_refresh else "partial")
    except Exception as e:
        logging.error("Error capturing and displaying: %s", e)
        display_initialized = False

@app.route('/updatescreen', methods=['GET'])
def update_screen():
    logging.info("Received request to update screen")
    with update_lock:
        if not display_initialized:
            logging.info("Reinitializing display as it was not initialized")
            initialize_epaper()
        capture_and_display(full_refresh=True)
        return "Screen updated successfully", 200

def main():
    global last_quick_update, last_full_update, display_initialized
    logging.info("Entering main loop")
    try:
        while True:
            current_time = time.time()

            if update_lock.locked():
                logging.debug("Update lock is active, sleeping for 0.5 seconds")
                time.sleep(0.5)
                continue

            if not display_initialized:
                logging.info("Display not initialized, reinitializing and waiting")
                initialize_epaper()
                time.sleep(quick_update_interval)
                continue

            with update_lock:
                if current_time - last_full_update >= full_update_interval:
                    capture_and_display(full_refresh=True)
                    last_full_update = current_time
                elif current_time - last_quick_update >= quick_update_interval:
                    capture_and_display(full_refresh=False)
                    last_quick_update = current_time

    except KeyboardInterrupt:
        logging.info("Program interrupted by Ctrl+C")
    except Exception as e:
        logging.critical("Unexpected error in main loop: %s", e, exc_info=True)
    finally:
        cleanup()

if __name__ == "__main__":
    logging.info("Starting Flask server")
    server = Thread(target=lambda: app.run(host='0.0.0.0', port=5002))
    server.daemon = True
    server.start()
    main()
