import os
import re
import uuid
from flask import Flask, request, jsonify, render_template
from models import db, Order, Ticket
from google.cloud.dialogflowcx_v3 import (
    SessionsClient, TextInput, QueryInput, DetectIntentRequest
)

# ── Google credentials ─────────────────────────────────────
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "serviceAccountKey.json"

app = Flask(__name__)

# ── Database config ────────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'orders.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

SECRET_TOKEN = "6e037887676fca2fe030065b2abc127a91ca899062295c2e58f58d3659f22c27"

# ── Dialogflow CX config ───────────────────────────────────
PROJECT_ID = "csci321-chatbot-for-cs"    # ← replace
AGENT_ID   = "e7e8fe80-878e-484e-b3d7-76ff1222b47b"      # ← replace
LOCATION   = "asia-southeast1"
LANGUAGE   = "en"

# ── Helpers ────────────────────────────────────────────────
def extract_order_id(raw):
    match = re.search(r"ORD-[0-9]+", str(raw), re.IGNORECASE)
    if match:
        return match.group(0).upper()  # ← normalise to uppercase before DB lookup
    return None

def extract_email(raw):
    match = re.search(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", str(raw))
    return match.group(0) if match else None

def bad_request(msg):
    return jsonify({
        "fulfillmentResponse": {
            "messages": [{"text": {"text": [msg]}}]
        }
    })

def detect_intent(session_id, text):
    client_options = {
        "api_endpoint": f"{LOCATION}-dialogflow.googleapis.com"
    }
    client = SessionsClient(client_options=client_options)

    session_path = (
        f"projects/{PROJECT_ID}/locations/{LOCATION}"
        f"/agents/{AGENT_ID}/sessions/{session_id}"
    )

    query_input = QueryInput(
        text=TextInput(text=text),
        language_code=LANGUAGE
    )

    response = client.detect_intent(
        request=DetectIntentRequest(
            session=session_path,
            query_input=query_input
        )
    )

    reply = "\n".join([
        msg.text.text[0]
        for msg in response.query_result.response_messages
        if msg.text.text
    ])
    return reply or "I'm not sure how to help with that. Could you rephrase?"

# ── Frontend ───────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

# ── Chat endpoint ──────────────────────────────────────────
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data       = request.get_json()
        message    = data.get("message", "").strip()
        session_id = data.get("session_id", str(uuid.uuid4()))

        if not message:
            return jsonify({"reply": "Please type a message."})

        reply = detect_intent(session_id, message)
        return jsonify({"reply": reply, "session_id": session_id})

    except Exception as e:
        print(f"CHAT ERROR: {e}")
        return jsonify({"reply": "Something went wrong. Please try again."}), 200

# ── Webhook ────────────────────────────────────────────────
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        token = request.headers.get("Authorization")
        if token != f"Bearer {SECRET_TOKEN}":
            return jsonify({"error": "Unauthorized"}), 401

        req        = request.get_json()
        tag        = req.get("fulfillmentInfo", {}).get("tag", "")
        parameters = req.get("sessionInfo",    {}).get("parameters", {})

        # ── READ: track package ────────────────────────────
        if tag == "track_package":
            print("PARAMETERS RECEIVED:", parameters) # added to check if parameters are passing
            order_id       = extract_order_id(parameters.get("order_id", ""))
            customer_email = extract_email(parameters.get("customer_email", ""))
            print("EXTRACTED:", order_id, customer_email)    # added to check if parameters have passed 

            if not order_id or not customer_email:
                return bad_request("I couldn't read your details. Please try again.")

            order = db.session.get(Order, order_id)

            if order and order.customer_email.lower() == customer_email.lower():
                response_text = (
                    f"Here are your package details:\n"
                    f"Order ID: {order.order_id}\n"
                    f"Status: {order.status}\n"
                    f"Estimated Delivery: {order.estimated_delivery}\n"
                    f"Courier: {order.courier}\n"
                    f"Delivery Address: {order.delivery_address}"
                )
                return jsonify({
                    "fulfillmentResponse": {
                        "messages": [{"text": {"text": [response_text]}}]
                    },
                    "sessionInfo": {
                        "parameters": {
                            "verified":           True,
                            "package_status":     order.status,
                            "estimated_delivery": order.estimated_delivery,
                            "courier":            order.courier,
                            "customer_name":      order.customer_name
                        }
                    }
                })
            else:
                return bad_request(
                    "We couldn't find an order matching those details. "
                    "Please double check and try again."
                )

        # ── UPDATE: change delivery address ────────────────
        elif tag == "change_delivery_address":
            order_id    = extract_order_id(parameters.get("order_id", ""))
            new_address = parameters.get("new_delivery_address")
            order = db.session.get(Order, order_id)

            if order and new_address:
                order.delivery_address = new_address
                db.session.commit()

                ticket = Ticket(
                    order_id=order_id,
                    customer_email=order.customer_email,
                    issue_type="address_change",
                    description=f"Delivery address changed to: {new_address}",
                    status="open"
                )
                db.session.add(ticket)
                db.session.commit()

                return jsonify({
                    "fulfillmentResponse": {
                        "messages": [{"text": {"text": [
                            f"Your delivery address for {order_id} has been "
                            f"updated to: {new_address}. "
                            f"A confirmation email will be sent shortly."
                        ]}}]
                    },
                    "sessionInfo": {
                        "parameters": {"updated": True}
                    }
                })
            else:
                return bad_request("We couldn't update your address. Please try again.")

        # ── UPDATE: cancel order ───────────────────────────
        elif tag == "cancel_order":
            order_id = extract_order_id(parameters.get("order_id", ""))
            order = db.session.get(Order, order_id)

            if order:
                order.status = "Cancelled"
                db.session.commit()

                ticket = Ticket(
                    order_id=order_id,
                    customer_email=order.customer_email,
                    issue_type="cancellation",
                    description=f"Customer requested cancellation of {order_id}",
                    status="open"
                )
                db.session.add(ticket)
                db.session.commit()

                return jsonify({
                    "fulfillmentResponse": {
                        "messages": [{"text": {"text": [
                            f"Your order {order_id} has been successfully cancelled. "
                            f"A confirmation email will be sent shortly."
                        ]}}]
                    },
                    "sessionInfo": {
                        "parameters": {"cancelled": True}
                    }
                })
            else:
                return bad_request("We couldn't find that order. Please try again.")

    except Exception as e:
        print(f"ERROR: {e}")
        return jsonify({
            "fulfillmentResponse": {
                "messages": [{"text": {"text": ["An internal error occurred."]}}]
            }
        }), 200

# ── Run ────────────────────────────────────────────────────
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
    