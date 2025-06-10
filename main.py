import os
import json
import requests
from urllib.parse import unquote, quote
from agent_engine import get_agent_runner, get_route_assessor
from flask import Flask, Blueprint, request, jsonify, render_template, render_template_string
from collections import defaultdict

app = Flask(__name__)

# Initialize Dispatchy agent
agent = get_agent_runner()
agent2 = get_route_assessor()

# Google API key
GOOGLE_KEY = os.environ.get("GOOGLE_KEY")

# Distance cache: ("origin|destination") => km
DISTANCE_CACHE = {}

def normalize_city(city_str):
    city_str = city_str.replace(",", ", ").replace("  ", " ").title()
    return city_str.strip()

def get_distances_batch(origin, destinations):
    """Fetch and cache distances from one origin to multiple destinations"""
    origin = normalize_city(origin)
    destinations = [normalize_city(d) for d in destinations if d != origin]

    # Skip if already cached
    uncached = [
        d for d in destinations
        if f"{origin}|{d}" not in DISTANCE_CACHE
    ]
    if not uncached:
        return

    print(f"\n📦 Fetching from origin: {origin}")
    print(f"➡ Destinations: {uncached}")

    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": origin,
        "destinations": "|".join(uncached),
        "key": GOOGLE_KEY,
        "units": "metric"
    }

    try:
        res = requests.get(url, params=params)
        data = res.json()
        print("🧾 API Response:", json.dumps(data, indent=2))

        if data.get("rows"):
            elements = data["rows"][0]["elements"]
            for i, d in enumerate(uncached):
                key = f"{origin}|{d}"
                element = elements[i]
                if element.get("status") == "OK":
                    DISTANCE_CACHE[key] = round(element["distance"]["value"] / 1000, 1)
                else:
                    DISTANCE_CACHE[key] = None
    except Exception as e:
        print(f"🚨 Error fetching from {origin} to batch:", e)


@app.route("/dispatch", methods=["GET", "POST"])
def handle_dispatch():
    if request.method == "POST":
        data = request.json
        loads = data.get("loads", [])
        base_location = data.get("base", "Brandon, MB")
    else:
        loads_param = request.args.get("loads")
        base_location = request.args.get("base", "Brandon, MB")
        try:
            loads = json.loads(unquote(loads_param)) if loads_param else []
        except:
            return jsonify({"error": "Invalid loads format."}), 400

    if not loads:
        return jsonify({"error": "Missing loads in request."}), 400

    try:
        base = normalize_city(base_location)

        # Normalize city names & assign IDs
        for i, load in enumerate(loads):
            load["load_id"] = i + 1
            load["pickupCity"] = normalize_city(load["pickupCity"])
            load["dropoffCity"] = normalize_city(load["dropoffCity"])

        # Pre-collect all unique distance pairs we will need
        city_pairs = set()

        for load in loads:
            pickup = load["pickupCity"]
            dropoff = load["dropoffCity"]
            city_pairs.add((base, pickup))           # deadhead
            city_pairs.add((pickup, dropoff))        # loaded
            city_pairs.add((dropoff, base))          # return
            for other in loads:
                if other["pickupCity"] != pickup:
                    city_pairs.add((dropoff, other["pickupCity"]))  # reload options

        # Group all unique destinations for each origin
        from collections import defaultdict
        origin_dest_map = defaultdict(set)

        for origin, dest in city_pairs:
            origin_dest_map[origin].add(dest)

        # Batch fetch
        for origin, dests in origin_dest_map.items():
            get_distances_batch(origin, list(dests))

        # Build enriched load data
        result = []
        for load in loads:
            pickup = load["pickupCity"]
            dropoff = load["dropoffCity"]

            reload_options = {}
            for other in loads:
                if other["pickupCity"] != pickup:
                    next_pickup = other["pickupCity"]
                    reload_options[next_pickup] = DISTANCE_CACHE.get(f"{dropoff}|{next_pickup}")

            result.append({
                "load_id": load["load_id"],
                "pickup": pickup,
                "dropoff": dropoff,
                "deadhead_km": DISTANCE_CACHE.get(f"{base}|{pickup}"),
                "loaded_km": DISTANCE_CACHE.get(f"{pickup}|{dropoff}"),
                "return_km": DISTANCE_CACHE.get(f"{dropoff}|{base}"),
                "reload_options": reload_options
            })

        formatted_message = (
            "You are Dispatchy — an efficient AI dispatcher.\n\n"
            "The objective is simple:\n"
            "- Get all loads done using as few drivers as possible.\n"
            "- Ensure each driver hits at least 70% loaded km.\n"
            "- Maximize route efficiency and minimize empty miles.\n\n"
            "Each load includes:\n"
            "- pickup city\n"
            "- dropoff city\n"
            "- deadhead distance (from base to pickup)\n"
            "- loaded distance (from pickup to dropoff)\n"
            "- return distance (from dropoff to base)\n"
            "- reload options (distance from current dropoff to other pickup cities)\n\n"
            "Expected Output:\n"
            "- For each driver:\n"
            "  - Route (list of load IDs)\n"
            "  - Total empty km\n"
            "  - Total loaded km\n"
            "  - Loaded percent (loaded / total)\n"
            "  - Estimated hours: based on 80 km/h travel speed + 2 hours per load (1 hour load, 1 hour unload)\n\n"
            "Final section:\n"
            "- Suggestions on reducing empty miles (e.g., any trip segments with >100 km deadhead)\n"
            "- Missed reload opportunities\n\n"
            "Constraints:\n"
            "- Drivers should minimize empty km.\n"
            "- Drivers should always attempt to reload after a dropoff, using the closest available pickup from `reload_options`.\n"
            "- If a dropoff city is the same as another pickup, it must be chained.\n"
            "- The goal is not to return to base after each load, but only once the route is complete.\n"
            "- Minimum 70% loaded km per driver.\n"
            "- If the dropoff city matches the next pickup city, this is not a return or deadhead — it is a direct reload."
            "- In those cases, treat the entire trip (both legs) as loaded km."
            "- Do not count the distance between a dropoff and matching pickup as empty."
            f"Here is the list of enriched loads:\n{json.dumps(result, indent=2)}"
)

        response = agent.chat(formatted_message)

        html_output = response.response.replace("\n", "<br>")

        return render_template_string(f"<html><body><h2>Dispatch Plan</h2><p style='font-family: monospace;'>{html_output}</p></body></html>")

       

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/optimize-routes", methods=["POST"])
def optimize_routes():
    data = request.json
    predefined_routes = data.get("routes", [])
    base_location = normalize_city(data.get("base", "Brandon, MB"))
    loads = data.get("loads", [])

    if not predefined_routes or not loads:
        return jsonify({"error": "Missing 'routes' or 'loads' in request."}), 400

    # Normalize and enrich load info
    load_map = {}
    city_pairs = set()

    for i, load in enumerate(loads):
        load_id = i + 1
        pickup = normalize_city(load["pickupCity"])
        dropoff = normalize_city(load["dropoffCity"])
        load_map[load_id] = {
            "load_id": load_id,
            "pickup": pickup,
            "dropoff": dropoff
        }
        city_pairs.update({
            (base_location, pickup),
            (pickup, dropoff),
            (dropoff, base_location)
        })

    # Build reload options
    for a in load_map.values():
        for b in load_map.values():
            if a["pickup"] != b["pickup"]:
                city_pairs.add((a["dropoff"], b["pickup"]))

    # Fetch distances
    origin_dest_map = defaultdict(set)
    for origin, dest in city_pairs:
        origin_dest_map[origin].add(dest)
    for origin, dests in origin_dest_map.items():
        get_distances_batch(origin, list(dests))

    # Enrich all loads with distance info
    for load in load_map.values():
        load["deadhead_km"] = DISTANCE_CACHE.get(f"{base_location}|{load['pickup']}")
        load["loaded_km"] = DISTANCE_CACHE.get(f"{load['pickup']}|{load['dropoff']}")
        load["return_km"] = DISTANCE_CACHE.get(f"{load['dropoff']}|{base_location}")
        load["reload_options"] = {
            b["pickup"]: DISTANCE_CACHE.get(f"{load['dropoff']}|{b['pickup']}")
            for b in load_map.values() if b["pickup"] != load["pickup"]
        }

    # Construct enriched route breakdowns
    enriched_routes = []
    for route in predefined_routes:
        driver_id = route["driver"]
        load_ids = route["load_ids"]
        total_empty = 0
        total_loaded = 0
        total_hours = 0
        num_loads = len(load_ids)

        ordered = [load_map[lid] for lid in load_ids]

        # Deadhead: base to first pickup
        total_empty += DISTANCE_CACHE.get(f"{base_location}|{ordered[0]['pickup']}", 0)

        for i in range(len(ordered)):
            a = ordered[i]
            total_loaded += a["loaded_km"] or 0
            if i < len(ordered) - 1:
                b = ordered[i + 1]
                total_empty += DISTANCE_CACHE.get(f"{a['dropoff']}|{b['pickup']}", 0)
            else:
                # Return to base after last dropoff
                total_empty += DISTANCE_CACHE.get(f"{a['dropoff']}|{base_location}", 0)

        total_km = total_empty + total_loaded
        loaded_percent = round((total_loaded / total_km) * 100, 1) if total_km else 0
        travel_hours = total_km / 80
        load_hours = num_loads * 2
        total_hours = round(travel_hours + load_hours, 2)

        enriched_routes.append({
            "driver": driver_id,
            "load_ids": load_ids,
            "total_empty_km": round(total_empty, 1),
            "total_loaded_km": round(total_loaded, 1),
            "loaded_percent": loaded_percent,
            "estimated_hours": total_hours
        })

    # Send to agent for analysis
    message = (
        "You are Dispatchy, a route assessment and optimization specialist.\n\n"
        "Here are the current driver assignments with actual calculated distance and time data.\n"
        "Assess if any routes could be improved, consolidated, or made more efficient.\n"
        "Only make changes if they will reduce total empty km or improve loaded %.\n\n"
        "Base location: " + base_location + "\n\n"
        f"Detailed routes:\n{json.dumps(enriched_routes, indent=2)}"
    )

    response = agent2.chat(message)
    html_output = response.response.replace("\n", "<br>")

    return f"<html><body><h2>Route Optimization Review</h2><p style='font-family: monospace;'>{html_output}</p></body></html>"



@app.route("/")
def show_dispatch_form():
    return render_template("dispatch_form.html")

@app.route("/optimize")
def show_optimize_form():
    return render_template("optimize_form.html")

# Start the Flask server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
