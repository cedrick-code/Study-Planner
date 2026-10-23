import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from urllib.parse import quote as url_quote

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

QUOTE_TTL = 60 * 60 * 24  # 24 hours

# Used when the Quotable API is unreachable
FALLBACK_QUOTES = [
    ("It always seems impossible until it's done.", "Nelson Mandela"),
    ("The secret of getting ahead is getting started.", "Mark Twain"),
    ("It does not matter how slowly you go as long as you do not stop.", "Confucius"),
    ("Success is the sum of small efforts repeated day in and day out.", "Robert Collier"),
    ("Don't watch the clock; do what it does. Keep going.", "Sam Levenson"),
    ("The future depends on what you do today.", "Mahatma Gandhi"),
    ("You don't have to be great to start, but you have to start to be great.", "Zig Ziglar"),
    ("Well begun is half done.", "Aristotle"),
    ("The expert in anything was once a beginner.", "Helen Hayes"),
    ("Small deeds done are better than great deeds planned.", "Peter Marshall"),
    ("Quality is not an act, it is a habit.", "Aristotle"),
    ("What we learn with pleasure we never forget.", "Alfred Mercier"),
]

def _from_quotable():
    response = requests.get("https://api.quotable.io/random", timeout=3)
    response.raise_for_status()
    data = response.json()
    item = data[0] if isinstance(data, list) else data
    return {"text": item["content"], "author": item["author"], "source": "Quotable"}


def _from_dummyjson():
    response = requests.get(
        "https://dummyjson.com/quotes/random", timeout=settings.API_TIMEOUT
    )
    response.raise_for_status()
    item = response.json()
    return {"text": item["quote"], "author": item["author"], "source": "DummyJSON"}


def _from_zenquotes():
    response = requests.get(
        "https://zenquotes.io/api/random", timeout=settings.API_TIMEOUT
    )
    response.raise_for_status()
    item = response.json()[0]
    # When rate-limited, ZenQuotes sends a warning message as if it were a quote
    if item["a"] == "zenquotes.io":
        raise ValueError("ZenQuotes rate limit reached")
    return {"text": item["q"], "author": item["a"], "source": "ZenQuotes"}


# Tried in this order. Reorder the list to change priority.
QUOTE_PROVIDERS = [_from_quotable, _from_dummyjson, _from_zenquotes]


def get_quote(user):
    """Different quote per user, kept for 24 hours. Never raises."""
    cache_key = f"quote_user_{user.id}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    for provider in QUOTE_PROVIDERS:
        try:
            quote = provider()
        except (requests.RequestException, KeyError, IndexError, ValueError):
            continue  # this service failed, try the next one
        cache.set(cache_key, quote, QUOTE_TTL)
        return quote

    # Every service failed: use the built-in list (not cached, so we retry next visit)
    index = (timezone.localdate().toordinal() + user.id) % len(FALLBACK_QUOTES)
    text, author = FALLBACK_QUOTES[index]
    return {"text": text, "author": author, "source": "offline"}

DICTIONARY_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"


def get_definition(word):
    """Look up a word. Returns a dict, or {"error": "..."}. Never raises."""
    word = word.strip()
    if not word:
        return {"error": "Type a word to look up."}
    if " " in word:
        return {"error": "Please look up one word at a time."}

    try:
        response = requests.get(
            DICTIONARY_URL + url_quote(word), timeout=settings.API_TIMEOUT
        )
        if response.status_code == 404:
            return {"error": f'No definition found for "{word}". Check the spelling.'}
        response.raise_for_status()
        entry = response.json()[0]

        # Pronunciation text and audio can be in different places
        phonetic = entry.get("phonetic", "")
        audio = ""
        for item in entry.get("phonetics", []):
            phonetic = phonetic or item.get("text", "")
            if item.get("audio") and not audio:
                audio = item["audio"]
        if audio.startswith("//"):
            audio = "https:" + audio

        # Keep it short: up to 3 parts of speech, 2 definitions each
        meanings = []
        for meaning in entry.get("meanings", [])[:3]:
            definitions = [
                {"text": d["definition"], "example": d.get("example", "")}
                for d in meaning.get("definitions", [])[:2]
            ]
            meanings.append(
                {"part_of_speech": meaning.get("partOfSpeech", ""), "definitions": definitions}
            )

        return {
            "word": entry.get("word", word),
            "phonetic": phonetic,
            "audio": audio,
            "meanings": meanings,
        }

    except (requests.RequestException, KeyError, IndexError, ValueError):
        return {"error": "The dictionary is unavailable right now. The rest of the planner still works."}