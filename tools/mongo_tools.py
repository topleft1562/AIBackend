from tools.db import users
from pymongo.errors import PyMongoError

def assign_trivia_points(telegramId: int, groupId: int):
    group_path = f"groupPoints.{groupId}"
    points_path = f"{group_path}.points"
    try:
        # Step 1: ensure the groupPoints[groupId] object exists
        user = users.find_one({ "telegramId": telegramId })

        if not user:
            return f"❌ User with telegramId {telegramId} not found."

        if str(groupId) not in user.get("groupPoints", {}):
            users.update_one(
                { "telegramId": telegramId },
                { "$set": {
                    group_path: {
                        "points": 0.0,
                        "invites": 0,
                        "messageCount": 0,
                        "raids": 0
                    }
                }}
            )

        # Step 2: safely increment the trivia points
        result = users.update_one(
            { "telegramId": telegramId },
            { "$inc": { points_path: 0.1 } }
        )

        if result.modified_count > 0:
            return f"✅ 0.1 points awarded to user {telegramId} in group {groupId}."
        else:
            return "⚠️ Trivia points unchanged — possibly already awarded?"

    except PyMongoError as e:
        print(f"❌ MongoDB error: {e}")
        return "❌ MongoDB error while assigning trivia points."
