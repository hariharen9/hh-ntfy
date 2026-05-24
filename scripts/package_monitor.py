import os
import sys
import json
import re
from datetime import datetime, timezone, timedelta
import requests

# Reconfigure stdout to use UTF-8 to prevent UnicodeEncodeErrors on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Target personal packages to monitor download statistics
PACKAGES = [
    {"name": "Kessler CLI", "platform": "npm", "identifier": "kessler-cli"},
    {"name": "Kessler VSCode", "platform": "vscode", "identifier": "hariharen.kessler-vscode"},
    {"name": "Localseek VSCode", "platform": "vscode", "identifier": "Hariharen.localseek"},
    {"name": "PEG-this", "platform": "pypi", "identifier": "peg-this"},
    {"name": "Enhance-this", "platform": "pypi", "identifier": "enhance-this"},
    {"name": "LamaCLI", "platform": "npm", "identifier": "lamacli"},
]

# Resolve directories dynamically relative to the script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "data", "package_status.json"))


def get_ntfy_url():
    """Resolves the namespaced ntfy URL from environment variables."""
    secret = os.environ.get("NTFY_PACKAGE_SECRET_LINK") or os.environ.get("NTFY_UPTIME_SECRET_LINK")
    if not secret:
        print("[Critical Error] Neither NTFY_PACKAGE_SECRET_LINK nor NTFY_UPTIME_SECRET_LINK environment variable is set!")
        print("Please configure this in your GitHub Repository Secrets.")
        sys.exit(1)

    if secret.startswith("http://") or secret.startswith("https://"):
        return secret
    return f"https://ntfy.sh/{secret.strip('/')}"


def load_previous_stats():
    """Loads the last recorded package statistics from the persistent JSON cache."""
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    if not os.path.exists(CACHE_FILE):
        print(f"[Cache] No package cache file found. Initializing clean baseline.")
        return {}

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content or content == "{}":
                return {}
            return json.loads(content)
    except Exception as e:
        print(f"[Cache Error] Failed to read cache: {e}. Starting fresh.")
        return {}


def save_current_stats(stats_map):
    """Saves the current package statistics to the persistent JSON cache."""
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(stats_map, f, indent=2, ensure_ascii=False)
        print(f"[Cache] Successfully updated package statistics cache.")
    except Exception as e:
        print(f"[Cache Error] Failed to write statistics cache: {e}")


def fetch_npm_stats(identifier):
    """Fetches download statistics and latest version from npm registry."""
    encoded_id = identifier.replace("/", "%2F")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    one_year_ago = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")
    
    headers = {"User-Agent": "Mozilla/5.0 PackageMonitor/1.0 (Venn clone; client:hariharen)"}
    
    try:
        day_res = requests.get(f"https://api.npmjs.org/downloads/point/last-day/{encoded_id}", headers=headers, timeout=10)
        week_res = requests.get(f"https://api.npmjs.org/downloads/point/last-week/{encoded_id}", headers=headers, timeout=10)
        month_res = requests.get(f"https://api.npmjs.org/downloads/point/last-month/{encoded_id}", headers=headers, timeout=10)
        year_res = requests.get(f"https://api.npmjs.org/downloads/point/{one_year_ago}:{today}/{encoded_id}", headers=headers, timeout=10)
        info_res = requests.get(f"https://registry.npmjs.org/{encoded_id}/latest", headers=headers, timeout=10)
        
        day_downloads = day_res.json().get("downloads", 0) if day_res.status_code == 200 else 0
        week_downloads = week_res.json().get("downloads", 0) if week_res.status_code == 200 else 0
        month_downloads = month_res.json().get("downloads", 0) if month_res.status_code == 200 else 0
        year_downloads = year_res.json().get("downloads", 0) if year_res.status_code == 200 else 0
        
        version = None
        if info_res.status_code == 200:
            version = info_res.json().get("version")
            
        return {
            "daily": day_downloads,
            "weekly": week_downloads,
            "monthly": month_downloads,
            "yearly": year_downloads,
            "total": None,
            "version": version
        }
    except Exception as e:
        print(f"[NPM Fetch Error] {identifier}: {e}")
        return None


def fetch_pypi_stats(identifier):
    """Fetches download statistics, lifetime counts, and version from PyPI & pepy.tech."""
    headers = {"User-Agent": "Mozilla/5.0 PackageMonitor/1.0 (Venn clone; client:hariharen)"}
    
    try:
        stats_res = requests.get(f"https://pypistats.org/api/packages/{identifier}/recent", headers=headers, timeout=10)
        meta_res = requests.get(f"https://pypi.org/pypi/{identifier}/json", headers=headers, timeout=10)
        pepy_res = requests.get(f"https://static.pepy.tech/badge/{identifier}", headers=headers, timeout=10)
        
        daily = weekly = monthly = 0
        if stats_res.status_code == 200:
            stats_data = stats_res.json().get("data", {})
            daily = stats_data.get("last_day", 0)
            weekly = stats_data.get("last_week", 0)
            monthly = stats_data.get("last_month", 0)
            
        version = None
        if meta_res.status_code == 200:
            version = meta_res.json().get("info", {}).get("version")
            
        total = None
        if pepy_res.status_code == 200:
            svg_text = pepy_res.text
            matches = re.findall(r'<text[^>]*>([^<]+)</text>', svg_text)
            if matches:
                val_str = matches[-1]
                match = re.match(r"^([\d.]+)([kMGT]?)$", val_str, re.IGNORECASE)
                if match:
                    num = float(match.group(1))
                    suffix = match.group(2).upper()
                    if suffix == 'K':
                        total = int(num * 1000)
                    elif suffix == 'M':
                        total = int(num * 1000000)
                    elif suffix == 'G':
                        total = int(num * 1000000000)
                    else:
                        total = int(num)
                        
        return {
            "daily": daily,
            "weekly": weekly,
            "monthly": monthly,
            "yearly": None,
            "total": total,
            "version": version
        }
    except Exception as e:
        print(f"[PyPI Fetch Error] {identifier}: {e}")
        return None


def fetch_vscode_stats(identifier):
    """Fetches total installs, downloads, updates, and latest version from VS Code Marketplace."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json; charset=utf-8; api-version=3.0-preview.1",
        "User-Agent": "Mozilla/5.0 PackageMonitor/1.0 (Venn clone; client:hariharen)",
    }
    payload = {
        "filters": [{
            "criteria": [{"filterType": 7, "value": identifier}],
            "pageSize": 1,
        }],
        "assetTypes": [],
        "flags": 914,
    }
    
    try:
        res = requests.post(
            "https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery",
            json=payload,
            headers=headers,
            timeout=10
        )
        if res.status_code == 200:
            data = res.json()
            results = data.get("results", [])
            if results and results[0].get("extensions"):
                ext = results[0]["extensions"][0]
                stats = ext.get("statistics", [])
                
                def get_stat(name):
                    for s in stats:
                        if s.get("statisticName") == name:
                            return s.get("value", 0)
                    return 0
                
                installs = int(round(get_stat("install")))
                total_downloads = int(round(get_stat("downloadCount")))
                version = ext.get("versions", [{}])[0].get("version")
                
                return {
                    "daily": None,  # Not provided, will be calculated as delta
                    "weekly": None,
                    "monthly": None,
                    "yearly": None,
                    "total": installs,  # Installs map to total lifetime
                    "total_downloads": total_downloads,
                    "version": version
                }
        return None
    except Exception as e:
        print(f"[VSCode Fetch Error] {identifier}: {e}")
        return None


def format_number(num):
    """Helper to format large numbers cleanly."""
    if num is None:
        return "—"
    if num >= 1000000:
        return f"{num / 1000000:.1f}M"
    if num >= 1000:
        return f"{num / 1000:.1f}K"
    return f"{num:,}"


def format_delta(delta):
    """Helper to format growth/decline strings."""
    if delta is None or delta == 0:
        return "stable"
    if delta > 0:
        return f"+{delta:,} ▲"
    return f"{delta:,} ▼"


def monitor_packages():
    print("=" * 60)
    print("🌌 Personal Command Center: Package Download Statistics")
    print("=" * 60)

    ntfy_url = get_ntfy_url()
    
    prev_stats = load_previous_stats()
    current_stats = {}
    
    report_items = []
    
    for pkg in PACKAGES:
        name = pkg["name"]
        platform = pkg["platform"]
        identifier = pkg["identifier"]
        cache_key = f"{platform}:{identifier}"
        
        print(f"[Monitor] Fetching {name} ({identifier} on {platform.upper()})...")
        
        stats = None
        if platform == "npm":
            stats = fetch_npm_stats(identifier)
        elif platform == "pypi":
            stats = fetch_pypi_stats(identifier)
        elif platform == "vscode":
            stats = fetch_vscode_stats(identifier)
            
        if not stats:
            print(f"[Skip] Could not fetch data for {name}. Maintaining old state.")
            current_stats[cache_key] = prev_stats.get(cache_key)
            continue
            
        prev_pkg = prev_stats.get(cache_key) or {}
        
        # Calculate Deltas
        daily_count = stats["daily"]
        daily_delta_str = ""
        total_delta_str = ""
        
        if platform in ["npm", "pypi"]:
            # Compare current daily downloads against yesterday's daily downloads
            prev_daily = prev_pkg.get("daily")
            if prev_daily is not None and daily_count is not None:
                delta = daily_count - prev_daily
                daily_delta_str = f" ({format_delta(delta)})"
            
            # For PyPI, we can also compare total downloads
            if platform == "pypi":
                prev_total = prev_pkg.get("total")
                current_total = stats["total"]
                if prev_total is not None and current_total is not None:
                    t_delta = current_total - prev_total
                    total_delta_str = f" ({format_delta(t_delta)})"
                    
        elif platform == "vscode":
            # VS Code does not provide daily stats natively, so we calculate it ourselves
            # New daily installs = today's total installs - yesterday's total installs
            prev_total_installs = prev_pkg.get("total")
            current_total_installs = stats["total"]
            
            prev_total_downloads = prev_pkg.get("total_downloads")
            current_total_downloads = stats["total_downloads"]
            
            calculated_daily_installs = 0
            calculated_daily_downloads = 0
            
            if prev_total_installs is not None and current_total_installs is not None:
                calculated_daily_installs = max(0, current_total_installs - prev_total_installs)
            if prev_total_downloads is not None and current_total_downloads is not None:
                calculated_daily_downloads = max(0, current_total_downloads - prev_total_downloads)
                
            stats["daily"] = calculated_daily_installs
            daily_count = calculated_daily_installs
            daily_delta_str = f" (+{calculated_daily_installs:,} installs today)"
            total_delta_str = f" (+{calculated_daily_downloads:,} downloads today)"
            
        # Store for cache
        current_stats[cache_key] = stats
        
        # Format registry badge
        badge = "📦" if platform == "npm" else "🐍" if platform == "pypi" else "💎"
        
        # Build Markdown Segment
        item_md = f"{badge} **{name}** (`{identifier}`)\n"
        if platform in ["npm", "pypi"]:
            item_md += f"• **Daily:** {format_number(daily_count)}{daily_delta_str}\n"
            if stats["weekly"] is not None or stats["monthly"] is not None:
                item_md += f"• **W / M:** {format_number(stats['weekly'])} / {format_number(stats['monthly'])}"
                if platform == "npm" and stats.get("yearly"):
                    item_md += f" | **Y:** {format_number(stats['yearly'])}"
                item_md += "\n"
            if stats["total"] is not None:
                item_md += f"• **Lifetime:** {format_number(stats['total'])}{total_delta_str}\n"
        elif platform == "vscode":
            item_md += f"• **Installs Today:** {daily_delta_str}\n"
            item_md += f"• **Downloads Today:** {total_delta_str}\n"
            item_md += f"• **Total Installs / Downloads:** {format_number(stats['total'])} / {format_number(stats['total_downloads'])}\n"
            
        if stats.get("version"):
            item_md += f"• **Version:** `v{stats['version']}`\n"
            
        report_items.append(item_md)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_title = f"Daily Download Statistics - {date_str}"
    
    markdown_body = f"### 🌌 Command Center Digest\n"
    markdown_body += "Here is your daily package download progress report:\n\n"
    markdown_body += "\n---\n".join(report_items)
    markdown_body += "\n\n*Synced via GitHub Actions & cron-job.org*"

    # Send ntfy Notification
    headers = {
        "Title": report_title,
        "Priority": "default",
        "Tags": "chart_with_upwards_trend,bar_chart,package",
        "X-Markdown": "yes",
    }
    
    try:
        response = requests.post(ntfy_url, data=markdown_body.encode("utf-8"), headers=headers, timeout=15)
        if response.status_code == 200:
            print("[Success] Daily stats report dispatched via ntfy!")
        else:
            print(f"[Error] ntfy API returned error: {response.text}")
    except Exception as e:
        print(f"[Network Error] Failed to connect to ntfy: {e}")

    # Save to persistent storage
    save_current_stats(current_stats)


if __name__ == "__main__":
    monitor_packages()
