import os
from flask import Flask, request, jsonify
from agent_engine import get_agent_runner

app = Flask(__name__)

# Initialize Dispatchy agent
agent = get_agent_runner()

@app.route("/dispatch", methods=["GET", "POST"])
def handle_dispatch():
    if request.method == "POST":
        data = request.json
        loads = data.get("loads", [])
        base_location = data.get("base", "Brandon, MB")
    else:
        from urllib.parse import unquote
        loads_param = request.args.get("loads")
        base_location = request.args.get("base", "Brandon, MB")
        try:
            loads = eval(unquote(loads_param)) if loads_param else []
        except:
            return jsonify({"error": "Invalid loads format."}), 400

    if not loads:
        return jsonify({"error": "Missing loads in request."}), 400

    try:
        formatted_message = (
            f"You are a logistics planner. Assign the following loads to the minimum number of drivers.\n"
            f"Each driver starts and ends at {base_location}.\n"
            f"Try to aim for 55 hours per driver, but never exceed 70 hours.\n"
            f"Optimize routes to group loads logically and reduce backtracking.\n\n"
            f"Loads:\n{loads}"
        )

        response = agent.chat(formatted_message)
        return jsonify({"plan": response.response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 🔹 Start the Flask server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
