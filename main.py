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

# Coordinate cache: city => (lat, lng)
COORD_CACHE = {}

def normalize_city(city_str):
    city_str = city_str.replace(",", ", ").replace("  ", " ").title()
    return city_str.strip()

def get_distance_key(origin, destination):
    sorted_pair = sorted([normalize_city(origin), normalize_city(destination)])
    return f"{sorted_pair[0]}|{sorted_pair[1]}"

def get_distances_batch(origin, destinations):
    origin = normalize_city(origin)
    destinations = [normalize_city(d) for d in destinations if d != origin]
    uncached = [d for d in destinations if get_distance_key(origin, d) not in DISTANCE_CACHE]
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
                key = get_distance_key(origin, d)
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
            # Pass rate through
            load["rate"] = float(load.get("rate", 0))


        city_pairs = set()
        for load in loads:
            pickup = load["pickupCity"]
            dropoff = load["dropoffCity"]
            city_pairs.update({(base, pickup), (pickup, dropoff), (dropoff, base)})
            for other in loads:
                city_pairs.add((dropoff, other["pickupCity"]))

        origin_dest_map = defaultdict(set)
        for origin, dest in city_pairs:
            origin_dest_map[origin].add(dest)
        for origin, dests in origin_dest_map.items():
            get_distances_batch(origin, list(dests))

        result = []
        pins = set()
        for load in loads:
            pickup = load["pickupCity"]
            dropoff = load["dropoffCity"]
            reload_options = {
                f"load_{other['load_id']}": {
                    "pickup": other["pickupCity"],
                    "deadhead_from_this_dropoff": DISTANCE_CACHE.get(get_distance_key(dropoff, other["pickupCity"]), 0),
                    "loaded_km": DISTANCE_CACHE.get(get_distance_key(other["pickupCity"], other["dropoffCity"]), 0)
                }
                for other in loads if other["load_id"] != load["load_id"]
            }

            result.append({
                "load_id": load["load_id"],
                "pickup": pickup,
                "dropoff": dropoff,
                "rate": load["rate"],
                "deadhead_km": DISTANCE_CACHE.get(get_distance_key(base, pickup), 0),
                "loaded_km": round(DISTANCE_CACHE.get(get_distance_key(pickup, dropoff), 0), 1),
                "return_km": DISTANCE_CACHE.get(get_distance_key(dropoff, base), 0),
                "reload_options": reload_options,
            })

        prompt = (
            "You are Dispatchy — an elite AI logistics planner.\n\n"
            "GOALS:\n"
            "- Minimize total empty kilometers across all drivers.\n"
            "- Assign all loads using as few drivers as possible.\n"
            "- Maximize revenue per mile (RPM) per driver.\n\n"
            "Revenue Instructions:\n"
            "- Each load has a `rate` (dollars/MT)."
            "- For each load: revenue = rate x 43 x loaded_km"
            "- For each driver: total revenue = sum of assigned loads' revenue."
            "- Convert total kilometers to miles (1 km = 0.621371 miles)."
            "- For each driver: RPM = total revenue / (total km * 0.621371)\n\n"
            "Instructions:\n"
            "- Drivers must start at base and end at or near base.\n"
            "- Chain loads together when possible to avoid unnecessary returns to base (using reload_options).\n"
            "- Do not return to base unless the route is completed.\n"
            "- For each driver: list assigned loads by load_id, with pickup, dropoff, loaded km, rate, revenue for each.\n"
            "- Show totals per driver: loaded km, empty km, total km, loaded %, **total revenue**, and **RPM**.\n"
            "- Show a summary table for all drivers (total revenue, total loaded km, total empty km, average RPM).\n"
            "- List unassigned loads (if any), with their rates and potential revenue.\n"
            "- Suggest any improvements if possible.\n\n"
            f"Here is the enriched load data:\n{json.dumps(result, indent=2)}"
        )

        response = agent.chat(prompt)
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
