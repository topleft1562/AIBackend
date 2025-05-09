from tools.mongo_tools import insert_game
from datetime import datetime


# In-memory setup tracking
pending_game_sessions = {}

def finalize_game(telegram_id):
    session = pending_game_sessions.get(telegram_id)
    if not session or session.get("step") != "done":
        return "❌ No game setup ready to finalize."

    result = insert_game("games", session)
    if "inserted_id" in result:
        del pending_game_sessions[telegram_id]
        return f"✅ Game created successfully! (ID: {result['inserted_id']})"
    else:
        return f"❌ Failed to create game: {result.get('error')}"


def parse_point_values(raw_text):
    """
    Parses input like '1=20,2=10,3=5' or 'correctAnswer=5,participation=1' into a dict.
    """
    entries = raw_text.split(",")
    parsed = {}
    for entry in entries:
        if "=" not in entry:
            raise ValueError("Missing '=' in point value")
        key, value = entry.split("=")
        parsed[key.strip()] = int(value.strip())
    return parsed

def handle_game_setup(telegram_id, group_id, message_text):
    session = pending_game_sessions.get(telegram_id)

    if not session:
        # Start new game setup
        pending_game_sessions[telegram_id] = {
            "groupId": group_id,
            "hostTelegramId": telegram_id,
            "step": "ask_game_type",
            "createdAt": datetime.utcnow()
        }
        return "🎮 Let's set up a game! What kind of game is this? (e.g. trivia, raffle, challenge?)"

    step = session["step"]

    if step == "ask_game_type":
        session["gameType"] = message_text.lower().strip()
        session["step"] = "ask_point_type"
        return "How should points be awarded? (ranking or per_action)"

    if step == "ask_point_type":
        point_type = message_text.lower().strip()
        if point_type not in ["ranking", "per_action"]:
            return "Please choose either 'ranking' or 'per_action'."
        session["pointType"] = point_type
        session["step"] = "ask_point_values"
        return "What's the point structure? (e.g. 1=20,2=10 or correctAnswer=5,participation=1)"

    if step == "ask_point_values":
        try:
            point_values = parse_point_values(message_text)
            session["pointValues"] = point_values
            session["step"] = "ask_player_mode"
            return "✅ Got it. Do you want to add players now or let people join later? (type: now or later)"
        except:
            return "⚠️ Invalid format. Please use something like: 1=20,2=10 or correctAnswer=5"

    if step == "ask_player_mode":
        mode = message_text.lower().strip()
        if mode not in ["now", "later"]:
            return "Please type either 'now' or 'later'."

        session["players"] = {}  # empty for now
        session["winners"] = []
        session["status"] = "in_progress"
        session["step"] = "done"

        return "🎉 All set! Say `/fatty startgame` to begin."

__all__ = ["handle_game_setup", "finalize_game", "pending_game_sessions"]