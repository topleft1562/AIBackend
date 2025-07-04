import os
import requests
from urllib.parse import quote

GOOGLE_API_KEY = os.getenv("GOOGLE_KEY")
ROUTE_CACHE = {}

def _make_cache_key(city1, city2):
    city1 = city1.strip().title()
    city2 = city2.strip().title()
    return " | ".join(sorted([city1, city2]))

def get_route_info(origin: str, destination: str):
    origin = origin.strip().title()
    destination = destination.strip().title()
    key = _make_cache_key(origin, destination)

    if key in ROUTE_CACHE:
        return ROUTE_CACHE[key]

    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": quote(origin),
        "destinations": quote(destination),
        "key": GOOGLE_API_KEY,
        "units": "metric"
    }

    try:
        res = requests.get(url, params=params)
        data = res.json()
        if data.get("rows") and data["rows"][0]["elements"][0]["status"] == "OK":
            element = data["rows"][0]["elements"][0]
            distance_km = round(element["distance"]["value"] / 1000, 1)
            driving_time_hr = round(distance_km / 80.0, 2)  # << manual speed assumption

            result = {
                "distance_km": distance_km,
                "duration_hr": driving_time_hr
            }

            ROUTE_CACHE[key] = result
            return result
        else:
            print(f"[ROUTING ERROR] Failed for {origin} → {destination}")
            return None
    except Exception as e:
        print(f"[ROUTING EXCEPTION] {origin} → {destination}: {e}")
        return None

def get_trip_time_with_load(origin, destination):
    """
    Returns:
    {
      "distance_km": 278.4,
      "drive_hr": 3.48,
      "load_unload_hr": 3.0,
      "total_hr": 6.48
    }
    """
    info = get_route_info(origin, destination)
    if not info:
        return None
    return {
        "distance_km": info["distance_km"],
        "drive_hr": info["duration_hr"],
        "load_unload_hr": 3.0,
        "total_hr": round(info["duration_hr"] + 3.0, 2)
    }
