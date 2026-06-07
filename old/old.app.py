from flask import Flask, request, jsonify
from old.database import orders
import re

secret_token = "6e037887676fca2fe030065b2abc127a91ca899062295c2e58f58d3659f22c27"
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        req = request.get_json()

        # Check token from request header
        token = request.headers.get("Authorization")
        if token != f"Bearer {secret_token}":
            return jsonify({"error": "Unauthorized"}), 401

        tag = req.get("fulfillmentInfo", {}).get("tag", "")

        if tag == "track_package":
            # Extract parameters from Dialogflow CX session
            parameters = req.get("sessionInfo", {}).get("parameters", {})

            # Clean order_id using regex
            raw_order = parameters.get("order_id", "")
            match_order = re.search(r"ORD-[0-9]+", str(raw_order))
            order_id = match_order.group(0) if match_order else None

            # Clean email using regex
            raw_email = parameters.get("customer_email", "")
            match_email = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", str(raw_email))
            customer_email = match_email.group(0) if match_email else None

            # Validate both exist
            if not order_id or not customer_email:
                return jsonify({
                    "fulfillmentResponse": {
                        "messages": [{"text": {"text": ["Could not read your details. Please try again."]}}]
                    }
                })

            # Look up order in dictionary
            order = orders.get(order_id)

            # Verify order exists and email matches
            if order and order["customer_email"].lower() == customer_email.lower():
                response_text = (
                    f"Order {order_id} found!\n"
                    f"Status: {order['status']}.\n"
                    f"Estimated delivery: {order['estimated_delivery']}\n"
                    f"via {order['courier']}."
                )
                verified = True
            else:
                response_text = (
                    "We couldn't find an order matching those details. "
                    "Please double check and try again."
                )
                verified = False
                order = None

            # Build and return response
            return jsonify({
                "fulfillmentResponse": {
                    "messages": [{"text": {"text": [response_text]}}]
                },
                "sessionInfo": {
                    "parameters": {
                        "verified": verified,
                        "package_status": order["status"] if verified else None,
                        "estimated_delivery": order["estimated_delivery"] if verified else None,
                        "courier": order["courier"] if verified else None,
                        "customer_name": order["customer_name"] if verified else None
                    }
                }
            })

    except Exception as e:
        print(f"ERROR: {e}")
        return jsonify({
            "fulfillmentResponse": {
                "messages": [{"text": {"text": ["An internal error occurred."]}}]
            }
        }), 200

if __name__ == "__main__":
    app.run(debug=True, port=5000)