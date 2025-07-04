import json
from agent_engine import agent
from hos import simulate_driver_plan


def extract_gap_segments(plan, route_matrix):
    """
    Finds empty route segments between chained loads in a plan.
    """
    segments = []
    loads = plan.get("plan", [])
    if not loads or len(loads) < 2:
        return []

    for i in range(len(loads) - 1):
        from_city = loads[i]["to"]
        to_city = loads[i + 1]["from"]
        key = " | ".join(sorted([from_city.strip().title(), to_city.strip().title()]))

        route = route_matrix.get(key)
        if route:
            segments.append({
                "from": from_city,
                "to": to_city,
                "empty_km": route["distance_km"]
            })

    return sorted(segments, key=lambda x: -x["empty_km"])

def generate_plan(loads, drivers, route_matrix, min_efficiency=0.7):
    prompt = f"""
You are a logistics optimization AI responsible for dispatching drivers across multiple loads.

**Your goals:**
- Maximize use of driver HOS: 70 hours in a 7-day cycle, max 14 hours/day.
- Drive time is based on 80 km/h using the provided route_matrix.
- Each load takes 1.5 hours to load and 1.5 hours to unload (3.0 hours total non-driving).
- If a driver hits 70 hours, they must take a 36-hour reset (preferably at home base).
- Chain loads to maintain at least {int(min_efficiency * 100)}% loaded kilometers.
- Prefer plans that fill the entire 70-hour cycle efficiently.

**Data provided:**
- Loads: pickup/dropoff locations, time windows, rate, weight, required amount.
- Drivers: current location, home base, available cycle hours, hours today used.
- route_matrix: contains driving distance (km) between all relevant cities.

**Output JSON per driver:**
- driver_id
- plan: list of loads in order, each with:
  - load_id
  - from (pickup city)
  - to (dropoff city)
  - date (YYYY-MM-DD)
  - drive_hr
- total_km
- loaded_km
- efficiency (loaded_km / total_km)
- revenue
"""

    full_input = {
        "drivers": drivers,
        "loads": loads,
        "routes": route_matrix
    }

    full_prompt = prompt + "\n\nInput:\n" + json.dumps(full_input, indent=2)

    response = agent.stream_chat(full_prompt)

    # Try to parse the response as JSON
    try:
        plans = json.loads(response.response)
    except Exception:
        return {
            "error": "Failed to parse LLM JSON. Raw response:",
            "raw": response.response
        }

    # Post-process each driver plan
    for plan in plans:
        driver = next((d for d in drivers if d["id"] == plan["driver_id"]), None)
        if not driver:
            plan["hos_check"] = { "valid": False, "error": "Driver not found" }
            continue

        # Simulate HOS compliance
        sim_result = simulate_driver_plan(plan, driver)
        plan["hos_check"] = sim_result

        # Check efficiency threshold
        eff = plan.get("efficiency", 0)
        plan["meets_efficiency_target"] = eff >= min_efficiency

        # Extract empty segments between chained loads
        plan["gap_segments"] = extract_gap_segments(plan, route_matrix)

    return plans
