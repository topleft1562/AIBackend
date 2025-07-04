from collections import defaultdict
from datetime import datetime, timedelta

DAILY_LIMIT = 14.0
CYCLE_LIMIT = 70.0
RESET_DURATION_HR = 36.0
LOAD_UNLOAD_HR = 3.0

def simulate_driver_plan(plan, driver_state):
    """
    Given a list of loads with date + drive_hr,
    simulate workday-by-workday with 14h max/day, 70h cycle, and 36h resets.
    """
    schedule = []
    daily_hours = defaultdict(float)
    total_hours = 0.0
    reset_points = []

    available_hours = float(driver_state.get("available_hours", CYCLE_LIMIT))
    start_date = datetime.strptime(plan["plan"][0]["date"], "%Y-%m-%d")
    current_date = start_date
    day_index = 0
    current_day_loads = []

    i = 0
    while i < len(plan["plan"]):
        load = plan["plan"][i]
        drive_hr = float(load.get("drive_hr", 0))
        work_hr = drive_hr + LOAD_UNLOAD_HR

        # If adding this would exceed daily limit
        if daily_hours[current_date.date()] + work_hr > DAILY_LIMIT:
            # End the current day
            schedule.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "loads": current_day_loads,
                "hours_used": round(daily_hours[current_date.date()], 2)
            })
            current_date += timedelta(days=1)
            current_day_loads = []
            continue

        # Add to current day
        daily_hours[current_date.date()] += work_hr
        current_day_loads.append(load["load_id"])
        total_hours += work_hr

        # If total cycle time is exceeded → reset
        if total_hours > available_hours:
            reset_points.append(current_date.strftime("%Y-%m-%d"))
            schedule.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "loads": current_day_loads,
                "hours_used": round(daily_hours[current_date.date()], 2)
            })
            # Add reset block
            reset_day = current_date + timedelta(days=1)
            schedule.append({
                "date": reset_day.strftime("%Y-%m-%d"),
                "reset": True
            })
            # Advance date by 1.5 days
            current_date += timedelta(hours=RESET_DURATION_HR)
            current_day_loads = []
            daily_hours = defaultdict(float)
            total_hours = 0.0
            continue

        i += 1

    # Add final day
    if current_day_loads:
        schedule.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "loads": current_day_loads,
            "hours_used": round(daily_hours[current_date.date()], 2)
        })

    return {
        "driver_id": plan["driver_id"],
        "schedule": schedule,
        "total_hours": round(total_hours, 2),
        "reset_points": reset_points
    }
