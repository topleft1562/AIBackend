
def calc_route_metrics(loads, start_location=None, end_location=None, get_distance=None):
    loaded_km = 0
    empty_km = 0
    total_revenue = 0

    if not loads:
        return None

    # Deadhead from start location to first pickup
    if start_location and get_distance:
        empty_km += get_distance(start_location, loads[0]['pickupCity'])

    # For each load, add loaded km and revenue
    for i, load in enumerate(loads):
        loaded_km += load["loaded_km"]
        total_revenue += load["revenue"]
        # Empty between loads
        if i > 0 and get_distance:
            prev_drop = loads[i-1]['dropoffCity']
            this_pickup = load['pickupCity']
            empty_km += get_distance(prev_drop, this_pickup)

    # Deadhead from last dropoff to end location
    if end_location and get_distance:
        empty_km += get_distance(loads[-1]['dropoffCity'], end_location)

    total_km = loaded_km + empty_km
    loaded_pct = loaded_km / total_km if total_km else 0
    miles = total_km * 0.621371
    rpm = total_revenue / miles if miles else 0

    return {
        "loaded_km": loaded_km,
        "empty_km": empty_km,
        "total_km": total_km,
        "loaded_pct": loaded_pct,
        "total_revenue": total_revenue,
        "rpm": rpm,
        "miles": miles,
    }
