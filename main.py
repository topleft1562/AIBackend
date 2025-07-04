import os
import json
import requests
from urllib.parse import unquote
from agent_engine import get_agent_runner
from flask import Flask, render_template, request, jsonify, render_template_string
from collections import defaultdict
from planner import generate_plan


app = Flask(__name__)

# Initialize LLM Agent for AI Mode
agent = get_agent_runner()

GOOGLE_KEY = os.environ.get("GOOGLE_KEY")

# Distance cache: ("origin|destination") => km
DISTANCE_CACHE = {}

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
        steps.append({
            "type": "empty",
            "segment": f"{start} → {first_pickup}",
            "kms": empty_to_first,
            "rate": "-",
            "weight": "-",
            "revenue": "-",
            "rpm": "0.00"
        })
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
            miles = dist * 0.621371
            rpm = (revenue / miles) if miles else 0
            steps.append({
                "type": "loaded",
                "segment": f"{pickup} → {dropoff}",
                "kms": dist,
                "rate": rate,
                "weight": weight,
                "revenue": revenue,
                "rpm": f"{rpm:.2f}"
            })
            # Empty between this drop and next pickup (if not last)
            if i < len(loads) - 1:
                next_pickup = normalize_city(loads[i+1]["pickupCity"])
                deadhead = DISTANCE_CACHE.get(get_distance_key(dropoff, next_pickup), 0)
                empty_km += deadhead
                steps.append({
                    "type": "empty",
                    "segment": f"{dropoff} → {next_pickup}",
                    "kms": deadhead,
                    "rate": "-",
                    "weight": "-",
                    "revenue": "-",
                    "rpm": "0.00"
                })
        # Empty: Last drop -> end
        last_drop = normalize_city(loads[-1]["dropoffCity"])
        empty_back = DISTANCE_CACHE.get(get_distance_key(last_drop, end), 0)
        empty_km += empty_back
        steps.append({
            "type": "empty",
            "segment": f"{last_drop} → {end}",
            "kms": empty_back,
            "rate": "-",
            "weight": "-",
            "revenue": "-",
            "rpm": "0.00"
        })

    total_km = loaded_km + empty_km
    loaded_pct = (loaded_km / total_km * 100) if total_km else 0
    total_miles = total_km * 0.621371
    rpm = (total_revenue / total_miles) if total_miles else 0

    driving_hours = total_km / 85 if total_km else 0
    total_hours = driving_hours + 2 * num_loaded_legs
    hourly_rate = (total_revenue / total_hours) if total_hours else 0

    summary = {
        "route_num": route_num,
        "start": start,
        "end": end,
        "loaded_km": round(loaded_km, 1),
        "empty_km": round(empty_km, 1),
        "total_km": round(total_km, 1),
        "loaded_pct": round(loaded_pct, 1),
        "total_revenue": round(total_revenue, 2),
        "rpm": round(rpm, 2),
        "hourly_rate": round(hourly_rate, 2)
    }
    return summary, steps

def enumerate_qualifying_routes(enriched_data, loaded_pct_threshold=0.65, max_chain_amount=6):
    start = enriched_data["start_location"]
    end = enriched_data["end_location"]
    loads = enriched_data["loads"]
    results = []
    required_ids = {load["load_id"] for load in loads if load.get("required")}

    def search(path, used_ids, loaded_km, empty_km, revenue, city_steps):
        # Prune by max chain length
        if len(path) > max_chain_amount:
            return
        if path:
            total_km = loaded_km + empty_km + path[-1]["return_km"]
            loaded_pct = loaded_km / total_km if total_km else 0
            route_ids = {l["load_id"] for l in path}
            if loaded_pct >= loaded_pct_threshold and (not required_ids or required_ids.issubset(route_ids)):
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
                    "step_breakdown": []
                })
            # Prune if max possible loaded pct is now below threshold
            remaining_loaded = sum(l["loaded_km"] for l in loads if l["load_id"] not in used_ids)
            possible_total = loaded_km + remaining_loaded
            possible_km = total_km + remaining_loaded
            if possible_km and (possible_total / possible_km < loaded_pct_threshold):
                return

        # --- EARLY PRUNE for required loads ---
        remaining_unused = [l for l in loads if l["load_id"] not in used_ids]
        remaining_required = required_ids - set([l["load_id"] for l in path])
        if len(remaining_unused) < len(remaining_required):
            return

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
                    continue
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

@app.route("/dispatch", methods=["POST"])
def handle_dispatch():
    # AI mode (HTML output)
    data = request.json
    loads = data.get("loads", [])
    start_location = data.get("start", "Brandon, MB")
    end_location = data.get("end", "Brandon, MB")
    loaded_pct_goal = float(data.get("loaded_pct_goal", 65)) / 100
    max_chain_amount = int(data.get("max_chain_amount", 6))

    if not loads:
        return jsonify({"error": "Missing loads in request."}), 400

    try:
        start = normalize_city(start_location)
        end = normalize_city(end_location)

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
                "loaded_km": round(DISTANCE_CACHE.get(get_distance_key(pickup, dropoff), 0), 1),
                "return_km": DISTANCE_CACHE.get(get_distance_key(dropoff, end), 0),
                "reload_options": reload_options,
            })
        enriched_data = {
            "start_location": start,
            "end_location": end,
            "loads": result
        }

        # Add extra info for LLM if you want (not required for this example)

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
            f"- Only list routes that are {int(loaded_pct_goal*100)}% loaded or higher.\n"
            "- DO NOT include or list any routes where loaded % is less than this threshold. "
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
        response = agent.stream_chat(prompt)
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
    # Returns JSON list, one per trip
    data = request.json
    routes = data.get("routes", [])
    if not routes:
        return jsonify({"error": "No routes provided."}), 400

    city_pairs = set()
    for route in routes:
        start = normalize_city(route.get("start", ""))
        end = normalize_city(route.get("end", ""))
        loads = route.get("loads", [])
        if loads:
            city_pairs.add((start, normalize_city(loads[0]["pickupCity"])))
            for load in loads:
                pickup = normalize_city(load["pickupCity"])
                dropoff = normalize_city(load["dropoffCity"])
                city_pairs.add((pickup, dropoff))
            for i in range(len(loads) - 1):
                prev_drop = normalize_city(loads[i]["dropoffCity"])
                next_pickup = normalize_city(loads[i+1]["pickupCity"])
                city_pairs.add((prev_drop, next_pickup))
            city_pairs.add((normalize_city(loads[-1]["dropoffCity"]), end))

    origin_dest_map = defaultdict(set)
    for origin, dest in city_pairs:
        origin_dest_map[origin].add(dest)
    for origin, dests in origin_dest_map.items():
        get_distances_batch(origin, list(dests))

    all_results = []
    for idx, route in enumerate(routes):
        summary, breakdown = compute_direct_route_info(route, idx + 1)
        all_results.append({
            "summary": summary,
            "step_breakdown": breakdown
        })
    return jsonify(all_results)

@app.route("/manual", methods=["POST"])
def handle_manual_routes():
    data = request.json
    loads = data.get("loads", [])
    start_location = data.get("start", "Brandon, MB")
    end_location = data.get("end", "Brandon, MB")
    loaded_pct_goal = float(data.get("loaded_pct_goal", 65)) / 100
    max_chain_amount = int(data.get("max_chain_amount", 6))

    if not loads:
        return jsonify({"error": "Missing loads in request."}), 400

    try:
        start = normalize_city(start_location)
        end = normalize_city(end_location)

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
                "rate": load["rate"],
                "weight": load["weight"],
                "deadhead_km": DISTANCE_CACHE.get(get_distance_key(start, pickup), 0),
                "loaded_km": round(DISTANCE_CACHE.get(get_distance_key(pickup, dropoff), 0), 1),
                "return_km": DISTANCE_CACHE.get(get_distance_key(dropoff, end), 0),
                "reload_options": reload_options,
                "required": load.get("required", False),
            })
        enriched_data = {
            "start_location": start,
            "end_location": end,
            "loads": result
        }

        routes = enumerate_qualifying_routes(
            enriched_data,
            loaded_pct_threshold=loaded_pct_goal,
            max_chain_amount=max_chain_amount
        )

        # For each summary route, expand to breakdown like direct
        expanded = []
        for idx, route in enumerate(routes):
            trip_loads = []
            for lid in route["load_ids"]:
                found = next((l for l in result if l["load_id"] == lid), None)
                if found:
                    trip_loads.append({
                        "pickupCity": found["pickup"],
                        "dropoffCity": found["dropoff"],
                        "rate": found.get("rate", 0),
                        "weight": found.get("weight", 0)
                    })
            trip_route = {"start": start, "end": end, "loads": trip_loads}
            summary, step_breakdown = compute_direct_route_info(trip_route)
            route["step_breakdown"] = step_breakdown
            route["summary"] = summary
            # Overwrite the top-level fields with computed breakdown
            route["loaded_km"] = summary["loaded_km"]
            route["empty_km"] = summary["empty_km"]
            route["total_km"] = summary["total_km"]
            route["loaded_pct"] = summary["loaded_pct"]
            route["revenue"] = summary["total_revenue"]
            route["rpm"] = summary["rpm"]
            route["hourly_rate"] = summary["hourly_rate"]
            expanded.append(route)

        return jsonify(expanded)

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route("/ai_plan", methods=["POST"])
def ai_plan():
    try:
        data = request.get_json()
        loads = data.get("loads", [])
        drivers = data.get("drivers", [])
        min_efficiency = float(data.get("min_efficiency", 0.7))

        if not loads or not drivers:
            return jsonify({"error": "Missing loads or drivers"}), 400

        # 🔥 Build the route matrix here
        route_matrix = build_route_matrix(loads, drivers)

        plan = generate_plan(loads, drivers, route_matrix, min_efficiency)
        return jsonify(plan)

    except Exception as e:
        return jsonify({"error": str(e)}), 500



if __name__ == "__main__":
    app.run(port=5050, debug=True)

@app.route("/")
def show_dispatch_form():
    return render_template("dispatch_form.html", google_api_key=GOOGLE_KEY)

@app.route("/ai")
def show_ai_form():
    return render_template("ai_planner_form.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
