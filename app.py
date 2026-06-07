import os
from flask import Flask
from extensions import db, bcrypt, login_manager
from models import Admin, Customer


os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "serviceAccountKey.json"

app = Flask(__name__)
app.secret_key = "your-flask-secret-key-change-this"

# ── Database ───────────────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'orders.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ── Initialise extensions ──────────────────────────────────
db.init_app(app)
bcrypt.init_app(app)
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    # Try Admin first, then Customer
    user_id_str = str(user_id)
    if user_id_str.startswith("a-"):
        return db.session.get(Admin, int(user_id_str[2:]))
    elif user_id_str.startswith("c-"):
        return db.session.get(Customer, int(user_id_str[2:]))
    return None

# ── Register blueprints ────────────────────────────────────
from routes.admin   import admin_bp
from routes.webhook import webhook_bp
from routes.customer_auth import customer_bp

# Registering blueprints
app.register_blueprint(admin_bp)
app.register_blueprint(webhook_bp)
app.register_blueprint(customer_bp)

# ── Run ────────────────────────────────────────────────────
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)