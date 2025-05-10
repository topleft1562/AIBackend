from tools.db import users

def assign_trivia_points(telegramId: int, groupId: int):
    """
    Adds trivia points to a user's groupPoints[groupId].points.
    Initializes groupPoints[groupId] if missing.
    """
    group_path = f"groupPoints.{groupId}"
    points_path = f"{group_path}.points"

    result = users.update_one(
        { "telegramId": telegramId },
        {
            "$setOnInsert": {
                group_path: {
                    "points": 0,
                    "invites": 0,
                    "messageCount": 0,
                    "raids": 0
                }
            },
            "$inc": {
                points_path: 0.1
            }
        },
        upsert=True
    )

    if result.matched_count == 0 and result.upserted_id:
        return f"✅ User created and given 0.1 trivia points in group {groupId}."
    elif result.modified_count > 0:
        return f"✅ 0.1 points awarded to user {telegramId} in group {groupId}."
    else:
        return f"⚠️ Trivia points may already be up-to-date for user {telegramId}."