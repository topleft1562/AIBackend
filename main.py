import os
from flask import Flask, request, jsonify
from agent_engine import get_agent_runner

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


# 🔹 Twitter reply generator (uses FatCat LLM)
@app.route("/generate-twitter-reply", methods=["POST"])
def generate_twitter_reply():
    data = request.json
    group = data.get("groupName")

    if not group:
        return jsonify({"error": "Missing groupName"}), 400

    prompt = f"""
You are helping create a hype Twitter reply about the project "{group}".

✏️ Style: Short, punchy, first-person tone. Excited, bold, but casual. Imagine you're a real community member hyping up the token.

⚠️ Constraints:
- Keep it under 100 characters.
- Don't reuse phrasing from prior responses.
- Avoid hashtags unless they fit naturally.
- Don’t start with the project name.
- Do not return examples or quotes — return just the final tweet text.

🔥 Generate a completely unique tweet reply.
"""

    try:
        response = agent.chat(prompt)
        return jsonify({"reply": response.response.strip()})
    except Exception as e:
        print("❌ Error generating reply:", e)
        return jsonify({"error": "Failed to generate Twitter reply"}), 500


# 🔹 Start the Flask server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
