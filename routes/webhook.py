from flask import Blueprint, request, jsonify, render_template
from extensions import db
from models import Order, Ticket
from google.cloud.dialogflowcx_v3 import (
    SessionsClient, TextInput, QueryInput, DetectIntentRequest
)
import re
import uuid

webhook_bp = Blueprint("webhook", __name__)

SECRET_TOKEN = "6e037887676fca2fe030065b2abc127a91ca899062295c2e58f58d3659f22c27"
PROJECT_ID   = "csci321-chatbot-for-cs"
AGENT_ID     = "e7e8fe80-878e-484e-b3d7-76ff1222b47b"
LOCATION     = "asia-southeast1"
LANGUAGE     = "en"

# ── Helpers ────────────────────────────────────────────────
def extract_order_id(raw):
    match = re.search(r"ORD-[0-9]+", str(raw), re.IGNORECASE)
    if match:
        return match.group(0).upper()
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

def detect_intent(session_id, text, is_logged_in=False,
                  customer_email=None, active_order=None):
    from google.cloud.dialogflowcx_v3 import (
        SessionsClient, TextInput, QueryInput,
        DetectIntentRequest, QueryParameters
    )
    from google.protobuf.struct_pb2 import Struct

    client_options = {
        "api_endpoint": f"{LOCATION}-dialogflow.googleapis.com"
    }
    client = SessionsClient(client_options=client_options)

    session_path = (
        f"projects/{PROJECT_ID}/locations/{LOCATION}"
        f"/agents/{AGENT_ID}/sessions/{session_id}"
    )

    # ── Build session parameters to inject ────────────────
    params = Struct()
    params["is_logged_in"] = is_logged_in

    if is_logged_in and customer_email:
        params["customer_email"] = customer_email

    if active_order:
        params["package_status"]     = active_order.status
        params["estimated_delivery"] = active_order.estimated_delivery
        params["courier"]            = active_order.courier
        params["delivery_address"]   = active_order.delivery_address

    # ── Build the request with injected params ─────────────
    query_params = QueryParameters(parameters=params)

    query_input = QueryInput(
        text=TextInput(text=text),
        language_code=LANGUAGE
    )

    response = client.detect_intent(
        request=DetectIntentRequest(
            session=session_path,
            query_input=query_input,
            query_params=query_params
        )
    )

    reply = "\n".join([
        msg.text.text[0]
        for msg in response.query_result.response_messages
        if msg.text.text
    ])
    return reply or "I'm not sure how to help with that. Could you rephrase?"

# ── Frontend ───────────────────────────────────────────────
@webhook_bp.route("/")
def index():
    return render_template("index.html")

# ── Chat ───────────────────────────────────────────────────
@webhook_bp.route("/chat", methods=["POST"])
def chat():
    try:
        data       = request.get_json()
        message    = data.get("message", "").strip()
        session_id = data.get("session_id", str(uuid.uuid4()))

        if not message:
            return jsonify({"reply": "Please type a message."})

        # ── Check if customer is logged in ─────────────────
        from flask_login import current_user
        from models import Order

        is_logged_in   = current_user.is_authenticated
        customer_email = current_user.email if is_logged_in else None

        # Only auto-inject order if customer has exactly one active order
        active_order = None
        if is_logged_in:
            active_orders = Order.query.filter_by(
                customer_email=customer_email
            ).filter(
                Order.status != "Delivered",
                Order.status != "Cancelled"
            ).order_by(Order.created_at.desc()).all()

            if len(active_orders) == 1:
                active_order = active_orders[0]

        reply = detect_intent(
            session_id=session_id,
            text=message,
            is_logged_in=is_logged_in,
            customer_email=customer_email,
            active_order=active_order
        )

        return jsonify({"reply": reply, "session_id": session_id})

    except Exception as e:
        print(f"CHAT ERROR: {e}")
        return jsonify({"reply": "Something went wrong. Please try again."}), 200

# ── Webhook ────────────────────────────────────────────────
@webhook_bp.route("/webhook", methods=["POST"])
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
            order_id       = extract_order_id(parameters.get("order_id", ""))
            customer_email = extract_email(parameters.get("customer_email", ""))

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
            order       = db.session.get(Order, order_id)

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
            order    = db.session.get(Order, order_id)

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

        elif tag == "authenticated_track":
            parameters     = req.get("sessionInfo", {}).get("parameters", {})
            customer_email = parameters.get("customer_email", "")
            order_id       = extract_order_id(parameters.get("order_id", ""))

            if order_id:
                # Specific order ID provided — look it up directly
                order = db.session.get(Order, order_id)

                # Verify the order belongs to this customer
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
                                "package_status":     order.status,
                                "estimated_delivery": order.estimated_delivery,
                                "courier":            order.courier,
                                "delivery_address":   order.delivery_address
                            }
                        }
                    })
                else:
                    # Order ID doesn't belong to this customer
                    return bad_request(
                        "We couldn't find that order linked to your account. "
                        "Please check your order ID and try again."
                    )

            else:
                # No order ID provided — check how many active orders they have
                active_orders = Order.query.filter_by(
                    customer_email=customer_email
                ).filter(
                    Order.status != "Delivered",
                    Order.status != "Cancelled"
                ).order_by(Order.created_at.desc()).all()

                if len(active_orders) == 0:
                    return bad_request(
                        "We couldn't find any active orders linked to your account."
                    )

                elif len(active_orders) == 1:
                    # Only one active order — return it directly
                    order = active_orders[0]
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
                                "package_status":     order.status,
                                "estimated_delivery": order.estimated_delivery,
                                "courier":            order.courier,
                                "delivery_address":   order.delivery_address
                            }
                        }
                    })

                else:
                    # Multiple active orders — list them and ask which one
                    order_list = "\n".join([
                        f"• {o.order_id} — {o.status} (Est. {o.estimated_delivery})"
                        for o in active_orders
                    ])
                    return jsonify({
                        "fulfillmentResponse": {
                            "messages": [{"text": {"text": [
                                f"You have {len(active_orders)} active orders:\n"
                                f"{order_list}\n\n"
                                f"Which order ID would you like to track?"
                            ]}}]
                        }
                    })

    except Exception as e:
        print(f"ERROR: {e}")
        return jsonify({
            "fulfillmentResponse": {
                "messages": [{"text": {"text": ["An internal error occurred."]}}]
            }
        }), 200