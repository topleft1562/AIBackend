import os
import json
import requests
from urllib.parse import unquote
from agent_engine import get_agent_runner
from flask import Flask, request, jsonify, render_template, render_template_string
from collections import defaultdict

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
    origin = normalize_city(origin)
    destinations = [normalize_city(d) for d in destinations if d != origin]
    uncached = [d for d in destinations if f"{origin}|{d}" not in DISTANCE_CACHE]
    if not uncached:
        return

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
        print(f"Error fetching from {origin} to batch: {e}")

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

        for i, load in enumerate(loads):
            load["load_id"] = i + 1
            load["pickupCity"] = normalize_city(load["pickupCity"])
            load["dropoffCity"] = normalize_city(load["dropoffCity"])

        city_pairs = set()
        for load in loads:
            pickup = load["pickupCity"]
            dropoff = load["dropoffCity"]
            city_pairs.update({(base, pickup), (pickup, dropoff), (dropoff, base)})
            for other in loads:
                if other["pickupCity"] != pickup:
                    city_pairs.add((dropoff, other["pickupCity"]))

        origin_dest_map = defaultdict(set)
        for origin, dest in city_pairs:
            origin_dest_map[origin].add(dest)
        for origin, dests in origin_dest_map.items():
            get_distances_batch(origin, list(dests))

        result = []
        for load in loads:
            pickup = load["pickupCity"]
            dropoff = load["dropoffCity"]
            reload_options = {
                other["pickupCity"]: DISTANCE_CACHE.get(f"{dropoff}|{other['pickupCity']}")
                for other in loads if other["pickupCity"] != pickup
            }
            result.append({
                "load_id": load["load_id"],
                "pickup": pickup,
                "dropoff": dropoff,
                "deadhead_km": 0 if base == pickup else DISTANCE_CACHE.get(f"{base}|{pickup}", 0),
                "loaded_km": round(DISTANCE_CACHE.get(f"{pickup}|{dropoff}", 0), 1),
                "return_km": DISTANCE_CACHE.get(f"{dropoff}|{base}", 0),
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
            "  - Estimated hours: based on 80 km/h travel speed + 2 hours per load\n\n"
            "Final section:\n"
            "- Suggestions on reducing empty miles (e.g., any trip segments with >100 km deadhead)\n"
            "- Missed reload opportunities\n\n"
            "Constraints:\n"
            "- Drivers should minimize empty km.\n"
            "- Do not assume any pre-linked routes.\n"
            "- Evaluate reloads in sequence using reload_options.\n"
            "- If a dropoff city matches another pickup, or is within 100–200 km of one, treat as a reload.\n"
            "- The goal is not to return to base after each load, but only once the route is complete.\n"
            "- Each driver must return to base at the end of their route.\n"
            "- Minimum 70% loaded km per driver.\n"
            "- If any loads are not planned, output them as Unassigned loads.\n\n"
            f"Here is the list of enriched loads:\n{json.dumps(result, indent=2)}\n\n"
"Note: If multiple loads have the same pickup and dropoff, treat each load as separate. Do not assume they are chained unless the dropoff of one is the pickup of the next. Always include the distance back to pickup as empty km when a route returns to the same pickup."

        )

        response = agent.chat(formatted_message)
        html_output = response.response.replace("\n", "<br>")
        return render_template_string(f"<html><body><h2>Dispatch Plan</h2><p style='font-family: monospace;'>{html_output}</p></body></html>")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def show_dispatch_form():
    return render_template("dispatch_form.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
