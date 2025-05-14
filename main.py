import os
from flask import Flask, request, jsonify
from agent_engine import get_agent_runner
from collections import deque
from threading import Lock
from collections import defaultdict


app = Flask(__name__)

# Initialize agents
agent = get_agent_runner()
recent_replies_by_group = defaultdict(list)
locks_by_group = defaultdict(Lock)
MAX_RECENT = 100  # Limit history per group


# 🔹 FatCat endpoint
@app.route("/chat", methods=["POST"])
def chat_fatcat():
    data = request.json
    message = data.get("message", "")
    group_id = data.get("groupId")
    telegram_id = data.get("telegramId")
    
    if not message:
        return jsonify({"error": "Missing message"}), 400

    full_message = f"""{message}
[groupId: {group_id}]
[telegramId: {telegram_id}]
"""

    try:
        response = agent.chat(full_message)
        return jsonify({"reply": response.response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/generate-twitter-reply", methods=["POST"])
def generate_twitter_reply():
    data = request.json
    group = data.get("groupName")

    if not group:
        return jsonify({"error": "Missing groupName"}), 400

    lock = locks_by_group[group]

    with lock:
        recent = recent_replies_by_group[group]

        prompt = f"""
You are helping create a hype Twitter reply about the project "{group}".

✏️ Style: Short, punchy, first-person tone. Excited, bold, but casual. Imagine you're a real community member hyping up the token.

⚠️ Constraints:
- Keep it under 100 characters.
- Don't reuse these exact lines:\n\n{chr(10).join(recent)}
- Avoid hashtags unless they fit naturally.
- Don’t start with the project name.
- Do not return examples or quotes — return just the final tweet text.

🔥 Generate a completely unique tweet reply.
"""

        try:
            response = agent.chat(prompt).response.strip()

            if response in recent:
                return jsonify({"error": "Duplicate tweet detected, try again."}), 409

            recent.append(response)
            if len(recent) > MAX_RECENT:
                recent.pop(0)

            return jsonify({"reply": response})
        except Exception as e:
            print("❌ Error generating reply:", e)
            return jsonify({"error": "Failed to generate Twitter reply"}), 500


# 🔹 Start the Flask server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
