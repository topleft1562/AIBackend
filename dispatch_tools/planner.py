import openai
import os
from typing import List, Dict
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
import time

geolocator = Nominatim(user_agent="dispatch_planner")

# Estimate travel time at 80km/h
KM_PER_HOUR = 80
LOAD_UNLOAD_HOURS = 1.5  # For both pickup and dropoff
MAX_HOURS = 70  # Canadian DOT 70-hour limit

location_cache = {}

def get_coordinates(location_name: str):
    if location_name in location_cache:
        return location_cache[location_name]
    try:
        location = geolocator.geocode(location_name)
        if location:
            coords = (location.latitude, location.longitude)
            location_cache[location_name] = coords
            time.sleep(1)  # avoid API rate limits
            return coords
    except Exception:
        return None
    return None

def estimate_drive_hours(pickup: str, dropoff: str):
    coords1 = get_coordinates(pickup)
    coords2 = get_coordinates(dropoff)
    if coords1 and coords2:
        km = geodesic(coords1, coords2).km
        return km, km / KM_PER_HOUR + LOAD_UNLOAD_HOURS
    return 0, 0

def generate_simple_dispatch_plan(drivers: List[Dict], loads: List[Dict]) -> str:
    if not drivers:
        return "No drivers provided."
    if not loads:
        return "No loads provided."

    plan = []
    load_index = 0

    for i, driver in enumerate(drivers):
        name = driver.get("name", f"Driver {i+1}")
        location = driver.get("location", "Unknown")
        start_location = location
        assigned = []
        total_loaded_km = 0
        total_empty_km = 0
        total_hours = 0

        while load_index < len(loads):
            load = loads[load_index]
            km_empty, hours_empty = estimate_drive_hours(location, load['pickupCity'])
            km_loaded, hours_loaded = estimate_drive_hours(load['pickupCity'], load['dropoffCity'])

            projected_hours = total_hours + hours_empty + hours_loaded

            if projected_hours > MAX_HOURS:
                break

            total_empty_km += km_empty
            total_loaded_km += km_loaded
            total_hours += hours_empty + hours_loaded

            assigned.append(f"{load['pickupCity']} → {load['dropoffCity']}")
            location = load['dropoffCity']
            load_index += 1

        total_km = total_empty_km + total_loaded_km
        loaded_pct = round(100 * total_loaded_km / total_km) if total_km > 0 else 0

        if assigned:
            plan.append(
                f"• {name} ({start_location}): {' → '.join(assigned)} "
                f"(Total: {int(total_km)}km — {int(total_loaded_km)} loaded / {int(total_empty_km)} empty, "
                f"{round(total_hours, 1)}h, {loaded_pct}% loaded, {round(100 * total_hours / MAX_HOURS)}% of HOS used)"
            )
        else:
            plan.append(f"• {name} ({location}): No loads assigned (idle/reset)")

    return "\n".join(plan)
