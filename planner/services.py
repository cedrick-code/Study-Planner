import datetime
import hashlib
from urllib.parse import quote as url_quote

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .models import LocalHoliday


# =====================================================================
# 1. Weather: Open-Meteo
# =====================================================================

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


# =====================================================================
# 2. Daily quote: Quotable, with DummyJSON and ZenQuotes as backups
# =====================================================================

QUOTE_TTL = 60 * 60 * 24  # 24 hours

# Used when every quote service is unreachable
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


# =====================================================================
# 3. Word lookup: Free Dictionary API
# =====================================================================

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


# =====================================================================
# 4. Study topic: Wikipedia
# =====================================================================

WIKI_SEARCH_URL = "https://en.wikipedia.org/w/api.php"
WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/"
# Wikimedia asks apps to identify themselves
WIKI_HEADERS = {"User-Agent": "StudyPlanner/1.0 (student class project)"}
TOPIC_TTL = 60 * 60 * 24  # 24 hours

# Action words at the start of a task title that are not part of the topic
LEADING_WORDS = {
    "review", "study", "read", "finish", "complete", "prepare", "practice",
    "revise", "learn", "research", "summarize", "write", "do", "make",
    "about", "for", "the", "on",
}


def clean_topic(text):
    """'Review cell division' -> 'cell division'"""
    words = text.strip().split()
    while words and words[0].lower() in LEADING_WORDS:
        words.pop(0)
    return " ".join(words) or text.strip()


def get_topic(query):
    """Find a Wikipedia summary for a topic. Returns a dict, or {"error": "..."}."""
    query = clean_topic(query)
    if not query:
        return {"error": "Type a topic to look up."}

    cache_key = "topic_" + hashlib.md5(query.lower().encode()).hexdigest()
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        # Step 1: find the best matching article title
        search = requests.get(
            WIKI_SEARCH_URL,
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": 1,
                "format": "json",
            },
            headers=WIKI_HEADERS,
            timeout=settings.API_TIMEOUT,
        )
        search.raise_for_status()
        hits = search.json()["query"]["search"]
        if not hits:
            return {"error": f'No article found for "{query}". Try a different topic.'}
        title = hits[0]["title"]

        # Step 2: get that article's short summary
        summary = requests.get(
            WIKI_SUMMARY_URL + url_quote(title.replace(" ", "_"), safe=""),
            headers=WIKI_HEADERS,
            timeout=settings.API_TIMEOUT,
        )
        summary.raise_for_status()
        data = summary.json()

        if data.get("type") == "disambiguation":
            return {"error": f'"{title}" has several meanings. Try a more specific topic.'}

        topic = {
            "title": data["title"],
            "description": data.get("description", ""),
            "extract": data["extract"],
            "image": data.get("thumbnail", {}).get("source", ""),
            "url": data["content_urls"]["desktop"]["page"],
        }
        cache.set(cache_key, topic, TOPIC_TTL)
        return topic

    except (requests.RequestException, KeyError, IndexError, ValueError):
        return {"error": "Wikipedia is unavailable right now. The rest of the planner still works."}


# =====================================================================
# 5. Holidays: Nager.Date (Calendarific as backup) + Iligan days from the database
# =====================================================================

HOLIDAY_COUNTRY = "PH"
HOLIDAY_TTL = 60 * 60 * 24 * 7  # 7 days: holidays rarely change
NAGER_URL = "https://date.nager.at/api/v3/PublicHolidays/{year}/{country}"
CALENDARIFIC_URL = "https://calendarific.com/api/v2/holidays"


def _holidays_nager(year, country):
    response = requests.get(
        NAGER_URL.format(year=year, country=country), timeout=settings.API_TIMEOUT
    )
    response.raise_for_status()  # a 404 means this country is not covered
    data = response.json()
    if not data:
        raise ValueError("Nager.Date has no data for this country")
    items = [
        {"date": datetime.date.fromisoformat(h["date"]), "name": h["name"]}
        for h in data
    ]
    return {"items": items, "source": "Nager.Date"}


def _holidays_calendarific(year, country):
    if not settings.CALENDARIFIC_API_KEY:
        raise ValueError("No Calendarific key set")
    response = requests.get(
        CALENDARIFIC_URL,
        params={
            "api_key": settings.CALENDARIFIC_API_KEY,
            "country": country,
            "year": year,
        },
        timeout=settings.API_TIMEOUT,
    )
    response.raise_for_status()
    items = []
    for h in response.json()["response"]["holidays"]:
        types = h.get("type") or []
        if types and not any("holiday" in t.lower() for t in types):
            continue  # skip observances and seasons
        items.append(
            {"date": datetime.date.fromisoformat(h["date"]["iso"][:10]), "name": h["name"]}
        )
    if not items:
        raise ValueError("Calendarific returned no holidays")
    return {"items": items, "source": "Calendarific"}


def get_national_holidays(year):
    """Philippine national holidays for a year, or None if every service failed."""
    cache_key = f"holidays_{HOLIDAY_COUNTRY}_{year}"
    fail_key = cache_key + "_failed"

    cached = cache.get(cache_key)
    if cached:
        return cached
    if cache.get(fail_key):
        return None  # failed a moment ago; do not make the page wait again

    for provider in (_holidays_nager, _holidays_calendarific):
        try:
            result = provider(year, HOLIDAY_COUNTRY)
        except (requests.RequestException, KeyError, IndexError, ValueError):
            continue
        cache.set(cache_key, result, HOLIDAY_TTL)
        return result

    cache.set(fail_key, True, 60 * 5)  # remember the failure for 5 minutes
    return None


def get_holidays(start, end):
    """National holidays (API) plus Iligan days (database) between two dates."""
    items, sources, failed = [], set(), False

    for year in range(start.year, end.year + 1):
        national = get_national_holidays(year)
        if national is None:
            failed = True
            continue
        sources.add(national["source"])
        items += [
            {"date": h["date"], "name": h["name"], "local": False}
            for h in national["items"]
        ]

    for h in LocalHoliday.objects.filter(date__range=(start, end)):
        items.append({"date": h.date, "name": h.name, "local": True})

    items = [i for i in items if start <= i["date"] <= end]
    items.sort(key=lambda i: i["date"])
    return {"items": items, "sources": sorted(sources), "failed": failed}


def holiday_on(day):
    """The holiday name(s) on one date, or an empty string."""
    return " / ".join(i["name"] for i in get_holidays(day, day)["items"])