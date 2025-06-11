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

@app.route("/dispatch", methods=["POST"])
def handle_dispatch():
    
    data = request.json
    loads = data.get("loads", [])
    start_location = data.get("start", "Brandon, MB")
    end_location = data.get("end", "Brandon, MB")
    
    if not loads:
        return jsonify({"error": "Missing loads in request."}), 400

    try:
        start = normalize_city(start_location)
        end = normalize_city(end_location)

        for i, load in enumerate(loads):
            load["load_id"] = i + 1
            load["pickupCity"] = normalize_city(load["pickupCity"])
            load["dropoffCity"] = normalize_city(load["dropoffCity"])
            # Accept and calculate revenue on backend
            load["rate"] = float(load.get("rate", 0))
            load["weight"] = float(load.get("weight", 0))
            load["revenue"] = load["rate"] * load["weight"]

        city_pairs = set()
        for load in loads:
            pickup = load["pickupCity"]
            dropoff = load["dropoffCity"]
            city_pairs.update({(start, pickup), (pickup, dropoff), (dropoff, end)})
            for other in loads:
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
                "revenue": load["revenue"],
                "deadhead_km": DISTANCE_CACHE.get(get_distance_key(start, pickup), 0),
                "loaded_km": round(DISTANCE_CACHE.get(get_distance_key(pickup, dropoff), 0), 1),
                "return_km": DISTANCE_CACHE.get(get_distance_key(dropoff, end), 0),
                "reload_options": reload_options,
            })
        enriched_data = {
           "start_location": start,
           "end_location": end,
            "loads": result
        }

        prompt = (
            "You are Dispatchy — an elite AI logistics planner.\n\n"
            f"START LOCATION: {start}\n"
            f"END LOCATION: {end}\n"
            "GOALS:\n"
            "- Minimize total empty kilometers across all drivers.\n"
            "- Assign all loads using as few drivers as possible.\n"
            "- Maximize revenue per mile (RPM) per driver.\n\n"
            "DATA FORMATTING:\n"
            "- Format all tables in the response as HTML tables (use <table>, <tr>, <th>, <td>). Do NOT use Markdown or plain text tables.\n"
            "\n"
            "ROUTE/REVENUE INSTRUCTIONS:\n"
            "- Each load has a `revenue` field (rate x weight, in dollars).\n"
            "- For each driver:\n"
            "    - They start at `start_location`, travel deadhead_km to their first pickup.\n"
            "    - They may chain multiple loads: between loads, use reload_option's deadhead_from_this_dropoff as empty km.\n"
            "    - After the last dropoff, they must travel `return_km` to the end location; always include this as empty km.\n"
            "    - Total empty km = first load's deadhead_km + deadhead_from_this_dropoff kms between loads + return_km after last dropoff.\n"
            "    - Total loaded km = sum of loaded_km for all assigned loads.\n"
            "    - Total km = empty km + loaded km.\n"
            "- Do NOT add the deadhead_km for any load except the first one.\n"
            "- When loads are chained, only add the reload_km (deadhead_from_this_dropoff) between dropoff and next pickup.\n"
            "- After the last load, always add return_km.\n"
            "- For each driver: total revenue = sum of assigned loads' revenue.\n"
            "- Convert total kilometers to miles (1 km = 0.621371 miles).\n"
            "- For each driver: RPM = total revenue / (total km in miles)\n\n"
            "OUTPUT INSTRUCTIONS:\n"
            "- For each driver: List assigned loads (load_id, pickup, dropoff, loaded km, rate, weight, revenue).\n"
            "- Show totals: loaded km, empty km, total km, loaded %, total revenue, RPM ($/mile).\n"
            "- Show a summary table for all drivers (total revenue, total loaded km, total empty km, average RPM).\n"
            "- List unassigned loads (if any), with their rates, weights, and potential revenue.\n"
            "- Suggest any improvements if possible.\n\n"
            "- Each load can only be used once.\n"
            f"\nHere is the enriched dispatch data (start_location, end_location and all loads):\n{json.dumps(enriched_data, indent=2)}"
        )


        response = agent.chat(prompt)
        html_output = response.response

        return render_template_string(f"""
            <html>
                <head>
                    <style>
                        table {{
                            border-collapse: collapse;
                            margin: 16px 0;
                            font-size: 15px;
                            width: 100%;
                            background: #fff;
                        }}
                        th, td {{
                            border: 1px solid #bbb;
                            padding: 6px 10px;
                            text-align: center;
                        }}
                        th {{
                            background: #f4f4f4;
                        }}
                    </style>
                </head>
                <body>
                    <h2>Dispatch Plan</h2>
                    {html_output}
                </body>
            </html>
        """)


    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def show_dispatch_form():
    return render_template("dispatch_form.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
