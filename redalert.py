#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib3
import os
import json
import time
from loguru import logger
from datetime import datetime
#from rpi_ws281x import Adafruit_NeoPixel, Color


os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["LANG"] = "C.UTF-8"

# LED strip configuration:
LED_COUNT       = 15      # Number of LED pixels
LED_PIN         = 18      # GPIO pin connected to the pixels (18 uses PWM)
LED_FREQ_HZ     = 800000  # LED signal frequency in hertz
LED_DMA         = 10      # DMA channel
LED_BRIGHTNESS  = 65      # Brightness (0-255)
LED_INVERT      = False   # True to invert the signal
LED_CHANNEL     = 0       # PWM channel
RESPONSES_DIR   = os.getenv("RESPONSES_DIR", "responses")
MAX_IDS         = int(os.getenv("MAX_IDS", "1000"))

#TARGET_LOCATION = os.getenv("TARGET_LOCATION", "רעננה").strip()
TARGET_LOCATION = os.getenv("TARGET_LOCATION", "").strip()

# Release timer: 5 minutes
RELEASE_TIMEOUT_SECONDS = 10 * 60

logger.info("Monitoring alerts")

if TARGET_LOCATION:
    logger.info(f"Filtering alerts for location: {TARGET_LOCATION}")
else:
    logger.info("No location filter configured, saving all alerts")

http = urllib3.PoolManager()

_headers = {
    "Referer": "https://www.oref.org.il/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "X-Requested-With": "XMLHttpRequest",
}

url = "https://www.oref.org.il/WarningMessages/alert/alerts.json"

seen_ids = []
release_deadline = None


def cancel_release_timer(reason=""):
    """Cancel the active release timer and optionally log a reason."""
    global release_deadline

    if release_deadline is not None:
        logger.info(f"Release timer cancelled{': ' + reason if reason else ''}")

    release_deadline = None


def start_release_timer():
    """Start the release countdown timer."""
    global release_deadline

    release_deadline = time.time() + RELEASE_TIMEOUT_SECONDS
    logger.info(f"Release timer started for {RELEASE_TIMEOUT_SECONDS} seconds")


def check_release_timer():
    """Turn LEDs off when the release timer expires."""
    global release_deadline

    if release_deadline is None:
        return

    if time.time() >= release_deadline:
        logger.info("Release timer expired, turning LEDs off")
        release_deadline = None


def has_real_content(raw_data):
    """Return True when response bytes contain non-empty decoded content."""
    if not raw_data:
        return False

    cleaned = raw_data.decode("utf-8-sig", errors="ignore").strip()
    return bool(cleaned)


def parse_alert(raw_data):
    """Parse raw alert bytes into a validated alert dictionary or None."""
    try:
        parsed = json.loads(raw_data.decode("utf-8-sig", errors="ignore"))
    except json.JSONDecodeError:
        return None
    except Exception:
        return None

    if not parsed:
        return None

    if not isinstance(parsed, dict):
        return None

    if not parsed.get("id"):
        return None

    return parsed


def extract_metadata(parsed):
    """Extract normalized alert fields used by the event pipeline."""
    alert_id = str(parsed.get("id", "unknown"))
    cat = str(parsed.get("cat", "unknown"))
    title = str(parsed.get("title", ""))
    locations = parsed.get("data", [])

    if not isinstance(locations, list):
        locations = []

    return alert_id, cat, title, locations


def matches_target_location(locations):
    """Return True if alert locations match the configured target location."""
    if not TARGET_LOCATION:
        return True

    return TARGET_LOCATION in locations


def classify_event(cat, title):
    """Map alert category and title text to an internal event name."""
    if cat == "10" and "האירוע הסתיים" in title:
        return "on_release"
    if cat == "10" and "בדקות הקרובות" in title:
        return "on_pre_alert"
    if cat in ("1", "6"):
        return "on_alert"
    return None


def on_alert(parsed):
    """Handle active alert events by setting LEDs red and logging details."""
    cancel_release_timer("new alert received")
    logger.info(
        f"on_alert | alert_id={parsed.get('id')} cat={parsed.get('cat')} title={parsed.get('title')} data={parsed.get('data')}"
    )


def on_pre_alert(parsed):
    """Handle pre-alert events by setting LEDs orange and logging details."""
    cancel_release_timer("new pre-alert received")
    logger.info(
        f"on_pre_alert | alert_id={parsed.get('id')} cat={parsed.get('cat')} title={parsed.get('title')} data={parsed.get('data')}"
    )


def on_release(parsed):
    """Handle release events by setting LEDs green and starting the timer."""
    start_release_timer()
    logger.info(
        f"on_release | alert_id={parsed.get('id')} cat={parsed.get('cat')} title={parsed.get('title')} data={parsed.get('data')}"
    )


EVENT_HANDLERS = {
    "on_alert": on_alert,
    "on_pre_alert": on_pre_alert,
    "on_release": on_release,
}


if __name__ == '__main__':
    try:
        while True:
            r = None

            try:
                # Check timer every loop
                check_release_timer()

                r = http.request("GET", url, headers=_headers)

                raw_data = r.data
                status_code = r.status

                if status_code != 200:
                    logger.error(f"HTTP error {status_code}")
                    continue

                if not has_real_content(raw_data):
                    continue

                parsed = parse_alert(raw_data)
                if parsed is None:
                    logger.debug("Ignoring invalid or empty JSON response")
                    continue
                
                #logger.info(parsed)
                alert_id, cat, title, locations = extract_metadata(parsed)

                if alert_id in seen_ids:
                    continue

                seen_ids.append(alert_id)

                if len(seen_ids) >= MAX_IDS:
                    logger.info("Clearing seen_ids list to save memory")
                    seen_ids = []

                if not matches_target_location(locations):
                    logger.info(f"Alert {alert_id} ignored, target location not found in data: {locations}")
                    continue

                event = classify_event(cat, title)
                if event:
                    EVENT_HANDLERS[event](parsed)

            except Exception as ex:
                logger.error(f"Exception occurred: {ex}")

            finally:
                if r is not None:
                    r.release_conn()

            time.sleep(1)

    except Exception as ex:
        logger.error(f"Fatal exception: {ex}")
