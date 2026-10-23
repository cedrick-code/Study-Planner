import requests
from django.conf import settings

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Open-Meteo returns a numeric "weather code". This translates it to text.
WEATHER_CODES = {
    0: ("Clear sky", "☀️"),
    1: ("Mainly clear", "🌤️"),
    2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Fog", "🌫️"),
    48: ("Fog", "🌫️"),
    51: ("Light drizzle", "🌦️"),
    53: ("Drizzle", "🌦️"),
    55: ("Heavy drizzle", "🌦️"),
    61: ("Light rain", "🌧️"),
    63: ("Rain", "🌧️"),
    65: ("Heavy rain", "🌧️"),
    80: ("Rain showers", "🌦️"),
    81: ("Rain showers", "🌦️"),
    82: ("Violent showers", "⛈️"),
    95: ("Thunderstorm", "⛈️"),
    96: ("Thunderstorm with hail", "⛈️"),
    99: ("Thunderstorm with hail", "⛈️"),
}

RAINY_CODES = {51, 53, 55, 61, 63, 65, 80, 81, 82, 95, 96, 99}


def get_weather(city):
    """Return a dict with weather info, or {"error": "..."} if anything fails."""
    try:
        # Step 1: city name -> coordinates
        geo = requests.get(
            GEOCODE_URL,
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=settings.API_TIMEOUT,
        )
        geo.raise_for_status()
        results = geo.json().get("results")
        if not results:
            return {"error": f'Could not find a place called "{city}".'}

        place = results[0]

        # Step 2: coordinates -> current weather
        forecast = requests.get(
            FORECAST_URL,
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                "timezone": "auto",
            },
            timeout=settings.API_TIMEOUT,
        )
        forecast.raise_for_status()
        current = forecast.json()["current"]

        code = current["weather_code"]
        description, icon = WEATHER_CODES.get(code, ("Unknown", "🌡️"))

        return {
            "place": f'{place["name"]}, {place.get("country", "")}'.strip(", "),
            "temperature": round(current["temperature_2m"]),
            "humidity": current["relative_humidity_2m"],
            "wind": round(current["wind_speed_10m"]),
            "description": description,
            "icon": icon,
            "is_rainy": code in RAINY_CODES,
        }

    except (requests.RequestException, KeyError, ValueError):
        return {"error": "Weather is unavailable right now. The rest of the planner still works."}