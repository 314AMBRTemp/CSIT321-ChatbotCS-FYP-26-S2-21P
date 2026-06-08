from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
from extensions import db, bcrypt
from models import Customer

customer_bp = Blueprint("customer", __name__, url_prefix="/customer")

# ── Register ───────────────────────────────────────────────
@customer_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("customer.dashboard"))

    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        name     = request.form.get("name", "").strip()

        existing = Customer.query.filter_by(email=email).first()
        if existing:
            flash("An account with that email already exists.")
            return render_template("customer_register.html")

        customer = Customer(
            email=email,
            password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
            name=name
        )
        db.session.add(customer)
        db.session.commit()
        login_user(customer)
        return redirect(url_for("customer.dashboard"))

    return render_template("customer_register.html")

# ── Login ──────────────────────────────────────────────────
@customer_bp.route("/login", methods=["GET", "POST"])
def customer_login():
    if current_user.is_authenticated:
        return redirect(url_for("customer.dashboard"))

    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        customer = Customer.query.filter_by(email=email).first()

        if customer and bcrypt.check_password_hash(customer.password_hash, password):
            customer.last_login = datetime.utcnow()
            db.session.commit()
            login_user(customer)
            return redirect(url_for("customer.dashboard"))
        else:
            flash("Invalid email or password.")

    return render_template("customer_login.html")

# ── Dashboard (My Orders) ──────────────────────────────────
@customer_bp.route("/dashboard")
@login_required
def dashboard():
    from models import Order
    orders = Order.query.filter_by(
        customer_email=current_user.email
    ).order_by(Order.created_at.desc()).all()
    return render_template("user_purchases.html",
                           customer=current_user,
                           orders=orders)

# ── Logout ─────────────────────────────────────────────────
@customer_bp.route("/logout")
@login_required
def customer_logout():
    logout_user()
    return redirect(url_for("webhook.index"))
