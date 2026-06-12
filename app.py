import os
from flask import Flask
from extensions import db, bcrypt, login_manager
from models import Admin, Customer

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(BASE_DIR, "serviceAccountKey.json")

app = Flask(__name__)
app.secret_key = "your-flask-secret-key-change-this"

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'orders.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ── Initialise extensions ──────────────────────────────────
db.init_app(app)
bcrypt.init_app(app)
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    user_id_str = str(user_id)
    if user_id_str.startswith("a-"):
        return db.session.get(Admin, int(user_id_str[2:]))
    elif user_id_str.startswith("c-"):
        return db.session.get(Customer, int(user_id_str[2:]))
    return None

# ── Register blueprints ────────────────────────────────────
from routes.admin        import admin_bp
from routes.webhook      import webhook_bp
from routes.customer_auth import customer_bp

app.register_blueprint(admin_bp)
app.register_blueprint(webhook_bp)
app.register_blueprint(customer_bp)

# ── Storefront routes ──────────────────────────────────────
from flask import render_template, redirect, url_for

@app.route("/products")
def products():
    return render_template("products.html")

@app.route("/products/<product_id>")
def product_single(product_id):
    catalogue = {
        "cat-cup":      {"name": "Cat Cup",      "image": "products/product_square/mTx1.webp",  "price": "$15.00", "desc": "The perfect entry-level cat cup for your mornings. Holds up to 250ml of coffee, 24/7."},
        "hedgehog-cup": {"name": "Hedgehog Cup",  "image": "products/product_square/mtx2.jpeg",  "price": "$18.00", "desc": "A charming hedgehog cup to brighten your afternoon tea."},
        "fox-cup":      {"name": "Fox Cup",       "image": "products/product_square/mtx3.jpg",   "price": "$20.00", "desc": "Sly and stylish — the fox cup holds up to 350ml."},
        "rabbit-cup":   {"name": "Rabbit Cup",    "image": "products/product_square/mtx4.jpg",   "price": "$17.00", "desc": "Hop into your morning routine with this adorable rabbit cup."},
        "bear-cup":     {"name": "Bear Cup",      "image": "products/product_square/mtx5.webp",  "price": "$22.00", "desc": "Big, bold, and beary cute. Perfect for large coffees."},
    }
    product = catalogue.get(product_id)
    if not product:
        return redirect(url_for("products"))
    return render_template("products_single.html", product=product, product_id=product_id)

@app.route("/faq")
def faq():
    return render_template("faq.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

# ── Run ────────────────────────────────────────────────────
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
