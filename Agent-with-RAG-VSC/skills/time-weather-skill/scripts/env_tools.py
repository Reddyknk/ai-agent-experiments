from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import requests


def get_time_for_city(city: str) -> dict[str, Any]:
    return {
        "city": city,
        "timezone": "UTC",
        "local_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }


def get_weather_for_city(city: str) -> dict[str, Any]:
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "en"},
            timeout=10,
        )
        geo.raise_for_status()
        data = geo.json()
        if not data.get("results"):
            return {"city": city, "weather": "No geographic result found."}
        place = data["results"][0]
        lat = place["latitude"]
        lon = place["longitude"]
        weather = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weather_code",
                "timezone": "auto",
            },
            timeout=10,
        )
        weather.raise_for_status()
        result = weather.json()
        return {
            "city": city,
            "weather": result.get("current", {}),
        }
    except Exception as exc:
        return {"city": city, "weather": f"Unable to fetch weather: {exc}"}


if __name__ == "__main__":
    print(json.dumps(get_weather_for_city("Paris"), indent=2))
