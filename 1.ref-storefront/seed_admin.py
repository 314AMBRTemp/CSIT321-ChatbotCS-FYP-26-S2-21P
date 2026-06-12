from app import app
from models import db, Admin
from extensions import Bcrypt

bcrypt = Bcrypt(app)

with app.app_context():
    db.create_all()

    if Admin.query.count() == 0:
        admin = Admin(
            email="admin@shopbot.com",
            password_hash=bcrypt.generate_password_hash("admin123").decode("utf-8"),
            name="Admin User"
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin created.")
        print("   Email:    admin@shopbot.com")
        print("   Password: admin123")
    else:
        print("ℹ️  Admin already exists — skipping.")
