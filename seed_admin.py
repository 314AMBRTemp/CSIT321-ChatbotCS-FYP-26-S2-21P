from app import app
from models import db, Admin
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt(app)

with app.app_context():
    db.create_all()

    # Only create if no admins exist
    if Admin.query.count() == 0:
        password_hash = bcrypt.generate_password_hash("admin123").decode("utf-8")
        admin = Admin(
            email="admin@shopbot.com",
            password_hash=password_hash,
            name="Admin User"
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin created successfully.")
        print("Email:    admin@shopbot.com")
        print("Password: admin123")
    else:
        print("Admin already exists — skipping.")