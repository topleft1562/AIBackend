import os
from flask import Flask, request, jsonify
from agent_engine import get_agent_runner
from collections import defaultdict, deque
from threading import Lock
from tools.reply_example_loader import get_random_examples, ALL_EXAMPLES
import random
import uuid

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
    telegram_id = data.get("telegramId") or random.randint(1, 999999)
    random_entropy = str(uuid.uuid4())[:8]
    unique_id = f"{telegram_id}-{random_entropy}"

    if not group:
        return jsonify({"error": "Missing groupName"}), 400

    lock = locks_by_group[group]
    with lock:
        recent = recent_replies_by_group[group]
        recent_list = list(recent)[-5:]
        norm_recent = set(r.lower().strip() for r in recent_list)
        norm_examples = set(
            r.lower().strip().replace("{groupName}", group) for r in ALL_EXAMPLES
        )

        example_context = "\n".join(
            [f"- {r.replace('{groupName}', group)}" for r in get_random_examples()]
        )

        prompt = f"""
You are generating short Twitter replies to hype the crypto project "{group}".

🧬 Request ID: {unique_id}
(Note: Do NOT include this ID in your output. It's just for uniqueness.)
UserID: {telegram_id}  # Do NOT mention this in the reply. It's just for entropy.

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

❗ Important:
Do NOT copy or slightly reword the examples above. Create completely new and unique replies only.
"""

        try:
            # Optionally, support model parameters
            # response = agent.chat(prompt, temperature=1.0, frequency_penalty=0.6).response.strip()
            response = agent.chat(prompt).response.strip()

            replies = [r.strip() for r in response.split("\n") if r.strip()]

            for reply in replies:
                norm = reply.lower().strip()
                if norm not in norm_recent and norm not in norm_examples:
                    recent.append(reply)
                    return jsonify({"reply": reply})

            # Fallback if all replies were duplicates
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
