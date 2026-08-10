import os
from datetime import date, datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

from models import db, Employee, LeaveRequest, ChatMessage
from services.policy_repository import load_policies, search_policies
from services.career_repository import find_career_path, list_target_departments_from
from services.askivy_engine import answer_question, employee_facts, default_leave_dates
from services.rasa_adapter import rasa_bp

load_dotenv()


def create_app():
    app = Flask(__name__)

    database_url = os.getenv("DATABASE_URL", "sqlite:///askivy_hrms.db")
    # Render/Supabase sometimes provide postgres://, SQLAlchemy expects postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")}})

    with app.app_context():
        db.create_all()
        ensure_columns()        # raw SQL only -- must precede any ORM query
        seed_demo_data()
        ensure_admin_accounts()  # ORM -- must follow seeding

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "AskIvy HRMS API"})

    @app.get("/api/users")
    def users():
        employees = Employee.query.order_by(Employee.name).all()
        return jsonify([employee.to_dict() for employee in employees])

    @app.get("/api/employees/<employee_id>")
    def employee_profile(employee_id):
        employee = Employee.query.get_or_404(employee_id)
        return jsonify({"employee": employee.to_dict(), "facts": employee_facts(employee)})

    @app.get("/api/employees/<employee_id>/dashboard")
    def employee_dashboard(employee_id):
        employee = Employee.query.get_or_404(employee_id)
        leave_history = [req.to_dict() for req in sorted(employee.leave_requests, key=lambda r: r.start_date, reverse=True)]
        pending_count = sum(1 for req in employee.leave_requests if req.status == "Pending")
        return jsonify({
            "employee": employee.to_dict(),
            "facts": employee_facts(employee),
            "pendingCount": pending_count,
            "leaveHistory": leave_history,
        })

    @app.get("/api/employees/<employee_id>/leave")
    def employee_leave(employee_id):
        employee = Employee.query.get_or_404(employee_id)
        leave_history = [req.to_dict() for req in sorted(employee.leave_requests, key=lambda r: r.start_date, reverse=True)]
        return jsonify({"employee": employee.to_dict(), "facts": employee_facts(employee), "leaveHistory": leave_history})

    @app.post("/api/employees/<employee_id>/leave")
    def submit_leave(employee_id):
        employee = Employee.query.get_or_404(employee_id)
        payload = request.get_json(silent=True) or {}

        leave_type = str(payload.get("type", "Annual")).strip().capitalize()
        start_date = parse_date(payload.get("from"))
        end_date = parse_date(payload.get("to"))
        reason = payload.get("reason", "")
        submitted_via = payload.get("submittedVia", "Portal")

        if not start_date or not end_date:
            return jsonify({"error": "Start date and end date are required."}), 400
        if end_date < start_date:
            return jsonify({"error": "End date must be after start date."}), 400

        days = (end_date - start_date).days + 1
        leave = LeaveRequest(
            employee_id=employee.id,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            number_of_days=days,
            reason=reason,
            submitted_via=submitted_via,
            status="Pending",
        )
        db.session.add(leave)
        if leave_type == "Annual":
            employee.annual_leave_taken += days
        db.session.commit()

        return jsonify({"message": "Leave request submitted.", "leave": leave.to_dict(), "facts": employee_facts(employee)}), 201

    @app.post("/api/employees/<employee_id>/leave/<int:leave_id>/cancel")
    def cancel_leave(employee_id, leave_id):
        employee = Employee.query.get_or_404(employee_id)
        leave = LeaveRequest.query.filter_by(id=leave_id, employee_id=employee_id).first()
        if not leave:
            return jsonify({"error": "Leave request not found."}), 404
        if leave.status != "Pending":
            return jsonify({"error": f"Only pending requests can be cancelled (this one is {leave.status})."}), 400

        leave.status = "Cancelled"
        if leave.leave_type == "Annual":
            employee.annual_leave_taken -= leave.number_of_days
        db.session.commit()

        return jsonify({"message": "Leave request cancelled.", "leave": leave.to_dict(), "facts": employee_facts(employee)})

    @app.get("/api/employees/<employee_id>/chat")
    def employee_chat_history(employee_id):
        """One employee's own conversation history, newest first."""
        employee = Employee.query.get_or_404(employee_id)
        messages = sorted(employee.chat_messages, key=lambda m: m.created_at, reverse=True)
        return jsonify({
            "employee": employee.to_dict(),
            "messages": [m.to_dict() for m in messages],
        })

    @app.get("/api/admin/chats")
    def admin_chats():
        """Every conversation, for the support views. Optional ?employeeId= filter.

        The requester is identified by a query parameter, which is trivially spoofable --
        this app has no sessions or passwords anywhere, so this checks a ROLE, it does not
        authenticate an IDENTITY. Real deployment would put this behind proper auth; the
        403 below exists so the shape is right and the gap is explicit rather than absent.
        """
        requester_id = str(request.args.get("requesterId", "")).strip()
        requester = Employee.query.get(requester_id) if requester_id else None
        if not requester or not requester.is_admin:
            return jsonify({"error": "Support access required."}), 403

        query = ChatMessage.query
        employee_filter = str(request.args.get("employeeId", "")).strip()
        if employee_filter:
            query = query.filter_by(employee_id=employee_filter)

        try:
            limit = min(int(request.args.get("limit", 200)), 1000)
        except (TypeError, ValueError):
            return jsonify({"error": "limit must be a whole number."}), 400

        rows = query.order_by(ChatMessage.created_at.desc()).limit(limit).all()
        names = {e.id: e.name for e in Employee.query.all()}
        return jsonify({
            "total": query.count(),
            "returned": len(rows),
            "messages": [
                {**m.to_dict(), "employeeId": m.employee_id, "employeeName": names.get(m.employee_id, m.employee_id)}
                for m in rows
            ],
        })

    @app.get("/api/policies")
    def policies():
        return jsonify(load_policies())

    @app.get("/api/policies/search")
    def policies_search():
        """Keyword policy retrieval, shared by the rule-based engine and Rasa.

        The Rasa action server calls this instead of reimplementing matching,
        so both chat engines cite the same policies for the same question.
        """
        query = str(request.args.get("q", "")).strip()
        if not query:
            return jsonify({"error": "Query parameter 'q' is required."}), 400
        return jsonify(search_policies(query))

    @app.get("/api/careers/search")
    def careers_search():
        """Look up a defined career path between two departments.

        Returns 200 with `match: null` (plus whatever alternatives exist from
        the same starting department) when no path is defined for that pair —
        this is a normal, expected outcome, not an error. The caller decides
        how to phrase "we don't have a plan for that yet" honestly rather than
        having an LLM invent one.
        """
        from_department = str(request.args.get("from", "")).strip()
        to_department = str(request.args.get("to", "")).strip()
        if not from_department or not to_department:
            return jsonify({"error": "Query parameters 'from' and 'to' are required."}), 400

        match = find_career_path(from_department, to_department)
        if not match:
            return jsonify({"match": None, "alternatives": list_target_departments_from(from_department)})
        return jsonify({"match": match, "alternatives": []})

    @app.post("/api/askivy/chat")
    def askivy_chat():
        payload = request.get_json(silent=True) or {}
        employee_id = payload.get("employeeId")
        question = str(payload.get("message", "")).strip()

        if not employee_id or not question:
            return jsonify({"error": "employeeId and message are required."}), 400

        employee = Employee.query.get_or_404(employee_id)
        answer = answer_question(employee, question)

        chat = ChatMessage(
            employee_id=employee.id,
            question=question,
            response=answer["text"],
            policy_used=answer.get("source"),
        )
        db.session.add(chat)
        db.session.commit()

        return jsonify(answer)

    @app.post("/api/askivy/submit-leave")
    def askivy_submit_leave():
        payload = request.get_json(silent=True) or {}
        employee_id = payload.get("employeeId")
        leave_type = str(payload.get("type", "Annual")).strip().capitalize()
        try:
            days = int(payload.get("days", 1))
        except (TypeError, ValueError):
            return jsonify({"error": "days must be a whole number."}), 400
        if days < 1:
            return jsonify({"error": "days must be at least 1."}), 400

        employee = Employee.query.get_or_404(employee_id)
        start_date, end_date = default_leave_dates(days)

        leave = LeaveRequest(
            employee_id=employee.id,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            number_of_days=days,
            reason="Submitted through AskIvy chatbot",
            submitted_via="AskIvy",
            status="Pending",
        )
        db.session.add(leave)
        if leave_type == "Annual":
            employee.annual_leave_taken += days
        db.session.commit()

        return jsonify({
            "message": f"{leave_type} leave request submitted through AskIvy.",
            "leave": leave.to_dict(),
            "facts": employee_facts(employee),
        }), 201

    # Rasa CALM chat engine: /api/askivy/chat-rasa + reset/health helpers.
    # The rule-based /api/askivy/chat above stays registered so the two engines
    # can be compared side by side.
    app.register_blueprint(rasa_bp)

    return app


def parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


SUPPORT_ACCOUNT_ID = "nadia"

# Employees allowed into the support views. Comma-separated ids; override per deployment.
# In a real system this comes from an identity provider group, not a seeded list.
ADMIN_EMPLOYEE_IDS = [
    e.strip() for e in os.getenv("ADMIN_EMPLOYEE_IDS", SUPPORT_ACCOUNT_ID).split(",") if e.strip()
]


def support_account():
    """The HR person the support views are demoed as.

    Built by a factory rather than inline because two paths need it: a fresh seed, and
    ensure_schema() back-filling a database that already has rows.
    """
    return Employee(
        id=SUPPORT_ACCOUNT_ID, initials="NR", name="Nadia Rahman",
        role="HR Business Partner", department="Human Resources",
        start_date=date(2021, 3, 1), tenure_years=5, marital_status="Married",
        recent_event=None, annual_leave_entitlement=21, annual_leave_taken=6,
        probation=False, salary_band="Band 5", is_admin=True,
    )


def ensure_columns():
    """Add columns that `db.create_all()` won't. Runs BEFORE any ORM query.

    `create_all()` creates missing TABLES but never missing COLUMNS, so adding `is_admin`
    breaks any database that already has rows -- both the local SQLite file and the live
    Postgres on Render.

    Ordering matters and is easy to get wrong: this uses the inspector and raw SQL only,
    with no ORM queries, because the very first thing seed_demo_data() does is
    `Employee.query.first()` -- which SELECTs every mapped column, including the one that
    doesn't exist yet. Anything touching the ORM has to wait until after this has run.

    A real project would use Alembic. This is the smallest thing that avoids hand-surgery
    on a live database days before a demo.
    """
    inspector = db.inspect(db.engine)
    if "employees" not in inspector.get_table_names():
        return  # brand new database; create_all + seed handle it

    columns = {c["name"] for c in inspector.get_columns("employees")}
    if "is_admin" not in columns:
        # DEFAULT FALSE is valid on both SQLite (3.23+) and Postgres. `DEFAULT 0` is not --
        # Postgres rejects an integer default on a BOOLEAN column.
        db.session.execute(db.text(
            "ALTER TABLE employees ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE"
        ))
        db.session.commit()


def ensure_admin_accounts():
    """Make sure the support account exists and ADMIN_EMPLOYEE_IDS is applied.

    Runs AFTER seed_demo_data(), because seeding bails out the moment any employee exists
    and this function creates one.
    """
    if Employee.query.first() and not Employee.query.get(SUPPORT_ACCOUNT_ID):
        db.session.add(support_account())
        db.session.commit()

    for employee in Employee.query.all():
        should_be_admin = employee.id in ADMIN_EMPLOYEE_IDS
        if employee.is_admin != should_be_admin:
            employee.is_admin = should_be_admin
    db.session.commit()


def seed_demo_data():
    if Employee.query.first():
        return

    sarah = Employee(
        id="sarah",
        initials="ST",
        name="Sarah Tan",
        role="Principal Engineer",
        department="Engineering",
        start_date=date(2019, 3, 4),
        tenure_years=7,
        marital_status="Married",
        recent_event="Gave birth on 2026-05-10",
        annual_leave_entitlement=21,
        annual_leave_taken=9,
        probation=False,
        salary_band="Band 6",
    )
    marcus = Employee(
        id="marcus",
        initials="MR",
        name="Marcus Reyes",
        role="Junior Designer",
        department="Product",
        start_date=date(2026, 2, 2),
        tenure_years=0,
        marital_status="Single",
        recent_event="Recently joined — still in probation",
        annual_leave_entitlement=14,
        annual_leave_taken=3,
        probation=True,
        salary_band="Band 2",
    )

    # SME roster — 5 departments, 1-5 people each, sized so the seed data can
    # actually exercise things like career_paths.json (Engineering, Product,
    # Design, Sales, Operations all have real headcount) rather than existing
    # only as strings in a JSON file nobody's HRMS record uses.
    david = Employee(
        id="david", initials="DO", name="David Ong", role="Engineering Manager", department="Engineering",
        start_date=date(2017, 5, 12), tenure_years=9, marital_status="Married", recent_event=None,
        annual_leave_entitlement=21, annual_leave_taken=5, probation=False, salary_band="Band 7",
    )
    priya = Employee(
        id="priya", initials="PN", name="Priya Nair", role="Software Engineer", department="Engineering",
        start_date=date(2023, 1, 16), tenure_years=3, marital_status="Single", recent_event=None,
        annual_leave_entitlement=18, annual_leave_taken=6, probation=False, salary_band="Band 4",
    )
    aiden = Employee(
        id="aiden", initials="AL", name="Aiden Lim", role="Junior Software Engineer", department="Engineering",
        start_date=date(2025, 3, 10), tenure_years=1, marital_status="Single", recent_event=None,
        annual_leave_entitlement=14, annual_leave_taken=2, probation=False, salary_band="Band 2",
    )
    ethan = Employee(
        id="ethan", initials="EG", name="Ethan Goh", role="Product Manager", department="Product",
        start_date=date(2022, 6, 1), tenure_years=4, marital_status="Married", recent_event=None,
        annual_leave_entitlement=18, annual_leave_taken=4, probation=False, salary_band="Band 5",
    )
    meiling = Employee(
        id="meiling", initials="MT", name="Mei Ling Tan", role="Lead Product Designer", department="Design",
        start_date=date(2020, 9, 21), tenure_years=6, marital_status="Married", recent_event=None,
        annual_leave_entitlement=21, annual_leave_taken=8, probation=False, salary_band="Band 6",
    )
    farah = Employee(
        id="farah", initials="FA", name="Farah Aziz", role="UI/UX Designer", department="Design",
        start_date=date(2024, 4, 15), tenure_years=2, marital_status="Single", recent_event=None,
        annual_leave_entitlement=18, annual_leave_taken=5, probation=False, salary_band="Band 3",
    )
    rachel = Employee(
        id="rachel", initials="RK", name="Rachel Koh", role="Head of Sales", department="Sales",
        start_date=date(2018, 2, 19), tenure_years=8, marital_status="Married", recent_event=None,
        annual_leave_entitlement=21, annual_leave_taken=10, probation=False, salary_band="Band 7",
    )
    kevin = Employee(
        id="kevin", initials="KT", name="Kevin Tan", role="Account Executive", department="Sales",
        start_date=date(2023, 8, 7), tenure_years=3, marital_status="Single",
        recent_event="Recently completed HubSpot Sales certification",
        annual_leave_entitlement=18, annual_leave_taken=7, probation=False, salary_band="Band 4",
    )
    nurul = Employee(
        id="nurul", initials="NH", name="Nurul Huda", role="Sales Associate", department="Sales",
        start_date=date(2026, 6, 1), tenure_years=0, marital_status="Single",
        recent_event="Recently joined — still in probation",
        annual_leave_entitlement=14, annual_leave_taken=1, probation=True, salary_band="Band 2",
    )
    weijian = Employee(
        id="weijian", initials="WL", name="Wei Jian Lee", role="Operations Manager", department="Operations",
        start_date=date(2020, 11, 3), tenure_years=6, marital_status="Married", recent_event=None,
        annual_leave_entitlement=21, annual_leave_taken=9, probation=False, salary_band="Band 6",
    )
    siti = Employee(
        id="siti", initials="SR", name="Siti Rahman", role="Operations Executive", department="Operations",
        start_date=date(2024, 2, 26), tenure_years=2, marital_status="Married",
        recent_event="Interested in moving into Sales",
        annual_leave_entitlement=18, annual_leave_taken=4, probation=False, salary_band="Band 3",
    )
    junwei = Employee(
        id="junwei", initials="JC", name="Jun Wei Chua", role="Operations Associate", department="Operations",
        start_date=date(2025, 5, 19), tenure_years=1, marital_status="Single", recent_event=None,
        annual_leave_entitlement=14, annual_leave_taken=2, probation=False, salary_band="Band 2",
    )

    db.session.add_all([
        support_account(),
        sarah, marcus,
        david, priya, aiden,
        ethan,
        meiling, farah,
        rachel, kevin, nurul,
        weijian, siti, junwei,
    ])
    db.session.flush()

    demo_leave = [
        LeaveRequest(employee_id="sarah", leave_type="Annual", start_date=date(2026, 1, 13), end_date=date(2026, 1, 17), number_of_days=5, status="Approved", submitted_via="Portal"),
        LeaveRequest(employee_id="sarah", leave_type="Sick", start_date=date(2026, 3, 4), end_date=date(2026, 3, 5), number_of_days=2, status="Approved", submitted_via="Portal"),
        LeaveRequest(employee_id="sarah", leave_type="Annual", start_date=date(2026, 4, 21), end_date=date(2026, 4, 24), number_of_days=4, status="Approved", submitted_via="Portal"),
        LeaveRequest(employee_id="marcus", leave_type="Annual", start_date=date(2026, 5, 2), end_date=date(2026, 5, 2), number_of_days=1, status="Approved", submitted_via="Portal"),
        LeaveRequest(employee_id="marcus", leave_type="Sick", start_date=date(2026, 5, 20), end_date=date(2026, 5, 20), number_of_days=1, status="Approved", submitted_via="Portal"),
        LeaveRequest(employee_id="marcus", leave_type="Annual", start_date=date(2026, 6, 30), end_date=date(2026, 6, 30), number_of_days=1, status="Pending", submitted_via="Portal"),
        LeaveRequest(employee_id="david", leave_type="Annual", start_date=date(2026, 1, 5), end_date=date(2026, 1, 9), number_of_days=5, status="Approved", submitted_via="Portal"),
        LeaveRequest(employee_id="priya", leave_type="Annual", start_date=date(2026, 2, 10), end_date=date(2026, 2, 15), number_of_days=6, status="Approved", submitted_via="Portal"),
        LeaveRequest(employee_id="aiden", leave_type="Annual", start_date=date(2026, 3, 2), end_date=date(2026, 3, 3), number_of_days=2, status="Approved", submitted_via="Portal"),
        LeaveRequest(employee_id="ethan", leave_type="Annual", start_date=date(2026, 2, 16), end_date=date(2026, 2, 19), number_of_days=4, status="Approved", submitted_via="Portal"),
        LeaveRequest(employee_id="meiling", leave_type="Annual", start_date=date(2026, 1, 19), end_date=date(2026, 1, 26), number_of_days=8, status="Approved", submitted_via="Portal"),
        LeaveRequest(employee_id="farah", leave_type="Annual", start_date=date(2026, 3, 16), end_date=date(2026, 3, 20), number_of_days=5, status="Approved", submitted_via="Portal"),
        LeaveRequest(employee_id="rachel", leave_type="Annual", start_date=date(2026, 1, 12), end_date=date(2026, 1, 21), number_of_days=10, status="Approved", submitted_via="Portal"),
        LeaveRequest(employee_id="kevin", leave_type="Annual", start_date=date(2026, 4, 6), end_date=date(2026, 4, 12), number_of_days=7, status="Approved", submitted_via="Portal"),
        LeaveRequest(employee_id="nurul", leave_type="Annual", start_date=date(2026, 7, 20), end_date=date(2026, 7, 20), number_of_days=1, status="Pending", submitted_via="Portal"),
        LeaveRequest(employee_id="weijian", leave_type="Annual", start_date=date(2026, 2, 23), end_date=date(2026, 3, 3), number_of_days=9, status="Approved", submitted_via="Portal"),
        LeaveRequest(employee_id="siti", leave_type="Annual", start_date=date(2026, 5, 4), end_date=date(2026, 5, 7), number_of_days=4, status="Approved", submitted_via="Portal"),
        LeaveRequest(employee_id="junwei", leave_type="Annual", start_date=date(2026, 6, 8), end_date=date(2026, 6, 9), number_of_days=2, status="Approved", submitted_via="Portal"),
    ]
    db.session.add_all(demo_leave)
    db.session.commit()


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
