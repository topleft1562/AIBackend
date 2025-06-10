import os
import json
import requests
from flask import Flask, request, jsonify, render_template_string
from urllib.parse import unquote, quote
from agent_engine import get_agent_runner

app = Flask(__name__)

# Initialize Dispatchy agent
agent = get_agent_runner()

# Google Distance Matrix API key
GOOGLE_KEY = os.environ.get("GOOGLE_KEY")

# Cached distance dictionary
DISTANCE_CACHE = {}

# Normalize city formatting
def normalize_city(city_str):
    city_str = city_str.replace(",", ", ").replace("  ", " ").title()
    return city_str.strip()

# Helper function to batch fetch distances from Google API
def fetch_distance_matrix(origins, destinations):
    origins = [o for o in origins if o and o.strip()]
    destinations = [d for d in destinations if d and d.strip()]

    if not origins or not destinations:
        print("⚠️ Skipping empty origin/destination batch")
        return None

    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": "|".join([quote(o) for o in origins]),
        "destinations": "|".join([quote(d) for d in destinations]),
        "key": GOOGLE_KEY,
        "units": "metric"
    }
    try:
        res = requests.get(url, params=params)
        data = res.json()
        print("Google API response:", data)
        return data
    except Exception as e:
        print("Error fetching distance matrix:", e)
        return None

@app.route("/dispatch", methods=["GET", "POST"])
def handle_dispatch():
    if request.method == "POST":
        data = request.json
        loads = data.get("loads", [])
    else:
        loads_param = request.args.get("loads")
        try:
            loads = json.loads(unquote(loads_param)) if loads_param else []
        except:
            return jsonify({"error": "Invalid loads format."}), 400

    if not loads:
        return jsonify({"error": "Missing loads in request."}), 400

    try:
        # Step 1: Normalize and collect all unique points
        for load in loads:
            load["pickupCity"] = normalize_city(load["pickupCity"])
            load["dropoffCity"] = normalize_city(load["dropoffCity"])

        all_points = set()
        for load in loads:
            all_points.add(load["pickupCity"])
            all_points.add(load["dropoffCity"])

        all_points = list(all_points)
        pairs_to_fetch = [(o, d) for o in all_points for d in all_points if o != d and (o, d) not in DISTANCE_CACHE]

        # Step 2: Fetch all required distances in batches
        batch_size = 10
        for i in range(0, len(pairs_to_fetch), batch_size):
            batch = pairs_to_fetch[i:i + batch_size]
            origins = list(set([o for o, _ in batch]))
            destinations = list(set([d for _, d in batch]))

            data = fetch_distance_matrix(origins, destinations)
            if data and data.get("rows"):
                for o_idx, origin in enumerate(origins):
                    row = data["rows"][o_idx]
                    for d_idx, destination in enumerate(destinations):
                        element = row["elements"][d_idx]
                        if element["status"] == "OK":
                            dist_km = round(element["distance"]["value"] / 1000, 1)
                            DISTANCE_CACHE[(origin, destination)] = dist_km
                        else:
                            DISTANCE_CACHE[(origin, destination)] = None
                            print(f"⚠️ Distance not found for {origin} → {destination}")

        # Step 3: Build final enriched output
        result = []
        for load in loads:
            pickup = load["pickupCity"]
            dropoff = load["dropoffCity"]
            loaded_km = DISTANCE_CACHE.get((pickup, dropoff))

            reload_options = {
                other["pickupCity"]: DISTANCE_CACHE.get((dropoff, other["pickupCity"]))
                for other in loads if other["pickupCity"] != pickup
            }

            result.append({
                "pickup": pickup,
                "dropoff": dropoff,
                "loaded_km": loaded_km,
                "reload_options": reload_options
            })

        return jsonify({"enriched_loads": result})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 🔹 Start the Flask server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
