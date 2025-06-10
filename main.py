import os
import json
import requests
from flask import Flask, request, jsonify
from urllib.parse import unquote, quote
from agent_engine import get_agent_runner
from flask import render_template_string
from flask import render_template

app = Flask(__name__)

# Initialize Dispatchy agent
agent = get_agent_runner()

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


@app.route("/")
def show_form():
    return render_template("dispatch_form.html")

# Start the Flask server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
