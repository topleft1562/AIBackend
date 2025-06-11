import os
import json
import requests
from urllib.parse import unquote
from agent_engine import get_agent_runner
from flask import Flask, request, jsonify, render_template, render_template_string
from collections import defaultdict
from utils import generate_google_map_html, generate_route_map_link  # 🆕 map helpers

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

def get_coordinates(city):
    city = normalize_city(city)
    if city in COORD_CACHE:
        return COORD_CACHE[city]

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": city, "key": GOOGLE_KEY}
    try:
        res = requests.get(url, params=params)
        data = res.json()
        if data.get("results"):
            location = data["results"][0]["geometry"]["location"]
            latlng = (location["lat"], location["lng"])
            COORD_CACHE[city] = latlng
            return latlng
    except:
        pass
    return None

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
        pins = [base]
        for load in loads:
            pickup = load["pickupCity"]
            dropoff = load["dropoffCity"]
            reload_options = {
                f"load_{other['load_id']}": {
                    "pickup": other["pickupCity"],
                    "distance": DISTANCE_CACHE.get(get_distance_key(dropoff, other["pickupCity"]))
                }
                for other in loads if other["load_id"] != load["load_id"]
            }

            result.append({
                "load_id": load["load_id"],
                "pickup": pickup,
                "dropoff": dropoff,
                "deadhead_km": DISTANCE_CACHE.get(get_distance_key(base, pickup), 0),
                "loaded_km": round(DISTANCE_CACHE.get(get_distance_key(pickup, dropoff), 0), 1),
                "return_km": DISTANCE_CACHE.get(get_distance_key(dropoff, base), 0),
                "reload_options": reload_options,
            })

            pins.extend([pickup, dropoff])

        pin_coords = {city: get_coordinates(city) for city in pins}

        prompt = (
    "You are Dispatchy — an elite AI logistics planner.\n\n"
    "GOAL: Minimize total empty kilometers by chaining compatible loads.\n\n"
    "🚚 RULES:\n"
    "- Each driver starts at base and returns to base only after completing all their assigned loads.\n"
    "- Use every load exactly once. Do not duplicate or insert loads.\n"
    "- Chain loads in order where the dropoff of one is close to the pickup of the next.\n"
    "- Use the provided `reload_options` to determine chaining feasibility.\n"
    "- Never invent km — use only values provided for deadhead, loaded, and return.\n"
    "- Avoid backtracking. Do not revisit cities already dropped off at unless explicitly required.\n"
    "- Only calculate loaded km when a load is being hauled.\n\n"
    "✏️ Return a clean dispatch plan:\n"
    "- For each driver: list of load numbers with cities and distances\n"
    "- Clearly mark deadhead, loaded, and return distances\n"
    "- Final totals: total km, total loaded km, total empty km, and loaded %\n"
    "- Highlight if a better chaining order is possible\n"
    "- Identify any loads that couldn't be chained or assigned\n\n"
    "📦 Provided load data:\n"
    f"{json.dumps(result, indent=2)}"
)

        response = agent.chat(prompt)
        html_output = response.response.replace("\n", "<br>")

        map_html = generate_google_map_html(pin_coords, GOOGLE_KEY)
        route_link = generate_route_map_link(pins)

        return render_template_string(
            f"<html><body><h2>Dispatch Plan</h2>{map_html}<p><a href='{route_link}' target='_blank'>🌐 Open Route in Google Maps</a></p><p style='font-family: monospace;'>{html_output}</p></body></html>"
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def show_dispatch_form():
    return render_template("dispatch_form.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
