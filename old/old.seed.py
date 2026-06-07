from app import app
from models import db, Order

with app.app_context():
    db.create_all()  # Creates tables if they don't exist

    # Only seed if orders table is empty
    if Order.query.count() == 0:
        sample_orders = [
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
        ]
        db.session.add_all(sample_orders)
        db.session.commit()
        print("Database seeded successfully.")
    else:
        print("Database already has data — skipping seed.")


### To check if DB is populated, python -c "from app import app; from models import db, Order; app.app_context().push(); print(Order.query.all())"