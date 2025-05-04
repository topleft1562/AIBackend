from flask import Flask, request, jsonify
from agent_engine import get_agent_runner
from tools.token_tools import load_token_list

app = Flask(__name__)
agent = get_agent_runner()
load_token_list()

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
        return jsonify({ "reply": response.response })  # .response for FunctionCallingAgent result
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
