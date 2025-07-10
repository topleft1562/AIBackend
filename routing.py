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

def build_route_matrix(loads, drivers):
    """
    Build a route matrix using Google Maps API from all relevant city pairs.
    """
    unique_pairs = set()

    # Load-based pairs
    for load in loads:
        pickup = load["pickup"]["city"]
        dropoff = load["dropoff"]["city"]
        route_points = load.get("routePoints", [])

        cities = [pickup] + route_points + [dropoff]
        for i in range(len(cities) - 1):
            unique_pairs.add(_make_cache_key(cities[i], cities[i+1]))

    # Driver repositioning: current → pickup, dropoff → home_base
    for driver in drivers:
        for load in loads:
            unique_pairs.add(_make_cache_key(driver["location"], load["pickup"]["city"]))
            unique_pairs.add(_make_cache_key(load["dropoff"]["city"], driver["home_base"]))

    # Add inter-load repositioning (dropoff → pickup)
    for i in range(len(loads)):
        for j in range(len(loads)):
            if i != j:
                unique_pairs.add(_make_cache_key(loads[i]["dropoff"]["city"], loads[j]["pickup"]["city"]))

    # Build the matrix
    route_matrix = {}
    for key in unique_pairs:
        city1, city2 = key.split(" | ")
        info = get_route_info(city1, city2)
        if info:
            route_matrix[key] = info

    return route_matrix

def get_loaded_distance_with_routepoints(pickup, route_points, dropoff):
    """
    Compute the total distance from pickup → route_point(s) → dropoff.
    Falls back to pickup → dropoff if no route points.
    """
    if not route_points:
        info = get_route_info(pickup, dropoff)
        return info["distance_km"] if info else 0

    points = [pickup] + route_points + [dropoff]
    total_km = 0
    for i in range(len(points) - 1):
        info = get_route_info(points[i], points[i + 1])
        if info:
            total_km += info["distance_km"]
        else:
            print(f"[ROUTEPOINT ERROR] Missing distance from {points[i]} → {points[i+1]}")
    return round(total_km, 1)

def get_route_segments(pickup, route_points, dropoff):
    points = [pickup] + route_points + [dropoff]
    return [(points[i], points[i+1]) for i in range(len(points) - 1)]