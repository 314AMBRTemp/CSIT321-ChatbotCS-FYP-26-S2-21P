import os
import json
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
from extensions import db, bcrypt
from models import Admin, Order, Ticket, BotResponse

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# ── Config Review ──────────────────────────────────────────
@admin_bp.route("/config-review")
@login_required
def config_review():
    agent_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "exported_agent_Customer Support Chatbot")
    
    if not os.path.exists(agent_path):
        flash("Exported agent files not found. Please ensure the 'exported_agent' folder is in the project root.")
        return redirect(url_for("admin.admin_dashboard"))

    # 1. Parse Intents and Training Phrases
    intents_data = []
    intents_dir = os.path.join(agent_path, "intents")
    if os.path.exists(intents_dir):
        for intent_folder in os.listdir(intents_dir):
            folder_path = os.path.join(intents_dir, intent_folder)
            if not os.path.isdir(folder_path): continue
            
            # Get training phrases
            phrases = []
            phrases_file = os.path.join(folder_path, "trainingPhrases", "en.json")
            if os.path.exists(phrases_file):
                with open(phrases_file, 'r') as f:
                    data = json.load(f)
                    for tp in data.get("trainingPhrases", []):
                        parts = [p.get("text", "") for p in tp.get("parts", [])]
                        phrases.append("".join(parts))
            
            intents_data.append({
                "name": intent_folder,
                "phrases": phrases[:5] # Show first 5 for brevity
            })

    # 2. Parse Flow Routes
    routes_data = []
    flow_file = os.path.join(agent_path, "flows", "Default Start Flow", "Default Start Flow.json")
    if os.path.exists(flow_file):
        with open(flow_file, 'r') as f:
            data = json.load(f)
            for route in data.get("transitionRoutes", []):
                intent = route.get("intent", "Condition Only")
                target = route.get("targetPage") or route.get("targetFlow") or "N/A"
                
                # Get response if exists
                messages = []
                fulfillment = route.get("triggerFulfillment", {})
                for msg in fulfillment.get("messages", []):
                    text_list = msg.get("text", {}).get("text", [])
                    messages.extend(text_list)
                
                routes_data.append({
                    "intent": intent,
                    "target": target,
                    "response": messages[0] if messages else (f"Webhook: {fulfillment.get('tag')}" if fulfillment.get("webhook") else "No Response")
                })

    return render_template("admin_config_review.html", 
                           intents=intents_data, 
                           routes=routes_data,
                           admin=current_user)

# ── Login ──────────────────────────────────────────────────
@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.admin_dashboard"))

    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        admin    = Admin.query.filter_by(email=email).first()

        if admin and bcrypt.check_password_hash(admin.password_hash, password):
            admin.last_login = datetime.utcnow()
            db.session.commit()
            login_user(admin)
            return redirect(url_for("admin.admin_dashboard"))
        else:
            flash("Invalid email or password.")

    return render_template("admin_login.html")

# ── Dashboard ──────────────────────────────────────────────
@admin_bp.route("/")
@login_required
def admin_dashboard():
    # Sort by status (open first) then by creation date
    tickets   = Ticket.query.order_by(
        Ticket.status.asc(), # 'open' comes before 'resolved' alphabetically
        Ticket.created_at.desc()
    ).all()
    orders    = Order.query.order_by(Order.created_at.desc()).all()
    responses = BotResponse.query.all()
    return render_template("admin.html",
                           tickets=tickets,
                           orders=orders,
                           responses=responses,
                           admin=current_user)

# ── Logout ─────────────────────────────────────────────────
@admin_bp.route("/logout")
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for("admin.admin_login"))

# ── Update Ticket ──────────────────────────────────────────
@admin_bp.route("/tickets/<int:ticket_id>", methods=["PATCH"])
@login_required
def update_ticket(ticket_id):
    ticket = db.session.get(Ticket, ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404

    data   = request.get_json()
    status = data.get("status")

    if status not in ["open", "in_progress", "resolved"]:
        return jsonify({"error": "Invalid status"}), 400

    ticket.status = status
    db.session.commit()
    return jsonify({"message": "Ticket updated", "ticket": ticket.to_dict()})

# ── Delete Ticket ──────────────────────────────────────────
@admin_bp.route("/tickets/<int:ticket_id>", methods=["DELETE"])
@login_required
def delete_ticket(ticket_id):
    ticket = db.session.get(Ticket, ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404
    db.session.delete(ticket)
    db.session.commit()
    return jsonify({"message": "Ticket deleted"})

# ── Bot Responses CMS ──────────────────────────────────────
DOMAIN_TEMPLATES = {
    "Website Navigation": {
        "view products": "You can browse our full collection at http://localhost:5000/products",
        "contact info": "Need help? Reach out to us at http://localhost:5000/contact",
        "faq page": "Check out our most asked questions at http://localhost:5000/faq",
        "go home": "Return to the main page at http://localhost:5000/"
    },
    "Customer Service": {
        "track order": "To track your package, please log in and visit your dashboard or ask me 'Where is my order?'.",
        "cancel order": "If you need to cancel an order, please open a support ticket through me or contact us via email.",
        "damaged item": "I'm sorry to hear that! Please open a support ticket so our team can assist you with a replacement.",
        "account help": "You can manage your profile and view your order history in the 'My Account' section."
    },
    "Sales & Marketing": {
        "discount code": "Use code FIRST10 for 10% off your first purchase!",
        "wholesale inquiry": "For bulk orders, please email sales@assistflow.com",
        "shipping cost": "We offer free shipping on all orders over $50.",
        "return policy": "We have a 30-day return policy for all unused items."
    }
}

@admin_bp.route("/import-template", methods=["POST"])
@login_required
def import_template():
    data = request.get_json()
    template_name = data.get("template_name")
    
    if template_name not in DOMAIN_TEMPLATES:
        return jsonify({"error": "Template not found"}), 404
    
    template_data = DOMAIN_TEMPLATES[template_name]
    for intent, response in template_data.items():
        bot_resp = db.session.get(BotResponse, intent)
        if bot_resp:
            bot_resp.response_text = response
        else:
            bot_resp = BotResponse(intent_id=intent, response_text=response)
            db.session.add(bot_resp)
    
    db.session.commit()
    return jsonify({"message": f"Successfully imported {template_name} template!"})

@admin_bp.route("/responses", methods=["POST"])
@login_required
def update_bot_response():
    data = request.get_json()
    intent_id = data.get("intent_id")
    response_text = data.get("response_text")

    if not intent_id or not response_text:
        return jsonify({"error": "Missing data"}), 400

    bot_resp = db.session.get(BotResponse, intent_id)
    if bot_resp:
        bot_resp.response_text = response_text
    else:
        bot_resp = BotResponse(intent_id=intent_id, response_text=response_text)
        db.session.add(bot_resp)
    
    db.session.commit()
    return jsonify({"message": "Response updated successfully"})

@admin_bp.route("/responses/<intent_id>", methods=["DELETE"])
@login_required
def delete_bot_response(intent_id):
    bot_resp = db.session.get(BotResponse, intent_id)
    if bot_resp:
        db.session.delete(bot_resp)
        db.session.commit()
        return jsonify({"message": "Response deleted"})
    return jsonify({"error": "Not found"}), 404

# ── Get All Tickets (JSON) ─────────────────────────────────
@admin_bp.route("/tickets", methods=["GET"])
@login_required
def get_tickets():
    tickets = Ticket.query.order_by(Ticket.created_at.desc()).all()
    return jsonify([t.to_dict() for t in tickets])

# ── Get All Orders (JSON) ──────────────────────────────────
@admin_bp.route("/orders", methods=["GET"])
@login_required
def get_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return jsonify([o.to_dict() for o in orders])
