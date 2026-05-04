from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Chatbot server is running!"})

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "")

    # Placeholder — Dialogflow CX integration goes here later
    response = f"You said: {user_message}"

    return jsonify({"reply": response})

if __name__ == "__main__":
    app.run(debug=True)
