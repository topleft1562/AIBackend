from typing import List, Dict
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
import time

geolocator = Nominatim(user_agent="dispatch_planner")

KM_PER_HOUR = 80
LOAD_UNLOAD_HOURS = 1.5
MAX_HOURS = 70
WARNING_HOURS = 55

location_cache = {}

def get_coordinates(location_name: str):
    if location_name in location_cache:
        return location_cache[location_name]
    try:
        location = geolocator.geocode(location_name)
        if location:
            coords = (location.latitude, location.longitude)
            location_cache[location_name] = coords
            time.sleep(1)
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

def auto_dispatch_plan(loads: List[Dict], base_location: str = "Brandon, MB") -> str:
    if not loads:
        return "No loads provided."

    drivers = []
    plan = []

    for load in loads:
        assigned = False
        for driver in drivers:
            if driver["hours"] >= MAX_HOURS:
                continue

            empty_km, empty_hours = estimate_drive_hours(driver["current_location"], load['pickupCity'])
            loaded_km, loaded_hours = estimate_drive_hours(load['pickupCity'], load['dropoffCity'])
            return_km, return_hours = estimate_drive_hours(load['dropoffCity'], base_location)

            projected_hours = driver["hours"] + empty_hours + loaded_hours + return_hours

            if projected_hours <= MAX_HOURS:
                driver["empty_km"] += empty_km
                driver["loaded_km"] += loaded_km
                driver["hours"] += empty_hours + loaded_hours
                driver["current_location"] = load['dropoffCity']
                driver["assigned"].append(f"{load['pickupCity']} → {load['dropoffCity']}")
                assigned = True
                break

        if not assigned:
            name = f"Driver {len(drivers)+1}"
            km_loaded, hrs_loaded = estimate_drive_hours(load['pickupCity'], load['dropoffCity'])
            km_empty, hrs_empty = estimate_drive_hours(base_location, load['pickupCity'])
            drivers.append({
                "name": name,
                "start_location": base_location,
                "current_location": load['dropoffCity'],
                "assigned": [f"{load['pickupCity']} → {load['dropoffCity']}"],
                "loaded_km": km_loaded,
                "empty_km": km_empty,
                "hours": hrs_loaded + hrs_empty
            })

    for driver in drivers:
        if driver["current_location"] != base_location:
            return_km, return_hours = estimate_drive_hours(driver["current_location"], base_location)
            driver["empty_km"] += return_km
            driver["hours"] += return_hours
            driver["assigned"].append(f"return → {base_location}")
            driver["current_location"] = base_location

        total_km = driver["loaded_km"] + driver["empty_km"]
        loaded_pct = round(100 * driver["loaded_km"] / total_km) if total_km > 0 else 0
        hos_used = round(100 * driver["hours"] / MAX_HOURS)

        plan.append(
            f"• {driver['name']} ({base_location}): {' → '.join(driver['assigned'])} "
            f"(Total: {int(total_km)}km — {int(driver['loaded_km'])} loaded / {int(driver['empty_km'])} empty, "
            f"{round(driver['hours'], 1)}h, {loaded_pct}% loaded, {hos_used}% of HOS used)"
        )

    plan.insert(0, f"🚚 Total drivers needed: {len(drivers)}")
    return "\n".join(plan)