import os
from flask import Flask, request, jsonify
from dispatch_agent import get_agent_runner

app = Flask(__name__)

# Initialize Dispatchy agent
agent = get_agent_runner()

@app.route("/dispatch", methods=["GET", "POST"])
def handle_dispatch():
    if request.method == "POST":
        data = request.json
    else:
        data = request.args.to_dict(flat=False)
        # Convert multi-value inputs like drivers[]= and loads[] into proper list of dicts
        data = {
            "drivers": eval(data.get("drivers", ["[]"])[0]),
            "loads": eval(data.get("loads", ["[]"])[0])
        }

    drivers = data.get("drivers", [])
    loads = data.get("loads", [])

    if not drivers or not loads:
        return jsonify({"error": "Missing drivers or loads in request."}), 400

    try:
        formatted_message = (
            f"Plan the best dispatch route using the following drivers and loads:\n\n"
            f"Drivers:\n{drivers}\n\n"
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
