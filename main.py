import os
import json
import requests
from urllib.parse import unquote
from agent_engine import get_agent_runner
from flask import Flask, render_template, request, jsonify, render_template_string
from collections import defaultdict

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
    """
    Multi-driver, AI mode (JSON API).
    - Accepts: { drivers: [{start, end}], loads: [], loaded_pct_goal, max_chain_amount }
    - Returns: [{ driver: {...}, routes: [ {summary, step_breakdown}, ... ] }, ...]
    """
    data = request.json
    drivers = data.get("drivers", [])
    loads = data.get("loads", [])
    loaded_pct_goal = float(data.get("loaded_pct_goal", 65)) / 100
    max_chain_amount = int(data.get("max_chain_amount", 6))
    TOP_N = 5  # Show top 5 routes per driver

    if not drivers or not loads:
        return jsonify({"error": "Missing drivers or loads in request."}), 400

    # Prepare loads and distances (enrich once, use for all drivers)
    for i, load in enumerate(loads):
        load["load_id"] = i + 1
        load["pickupCity"] = normalize_city(load["pickupCity"])
        load["dropoffCity"] = normalize_city(load["dropoffCity"])
        load["rate"] = float(load.get("rate", 0))
        load["weight"] = float(load.get("weight", 0))
        load["revenue"] = load["rate"] * load["weight"]

    # Build global distance cache (for all driver starts/ends)
    city_pairs = set()
    for driver in drivers:
        start = normalize_city(driver.get("start", "Brandon, MB"))
        end = normalize_city(driver.get("end", "Brandon, MB"))
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

    # Add reload_options to all loads
    enriched_loads = []
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
        enriched_loads.append({
            **load,
            "reload_options": reload_options
        })

    all_results = []

    # For each driver, let the LLM suggest route orders (top N), then re-calculate actual metrics and breakdowns
    for driver in drivers:
        start = normalize_city(driver.get("start", "Brandon, MB"))
        end = normalize_city(driver.get("end", "Brandon, MB"))

        # Prepare payload for AI
        enriched_data = {
            "start_location": start,
            "end_location": end,
            "loads": enriched_loads
        }

        # LLM prompt for this driver
        prompt = (
            "You are Dispatchy, a logistics optimization assistant. "
            "Given the loads and all distances (see reload_options for empty kms between any two loads), "
            "find and list the top 5 most efficient route orderings for this driver, where: \n"
            f"- The route starts at: {start}\n"
            f"- The route ends at: {end}\n"
            f"- Each route is a unique sequence of one or more loads (no repeats).\n"
            f"- Do not include any route with loaded % below {int(loaded_pct_goal*100)}%.\n"
            f"- Do not chain more than {max_chain_amount} loads in a route.\n"
            f"- Return for each route: a list of load_ids (in order).\n"
            f"- Order the routes by highest loaded % and then revenue.\n"
            f"- Output ONLY JSON as: "
            "[ {\"load_ids\": [1,2,3], \"loaded_pct\": 83.5, \"revenue\": 4600.00}, ... ]\n"
            f"- No explanations, no markdown—just a JSON array with a maximum of 5 entries.\n"
            "\n"
            "Data follows:\n"
            f"{json.dumps(enriched_data, indent=2)}"
        )

        # Call LLM and parse
        response = agent.chat(prompt)
        try:
            ai_routes = json.loads(response.response)
        except Exception:
            # fallback if LLM puts text or JSON in code block
            import re
            match = re.search(r"\[\s*{.*?}\s*\]", response.response, re.DOTALL)
            if match:
                ai_routes = json.loads(match.group(0))
            else:
                ai_routes = []

        # Now for each AI route, compute step_breakdown and summary
        expanded_routes = []
        for idx, ai_route in enumerate(ai_routes[:TOP_N]):
            # Build route object as required by compute_direct_route_info
            trip_loads = []
            for lid in ai_route.get("load_ids", []):
                found = next((l for l in enriched_loads if l["load_id"] == lid), None)
                if found:
                    trip_loads.append({
                        "pickupCity": found["pickupCity"],
                        "dropoffCity": found["dropoffCity"],
                        "rate": found.get("rate", 0),
                        "weight": found.get("weight", 0)
                    })
            trip_route = {"start": start, "end": end, "loads": trip_loads}
            summary, step_breakdown = compute_direct_route_info(trip_route, idx + 1)
            expanded_routes.append({
                "summary": summary,
                "step_breakdown": step_breakdown
            })

        all_results.append({
            "driver": {"start": start, "end": end},
            "routes": expanded_routes
        })

    return jsonify(all_results)


@app.route("/direct_route_multi", methods=["POST"])
def direct_route_multi():
    data = request.json
    all_results = []

    # Always expect drivers + loads, no legacy handling
    drivers = data.get("drivers", [])
    loads = data.get("loads", [])

    if not drivers or not loads:
        return jsonify({"error": "Missing drivers or loads in request."}), 400

    for idx, driver in enumerate(drivers):
        start = normalize_city(driver.get("start", "Brandon, MB"))
        end = normalize_city(driver.get("end", "Brandon, MB"))
        route = {
            "start": start,
            "end": end,
            "loads": loads
        }
        summary, breakdown = compute_direct_route_info(route, idx + 1)
        # Structure as array of drivers, each with a routes array (for future flexibility)
        all_results.append({
            "driver": {"start": start, "end": end},
            "routes": [
                {
                    "summary": summary,
                    "step_breakdown": breakdown
                }
            ]
        })
    return jsonify(all_results)



@app.route("/manual", methods=["POST"])
def handle_manual_routes():
    data = request.json
    drivers = data.get("drivers", [])
    loads = data.get("loads", [])
    loaded_pct_goal = float(data.get("loaded_pct_goal", 65)) / 100
    max_chain_amount = int(data.get("max_chain_amount", 6))

    if not drivers or not loads:
        return jsonify({"error": "Missing drivers or loads in request."}), 400

    all_results = []

    for driver in drivers:
        start_location = driver.get("start", "Brandon, MB")
        end_location = driver.get("end", "Brandon, MB")

        start = normalize_city(start_location)
        end = normalize_city(end_location)

        # Prepare loads for this run (assign IDs only once at the top)
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

        all_results.append({
            "driver": {"start": start, "end": end},
            "routes": expanded
        })

    return jsonify(all_results)


@app.route("/")
def show_dispatch_form():
    return render_template("dispatch_form.html", google_api_key=GOOGLE_KEY)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
