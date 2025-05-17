import os
from flask import Flask, request, jsonify
from agent_engine import get_agent_runner
from collections import defaultdict, deque
from threading import Lock
from tools.reply_example_loader import get_random_examples


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
        recent_list = list(recent)[-5:]  # Only last 5 for uniqueness
        norm_recent = set(r.lower().strip() for r in recent_list)

        example_context = "\n".join([f"- {r.replace('{groupName}', group)}" for r in get_random_examples()])

        prompt = f"""
You're crafting short Twitter replies to hype the crypto project "{group}".

🧠 Recent replies to avoid:
{chr(10).join([f"- {r}" for r in recent_list]) if recent_list else "None"}

📦 Example replies for inspiration:
{example_context}

✏️ Style:
- First-person, fun, bold, excited
- Max 100 characters each
- No hashtags unless natural
- Don’t start with the project name

⚡️ Task:
Generate 5 completely fresh replies, each on a new line. No bullets. No quotes. Just 5 tweet-ready lines.
"""

        try:
            response = agent.chat(prompt).response.strip()
            replies = [r.strip() for r in response.split("\n") if r.strip()]

            for reply in replies:
                if reply.lower() not in norm_recent:
                    recent.append(reply)
                    return jsonify({"reply": reply})

            fallback = replies[0] if replies else "No unique reply found."
            recent.append(fallback)
            return jsonify({"reply": fallback})

        except Exception as e:
            print("❌ Error generating replies:", e)
            return jsonify({"error": "Failed to generate Twitter reply"}), 500


# 🔹 Start the Flask server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
