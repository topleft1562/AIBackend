import os
from flask import Flask, request, jsonify
from agent_engine import get_agent_runner          # FatCat agent
from datetime import datetime

pending_game_sessions = {}
app = Flask(__name__)

# Initialize agents
agent = get_agent_runner()

# In-memory setup tracking
pending_game_sessions = {}

# 🔹 FatCat endpoint with game trigger
@app.route("/chat", methods=["POST"])
def chat_fatcat():
    data = request.json
    message = data.get("message", "").strip()
    group_id = data.get("groupId")
    telegram_id = data.get("telegramId")

    if not message:
        return jsonify({"error": "Missing message"}), 400

    # 🧠 Game Setup Trigger
    trigger_phrases = ["start game", "let's do a game", "game night"]
    if any(phrase in message.lower() for phrase in trigger_phrases):
        reply = handle_game_setup(telegram_id, group_id, message)
        return jsonify({ "reply": reply })

    # 🧩 Continue game setup if in progress
    if telegram_id in pending_game_sessions:
        reply = handle_game_setup(telegram_id, group_id, message)
        return jsonify({ "reply": reply })

    # 🤖 Default: Send to FatCat AI
    full_message = f"""{message}
[groupId: {group_id}]
[telegramId: {telegram_id}]
"""

    try:
        response = agent.chat(full_message)
        return jsonify({ "reply": response.response })
    except Exception as e:
        return jsonify({ "error": str(e) }), 500



# 🔹 Twitter reply generator (uses FatCat LLM)
@app.route("/generate-twitter-reply", methods=["POST"])
def generate_twitter_reply():
    data = request.json
    group = data.get("groupName")
    examples = data.get("examples")

    if not group or not examples or not isinstance(examples, list):
        return jsonify({"error": "Missing or invalid fields: groupName, examples[]"}), 400

    prompt = f"""You are helping to write a quick Twitter reply about the group "{group}". 
Here are some examples of the style we're aiming for:

{chr(10).join([f'{i+1}. "{ex}"' for i, ex in enumerate(examples)])}

Now, based on the examples above, write **one** short, friendly, punchy Twitter reply about "{group}". 
Keep it under 100 characters. 
Do not add hashtags unless it naturally fits.
Reply as if you're a real person who loves the group. Only output the reply text, nothing else."""

    try:
        response = agent.chat(prompt)
        return jsonify({ "reply": response.response.strip() })
    except Exception as e:
        print("❌ Error generating reply:", e)
        return jsonify({"error": "Failed to generate Twitter reply"}), 500

# 🔹 Start the Flask server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
