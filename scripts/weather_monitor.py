import os
import sys
import requests
from email.header import Header

# Reconfigure stdout to use UTF-8 to prevent UnicodeEncodeErrors on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Default coordinates for Bengaluru, India (IST timezone)
DEFAULT_LAT = "12.925413"
DEFAULT_LON = "77.737527"
DEFAULT_CITY = "Bengaluru"

# WMO Weather interpretation codes (WW) to emojis and tags
WMO_WEATHER_CODES = {
    0: ("☀️ Clear sky", "sunny"),
    1: ("🌤️ Mainly clear", "sun_behind_small_cloud"),
    2: ("⛅ Partly cloudy", "sun_behind_cloud"),
    3: ("☁️ Overcast", "cloud"),
    45: ("🌫️ Fog", "fog"),
    48: ("🌫️ Depositing rime fog", "fog"),
    51: ("🌧️ Light drizzle", "droplet"),
    53: ("🌧️ Moderate drizzle", "droplet"),
    55: ("🌧️ Dense drizzle", "sweat_drops"),
    56: ("🌧️ Light freezing drizzle", "droplet"),
    57: ("🌧️ Dense freezing drizzle", "sweat_drops"),
    61: ("🌧️ Slight rain", "cloud_with_rain"),
    63: ("🌧️ Moderate rain", "cloud_with_rain"),
    65: ("🌧️ Heavy rain", "thunder_cloud_and_rain"),
    66: ("🌧️ Light freezing rain", "cloud_with_rain"),
    67: ("🌧️ Heavy freezing rain", "thunder_cloud_and_rain"),
    71: ("❄️ Slight snow fall", "snowflake"),
    73: ("❄️ Moderate snow fall", "snowflake"),
    75: ("❄️ Heavy snow fall", "snowflake"),
    77: ("❄️ Snow grains", "snowflake"),
    80: ("🌦️ Slight rain showers", "cloud_with_rain"),
    81: ("🌦️ Moderate rain showers", "cloud_with_rain"),
    82: ("🌦️ Violent rain showers", "thunder_cloud_and_rain"),
    85: ("❄️ Slight snow showers", "snowflake"),
    86: ("❄️ Heavy snow showers", "snowflake"),
    95: ("⛈️ Thunderstorm", "lightning_bolt"),
    96: ("⛈️ Thunderstorm with slight hail", "lightning_bolt"),
    99: ("⛈️ Thunderstorm with heavy hail", "lightning_bolt"),
}


def get_ntfy_url():
    """Resolves the namespaced ntfy URL from environment variables."""
    secret = os.environ.get("NTFY_WEATHER_SECRET_LINK") or os.environ.get("NTFY_UPTIME_SECRET_LINK")
    if not secret:
        print("[Critical Error] Neither NTFY_WEATHER_SECRET_LINK nor NTFY_UPTIME_SECRET_LINK is set!")
        print("Please configure this in your environment or GitHub Secrets.")
        sys.exit(1)

    if secret.startswith("http://") or secret.startswith("https://"):
        return secret
    return f"https://ntfy.sh/{secret.strip('/')}"


def fetch_weather():
    lat = os.environ.get("WEATHER_LATITUDE", DEFAULT_LAT)
    lon = os.environ.get("WEATHER_LONGITUDE", DEFAULT_LON)
    city = os.environ.get("WEATHER_CITY_NAME", DEFAULT_CITY)

    print("=" * 60)
    print(f"🌌 Daily Morning Weather Monitor: {city}")
    print("=" * 60)
    print(f"[Config] Latitude: {lat}, Longitude: {lon}")

    # Build Open-Meteo URL
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,precipitation_sum,precipitation_probability_max",
        "timezone": "auto"
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code != 200:
            print(f"[API Error] Open-Meteo returned status {response.status_code}: {response.text}")
            sys.exit(1)

        data = response.json()
        return data, city
    except Exception as e:
        print(f"[Network Error] Failed to fetch weather data: {e}")
        sys.exit(1)


def send_weather_report():
    ntfy_url = get_ntfy_url()
    masked_url = ntfy_url[:20] + "..." + ntfy_url[-8:] if len(ntfy_url) > 28 else "..."
    print(f"[Config] Target Push Endpoint: {masked_url}")

    data, city = fetch_weather()

    # Extract Current Data
    current = data.get("current", {})
    temp = current.get("temperature_2m", 0.0)
    feels_like = current.get("apparent_temperature", 0.0)
    humidity = current.get("relative_humidity_2m", 0)
    precip = current.get("precipitation", 0.0)
    weather_code = current.get("weather_code", 0)
    wind = current.get("wind_speed_10m", 0.0)

    # Extract Daily/Forecast Data (Today)
    daily = data.get("daily", {})
    max_temp = daily.get("temperature_2m_max", [0.0])[0]
    min_temp = daily.get("temperature_2m_min", [0.0])[0]
    rain_prob = daily.get("precipitation_probability_max", [0])[0]

    # Map weather code to details
    weather_desc, tag_icon = WMO_WEATHER_CODES.get(weather_code, ("🌡️ Unknown weather", "cyclone"))

    # Select greeting emoji based on weather
    greeting_emoji = "🌅"
    if "rain" in weather_desc.lower() or "drizzle" in weather_desc.lower():
        greeting_emoji = "🌧️"
    elif "thunderstorm" in weather_desc.lower():
        greeting_emoji = "⛈️"
    elif "clear" in weather_desc.lower():
        greeting_emoji = "☀️"

    # Build Premium Markdown Report
    markdown_body = f"### {greeting_emoji} Good Morning from **{city}**!\n"
    markdown_body += "Here is your daily weather forecast digest:\n\n"
    
    markdown_body += f"🌡️ **Current Temp:** {temp}°C (Feels like **{feels_like}°C**)\n"
    markdown_body += f"📊 **Condition:** {weather_desc}\n\n"
    
    markdown_body += "📋 **Details:**\n"
    markdown_body += f"• 💧 **Humidity:** {humidity}%\n"
    markdown_body += f"• 💨 **Wind Speed:** {wind} km/h\n"
    markdown_body += f"• 🌧️ **Precipitation Today:** {precip} mm\n\n"
    
    markdown_body += "📅 **Today's Outlook:**\n"
    markdown_body += f"• 📈 **High / Low:** {max_temp}°C / {min_temp}°C\n"
    markdown_body += f"• ☔ **Precipitation Prob:** {rain_prob}%\n\n"
    
    markdown_body += "*Synced via GitHub Actions & Open-Meteo API*"

    # Construct ntfy alert headers
    title = f"🌦️ Weather Report - {city}"
    headers = {
        "Title": Header(title, 'utf-8').encode(),
        "Priority": "default",
        "Tags": f"calendar,globe_with_meridians,{tag_icon}",
        "X-Markdown": "yes",
    }

    try:
        response = requests.post(ntfy_url, data=markdown_body.encode("utf-8"), headers=headers, timeout=15)
        if response.status_code == 200:
            print(f"[Success] Weather digest successfully sent for {city}!")
        else:
            print(f"[Error] ntfy API returned error: {response.text}")
    except Exception as e:
        print(f"[Network Error] Failed to connect to ntfy: {e}")


def load_local_env():
    """Loads environment variables from local.env located in the repository root."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.abspath(os.path.join(script_dir, "..", "local.env"))
    
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        os.environ[key.strip()] = val.strip().strip('"').strip("'")
            print("[Env] Loaded local settings from local.env")
        except Exception as e:
            print(f"[Warning] Failed to read 'local.env': {e}")


if __name__ == "__main__":
    load_local_env()
    send_weather_report()
