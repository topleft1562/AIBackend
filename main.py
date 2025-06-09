import os
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
        base_location = data.get("base", "Brandon,MB")
    else:
        loads_param = request.args.get("loads")
        base_location = request.args.get("base", "Brandon,MB")
        try:
            loads = eval(unquote(loads_param)) if loads_param else []
        except:
            return jsonify({"error": "Invalid loads format."}), 400

    if not loads:
        return jsonify({"error": "Missing loads in request."}), 400

    try:
        base = normalize_city(base_location)
        unique_points = set([base])

        for load in loads:
            load["pickupCity"] = normalize_city(load["pickupCity"])
            load["dropoffCity"] = normalize_city(load["dropoffCity"])
            unique_points.add(load["pickupCity"])
            unique_points.add(load["dropoffCity"])

        unique_points = list(unique_points)
        pair_list = [(o, d) for o in unique_points for d in unique_points if o != d and (o, d) not in DISTANCE_CACHE]

        batch_size = 10
        for i in range(0, len(pair_list), batch_size):
            batch = pair_list[i:i + batch_size]
            batch_origins = list(set([o for o, _ in batch if o and o.strip()]))
            batch_destinations = list(set([d for _, d in batch if d and d.strip()]))

            distance_data = fetch_distance_matrix(batch_origins, batch_destinations)
            if distance_data and distance_data.get("rows"):
                for o_idx, origin in enumerate(batch_origins):
                    row = distance_data["rows"][o_idx]
                    for d_idx, destination in enumerate(batch_destinations):
                        element = row["elements"][d_idx]
                        if element["status"] == "OK":
                            dist_km = round(element["distance"]["value"] / 1000, 1)
                            DISTANCE_CACHE[(origin, destination)] = dist_km
                        else:
                            print(f"⚠️ Distance not found for {origin} → {destination}: {element['status']}")

        enriched_loads = []
        for load in loads:
            pickup = load["pickupCity"]
            dropoff = load["dropoffCity"]

            empty_to_pickup_km = DISTANCE_CACHE.get((base, pickup))
            loaded_km = DISTANCE_CACHE.get((pickup, dropoff))
            return_empty_km = DISTANCE_CACHE.get((dropoff, base)) if dropoff != base else 0

            if empty_to_pickup_km is None or loaded_km is None:
                print(f"⚠️ Skipping load due to missing distances: {pickup} → {dropoff}")
                continue

            load["loaded_km"] = loaded_km
            load["empty_to_pickup_km"] = empty_to_pickup_km
            load["return_empty_km"] = return_empty_km
            enriched_loads.append(load)

        formatted_message = (
            f"You are a logistics planner AI. You are given a list of available loads and a base location.\n"
            f"Each driver starts and ends at {base_location}.\n"
            f"Your task is to extract as many optimized driver routes as possible from the loads provided, \n"
            f"where each route achieves at least 70% loaded km.\n"
            f"Use 80 km/h as average speed, and 1.5 hours for each pickup or delivery stop.\n"
            f"Try chaining multiple loads together per driver to meet efficiency.\n"
            f"If any route nearly qualifies but falls short, include a clear suggestion on what additional loads (city to city) would help.\n"
            f"Also identify origin/destination areas where additional loads would enable more 70%+ routes.\n\n"
            f"For each route, format like:\n"
            f"brandon → redvers (empty) — 300 km\n"
            f"redvers → brandon (loaded) — 300 km\n"
            f"total km: 600\n"
            f"loaded %: 50%\n"
            f"HOS: 11.3 hrs\n\n"
            f"Do this for each valid driver. No markdown. Keep output uniform and clean.\n\n"
            f"Loads:\n{enriched_loads}"
        )

        response = agent.chat(formatted_message)

        html_output = response.response.replace("\n", "<br>")

        return render_template_string(f"<html><body><h2>Dispatch Plan</h2><p style='font-family: monospace;'>{html_output}</p></body></html>")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 🔹 Start the Flask server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
