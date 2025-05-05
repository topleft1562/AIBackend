from tools.db import users, group_subs, projects
from datetime import datetime, timezone
from tools.db import raids

def get_user_by_telegram_id(telegram_id: int) -> str:
    user = users.find_one({"telegramId": telegram_id})
    if not user:
        return "❌ User not found."

    username = user.get("username", f"user{telegram_id}").upper()
    referral_link = user.get("referralLink", "No referral link")
    group_points = user.get("groupPoints", {})
    wallets = user.get("wallets", {})

    message = f"👤 {username} profile:\n\n"
    message += f"🤝 {username}'s referral link:\n{referral_link}\n\n"

    if group_points:
        for group_id, stats in group_points.items():
            points = round(stats.get("points", 0), 1)
            invites = int(stats.get("invites", 0))
            message_count = int(stats.get("messageCount", 0))

            message += f"🌟 Group {group_id} Stats:\n"
            message += f"{points} points & {invites} invites\n"
            message += f"{message_count} messages sent\n\n"
    else:
        message += "🌟 No group activity found.\nStart chatting to earn points!\n\n"

    if wallets:
        message += "💳 Wallets:\n"
        if wallets.get("solana"):
            message += f"Solana: {wallets['solana']}\n"
        if wallets.get("evm"):
            message += f"EVM: {wallets['evm']}\n"
        if not wallets.get("solana") and not wallets.get("evm"):
            message += "No wallets connected.\n"
    else:
        message += "💳 No wallets connected.\n"

    return message


def get_group_subscription(group_id: int) -> str:
    group = group_subs.find_one({"groupId": group_id})
    return str(group) if group else "Group not found."

def get_project_by_name(name: str) -> str:
    project = projects.find_one({"name": name})
    return str(project) if project else "Project not found."

def get_project_by_group_id(group_id: int) -> str:
    project = projects.find_one({"groupId": group_id})
    return str(project) if project else "No project found for that group ID."

def get_leaderboard(group_id: int, is_group_chat: bool = True) -> str:
    number_emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']

    pipeline = [
        {
            "$project": {
                "telegramId": 1,
                "username": 1,
                "displayName": 1,
                "raidCount": { "$ifNull": [f"$groupPoints.{str(group_id)}.raids", 0] },
                "points": { "$ifNull": [f"$groupPoints.{str(group_id)}.points", 0] }
            }
        },
        { "$sort": { "points": -1 } },
        { "$limit": 10 }
    ]

    top_users = list(users.aggregate(pipeline))

    if is_group_chat:
        message = "🎯 Group Leaderboard\n\n"
        if not top_users:
            return message + "No active users yet. Start chatting to earn points!"

        for i, user in enumerate(top_users):
            icon = (
                "👑" if i == 0 else
                "🥈" if i == 1 else
                "🥉" if i == 2 else
                number_emojis[i] if i < len(number_emojis) else f"{i+1}."
            )
            name = user.get("displayName") or user.get("username") or f"user{user['telegramId']}"
            points = round(user.get("points", 0), 1)
            message += f"{icon} {name} — {points} pts\n"
        return message

    # Private chat format
    message = "🏆 Community Leaders\n━━━━━━━━━━━━━━━\n\n"
    for i, user in enumerate(top_users):
        icon = (
            "👑" if i == 0 else
            "🥈" if i == 1 else
            "🥉" if i == 2 else
            number_emojis[i] if i < len(number_emojis) else f"{i+1}."
        )
        username = user.get("username") or f"user{user['telegramId']}"
        points = f"{round(user.get('points', 0), 1):,.1f}"
        raids = user.get("raidCount", 0)
        message += f"{icon} @{username}\n"
        message += f"• 💎 {points} points\n"
        message += f"• 🎯 {raids} contributions\n\n"

    message += "💫 Keep engaging to climb the ranks!\n━━━━━━━━━━━━━━━"
    return message

def get_project_leaderboard(limit: int = 5) -> str:
    # Get top projects sorted by total points
    pipeline = [
        {
            "$project": {
                "name": 1,
                "displayName": { "$ifNull": ["$displayName", "$name"] },
                "points": { "$ifNull": ["$stats.totalPoints", 0] },
                "inviteLink": 1,
                "telegramId": 1
            }
        },
        { "$sort": { "points": -1 } },
        { "$limit": limit }
    ]

    top_projects = list(projects.aggregate(pipeline))
    if not top_projects:
        return ""

    message = f"🏆 <b>Top {limit} Projects Leaderboard</b>\n\n"
    for i, entry in enumerate(top_projects):
        trophy = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "🏅"
        name = entry.get("displayName") or entry.get("name", "Unnamed Project")
        points = round(entry.get("points", 0))
        link = entry.get("inviteLink")

        if link:
            line = f'<b>{name}</b> (<a href="{link}">Join</a>)'
        else:
            line = f"<b>{name}</b>"

        message += f"{trophy} {line}\n📊 <i>{points} points</i>\n\n"

    return message

def get_group_raids(group_id: int) -> str:
    now = datetime.now(timezone.utc)

    active_raids = list(raids.find({
        "groupId": group_id,
        "status": "in_progress"
    }).sort("createdAt", -1))

    if not active_raids:
        return "❌ No active raids found for this group."

    lines = [f"🎯 Active Raids ({len(active_raids)} total)", "━━━━━━━━━━━━━━━"]

    for i, raid in enumerate(active_raids, 1):
        tweet = raid.get("tweetContent", {})
        author = tweet.get("author", {})
        stats = raid.get("statistics", {})
        url = raid.get("tweetUrl", "")
        text = tweet.get("text", "").split("\n")[0][:50] + "..." if tweet.get("text") else "No text"
        created_at = raid.get("createdAt", now)
        time_left = max(0, raid.get("duration", 1800) - int((now - created_at).total_seconds()))
        minutes, seconds = divmod(time_left, 60)

        lines.append(f"\n{i}. 👤 @{author.get('username', 'unknown')} • {minutes}m {seconds}s left")
        lines.append(f"📝 “{text}”")
        line = []
        if raid["requiredActions"].get("like"): line.append(f"❤️ {stats.get('likes', 0)}")
        if raid["requiredActions"].get("retweet"): line.append(f"🔁 {stats.get('retweets', 0)}")
        if raid["requiredActions"].get("reply"): line.append(f"💬 {stats.get('replies', 0)}")
        if raid["requiredActions"].get("bookmark"): line.append(f"🔖 {stats.get('bookmarks', 0)}")
        lines.append(" ".join(line))
        if url: lines.append(f"🔗 {url}")

    return "\n".join(lines)
