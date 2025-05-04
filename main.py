import os
import threading
from flask import Flask, request, jsonify
from agent_engine import get_agent_runner
from tools.token_tools import load_token_list

app = Flask(__name__)

# Start token loading in background (non-blocking for Railway)
threading.Thread(target=load_token_list, daemon=True).start()

# Initialize FatCat agent
agent = get_agent_runner()

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    message = data.get("message", "")
    group_id = data.get("groupId")
    telegram_id = data.get("telegramId")

    if not message:
        return jsonify({"error": "Missing message"}), 400

    try:
        response = agent.chat(
            message,
            tools_metadata={"groupId": group_id, "telegramId": telegram_id}
        )
        return jsonify({"reply": response.response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Use Railway's injected PORT env var or default to 5000 locally
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
