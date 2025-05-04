import re
from tools.db import users, group_subs, projects

def extract_group_id(message: str) -> int | None:
    match = re.search(r"\[groupId:\s*(\d+)\]", message)
    return int(match.group(1)) if match else None

def get_user_by_telegram_id(telegram_id: int) -> str:
    user = users.find_one({"telegramId": telegram_id})
    return str(user) if user else "User not found."

def get_group_subscription(group_id: int) -> str:
    group = group_subs.find_one({"groupId": group_id})
    return str(group) if group else "Group not found."

def get_project_by_name(name: str) -> str:
    project = projects.find_one({"name": name})
    return str(project) if project else "Project not found."

def get_project_by_group_id(group_id: int) -> str:
    project = projects.find_one({"groupId": group_id})
    return str(project) if project else "No project found for that group ID."

def get_leaderboard(message: str) -> str:
    group_id = extract_group_id(message)
    if not group_id:
        return "❌ Please include [groupId: <number>] in your message."

    pipeline = [
        {
            "$project": {
                "telegramId": 1,
                "username": 1,
                "points": {"$ifNull": [f"$groupPoints.{str(group_id)}.points", 0]}
            }
        },
        {"$sort": {"points": -1}},
        {"$limit": 10}
    ]

    top_users = list(users.aggregate(pipeline))
    if not top_users:
        return f"No users found for group {group_id}."

    leaderboard = [f"🏆 Group {group_id} Leaderboard:"]
    for i, user in enumerate(top_users, 1):
        username = user.get("username") or f"user{user['telegramId']}"
        leaderboard.append(f"{i}. {username} — {user['points']} points")

    return "\n".join(leaderboard)
