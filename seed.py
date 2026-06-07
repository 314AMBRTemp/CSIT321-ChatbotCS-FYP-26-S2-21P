from app import app
from models import db, Order, Customer
from extensions import bcrypt

with app.app_context():
    db.create_all()

    # ── Seed customers ─────────────────────────────────────
    if Customer.query.count() == 0:
        customers = [
            Customer(
                email="alice@email.com",
                password_hash=bcrypt.generate_password_hash("password123").decode("utf-8"),
                name="Alice Tan"
            ),
            Customer(
                email="bob@email.com",
                password_hash=bcrypt.generate_password_hash("password123").decode("utf-8"),
                name="Bob Lim"
            ),
            Customer(
                email="carol@email.com",
                password_hash=bcrypt.generate_password_hash("password123").decode("utf-8"),
                name="Carol Ng"
            ),
            Customer(
                email="david@email.com",
                password_hash=bcrypt.generate_password_hash("password123").decode("utf-8"),
                name="David Koh"
            ),
            Customer(
                email="emily@email.com",
                password_hash=bcrypt.generate_password_hash("password123").decode("utf-8"),
                name="Emily Lim"
            ),
        ]
        db.session.add_all(customers)
        db.session.commit()
        print("Customers seeded successfully.")
    else:
        print("Customers already exist — skipping.")

    # ── Seed orders ────────────────────────────────────────
    if Order.query.count() == 0:
        orders = [
            Order(
                order_id="ORD-001",
                customer_email="alice@email.com",
                customer_name="Alice Tan",
                status="Out for Delivery",
                estimated_delivery="2025-05-17",
                courier="SingPost",
                delivery_address="123 Orchard Road, Singapore 238858"
            ),
            Order(
                order_id="ORD-002",
                customer_email="bob@email.com",
                customer_name="Bob Lim",
                status="In Transit",
                estimated_delivery="2025-05-19",
                courier="NinjaVan",
                delivery_address="456 Jurong East Ave, Singapore 609731"
            ),
            Order(
                order_id="ORD-003",
                customer_email="carol@email.com",
                customer_name="Carol Ng",
                status="Delivered",
                estimated_delivery="2025-05-15",
                courier="J&T Express",
                delivery_address="789 Tampines St, Singapore 520789"
            ),
            Order(
                order_id="ORD-004",
                customer_email="alice@email.com",
                customer_name="Alice Tan",
                status="Processing",
                estimated_delivery="2025-05-22",
                courier="SingPost",
                delivery_address="123 Orchard Road, Singapore 238858"
            ),
            Order(
                order_id="ORD-005",
                customer_email="david@email.com",
                customer_name="David Koh",
                status="In Transit",
                estimated_delivery="2025-05-20",
                courier="DHL",
                delivery_address="321 Bukit Timah Rd, Singapore 259695"
            ),
            Order(
                order_id="ORD-006",
                customer_email="emily@email.com",
                customer_name="Emily Lim",
                status="Out for Delivery",
                estimated_delivery="2025-05-17",
                courier="NinjaVan",
                delivery_address="88 Clementi Ave, Singapore 129955"
            ),
            Order(
                order_id="ORD-007",
                customer_email="bob@email.com",
                customer_name="Bob Lim",
                status="Delivered",
                estimated_delivery="2025-05-14",
                courier="J&T Express",
                delivery_address="456 Jurong East Ave, Singapore 609731"
            ),
            Order(
                order_id="ORD-008",
                customer_email="carol@email.com",
                customer_name="Carol Ng",
                status="Cancelled",
                estimated_delivery="2025-05-18",
                courier="SingPost",
                delivery_address="789 Tampines St, Singapore 520789"
            ),
        ]
        db.session.add_all(orders)
        db.session.commit()
        print("Orders seeded successfully.")
    else:
        print("Orders already exist — skipping.")