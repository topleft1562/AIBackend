import os
from flask import Flask, request, jsonify
from agent_engine import get_agent_runner
from collections import defaultdict, deque
from threading import Lock

app = Flask(__name__)

# Initialize agents
agent = get_agent_runner()

# Track last replies per group
recent_replies_by_group = defaultdict(lambda: deque(maxlen=100))
locks_by_group = defaultdict(Lock)

MAX_ATTEMPTS = 3

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

        def normalize(text):
            return ''.join(c.lower() for c in text if c.isalnum())

        norm_recent = set(normalize(r) for r in recent)

        for attempt in range(MAX_ATTEMPTS):
            prompt = f"""
You are writing a fun, punchy tweet reply about the crypto project "{group}".

✏️ Style:
- Short, bold, and casual
- First-person voice
- Max 100 characters
- No hashtags unless they fit naturally
- Don’t start with the project name

🔥 Generate a completely unique tweet reply.

Reply with **only** the final tweet text. It should feel fresh and authentic.
"""

            try:
                response = agent.chat(prompt).response.strip()
                norm_reply = normalize(response)

                if norm_reply not in norm_recent:
                    recent.append(response)
                    return jsonify({"reply": response})
            except Exception as e:
                print("❌ Error generating reply:", e)
                return jsonify({"error": "Failed to generate Twitter reply"}), 500

        return jsonify({"error": "Failed to generate a unique reply after multiple tries"}), 409



# 🔹 Start the Flask server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
