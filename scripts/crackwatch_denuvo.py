import os
import sys
import time
import requests
import feedparser

# Target RSS feed for r/CrackWatch
RSS_URL = "https://www.reddit.com/r/CrackWatch/new/.rss"
TARGET_FLAIR = "Denuvo release"

# Resolve directories dynamically relative to the script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "data", "crackwatch_seen.txt"))


def get_ntfy_url():
    """Resolves the namespaced ntfy URL from environment variables."""
    secret = os.environ.get("NTFY_CW_DENUVO_SECRET_LINK")
    if not secret:
        print("[Critical Error] NTFY_CW_DENUVO_SECRET_LINK environment variable is not set!")
        print("Please configure this in your GitHub Repository Secrets.")
        sys.exit(1)

    # Allow the secret to be either the full URL or just the topic name
    if secret.startswith("http://") or secret.startswith("https://"):
        return secret
    return f"https://ntfy.sh/{secret.strip('/')}"


def load_seen_posts():
    """Loads previously notified post URLs from the persistent text cache."""
    # Ensure the data directory exists
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)

    if not os.path.exists(CACHE_FILE):
        print(f"[Cache] No cache file found at '{CACHE_FILE}'. Initializing clean state.")
        return []

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            # Read non-empty lines
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"[Cache Error] Failed to read cache: {e}. Starting fresh.")
        return []


def save_seen_posts(seen_list, max_size=150):
    """Saves the updated seen post URLs back to the persistent text cache, pruning old history."""
    try:
        # Keep only the last `max_size` items to prevent the repo from ballooning
        pruned_list = seen_list[-max_size:]

        # Make sure parent directory exists
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)

        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            for link in pruned_list:
                f.write(f"{link}\n")
        print(f"[Cache] Successfully saved and pruned cache. Tracking {len(pruned_list)} items.")
    except Exception as e:
        print(f"[Cache Error] Failed to write cache: {e}")


def send_ntfy_alert(ntfy_url, title, link, flair):
    """Sends a high-priority push notification directly to the phone via ntfy."""
    headers = {
        "Title": "🔥 Denuvo Release Detected!",
        "Priority": "high",
        "Tags": "video_game,lock,rocket",
        "Click": link,  # Tapping the notification opens the Reddit thread directly
    }
    body_text = f"Post: {title}\nFlair Match: [{flair}]"

    try:
        response = requests.post(ntfy_url, data=body_text.encode("utf-8"), headers=headers, timeout=15)
        if response.status_code == 200:
            print(f"[Success] Push alert delivered for: {title[:45]}...")
        else:
            print(f"[Error] ntfy API returned status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[Network Error] Failed to connect to ntfy: {e}")


def run_tracker():
    print("=" * 60)
    print("Universal ntfy Automation: CrackWatch Denuvo Tracker")
    print("=" * 60)

    # Get and validate ntfy URL
    ntfy_url = get_ntfy_url()
    # Masking part of the secret for security logs
    masked_url = ntfy_url[:20] + "..." + ntfy_url[-8:] if len(ntfy_url) > 28 else "..."
    print(f"[Config] Target Push Endpoint: {masked_url}")
    print(f"[Config] Filtering strictly for flair: '{TARGET_FLAIR}'")

    # Load cache
    seen_posts = load_seen_posts()
    print(f"[Cache] Loaded {len(seen_posts)} seen posts from cache.")

    # Pull the RSS feed
    # Using an organic User-Agent to avoid Reddit blockages on generic cloud IPs
    headers = {"User-Agent": "script:crackwatch_denuvo_tracker:v1.0 (by /u/godofredddit)"}
    try:
        response = requests.get(RSS_URL, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"[RSS Fetch Error] Reddit responded with HTTP status {response.status_code}")
            sys.exit(0)  # Exit cleanly so the workflow runs successfully, but reports warning
    except Exception as e:
        print(f"[RSS Fetch Network Exception] {e}")
        sys.exit(0)

    feed = feedparser.parse(response.content)
    if not feed.entries:
        print("[RSS] Feed is empty or could not be parsed.")
        sys.exit(0)

    print(f"[RSS] Successfully fetched {len(feed.entries)} entries.")

    new_matches = 0
    updated_seen_posts = list(seen_posts)

    # Iterate through feed entries (reversed so oldest are processed first)
    for entry in reversed(feed.entries):
        entry_link = entry.link.strip()

        if entry_link in seen_posts:
            continue

        # Check if the post has the target flair
        is_match = False
        matched_flair = TARGET_FLAIR

        # Reddit RSS includes categories/flairs in entry.tags list
        if hasattr(entry, "tags"):
            for tag in entry.tags:
                tag_term = tag.get("term", "")
                if TARGET_FLAIR.lower() in tag_term.lower():
                    is_match = True
                    matched_flair = tag_term
                    break

        if is_match:
            print(f"[MATCH DETECTED] {entry.title} ({entry_link})")
            send_ntfy_alert(ntfy_url, entry.title, entry_link, matched_flair)
            new_matches += 1

        # Track that we have processed this post
        updated_seen_posts.append(entry_link)

    print(f"[Finished] Run complete. Found {new_matches} new match(es).")

    # Only write back if we actually saw new posts to prevent unnecessary commits
    if len(updated_seen_posts) > len(seen_posts):
        save_seen_posts(updated_seen_posts)
    else:
        print("[Cache] No new posts parsed. Cache remains unchanged.")


if __name__ == "__main__":
    run_tracker()
