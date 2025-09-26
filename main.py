import os
from flask import Flask, request, jsonify
from agent_engine import get_agent_runner  # FatCat agent

app = Flask(__name__)
agent = get_agent_runner()

# 30 quick, punchy crypto-style example replies for inspiration
crypto_examples = [
    "Loading the bags 🚀",
    "Chart looking spicy 🔥",
    "Only up from here 📈",
    "Diamond hands ready 💎",
    "GM fam, bullish vibes 🌞",
    "Next leg incoming ⚡",
    "Whales watching closely 👀",
    "Building through the bear 🏗️",
    "This is the way 🛡️",
    "Ready for liftoff 🚀",
    "Buying the dip like a champ 🏄‍♂️",
    "Accumulation mode on 🟢",
    "Liquidity hunting time 🦈",
    "Sent it to the moon 🌕",
    "Strong hands, stronger conviction 💪",
    "Patience pays off 🕰️",
    "Bag secured, vibes immaculate ✨",
    "Fresh breakout brewing ☕",
    "The floor is lava 🧱🔥",
    "Rockets loaded and fueled 🚀⛽",
    "Fearless ape season 🦍",
    "Flip the chart upside down 🤸‍♂️",
    "No weak hands allowed ❌🤲",
    "Trend reversal loading 🔄",
    "Buy pressure heating up ♨️",
    "Chart art masterpiece 🎨",
    "Bulls back in town 🐂",
    "Bear trap set 🪤",
    "Deep liquidity incoming 💧",
    "Ocean of green candles 🌊",
]

# ---------------- FatCat chat endpoint ----------------
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


# ---------------- Twitter reply generator (crypto style) ----------------
@app.route("/generate-twitter-reply", methods=["POST"])
def generate_twitter_reply():
    data = request.json
    group = data.get("groupName")
    telegram_id = data.get("telegramId")

    if not group or not telegram_id:
        return jsonify({"error": "Missing groupName or telegramId"}), 400

    # Compose a unique, fresh prompt every call
    prompt = f"""You are helping to write a quick crypto-style Twitter reply about "{group}".
Session id: {os.urandom(4).hex()}  # to help force uniqueness

Here are sample vibes:

{chr(10).join([f'{i+1}. \"{ex}\"' for i, ex in enumerate(crypto_examples)])}

Now write **one** short, punchy, crypto-savvy reply about "{group}".
Rules:
- Keep under 100 characters.
- No hashtags unless natural.
- Make it feel like a genuine degen tweet.
- It **must** be fresh and different every time, even for similar input.
Output only the reply text.
"""
    try:
        response = agent.chat(prompt)
        return jsonify({"reply": response.response.strip()})
    except Exception as e:
        print("❌ Error generating reply:", e)
        return jsonify({"error": "Failed to generate Twitter reply"}), 500


# ---------------- Start the Flask server ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
