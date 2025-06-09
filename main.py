import os
import requests
from flask import Flask, request, jsonify, render_template_string
from urllib.parse import unquote
from agent_engine import get_agent_runner

app = Flask(__name__)

# Initialize Dispatchy agent
agent = get_agent_runner()

# Google Distance Matrix API key
GOOGLE_KEY = os.environ.get("GOOGLE_KEY")

# Cached distance dictionary
DISTANCE_CACHE = {}

# Helper function to batch fetch distances from Google API
def fetch_distance_matrix(origins, destinations):
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": "|".join(origins),
        "destinations": "|".join(destinations),
        "key": GOOGLE_KEY,
        "units": "metric"
    }
    try:
        res = requests.get(url, params=params)
        data = res.json()
        print("Google API response:", data)  # 🔹 Log the full API response for debugging
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
        # Prepare all unique city pairs for distance lookup
        unique_pairs = set()
        base = base_location.replace(" ", "")
        for load in loads:
            pickup = load["pickupCity"].replace(" ", "")
            dropoff = load["dropoffCity"].replace(" ", "")
            unique_pairs.add((base, pickup))
            unique_pairs.add((pickup, dropoff))
            if dropoff != base:
                unique_pairs.add((dropoff, base))

        # Batch request to respect Google API's 100 element limit
        pair_list = [(o, d) for (o, d) in unique_pairs if (o, d) not in DISTANCE_CACHE]
        batch_size = 10  # 10x10 = 100 elements
        for i in range(0, len(pair_list), batch_size):
            batch = pair_list[i:i + batch_size]
            batch_origins = list(set([o for o, _ in batch]))
            batch_destinations = list(set([d for _, d in batch]))

            distance_data = fetch_distance_matrix(batch_origins, batch_destinations)
            if distance_data and distance_data.get("rows"):
                for o_idx, origin in enumerate(batch_origins):
                    row = distance_data["rows"][o_idx]
                    for d_idx, destination in enumerate(batch_destinations):
                        element = row["elements"][d_idx]
                        if element["status"] == "OK":
                            dist_km = round(element["distance"]["value"] / 1000, 1)
                            DISTANCE_CACHE[(origin, destination)] = dist_km

        # Enrich loads with distances
        enriched_loads = []
        for load in loads:
            pickup = load["pickupCity"].replace(" ", "")
            dropoff = load["dropoffCity"].replace(" ", "")

            empty_to_pickup_km = DISTANCE_CACHE.get((base, pickup), 0)
            loaded_km = DISTANCE_CACHE.get((pickup, dropoff), 0)
            return_empty_km = DISTANCE_CACHE.get((dropoff, base), 0) if dropoff != base else 0

            load["loaded_km"] = loaded_km
            load["empty_to_pickup_km"] = empty_to_pickup_km
            load["return_empty_km"] = return_empty_km
            enriched_loads.append(load)

        formatted_message = (
            f"You are a logistics planner. Assign the following loads to the minimum number of drivers.\n"
            f"Each driver starts and ends at {base_location}.\n"
            f"Try to aim for 55 hours per driver, but never exceed 70 hours.\n"
            f"Optimize routes to group loads logically and reduce backtracking.\n"
            f"Use an average driving speed of 80 km/h.\n"
            f"Assume each load/unload takes 1.5 hours.\n"
            f"Only return plans where loaded km is at least 70% of total km driven.\n"
            f"For each driver, show the exact route like: base → pickup (empty) → dropoff (loaded) → next pickup, etc.\n"
            f"Also include: total km, loaded km, empty km, total hours, and HOS % used.\n\n"
            f"Loads:\n{enriched_loads}"
        )

        response = agent.chat(formatted_message)

        html_output = response.response.replace("\n", "<br>") \
                                        .replace("**", "<b>") \
                                        .replace("###", "<h3>") \
                                        .replace("---", "<hr>")

        return render_template_string(f"<html><body><h2>Dispatch Plan</h2>{html_output}</body></html>")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 🔹 Start the Flask server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
