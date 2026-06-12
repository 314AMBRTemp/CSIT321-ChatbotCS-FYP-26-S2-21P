from app import app
from models import db, Customer, Order, Ticket
from extensions import bcrypt

NEW_CUSTOMERS = [
    {"email": "fiona@email.com",  "name": "Fiona Yap",    "password": "password123"},
    {"email": "george@email.com", "name": "George Tan",   "password": "password123"},
    {"email": "hannah@email.com", "name": "Hannah Wong",  "password": "password123"},
    {"email": "ivan@email.com",   "name": "Ivan Chua",    "password": "password123"},
]

NEW_ORDERS = [
    # Alice Tan — 2 more
    {"order_id": "ORD-009", "email": "alice@email.com",  "name": "Alice Tan",   "status": "Delivered",        "delivery": "2026-04-10", "courier": "NinjaVan",    "address": "123 Orchard Road, Singapore 238858"},
    {"order_id": "ORD-010", "email": "alice@email.com",  "name": "Alice Tan",   "status": "Processing",       "delivery": "2026-06-20", "courier": "SingPost",    "address": "123 Orchard Road, Singapore 238858"},
    # Bob Lim — 2 more
    {"order_id": "ORD-011", "email": "bob@email.com",    "name": "Bob Lim",     "status": "In Transit",       "delivery": "2026-06-12", "courier": "DHL",         "address": "456 Jurong East Ave, Singapore 609731"},
    {"order_id": "ORD-012", "email": "bob@email.com",    "name": "Bob Lim",     "status": "Delivered",        "delivery": "2026-05-30", "courier": "J&T Express", "address": "456 Jurong East Ave, Singapore 609731"},
    # David Koh — 1 more
    {"order_id": "ORD-013", "email": "david@email.com",  "name": "David Koh",   "status": "Out for Delivery", "delivery": "2026-06-08", "courier": "Qxpress",     "address": "321 Bukit Timah Rd, Singapore 259695"},
    # Emily Lim — 2 more
    {"order_id": "ORD-014", "email": "emily@email.com",  "name": "Emily Lim",   "status": "Delivered",        "delivery": "2026-05-25", "courier": "SingPost",    "address": "88 Clementi Ave, Singapore 129955"},
    {"order_id": "ORD-015", "email": "emily@email.com",  "name": "Emily Lim",   "status": "Cancelled",        "delivery": "2026-05-18", "courier": "NinjaVan",    "address": "88 Clementi Ave, Singapore 129955"},
    # Fiona Yap — 3 orders
    {"order_id": "ORD-016", "email": "fiona@email.com",  "name": "Fiona Yap",   "status": "Delivered",        "delivery": "2026-04-22", "courier": "J&T Express", "address": "10 Pasir Ris Drive, Singapore 519491"},
    {"order_id": "ORD-017", "email": "fiona@email.com",  "name": "Fiona Yap",   "status": "Delivered",        "delivery": "2026-05-15", "courier": "SingPost",    "address": "10 Pasir Ris Drive, Singapore 519491"},
    {"order_id": "ORD-018", "email": "fiona@email.com",  "name": "Fiona Yap",   "status": "In Transit",       "delivery": "2026-06-14", "courier": "DHL",         "address": "10 Pasir Ris Drive, Singapore 519491"},
    # George Tan — 2 orders
    {"order_id": "ORD-019", "email": "george@email.com", "name": "George Tan",  "status": "Processing",       "delivery": "2026-06-18", "courier": "NinjaVan",    "address": "55 Ang Mo Kio Ave 3, Singapore 569933"},
    {"order_id": "ORD-020", "email": "george@email.com", "name": "George Tan",  "status": "Delivered",        "delivery": "2026-05-08", "courier": "Qxpress",     "address": "55 Ang Mo Kio Ave 3, Singapore 569933"},
    # Hannah Wong — 3 orders
    {"order_id": "ORD-021", "email": "hannah@email.com", "name": "Hannah Wong", "status": "Out for Delivery", "delivery": "2026-06-09", "courier": "SingPost",    "address": "77 Woodlands Ave 6, Singapore 738633"},
    {"order_id": "ORD-022", "email": "hannah@email.com", "name": "Hannah Wong", "status": "Delivered",        "delivery": "2026-04-30", "courier": "J&T Express", "address": "77 Woodlands Ave 6, Singapore 738633"},
    {"order_id": "ORD-023", "email": "hannah@email.com", "name": "Hannah Wong", "status": "Cancelled",        "delivery": "2026-05-05", "courier": "NinjaVan",    "address": "77 Woodlands Ave 6, Singapore 738633"},
    # Ivan Chua — 2 orders
    {"order_id": "ORD-024", "email": "ivan@email.com",   "name": "Ivan Chua",   "status": "In Transit",       "delivery": "2026-06-13", "courier": "DHL",         "address": "200 Bedok North Ave 1, Singapore 460200"},
    {"order_id": "ORD-025", "email": "ivan@email.com",   "name": "Ivan Chua",   "status": "Delivered",        "delivery": "2026-05-20", "courier": "SingPost",    "address": "200 Bedok North Ave 1, Singapore 460200"},
]

with app.app_context():
    added_customers = 0
    for c in NEW_CUSTOMERS:
        if not Customer.query.filter_by(email=c["email"]).first():
            db.session.add(Customer(
                email=c["email"],
                name=c["name"],
                password_hash=bcrypt.generate_password_hash(c["password"]).decode("utf-8")
            ))
            added_customers += 1

    db.session.commit()
    print(f"Added {added_customers} new customer(s).")

    added_orders = 0
    for o in NEW_ORDERS:
        if not Order.query.filter_by(order_id=o["order_id"]).first():
            db.session.add(Order(
                order_id=o["order_id"],
                customer_email=o["email"],
                customer_name=o["name"],
                status=o["status"],
                estimated_delivery=o["delivery"],
                courier=o["courier"],
                delivery_address=o["address"]
            ))
            added_orders += 1

    db.session.commit()
    print(f"Added {added_orders} new order(s).")
    print("\nNew accounts (all password: password123):")
    for c in NEW_CUSTOMERS:
        print(f"  {c['name']:15}  {c['email']}")

    # ── Seed tickets ───────────────────────────────────────
    NEW_TICKETS = [
        {"order_id": "ORD-001", "email": "alice@email.com",  "issue_type": "Damaged Item",       "description": "Cup arrived with a large crack on the rim.",                          "status": "open"},
        {"order_id": "ORD-002", "email": "bob@email.com",    "issue_type": "Missing Package",    "description": "Tracking shows delivered but package was not received.",              "status": "open"},
        {"order_id": "ORD-003", "email": "carol@email.com",  "issue_type": "Wrong Item",         "description": "Received a different design than what was ordered.",                  "status": "resolved"},
        {"order_id": "ORD-005", "email": "david@email.com",  "issue_type": "Address Change",     "description": "Delivery address changed to 88 Clementi Ave, Singapore 129955.",     "status": "resolved"},
        {"order_id": "ORD-006", "email": "emily@email.com",  "issue_type": "Damaged Item",       "description": "Packaging was torn and the cup inside was chipped.",                  "status": "open"},
        {"order_id": "ORD-011", "email": "bob@email.com",    "issue_type": "Delivery Delay",     "description": "Order has been in transit for over a week with no updates.",          "status": "open"},
        {"order_id": "ORD-018", "email": "fiona@email.com",  "issue_type": "Missing Package",    "description": "Estimated delivery passed 3 days ago and item has not arrived.",      "status": "open"},
        {"order_id": "ORD-019", "email": "george@email.com", "issue_type": "Wrong Item",         "description": "Received cat design instead of the ordered bear design cup.",         "status": "open"},
        {"order_id": "ORD-021", "email": "hannah@email.com", "issue_type": "Damaged Packaging",  "description": "Box was heavily dented on arrival but item appears intact.",          "status": "resolved"},
        {"order_id": "ORD-010", "email": "alice@email.com",  "issue_type": "Cancellation",       "description": "Customer requested cancellation of ORD-010.",                        "status": "resolved"},
    ]

    added_tickets = 0
    for t in NEW_TICKETS:
        existing = Ticket.query.filter_by(
            order_id=t["order_id"],
            customer_email=t["email"],
            issue_type=t["issue_type"]
        ).first()
        if not existing:
            db.session.add(Ticket(
                order_id=t["order_id"],
                customer_email=t["email"],
                issue_type=t["issue_type"],
                description=t["description"],
                status=t["status"]
            ))
            added_tickets += 1

    db.session.commit()
    print(f"Added {added_tickets} new ticket(s).")
