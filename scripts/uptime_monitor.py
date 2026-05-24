import os
import sys
import json
import requests

# Target websites to monitor
WEBSITES = [
    {"name": "HariHaren Site", "url": "https://hariharen.site"},
    {"name": "Scync Space", "url": "https://scync.space"},
    {"name": "JobTrac Site", "url": "https://jobtrac.site"},
    {"name": "Google", "url": "https://www.google.com"},
]

# Resolve directories dynamically relative to the script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "data", "uptime_status.json"))


def get_ntfy_url():
    """Resolves the namespaced ntfy URL from environment variables."""
    secret = os.environ.get("NTFY_UPTIME_SECRET_LINK")
    if not secret:
        print("[Critical Error] NTFY_UPTIME_SECRET_LINK environment variable is not set!")
        print("Please configure this in your GitHub Repository Secrets.")
        sys.exit(1)

    # Allow the secret to be either the full URL or just the topic name
    if secret.startswith("http://") or secret.startswith("https://"):
        return secret
    return f"https://ntfy.sh/{secret.strip('/')}"


def load_previous_status():
    """Loads the last known status matrix from the persistent JSON cache."""
    # Ensure data directory exists
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)

    if not os.path.exists(CACHE_FILE):
        print(f"[Cache] No status cache file found at '{CACHE_FILE}'. Initializing clean state.")
        return {}

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Cache Error] Failed to read cache: {e}. Starting fresh.")
        return {}


def save_current_status(status_map):
    """Saves the current status matrix to the persistent JSON cache."""
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(status_map, f, indent=2, ensure_ascii=False)
        print(f"[Cache] Successfully updated status cache file.")
    except Exception as e:
        print(f"[Cache Error] Failed to write status cache: {e}")


def send_ntfy_alert(ntfy_url, site_name, site_url, state, details=None):
    """Sends transition-state alerts (outage or recovery) to your phone."""
    if state == "DOWN":
        headers = {
            "Title": f"🚨 OUTAGE DETECTED: {site_name}",
            "Priority": "max",  # Rings/vibrates aggressively
            "Tags": "rotating_light,skull,x",
            "Click": site_url,
        }
        body_text = f"Website is unreachable!\nURL: {site_url}\nError/Details: {details}"
    else:
        headers = {
            "Title": f"✅ RECOVERED: {site_name}",
            "Priority": "default",  # Standard notification
            "Tags": "white_check_mark,tada,partying_face",
            "Click": site_url,
        }
        body_text = f"Website is back online!\nURL: {site_url}\nStatus: Responding successfully (200 OK)."

    try:
        response = requests.post(ntfy_url, data=body_text.encode("utf-8"), headers=headers, timeout=15)
        if response.status_code == 200:
            print(f"[Success] Push alert delivered for state transition: {site_name} is now {state}")
        else:
            print(f"[Error] ntfy API returned error: {response.text}")
    except Exception as e:
        print(f"[Network Error] Failed to connect to ntfy: {e}")


def check_uptime():
    print("=" * 60)
    print("Universal ntfy Automation: Multi-Site Uptime Ping Bot")
    print("=" * 60)

    # Get ntfy URL
    ntfy_url = get_ntfy_url()
    masked_url = ntfy_url[:20] + "..." + ntfy_url[-8:] if len(ntfy_url) > 28 else "..."
    print(f"[Config] Target Push Endpoint: {masked_url}")

    # Load cache
    prev_status = load_previous_status()
    current_status = {}

    headers = {"User-Agent": "Mozilla/5.0 UptimeBot/1.0 (Ping check; client:hariharen)"}

    state_changed = False

    for site in WEBSITES:
        name = site["name"]
        url = site["url"]
        print(f"[Ping] Checking {name} ({url})...")

        is_up = False
        error_msg = None

        try:
            # Perform a GET request with 10-second timeout
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            # Accept any 2xx or 3xx status codes as UP
            if 200 <= response.status_code < 400:
                is_up = True
            else:
                error_msg = f"HTTP Status {response.status_code}"
        except requests.exceptions.Timeout:
            error_msg = "Connection Timeout (10s)"
        except requests.exceptions.ConnectionError:
            error_msg = "Connection Refused / DNS Resolution Failed"
        except Exception as e:
            error_msg = f"Exception: {type(e).__name__}"

        current_state = "UP" if is_up else "DOWN"
        current_status[url] = current_state

        # Get last known state (default to None for first run)
        last_state = prev_status.get(url)

        print(f"[Result] {name} is {current_state}." + (f" Error: {error_msg}" if not is_up else ""))

        if last_state is None:
            # First run: establish baseline
            # If it is down on the very first run, notify the user so they know immediately.
            # If it is up, do not spam them.
            if current_state == "DOWN":
                send_ntfy_alert(ntfy_url, name, url, "DOWN", error_msg)
                state_changed = True
            else:
                print(f"[Info] First run baseline set for {name}: UP")
        elif last_state != current_state:
            # State transition detected!
            send_ntfy_alert(ntfy_url, name, url, current_state, error_msg if current_state == "DOWN" else None)
            state_changed = True

    # Save cache if state changes (or first run baseline is established)
    if state_changed or prev_status != current_status:
        save_current_status(current_status)
    else:
        print("[Cache] No state changes detected across all monitored sites. Cache remains unchanged.")


if __name__ == "__main__":
    check_uptime()
