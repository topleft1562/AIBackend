import os
import json
import requests
from flask import Flask, request, jsonify
from urllib.parse import unquote, quote

app = Flask(__name__)

# Google API key
GOOGLE_KEY = os.environ.get("GOOGLE_KEY")

# Distance cache: ("origin|destination") => km
DISTANCE_CACHE = {}

def normalize_city(city_str):
    city_str = city_str.replace(",", ", ").replace("  ", " ").title()
    return city_str.strip()

def get_distance(origin, destination):
    """Check cache, else fetch from API and store in cache"""
    key = f"{origin}|{destination}"
    if key in DISTANCE_CACHE:
        return DISTANCE_CACHE[key]

    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": quote(origin),
        "destinations": quote(destination),
        "key": GOOGLE_KEY,
        "units": "metric"
    }

    try:
        res = requests.get(url, params=params)
        data = res.json()
        if data["rows"][0]["elements"][0]["status"] == "OK":
            dist_km = round(data["rows"][0]["elements"][0]["distance"]["value"] / 1000, 1)
            DISTANCE_CACHE[key] = dist_km
            return dist_km
    except Exception as e:
        print(f"Error fetching distance from {origin} to {destination}:", e)

    DISTANCE_CACHE[key] = None
    return None

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

        # Fetch missing distances and store in cache
        for origin, dest in city_pairs:
            get_distance(origin, dest)

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

        return jsonify({"enriched_loads": result})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Start the Flask server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
