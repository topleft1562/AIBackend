import os
from flask import Flask, request, jsonify
from agent_engine import get_agent_runner
import random
import uuid

app = Flask(__name__)

# Initialize agents
agent = get_agent_runner()


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
    telegramId = data.get("telegramId")
    if not group:
        return jsonify({"error": "Missing groupName"}), 400

    entropy_seed = str(uuid.uuid4())[:8]

    prompt = f"""
You are generating short Twitter replies to hype the crypto project "{group}".

🧬 Entropy ID: {entropy_seed}
Use this as creative randomness. Do NOT include it in the replies.

🔒 Telegram USER ID: {telegramId}
This is the users Telegram Id, use this for uniqueness. Do NOT include it in the replies.

🎯 Style:
- First-person, fun, chaotic, bold
- Max 100 characters
- No hashtags unless they feel organic
- Don’t start with the project name
- Imagine 20 different people replying to the same post

🛠 Task:
Generate 20 unique Twitter replies.
Each reply on a new line. No bullets. No numbers. No quotes.
Just raw tweet replies.
"""

    try:
        response = agent.chat(prompt).response.strip()
        replies = [r.strip() for r in response.split("\n") if r.strip()]
        if replies:
            return jsonify({"reply": random.choice(replies)})
        else:
            return jsonify({"error": "No replies generated"}), 500
    except Exception as e:
        print("❌ Error generating replies:", e)
        return jsonify({"error": "Failed to generate Twitter reply"}), 500



# 🔹 Start the Flask server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
