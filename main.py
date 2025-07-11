import os
import json
import requests
from urllib.parse import unquote
from agent_engine import get_agent_runner
from flask import Flask, render_template, request, jsonify, render_template_string
from collections import defaultdict
from planner import generate_plan
from routing import build_route_matrix, get_loaded_distance_with_routepoints
from threading import Thread, Lock
from queue import Queue
import uuid

app = Flask(__name__)

# Initialize LLM Agent for AI Mode
agent = get_agent_runner()

GOOGLE_KEY = os.environ.get("GOOGLE_KEY")

# Distance cache: ("origin|destination") => km
DISTANCE_CACHE = {}
TASKS = {}

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
        # Empty: Start → first pickup
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

        for i, load in enumerate(loads):
            pickup = normalize_city(load["pickupCity"])
            dropoff = normalize_city(load["dropoffCity"])
            route_points = [normalize_city(p) for p in load.get("routePoints", [])]

            rate = load.get("rate", "-")
            weight = load.get("weight", "-")
            revenue = rate * weight

            # Build city list: pickup → [route points] → dropoff
            cities = [pickup] + route_points + [dropoff]
            segment_label = " → ".join(cities)

            dist = 0
            for j in range(len(cities) - 1):
                dist += DISTANCE_CACHE.get(get_distance_key(cities[j], cities[j + 1]), 0)

            loaded_km += dist
            total_revenue += revenue
            num_loaded_legs += 1
            miles = dist * 0.621371
            rpm = (revenue / miles) if miles else 0

            steps.append({
                "type": "loaded",
                "segment": segment_label,
                "kms": round(dist, 1),
                "rate": rate,
                "weight": weight,
                "revenue": revenue,
                "rpm": f"{rpm:.2f}"
            })

            # Empty between this dropoff and next pickup
            if i < len(loads) - 1:
                next_pickup = normalize_city(loads[i + 1]["pickupCity"])
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

        # Final empty: last dropoff → end
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


def enumerate_qualifying_routes_threaded(enriched_data, loaded_pct_threshold=0.65, max_chain_amount=6, num_threads=12, task_progress_hook=None):
    start = enriched_data["start_location"]
    end = enriched_data["end_location"]
    loads = enriched_data["loads"]
    required_ids = {load["load_id"] for load in loads if load.get("required")}

    results = []
    result_lock = Lock()
    progress_queue = Queue()
    task_queue = Queue()

    for load in loads:
        task_queue.put(load)

    total_tasks = task_queue.qsize()
    progress_done = 0

    def get_load_revenue(load):
        return load["rate"] * load["weight"]

    def get_load_loaded_km(load):
        return get_loaded_distance_with_routepoints(
            load["pickup"], load.get("routePoints", []), load["dropoff"]
        )

    def search(path, used_ids, loaded_km, empty_km, revenue, city_steps, local_results):
        if task_progress_hook and callable(getattr(task_progress_hook, "check_cancelled", None)):
            if task_progress_hook.check_cancelled():
                raise Exception("Task cancelled")

        if len(path) >= max_chain_amount:
            return

        total_km = loaded_km + empty_km + path[-1]["return_km"]
        loaded_pct = loaded_km / total_km if total_km else 0
        route_ids = {l["load_id"] for l in path}
        if loaded_pct >= loaded_pct_threshold and (not required_ids or required_ids.issubset(route_ids)):
            seq = city_steps + [f"<span style='color:red'>{end}</span>"]
            total_miles = total_km * 0.621371
            rpm = (revenue / total_miles) if total_miles else 0
            local_results.append({
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

        remaining_loaded = sum(get_load_loaded_km(l) for l in loads if l["load_id"] not in used_ids)
        possible_total = loaded_km + remaining_loaded
        possible_km = total_km + remaining_loaded
        if possible_km and (possible_total / possible_km < loaded_pct_threshold):
            return

        remaining_unused = [l for l in loads if l["load_id"] not in used_ids]
        remaining_required = required_ids - set([l["load_id"] for l in path])
        if len(remaining_unused) < len(remaining_required):
            return

        for load in loads:
            lid = load["load_id"]
            if lid in used_ids:
                continue
            prev = path[-1]
            reload_info = prev["reload_options"].get(f"load_{lid}")
            if not reload_info:
                continue

            new_empty = empty_km + reload_info.get("deadhead_from_this_dropoff", reload_info.get("deadhead_to_this_pickup", 0))
            new_loaded = loaded_km + get_load_loaded_km(load)
            new_revenue = revenue + get_load_revenue(load)

            step_cities = [f"<span style='color:blue'>{load['pickup']}</span>"]
            for rp in load.get("routePoints", []):
                step_cities.append(f"<span style='color:orange'>{rp.title()}</span>")
            step_cities.append(f"<span style='color:red'>{load['dropoff']}</span>")

            new_steps = city_steps + step_cities

            search(path + [load], used_ids | {lid}, new_loaded, new_empty, new_revenue, new_steps, local_results)

    def worker():
        while not task_queue.empty():
            try:
                load = task_queue.get_nowait()
            except:
                break
            lid = load["load_id"]
            local_results = []
            try:
                step_cities = [
                    f"<span style='color:green'>{start}</span>",
                    f"<span style='color:blue'>{load['pickup']}</span>",
                ]
                for rp in load.get("routePoints", []):
                    step_cities.append(f"<span style='color:orange'>{rp.title()}</span>")
                step_cities.append(f"<span style='color:red'>{load['dropoff']}</span>")

                search(
                    [load],
                    {lid},
                    get_load_loaded_km(load),
                    load["deadhead_km"],
                    get_load_revenue(load),
                    step_cities,
                    local_results
                )

                with result_lock:
                    results.extend(local_results)
            except Exception as e:
                print(f"[Worker] Load {lid} failed: {e}")
            finally:
                progress_queue.put(1)

    threads = [Thread(target=worker) for _ in range(num_threads)]
    for t in threads:
        t.start()

    while any(t.is_alive() for t in threads):
        while not progress_queue.empty():
            progress_done += progress_queue.get()
            pct = int(progress_done / total_tasks * 100)
            if task_progress_hook:
                task_progress_hook(pct)
            else:
                print(f"Progress: {pct}%")

    for t in threads:
        t.join()

    results.sort(key=lambda r: (-r["loaded_pct"], -r["revenue"]))
    return results




@app.route("/cancel_task/<task_id>", methods=["POST"])
def cancel_task(task_id):
    if task_id in TASKS and TASKS[task_id]["state"] == "in_progress":
        TASKS[task_id]["cancelled"] = True
        return jsonify({"status": "cancelled"})
    return jsonify({"status": "not_found or already complete"}), 400

@app.route("/dispatch_async", methods=["POST"])
def dispatch_async():
    data = request.json
    task_id = str(uuid.uuid4())
    TASKS[task_id] = {
        "state": "in_progress",
        "progress": 0,
        "result": None,
        "cancelled": False
    }


    def run_task():
        try:
            TASKS[task_id]["progress"] = 10

            # Extract & normalize input
            loads = data.get("loads", [])
            start_location = normalize_city(data.get("start", "Brandon, MB"))
            end_location = normalize_city(data.get("end", "Brandon, MB"))
            loaded_pct_goal = float(data.get("loaded_pct_goal", 65)) / 100
            max_chain_amount = int(data.get("max_chain_amount", 6))

            for i, load in enumerate(loads):
                load["load_id"] = i + 1
                load["pickupCity"] = normalize_city(load["pickupCity"])
                load["dropoffCity"] = normalize_city(load["dropoffCity"])
                load["routePoints"] = [normalize_city(p) for p in load.get("routePoints", [])]
                load["rate"] = float(load.get("rate", 0))
                load["weight"] = float(load.get("weight", 0))
                load["revenue"] = load["rate"] * load["weight"]

            TASKS[task_id]["progress"] = 15

            # Pre-fetch all needed distances
            city_pairs = set()
            for load in loads:
                pickup = load["pickupCity"]
                dropoff = load["dropoffCity"]
                route_points = load.get("routePoints", [])
                cities = [pickup] + route_points + [dropoff]

                city_pairs.add((start_location, pickup))
                for i in range(len(cities) - 1):
                    city_pairs.add((cities[i], cities[i + 1]))
                city_pairs.add((dropoff, end_location))
                for other in loads:
                    city_pairs.add((dropoff, other["pickupCity"]))

            origin_dest_map = defaultdict(set)
            for origin, dest in city_pairs:
                origin_dest_map[origin].add(dest)
            for origin, dests in origin_dest_map.items():
                get_distances_batch(origin, list(dests))

            TASKS[task_id]["progress"] = 20

            # Build enriched loads with reload options
            result = []
            for load in loads:
                pickup = load["pickupCity"]
                dropoff = load["dropoffCity"]
                reload_options = {
                    f"load_{other['load_id']}": {
                        "pickup": other["pickupCity"],
                        "deadhead_to_this_pickup": DISTANCE_CACHE.get(get_distance_key(dropoff, other["pickupCity"]), 0),
                        "loaded_km": sum(
                            DISTANCE_CACHE.get(get_distance_key(cities[i], cities[i + 1]), 0)
                            for i in range(len(cities) - 1)
                        )   
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
                    "deadhead_km": DISTANCE_CACHE.get(get_distance_key(start_location, pickup), 0),
                    "loaded_km": round(DISTANCE_CACHE.get(get_distance_key(pickup, dropoff), 0), 1),
                    "return_km": DISTANCE_CACHE.get(get_distance_key(dropoff, end_location), 0),
                    "reload_options": reload_options,
                    "required": load.get("required", False),
                })

            enriched_data = {
                "start_location": start_location,
                "end_location": end_location,
                "loads": result
            }

            TASKS[task_id]["progress"] = 30

            def make_progress_hook(task_id):
                def hook(pct):
                    if TASKS[task_id].get("cancelled"):
                        raise Exception("Task cancelled")
                    TASKS[task_id]["progress"] = 30 + int(pct * 0.7)
                hook.check_cancelled = lambda: TASKS[task_id].get("cancelled", False)
                return hook 

            # Calculate all qualifying routes
            routes = enumerate_qualifying_routes_threaded(
                enriched_data,
                loaded_pct_threshold=loaded_pct_goal,
                max_chain_amount=max_chain_amount,
                num_threads=12,
                task_progress_hook=make_progress_hook(task_id)
            )

            # Cap to top 100 results and compute breakdowns
            expanded = []
            for idx, route in enumerate(routes[:100]):
                trip_loads = []
                for lid in route["load_ids"]:
                    found = next((l for l in enriched_data["loads"] if l["load_id"] == lid), None)
                    if found:
                        trip_loads.append({
                            "pickupCity": found["pickup"],
                            "dropoffCity": found["dropoff"],
                            "rate": found.get("rate", 0),
                            "weight": found.get("weight", 0)
                        })
                trip_route = {
                    "start": enriched_data["start_location"],
                    "end": enriched_data["end_location"],
                    "loads": trip_loads
                }
                summary, step_breakdown = compute_direct_route_info(trip_route)
                route["summary"] = summary
                route["step_breakdown"] = step_breakdown
                route["loaded_km"] = summary["loaded_km"]
                route["empty_km"] = summary["empty_km"]
                route["total_km"] = summary["total_km"]
                route["loaded_pct"] = summary["loaded_pct"]
                route["revenue"] = summary["total_revenue"]
                route["rpm"] = summary["rpm"]
                route["hourly_rate"] = summary["hourly_rate"]
                expanded.append(route)

            TASKS[task_id] = {
                "state": "complete",
                "progress": 100,
                "result": expanded
            }


        except Exception as e:
            import traceback
            TASKS[task_id] = {
                "state": "error",
                "error": str(e),
                "trace": traceback.format_exc()
            }

    Thread(target=run_task).start()
    return jsonify({"task_id": task_id})


@app.route("/task_status/<task_id>")
def task_status(task_id):
    task = TASKS.get(task_id)
    if not task:
        return jsonify({"error": "Invalid task ID"}), 404
    return jsonify(task)


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
                route_points = [normalize_city(p) for p in load.get("routePoints", [])]
                cities = [pickup] + route_points + [dropoff]
                for i in range(len(cities) - 1):
                    city_pairs.add((cities[i], cities[i + 1]))
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
