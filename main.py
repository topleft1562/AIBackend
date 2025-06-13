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
    "You are Dispatchy, a highly efficient logistics planner. "
    "Your task is to analyze the provided load and distance data (`enriched_data`) and generate every possible efficient route that meets the following criteria:\n"
    "\n"
    "ROUTE REQUIREMENTS:\n"
    "- Each route must:\n"
    "    • Start at `start_location`.\n"
    "    • End at `end_location`.\n"
    "    • Chain together one or more loads, in any valid order (no repeats per route).\n"
    "    • For the first load, include `deadhead_km` (distance from start_location to first pickup) as empty km.\n"
    "    • For each pair of consecutive loads, include `deadhead_from_this_dropoff` (from reload_options) as empty km between loads.\n"
    "    • After the last load, include `return_km` (from last dropoff to end_location) as empty km.\n"
    "    • For each load, loaded km = `loaded_km` (pickup to dropoff).\n"
    "    • For each load, revenue = rate × weight.\n"
    "    • For each route, total revenue = sum of load revenues.\n"
    "    • For each route, total loaded km = sum of all loaded_km.\n"
    "    • For each route, total empty km = sum of all deadhead km (initial, between loads, and final return).\n"
    "    • For each route, total km = total loaded km + total empty km.\n"
    "    • For each route, loaded % = total loaded km / total km.\n"
    "    • For each route, RPM ($/mile) = total revenue / (total km × 0.621371).\n"
    "- Only show routes where loaded % is at least 70% (0.7 or higher).\n"
    "\n"
    "OUTPUT INSTRUCTIONS:\n"
    "- For each qualifying route, output a single HTML table row with:\n"
    "    • Sequence of cities: show the path step by step, starting at start_location and ending at end_location, with each segment (pickup→dropoff or empty) labeled and colored (loaded segments green, empty segments red, use <span style='color:green'> for loaded and <span style='color:red'> for empty if possible).\n"
    "    • Load IDs (in order), total loaded km, total empty km, loaded %, total km, total revenue, and RPM ($/mile).\n"
    "- Do NOT show step-by-step calculations or explanations—just the final tables.\n"
    "- Format all route information as a single HTML table (no markdown).\n"
    "\n"
    "ADDITIONAL INSTRUCTIONS:\n"
    "- After the table, provide clear HTML bullet points (or a small table) suggesting specific city pairs or segments where adding loads would allow more routes to qualify at 70%+ loaded ratio (e.g., 'A load from City X to City Y would let you chain these routes'). Be explicit about the direction needed.\n"
    "- Do NOT generate hypothetical routes with unassigned loads; just give suggestions for lanes that would enable more efficient chaining based on existing gaps in the data.\n"
    "\n"
    "DATA STRUCTURE:\n"
    "- The `enriched_data` is a JSON object with:\n"
    "    • start_location (string): City where all routes begin.\n"
    "    • end_location (string): City where all routes end.\n"
    "    • loads (array): Each load is an object with:\n"
    "        ◦ load_id (int): Unique identifier.\n"
    "        ◦ pickup (string): Pickup city.\n"
    "        ◦ dropoff (string): Dropoff city.\n"
    "        ◦ revenue (float): rate × weight for this load.\n"
    "        ◦ deadhead_km (float): Distance from start_location to pickup city.\n"
    "        ◦ loaded_km (float): Pickup to dropoff distance.\n"
    "        ◦ return_km (float): Dropoff to end_location.\n"
    "        ◦ reload_options (dict): For each possible next load, gives next pickup, deadhead_from_this_dropoff (empty km), and loaded_km.\n"
    "\n"
    "Here is the enriched_data:\n"
    f"{json.dumps(enriched_data, indent=2)}"
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
    

@app.route("/direct_route_multi", methods=["POST"])
def direct_route_multi():
    data = request.json
    routes = data.get("routes", [])
    if not routes:
        return jsonify({"error": "No routes provided."}), 400

    # --- 1. COLLECT ALL REQUIRED CITY PAIRS ---
    city_pairs = set()
    for route in routes:
        start = normalize_city(route.get("start", ""))
        end = normalize_city(route.get("end", ""))
        loads = route.get("loads", [])
        if loads:
            # Start -> first pickup
            city_pairs.add((start, normalize_city(loads[0]["pickupCity"])))
            # Each load pickup -> dropoff
            for load in loads:
                pickup = normalize_city(load["pickupCity"])
                dropoff = normalize_city(load["dropoffCity"])
                city_pairs.add((pickup, dropoff))
            # Between loads (dropoff -> next pickup)
            for i in range(len(loads) - 1):
                prev_drop = normalize_city(loads[i]["dropoffCity"])
                next_pickup = normalize_city(loads[i+1]["pickupCity"])
                city_pairs.add((prev_drop, next_pickup))
            # Last dropoff -> end
            city_pairs.add((normalize_city(loads[-1]["dropoffCity"]), end))

    # --- 2. FETCH ALL DISTANCES THAT AREN'T CACHED ---
    origin_dest_map = defaultdict(set)
    for origin, dest in city_pairs:
        origin_dest_map[origin].add(dest)
    for origin, dests in origin_dest_map.items():
        get_distances_batch(origin, list(dests))

    # --- 3. CALCULATE AND RENDER ALL ROUTES ---
    all_results = []
    for idx, route in enumerate(routes):
        info, table_html = compute_direct_route_info(route, idx + 1)
        all_results.append(table_html)

    html = """
<html>
<head>
    <style>
        table {{
            border-collapse: collapse;
            margin: 20px 0;
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
        .route-title {{
            font-weight: bold;
            font-size: 18px;
            margin-top: 22px;
            margin-bottom: 8px;
        }}
    </style>
</head>
<body>
    <h2>Direct Route Comparison</h2>
    {}
</body>
</html>
""".format("".join(all_results))


    return html

def compute_direct_route_info(route, route_num=1):
    start = normalize_city(route.get("start", ""))
    end = normalize_city(route.get("end", ""))
    loads = route.get("loads", [])

    loaded_km = 0.0
    empty_km = 0.0
    total_revenue = 0.0
    steps = []
    num_loaded_legs = 0

    if loads:
        # Empty: Start -> first pickup
        first_pickup = normalize_city(loads[0]["pickupCity"])
        empty_to_first = DISTANCE_CACHE.get(get_distance_key(start, first_pickup), 0)
        empty_km += empty_to_first
        steps.append(("Empty", f"{start} → {first_pickup}", empty_to_first, "-", "-", "-", "0.00"))
        # Loaded and empty between loads
        for i, load in enumerate(loads):
            pickup = normalize_city(load["pickupCity"])
            dropoff = normalize_city(load["dropoffCity"])
            rate = float(load.get("rate", 0))
            weight = float(load.get("weight", 0))
            revenue = rate * weight
            dist = DISTANCE_CACHE.get(get_distance_key(pickup, dropoff), 0)
            loaded_km += dist
            total_revenue += revenue
            num_loaded_legs += 1
            # RPM for this loaded segment
            miles = dist * 0.621371
            rpm = (revenue / miles) if miles else 0
            steps.append(("Loaded", f"{pickup} → {dropoff}", dist, rate, weight, revenue, f"{rpm:.2f}"))
            # Empty between this drop and next pickup (if not last)
            if i < len(loads) - 1:
                next_pickup = normalize_city(loads[i+1]["pickupCity"])
                deadhead = DISTANCE_CACHE.get(get_distance_key(dropoff, next_pickup), 0)
                empty_km += deadhead
                steps.append(("Empty", f"{dropoff} → {next_pickup}", deadhead, "-", "-", "-", "0.00"))
        # Empty: Last drop -> end
        last_drop = normalize_city(loads[-1]["dropoffCity"])
        empty_back = DISTANCE_CACHE.get(get_distance_key(last_drop, end), 0)
        empty_km += empty_back
        steps.append(("Empty", f"{last_drop} → {end}", empty_back, "-", "-", "-", "0.00"))

    total_km = loaded_km + empty_km
    loaded_pct = (loaded_km / total_km * 100) if total_km else 0
    total_miles = total_km * 0.621371
    rpm = (total_revenue / total_miles) if total_miles else 0

    # Calculate hourly rate
    # Hours = driving + 1hr load + 1hr unload per loaded leg
    driving_hours = total_km / 85 if total_km else 0
    total_hours = driving_hours + 2 * num_loaded_legs
    hourly_rate = (total_revenue / total_hours) if total_hours else 0

    table = f'<div class="route-title">Route {route_num}: {start} → {end}</div>'
    table += "<table><tr><th>Step</th><th>Segment</th><th>KMs</th><th>Rate</th><th>Weight</th><th>Revenue</th><th>RPM ($/mile)</th></tr>"
    for t in steps:
        table += f"<tr>{''.join(f'<td>{x}</td>' for x in t)}</tr>"
    table += "</table>"
    table += f"""
    <table>
    <tr>
      <th>Total Loaded KM</th>
      <th>Total Empty KM</th>
      <th>Total KM</th>
      <th>Loaded %</th>
      <th>Total Revenue ($)</th>
      <th>RPM ($/mile)</th>
      <th>Hourly Rate ($/hour)</th>
    </tr>
    <tr>
      <td>{loaded_km:.1f}</td>
      <td>{empty_km:.1f}</td>
      <td>{total_km:.1f}</td>
      <td>{loaded_pct:.1f}%</td>
      <td>{total_revenue:,.2f}</td>
      <td>{rpm:.2f}</td>
      <td>{hourly_rate:.2f}</td>
    </tr>
    </table>
    """
    return {
        "loaded_km": loaded_km, "empty_km": empty_km, "total_km": total_km,
        "loaded_pct": loaded_pct, "total_revenue": total_revenue, "rpm": rpm,
        "hourly_rate": hourly_rate
    }, table


@app.route("/")
def show_dispatch_form():
    return render_template("dispatch_form.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
