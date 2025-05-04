import os
import threading
from flask import Flask, request, jsonify
from agent_engine import get_agent_runner
from tools.token_tools import load_token_list

app = Flask(__name__)

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
    
    # Build message with metadata context
    full_message = f"""{message}

        [groupId: {group_id}]
        [telegramId: {telegram_id}]
        """
   
    try:
        response = agent.chat(full_message)
        return jsonify({"reply": response.response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))  # Railway will provide this
    app.run(host="0.0.0.0", port=port)
