from app import app
from models import db, Customer, Order, Ticket
from extensions import bcrypt

# ── Original test customers ────────────────────────────────
CUSTOMERS = [
    {"email": "alice@email.com",  "name": "Alice Tan",   "password": "password123"},
    {"email": "bob@email.com",    "name": "Bob Lim",     "password": "password123"},
    {"email": "carol@email.com",  "name": "Carol Ng",    "password": "password123"},
    {"email": "david@email.com",  "name": "David Koh",   "password": "password123"},
    {"email": "emily@email.com",  "name": "Emily Lim",   "password": "password123"},
    {"email": "fiona@email.com",  "name": "Fiona Yap",   "password": "password123"},
    {"email": "george@email.com", "name": "George Tan",  "password": "password123"},
    {"email": "hannah@email.com", "name": "Hannah Wong", "password": "password123"},
    {"email": "ivan@email.com",   "name": "Ivan Chua",   "password": "password123"},
    # ── Team accounts ──────────────────────────────────────
    {"email": "lazo002+fyp21p@mymail.sim.edu.sg",  "name": "Lazo",      "password": "password123"},
    {"email": "hfyap001+fyp21p@mymail.sim.edu.sg", "name": "H F Yap",   "password": "password123"},
    {"email": "syhlim002+fyp21p@mymail.sim.edu.sg","name": "S Y H Lim", "password": "password123"},
    {"email": "ramli003+fyp21p@mymail.sim.edu.sg", "name": "Ramli",     "password": "password123"},
    {"email": "rjwlim002+fyp21p@mymail.sim.edu.sg","name": "R J W Lim", "password": "password123"},
    {"email": "sjapit+fyp21p@uow.edu.au",          "name": "S J Apit",  "password": "password123"},
]

ORDERS = [
    # ── Alice Tan ──────────────────────────────────────────
    {"order_id": "ORD-001", "email": "alice@email.com",  "name": "Alice Tan",   "status": "Out for Delivery", "delivery": "2025-05-17", "courier": "SingPost",    "address": "123 Orchard Road, Singapore 238858"},
    {"order_id": "ORD-004", "email": "alice@email.com",  "name": "Alice Tan",   "status": "Processing",       "delivery": "2025-05-22", "courier": "SingPost",    "address": "123 Orchard Road, Singapore 238858"},
    {"order_id": "ORD-009", "email": "alice@email.com",  "name": "Alice Tan",   "status": "Delivered",        "delivery": "2026-04-10", "courier": "NinjaVan",    "address": "123 Orchard Road, Singapore 238858"},
    {"order_id": "ORD-010", "email": "alice@email.com",  "name": "Alice Tan",   "status": "Processing",       "delivery": "2026-06-20", "courier": "SingPost",    "address": "123 Orchard Road, Singapore 238858"},
    # ── Bob Lim ────────────────────────────────────────────
    {"order_id": "ORD-002", "email": "bob@email.com",    "name": "Bob Lim",     "status": "In Transit",       "delivery": "2025-05-19", "courier": "NinjaVan",    "address": "456 Jurong East Ave, Singapore 609731"},
    {"order_id": "ORD-007", "email": "bob@email.com",    "name": "Bob Lim",     "status": "Delivered",        "delivery": "2025-05-14", "courier": "J&T Express", "address": "456 Jurong East Ave, Singapore 609731"},
    {"order_id": "ORD-011", "email": "bob@email.com",    "name": "Bob Lim",     "status": "In Transit",       "delivery": "2026-06-12", "courier": "DHL",         "address": "456 Jurong East Ave, Singapore 609731"},
    {"order_id": "ORD-012", "email": "bob@email.com",    "name": "Bob Lim",     "status": "Delivered",        "delivery": "2026-05-30", "courier": "J&T Express", "address": "456 Jurong East Ave, Singapore 609731"},
    # ── Carol Ng ───────────────────────────────────────────
    {"order_id": "ORD-003", "email": "carol@email.com",  "name": "Carol Ng",    "status": "Delivered",        "delivery": "2025-05-15", "courier": "J&T Express", "address": "789 Tampines St, Singapore 520789"},
    {"order_id": "ORD-008", "email": "carol@email.com",  "name": "Carol Ng",    "status": "Cancelled",        "delivery": "2025-05-18", "courier": "SingPost",    "address": "789 Tampines St, Singapore 520789"},
    # ── David Koh ──────────────────────────────────────────
    {"order_id": "ORD-005", "email": "david@email.com",  "name": "David Koh",   "status": "In Transit",       "delivery": "2025-05-20", "courier": "DHL",         "address": "321 Bukit Timah Rd, Singapore 259695"},
    {"order_id": "ORD-013", "email": "david@email.com",  "name": "David Koh",   "status": "Out for Delivery", "delivery": "2026-06-08", "courier": "Qxpress",     "address": "321 Bukit Timah Rd, Singapore 259695"},
    # ── Emily Lim ──────────────────────────────────────────
    {"order_id": "ORD-006", "email": "emily@email.com",  "name": "Emily Lim",   "status": "Out for Delivery", "delivery": "2025-05-17", "courier": "NinjaVan",    "address": "88 Clementi Ave, Singapore 129955"},
    {"order_id": "ORD-014", "email": "emily@email.com",  "name": "Emily Lim",   "status": "Delivered",        "delivery": "2026-05-25", "courier": "SingPost",    "address": "88 Clementi Ave, Singapore 129955"},
    {"order_id": "ORD-015", "email": "emily@email.com",  "name": "Emily Lim",   "status": "Cancelled",        "delivery": "2026-05-18", "courier": "NinjaVan",    "address": "88 Clementi Ave, Singapore 129955"},
    # ── Fiona Yap ──────────────────────────────────────────
    {"order_id": "ORD-016", "email": "fiona@email.com",  "name": "Fiona Yap",   "status": "Delivered",        "delivery": "2026-04-22", "courier": "J&T Express", "address": "10 Pasir Ris Drive, Singapore 519491"},
    {"order_id": "ORD-017", "email": "fiona@email.com",  "name": "Fiona Yap",   "status": "Delivered",        "delivery": "2026-05-15", "courier": "SingPost",    "address": "10 Pasir Ris Drive, Singapore 519491"},
    {"order_id": "ORD-018", "email": "fiona@email.com",  "name": "Fiona Yap",   "status": "In Transit",       "delivery": "2026-06-14", "courier": "DHL",         "address": "10 Pasir Ris Drive, Singapore 519491"},
    # ── George Tan ─────────────────────────────────────────
    {"order_id": "ORD-019", "email": "george@email.com", "name": "George Tan",  "status": "Processing",       "delivery": "2026-06-18", "courier": "NinjaVan",    "address": "55 Ang Mo Kio Ave 3, Singapore 569933"},
    {"order_id": "ORD-020", "email": "george@email.com", "name": "George Tan",  "status": "Delivered",        "delivery": "2026-05-08", "courier": "Qxpress",     "address": "55 Ang Mo Kio Ave 3, Singapore 569933"},
    # ── Hannah Wong ────────────────────────────────────────
    {"order_id": "ORD-021", "email": "hannah@email.com", "name": "Hannah Wong", "status": "Out for Delivery", "delivery": "2026-06-09", "courier": "SingPost",    "address": "77 Woodlands Ave 6, Singapore 738633"},
    {"order_id": "ORD-022", "email": "hannah@email.com", "name": "Hannah Wong", "status": "Delivered",        "delivery": "2026-04-30", "courier": "J&T Express", "address": "77 Woodlands Ave 6, Singapore 738633"},
    {"order_id": "ORD-023", "email": "hannah@email.com", "name": "Hannah Wong", "status": "Cancelled",        "delivery": "2026-05-05", "courier": "NinjaVan",    "address": "77 Woodlands Ave 6, Singapore 738633"},
    # ── Ivan Chua ──────────────────────────────────────────
    {"order_id": "ORD-024", "email": "ivan@email.com",   "name": "Ivan Chua",   "status": "In Transit",       "delivery": "2026-06-13", "courier": "DHL",         "address": "200 Bedok North Ave 1, Singapore 460200"},
    {"order_id": "ORD-025", "email": "ivan@email.com",   "name": "Ivan Chua",   "status": "Delivered",        "delivery": "2026-05-20", "courier": "SingPost",    "address": "200 Bedok North Ave 1, Singapore 460200"},
    # ── Lazo ───────────────────────────────────────────────
    {"order_id": "ORD-026", "email": "lazo002+fyp21p@mymail.sim.edu.sg",  "name": "Lazo",      "status": "In Transit",       "delivery": "2026-06-20", "courier": "NinjaVan",    "address": "10 Simei Street 1, Singapore 529948"},
    {"order_id": "ORD-027", "email": "lazo002+fyp21p@mymail.sim.edu.sg",  "name": "Lazo",      "status": "Delivered",        "delivery": "2026-05-30", "courier": "SingPost",    "address": "10 Simei Street 1, Singapore 529948"},
    # ── H F Yap ────────────────────────────────────────────
    {"order_id": "ORD-028", "email": "hfyap001+fyp21p@mymail.sim.edu.sg", "name": "H F Yap",   "status": "Processing",       "delivery": "2026-06-22", "courier": "J&T Express", "address": "22 Bishan Street 11, Singapore 570022"},
    {"order_id": "ORD-029", "email": "hfyap001+fyp21p@mymail.sim.edu.sg", "name": "H F Yap",   "status": "Delivered",        "delivery": "2026-05-18", "courier": "DHL",         "address": "22 Bishan Street 11, Singapore 570022"},
    # ── S Y H Lim ──────────────────────────────────────────
    {"order_id": "ORD-030", "email": "syhlim002+fyp21p@mymail.sim.edu.sg","name": "S Y H Lim", "status": "Out for Delivery", "delivery": "2026-06-19", "courier": "Qxpress",     "address": "33 Yishun Ave 2, Singapore 769098"},
    {"order_id": "ORD-031", "email": "syhlim002+fyp21p@mymail.sim.edu.sg","name": "S Y H Lim", "status": "Cancelled",        "delivery": "2026-05-10", "courier": "SingPost",    "address": "33 Yishun Ave 2, Singapore 769098"},
    # ── Ramli ──────────────────────────────────────────────
    {"order_id": "ORD-032", "email": "ramli003+fyp21p@mymail.sim.edu.sg", "name": "Ramli",     "status": "In Transit",       "delivery": "2026-06-21", "courier": "NinjaVan",    "address": "44 Tampines Ave 5, Singapore 520044"},
    {"order_id": "ORD-033", "email": "ramli003+fyp21p@mymail.sim.edu.sg", "name": "Ramli",     "status": "Delivered",        "delivery": "2026-05-25", "courier": "J&T Express", "address": "44 Tampines Ave 5, Singapore 520044"},
    # ── R J W Lim ──────────────────────────────────────────
    {"order_id": "ORD-034", "email": "rjwlim002+fyp21p@mymail.sim.edu.sg","name": "R J W Lim", "status": "Processing",       "delivery": "2026-06-25", "courier": "DHL",         "address": "55 Jurong West Ave 3, Singapore 640055"},
    {"order_id": "ORD-035", "email": "rjwlim002+fyp21p@mymail.sim.edu.sg","name": "R J W Lim", "status": "Delivered",        "delivery": "2026-05-12", "courier": "SingPost",    "address": "55 Jurong West Ave 3, Singapore 640055"},
    # ── S J Apit ───────────────────────────────────────────
    {"order_id": "ORD-036", "email": "sjapit+fyp21p@uow.edu.au",          "name": "S J Apit",  "status": "Out for Delivery", "delivery": "2026-06-18", "courier": "Qxpress",     "address": "66 Clementi Road, Singapore 129966"},
    {"order_id": "ORD-037", "email": "sjapit+fyp21p@uow.edu.au",          "name": "S J Apit",  "status": "Delivered",        "delivery": "2026-05-22", "courier": "NinjaVan",    "address": "66 Clementi Road, Singapore 129966"},
]

TICKETS = [
    {"order_id": "ORD-001", "email": "alice@email.com",  "issue_type": "Damaged Item",      "description": "Cup arrived with a large crack on the rim.",                        "status": "open"},
    {"order_id": "ORD-002", "email": "bob@email.com",    "issue_type": "Missing Package",   "description": "Tracking shows delivered but package was not received.",            "status": "open"},
    {"order_id": "ORD-003", "email": "carol@email.com",  "issue_type": "Wrong Item",        "description": "Received a different design than what was ordered.",                "status": "resolved"},
    {"order_id": "ORD-005", "email": "david@email.com",  "issue_type": "Address Change",    "description": "Delivery address changed to 88 Clementi Ave, Singapore 129955.",   "status": "resolved"},
    {"order_id": "ORD-006", "email": "emily@email.com",  "issue_type": "Damaged Item",      "description": "Packaging was torn and the cup inside was chipped.",                "status": "open"},
    {"order_id": "ORD-011", "email": "bob@email.com",    "issue_type": "Delivery Delay",    "description": "Order has been in transit for over a week with no updates.",        "status": "open"},
    {"order_id": "ORD-018", "email": "fiona@email.com",  "issue_type": "Missing Package",   "description": "Estimated delivery passed 3 days ago and item has not arrived.",    "status": "open"},
    {"order_id": "ORD-019", "email": "george@email.com", "issue_type": "Wrong Item",        "description": "Received cat design instead of the ordered bear design cup.",       "status": "open"},
    {"order_id": "ORD-021", "email": "hannah@email.com", "issue_type": "Damaged Packaging", "description": "Box was heavily dented on arrival but item appears intact.",        "status": "resolved"},
    {"order_id": "ORD-010", "email": "alice@email.com",  "issue_type": "Cancellation",      "description": "Customer requested cancellation of ORD-010.",                      "status": "resolved"},
]


with app.app_context():
    db.create_all()

    # ── Customers ──────────────────────────────────────────
    added_customers = 0
    for c in CUSTOMERS:
        if not Customer.query.filter_by(email=c["email"]).first():
            db.session.add(Customer(
                email=c["email"],
                name=c["name"],
                password_hash=bcrypt.generate_password_hash(c["password"]).decode("utf-8")
            ))
            added_customers += 1
    db.session.commit()
    print(f"Added {added_customers} new customer(s).")

    # ── Orders ─────────────────────────────────────────────
    added_orders = 0
    for o in ORDERS:
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

    # ── Tickets ────────────────────────────────────────────
    added_tickets = 0
    for t in TICKETS:
        if not Ticket.query.filter_by(
            order_id=t["order_id"],
            customer_email=t["email"],
            issue_type=t["issue_type"]
        ).first():
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

    print("\n✅ Seed complete.")
    print("   All passwords: password123")
    print("   Accounts:")
    for c in CUSTOMERS:
        print(f"     {c['name']:15}  {c['email']}")
