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
                    "deadhead_to_this_pickup": DISTANCE_CACHE.get(get_distance_key(dropoff, other["pickupCity"]), 0),
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
    "You are Dispatchy, a logistics planning expert. "
    "You are given load and distance data (`enriched_data`) describing possible freight loads, their cities, and the distances between all relevant points.\n"
    "\n"
    "Consider every possible sequence (order) of loads—do not limit to just one or two orders. For example, if there are three loads, test all possible chaining orders (such as 1-2-3, 1-3-2, 2-1-3, etc.)."
    "Explicitly enumerate all possible orderings and include all qualifying routes."
    "Your goal is to calculate EVERY possible valid route (any order, no repeats, all combinations some single loads to all chained together.) that:\n"
    "- Starts at `start_location` and ends at `end_location`.\n"
    "- For each route, calculates metrics as follows:\n"
    "    1. **Empty km**: Sum the following:\n"
    "       - The `deadhead_km` (distance from start_location to first load's pickup).\n"
    "       - For each pair of consecutive loads in the route, add the `deadhead_to_this_pickup` from the previous load's `reload_options`, using the next load's load_id as key.\n"
    "       - The `return_km` (distance from the last load's dropoff to end_location).\n"
    "    2. **Loaded km**: Sum each load's `loaded_km` (pickup to dropoff).\n"
    "    3. **Total km**: loaded km + empty km.\n"
    "    4. **Loaded %**: loaded km / total km.\n"
    "    5. **Revenue**: For each load, revenue = rate × weight; total revenue is sum of all loads in the route.\n"
    "    6. **RPM ($/mile)**: total revenue / (total km × 0.621371).\n"
    "- Only list routes that are 65% loaded or higher.\n"
    "- DO NOT include or list any routes where loaded % is less than 65%. "
    "- DO NOT explain, show, or mention any route below the threshold—only show those that qualify."
    "- Important: Do NOT use revenue or RPM as a filter. They are for display only."
    "- Always show all qualifying routes, even if revenue or RPM is zero."
    "\n"
    "**Important Calculation Recipe:**\n"
    "For a route like: Load A → Load B → Load C:\n"
    "- Empty km = deadhead_km (from load A) + deadhead_to_this_pickup (from reload option A for B) + deadhead_to_this_pickup (from reload option B for C) + return_km (from load C)\n"
    "- Loaded km = loaded_km for A + B + C\n"
    "\n"
    "Present each qualifying route as an HTML table row, showing:\n"
    "- For each route, show the sequence of city steps, color-coded as follows: "
    "start points in <span style='color:green'>green</span>, "
    "each pickup (loading) point in <span style='color:blue'>blue</span>, "
    "each dropoff (unloading) point in <span style='color:red'>red</span>, "
    "and any empty (deadhead) move to the end location also in <span style='color:red'>red</span>. "
    "After the city sequence, show: load_ids (in order), total loaded km, total empty km, loaded %, total km, total revenue, and RPM ($/mile). "
    "- Format ONLY as an HTML table (no markdown, no explanations).\n"
    "\n"
    "After the table, give HTML bullet-point suggestions on which city pairs (and in which direction) would make new chains more efficient if more loads were available.\n"
    "\n"
    "The data structure is as follows:\n"
    "- start_location (string): Starting city.\n"
    "- end_location (string): Ending city.\n"
    "- loads (array): Each with:\n"
    "  - load_id (int), pickup (string), dropoff (string), revenue (float), deadhead_km (float), loaded_km (float), return_km (float), reload_options (dict of next load_id: {'pickup', 'deadhead_to_this_pickup': empty kms to this pickup, 'loaded_km': loaded kms for this load})\n"
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


def enumerate_qualifying_routes(enriched_data, loaded_pct_threshold=0.65):
    start = enriched_data["start_location"]
    end = enriched_data["end_location"]
    loads = enriched_data["loads"]
    results = []
    required_ids = {load["load_id"] for load in loads if load.get("required")}

    def search(path, used_ids, loaded_km, empty_km, revenue, city_steps):
        if path:
            total_km = loaded_km + empty_km + path[-1]["return_km"]
            loaded_pct = loaded_km / total_km if total_km else 0
            route_ids = {l["load_id"] for l in path}
            if loaded_pct >= loaded_pct_threshold and required_ids.issubset(route_ids):
                seq = city_steps + [f"<span style='color:red'>{end}</span>"]
                total_miles = total_km * 0.621371
                rpm = (revenue / total_miles) if total_miles else 0
                results.append({
                    "city_sequence": " → ".join(seq),
                    "load_ids": [l["load_id"] for l in path],
                    "loaded_km": round(loaded_km, 1),
                    "empty_km": round(empty_km + path[-1]["return_km"], 1),
                    "loaded_pct": round(loaded_pct * 100, 1),
                    "total_km": round(total_km, 1),
                    "revenue": round(revenue, 2),
                    "rpm": round(rpm, 2),
                })
            # Prune if max possible loaded pct is now below threshold
            remaining_loaded = sum(l["loaded_km"] for l in loads if l["load_id"] not in used_ids)
            possible_total = loaded_km + remaining_loaded
            possible_km = total_km + remaining_loaded
            if possible_km and (possible_total / possible_km < loaded_pct_threshold):
                return  # Can't recover above threshold, prune

        # --- EARLY PRUNE for required loads ---
        remaining_unused = [l for l in loads if l["load_id"] not in used_ids]
        remaining_required = required_ids - set([l["load_id"] for l in path])
        if len(remaining_unused) < len(remaining_required):
            return  # Not enough loads left to satisfy required set

        for load in loads:
            lid = load["load_id"]
            if lid in used_ids:
                continue
            if not path:
                new_empty = load["deadhead_km"]
                new_loaded = load["loaded_km"]
                new_revenue = load.get("revenue", 0.0)
                new_steps = [
                    f"<span style='color:green'>{start}</span>",
                    f"<span style='color:blue'>{load['pickup']}</span>",
                    f"<span style='color:red'>{load['dropoff']}</span>",
                ]
                search([load], used_ids | {lid}, new_loaded, new_empty, new_revenue, new_steps)
            else:
                prev = path[-1]
                reload_key = f"load_{lid}"
                reload_info = prev["reload_options"].get(reload_key)
                if not reload_info:
                    continue  # Can't chain
                new_empty = empty_km + reload_info.get("deadhead_from_this_dropoff", reload_info.get("deadhead_to_this_pickup", 0))
                new_loaded = loaded_km + load["loaded_km"]
                new_revenue = revenue + load.get("revenue", 0.0)
                new_steps = city_steps + [
                    f"<span style='color:blue'>{load['pickup']}</span>",
                    f"<span style='color:red'>{load['dropoff']}</span>",
                ]
                search(path + [load], used_ids | {lid}, new_loaded, new_empty, new_revenue, new_steps)

    search([], set(), 0, 0, 0, [])
    results.sort(key=lambda r: (-r["loaded_pct"], -r["revenue"]))
    return results



@app.route("/manual", methods=["POST"])
def handle_manual_routes():
    data = request.json
    loads = data.get("loads", [])
    start_location = data.get("start", "Brandon, MB")
    end_location = data.get("end", "Brandon, MB")

    if not loads:
        return jsonify({"error": "Missing loads in request."}), 400

    try:
        start = normalize_city(start_location)
        end = normalize_city(end_location)

        # -- Data prep as before --
        for i, load in enumerate(loads):
            load["load_id"] = i + 1
            load["pickupCity"] = normalize_city(load["pickupCity"])
            load["dropoffCity"] = normalize_city(load["dropoffCity"])
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
                    "deadhead_to_this_pickup": DISTANCE_CACHE.get(get_distance_key(dropoff, other["pickupCity"]), 0),
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
                "loaded_km": round(DISTANCE_CACHE.get(get_distance_key(pickup, dropoff), 1)),
                "return_km": DISTANCE_CACHE.get(get_distance_key(dropoff, end), 0),
                "reload_options": reload_options,
                "required": load.get("required", False),
            })
        enriched_data = {
           "start_location": start,
           "end_location": end,
            "loads": result
        }

        routes = enumerate_qualifying_routes(enriched_data, loaded_pct_threshold=0.65)

        # ---- HTML TABLE RENDER ----
        if routes:
            table_html = """<table>
            <tr>
              <th>City Sequence</th>
              <th>Load IDs</th>
              <th>Loaded km</th>
              <th>Empty km</th>
              <th>Loaded %</th>
              <th>Total km</th>
              <th>Revenue</th>
              <th>RPM ($/mile)</th>
            </tr>
            """
            for route in routes:
                table_html += f"<tr><td>{route['city_sequence']}</td><td>{', '.join(map(str,route['load_ids']))}</td><td>{route['loaded_km']}</td><td>{route['empty_km']}</td><td>{route['loaded_pct']}%</td><td>{route['total_km']}</td><td>{route['revenue']}</td><td>{route['rpm']}</td></tr>"
            table_html += "</table>"
        else:
            table_html = "<div style='color:#e53e3e'>No routes found with 65%+ loaded km.</div>"

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
                    <h2>Manual Best Route(s)</h2>
                    {table_html}
                </body>
            </html>
        """)

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500




@app.route("/")
def show_dispatch_form():
    return render_template("dispatch_form.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
