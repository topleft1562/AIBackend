import json
from agent_engine import get_agent_runner
from hos import simulate_driver_plan

agent = get_agent_runner()

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
**Do not include markdown or text outside the JSON brackets.
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

Additional Constraints:
- The driver must END the route at their home base, unless explicitly allowed to reset away from home.
- Output total_km, loaded_km, and empty_km (so efficiency = loaded_km / total_km).
- For each load, revenue = rate * weight.
- Total revenue is the sum of all load revenues in the plan.
- Calculate total drive time based on 80 km/h.
- Include any repositioning (empty) legs in the plan with drive_hr and empty_km.

"""


    full_input = {
        "drivers": drivers,
        "loads": loads,
        "routes": route_matrix
    }

    full_prompt = prompt + "\n\nInput:\n" + json.dumps(full_input, indent=2)

    response = agent.chat(full_prompt)
    print(response)
    # Try to parse the response as JSON
    try:
        plans = json.loads(response.response)
    except Exception:
        return {
            "error": "Failed to parse LLM JSON. Raw response:",
            "raw": response.response
        }

    # Add fallback revenue calc + empty km logic if LLM missed it
    for plan in plans:
        plan["revenue"] = 0
        plan["loaded_km"] = 0
        plan["empty_km"] = 0
        last_city = None

        for leg in plan["plan"]:
            # Calculate revenue per load if needed
            load = next((l for l in loads if l["pickup"]["city"].lower() == leg["from"].lower()
                        and l["dropoff"]["city"].lower() == leg["to"].lower()), None)
            if load:
                leg_revenue = load["rate"] * load["weight"]
                plan["revenue"] += leg_revenue

            # Use route_matrix for km
            key = " | ".join(sorted([leg["from"].strip().title(), leg["to"].strip().title()]))
            route = route_matrix.get(key)
            if not route:
                continue

            plan["total_km"] = plan.get("total_km", 0) + route["distance_km"]

            # Empty or loaded?
            if last_city:
                if leg["from"].lower() != last_city.lower():
                    # There was an empty segment in between
                    empty_key = " | ".join(sorted([last_city.strip().title(), leg["from"].strip().title()]))
                    empty_route = route_matrix.get(empty_key)
                    if empty_route:
                        plan["empty_km"] += empty_route["distance_km"]
                        plan["total_km"] += empty_route["distance_km"]

            plan["loaded_km"] += route["distance_km"]
            last_city = leg["to"]

        # Final return to home?
        driver = next((d for d in drivers if d["id"] == plan["driver_id"]), None)
        if driver and last_city and last_city.lower() != driver["home_base"].lower():
            ret_key = " | ".join(sorted([last_city.strip().title(), driver["home_base"].strip().title()]))
            ret_route = route_matrix.get(ret_key)
            if ret_route:
                plan["empty_km"] += ret_route["distance_km"]
                plan["total_km"] += ret_route["distance_km"]

        plan["efficiency"] = plan["loaded_km"] / plan["total_km"] if plan["total_km"] else 0


        return plans
