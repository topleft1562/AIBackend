import os
import requests
from flask import Flask, request, jsonify, render_template_string
from urllib.parse import unquote
from agent_engine import get_agent_runner
import time

app = Flask(__name__)

# Initialize Dispatchy agent
agent = get_agent_runner()

# Google Distance Matrix API function
GOOGLE_KEY = os.environ.get("GOOGLE_KEY")



def get_distance_km_google(origin, destination, retries=3, delay=2):
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": origin,
        "destinations": destination,
        "key": GOOGLE_KEY,
        "units": "metric"
    }

    for attempt in range(retries):
        try:
            res = requests.get(url, params=params, timeout=10)
            data = res.json()
            if data["rows"] and data["rows"][0]["elements"][0]["status"] == "OK":
                return round(data["rows"][0]["elements"][0]["distance"]["value"] / 1000, 1)
        except Exception as e:
            print(f"Distance matrix error ({attempt + 1}/{retries}): {e}")
            time.sleep(delay)

    return None  # fallback on failure


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
        # Add distance metadata to each load
        enriched_loads = []
        for load in loads:
            pickup = load["pickupCity"].replace(" ", "")
            dropoff = load["dropoffCity"].replace(" ", "")
            base = base_location.replace(" ", "")

            empty_to_pickup_km = get_distance_km_google(base, pickup)
            loaded_km = get_distance_km_google(pickup, dropoff)
            return_empty_km = get_distance_km_google(dropoff, base) if dropoff != base else 0

            load["loaded_km"] = loaded_km or 0
            load["empty_to_pickup_km"] = empty_to_pickup_km or 0
            load["return_empty_km"] = return_empty_km or 0
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
