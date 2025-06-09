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
WARNING_HOURS = 55  # Above this counts as overtime

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
    assignments = [
        {
            "driver": driver,
            "start_location": driver.get("location", "Unknown"),
            "current_location": driver.get("location", "Unknown"),
            "name": driver.get("name", "Unnamed"),
            "assigned": [],
            "loaded_km": 0,
            "empty_km": 0,
            "hours": 0
        } for driver in drivers
    ]

    for load in loads:
        best_choice = None
        lowest_overtime = float("inf")

        for assignment in assignments:
            if assignment["hours"] >= MAX_HOURS:
                continue

            empty_km, empty_hours = estimate_drive_hours(assignment["current_location"], load['pickupCity'])
            loaded_km, loaded_hours = estimate_drive_hours(load['pickupCity'], load['dropoffCity'])
            projected_hours = assignment["hours"] + empty_hours + loaded_hours

            overtime = max(projected_hours - WARNING_HOURS, 0)

            if projected_hours <= MAX_HOURS and overtime < lowest_overtime:
                best_choice = assignment
                lowest_overtime = overtime

        if best_choice:
            best_choice["empty_km"] += empty_km
            best_choice["loaded_km"] += loaded_km
            best_choice["hours"] += empty_hours + loaded_hours
            best_choice["current_location"] = load['dropoffCity']
            best_choice["assigned"].append(f"{load['pickupCity']} → {load['dropoffCity']}")

    for assignment in assignments:
        total_km = assignment["loaded_km"] + assignment["empty_km"]
        loaded_pct = round(100 * assignment["loaded_km"] / total_km) if total_km > 0 else 0
        hos_used = round(100 * assignment["hours"] / MAX_HOURS)

        if assignment["assigned"]:
            plan.append(
                f"• {assignment['name']} ({assignment['start_location']}): {' → '.join(assignment['assigned'])} "
                f"(Total: {int(total_km)}km — {int(assignment['loaded_km'])} loaded / {int(assignment['empty_km'])} empty, "
                f"{round(assignment['hours'], 1)}h, {loaded_pct}% loaded, {hos_used}% of HOS used)"
            )
        else:
            plan.append(f"• {assignment['name']} ({assignment['start_location']}): No loads assigned (idle/reset)")

    return "\n".join(plan)
