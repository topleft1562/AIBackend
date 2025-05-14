import os
from flask import Flask, request, jsonify
from agent_engine import get_agent_runner
from collections import deque


app = Flask(__name__)

# Initialize agents
agent = get_agent_runner()
recent_replies = deque(maxlen=100)


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

    recent_section = "\n".join([f"- {r}" for r in recent_replies])
    
    prompt = f"""
You are helping write a hype tweet reply about the project "{group}".

✏️ Style:
- Short, bold, and casual
- First-person voice
- Max 100 characters
- No hashtags unless they fit naturally
- Don’t start with the project name

🔥 Generate a completely unique tweet reply.

❌ Do NOT reuse or closely mimic any of these previous replies:
{recent_section}

✅ Only return the final tweet text, nothing else. Keep it fresh, fun, and different.
"""

    try:
        response = agent.chat(prompt)
        reply = response.response.strip()
        
        if reply and reply not in recent_replies:
            recent_replies.append(reply)
        
        return jsonify({ "reply": reply })
    except Exception as e:
        print("❌ Error generating reply:", e)
        return jsonify({"error": "Failed to generate Twitter reply"}), 500


# 🔹 Start the Flask server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
