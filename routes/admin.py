from flask import (Blueprint, render_template, redirect,
                   url_for, flash, request, jsonify)
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
from extensions import db, bcrypt
from models import Admin, Order, Ticket

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# ── Login ──────────────────────────────────────────────────
@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.admin_dashboard"))

    if request.method == "POST":
        email    = request.form.get("email")
        password = request.form.get("password")
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
    tickets = Ticket.query.order_by(Ticket.created_at.desc()).all()
    orders  = Order.query.order_by(Order.created_at.desc()).all()
    return render_template("admin.html",
                           tickets=tickets,
                           orders=orders,
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