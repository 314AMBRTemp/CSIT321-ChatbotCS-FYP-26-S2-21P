import json
import os
from datetime import date, datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

from models import db, Employee, LeaveRequest, ChatMessage, Policy, PolicyExplanation, HRRequest
from services.policies import active_source, load_policies, search_policies
from services.policy_repository import load_policies as load_policies_from_file
from services.career_repository import find_career_path, list_target_departments_from
from services.askivy_engine import answer_question, employee_facts, default_leave_dates
from services.policy_answer import build_policy_answer
from services.rasa_adapter import rasa_bp

load_dotenv()


def _require_admin():
    """(employee, None) if ?requesterId= names an admin, else (None, (response, status)).

    Same trivially-spoofable-by-design check used by the two original admin routes --
    there are no passwords anywhere in this app, so this checks a ROLE via a query
    parameter, not an authenticated IDENTITY. Factored out once a third admin-only route
    needed the identical five lines; the two originals were left as they were rather than
    churned for a message-wording match that doesn't matter.
    """
    requester_id = str(request.args.get("requesterId", "")).strip()
    requester = db.session.get(Employee, requester_id) if requester_id else None
    if not requester or not requester.is_admin:
        return None, (jsonify({"error": "Admin access required."}), 403)
    return requester, None


# 3.2.5 -- Open -> In Progress -> Closed is enough to show progress without inventing a
# full ticketing workflow. HRRequest.status defaults to "Open" and only this list moves it.
HR_REQUEST_STATUSES = ["Open", "In Progress", "Closed"]


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
        ensure_managers()        # ORM -- needs every employee row to resolve dept heads
        seed_policies()          # keeps the policies table in step with hr_policies.json
        # Which source actually won, printed at boot. active_source() reports what was asked
        # for; this reports what is being served, so an empty-table fallback is visible in
        # the Render logs instead of being something you infer from odd answers later.
        print(f"[askivy] policy source requested={active_source()} serving={len(load_policies())} policies")

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

    @app.get("/api/employees/<employee_id>/hr-requests")
    def employee_hr_requests(employee_id):
        """One employee's own raised requests, so they can check progress on something they
        asked AskIvy to escalate (3.2.2). No admin gate -- it's their own data, same as
        /leave and /chat above."""
        employee = Employee.query.get_or_404(employee_id)
        rows = HRRequest.query.filter_by(employee_id=employee.id).order_by(HRRequest.created_at.desc()).all()
        return jsonify([row.to_dict() for row in rows])

    @app.get("/api/admin/chats")
    def admin_chats():
        """Every conversation, for the support views. Optional ?employeeId= filter.

        The requester is identified by a query parameter, which is trivially spoofable --
        this app has no sessions or passwords anywhere, so this checks a ROLE, it does not
        authenticate an IDENTITY. Real deployment would put this behind proper auth; the
        403 below exists so the shape is right and the gap is explicit rather than absent.
        """
        requester_id = str(request.args.get("requesterId", "")).strip()
        requester = db.session.get(Employee, requester_id) if requester_id else None
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

    @app.post("/api/policies/explain")
    def policies_explain():
        """A policy answer tailored to one employee. Called by both chat engines.

        Rasa's action server calls this rather than building the answer itself, for the same
        reason it calls /api/policies/search -- the deployed site runs the rule-based engine,
        so an answer assembled inside actions.py would never reach the demo.
        """
        payload = request.get_json(silent=True) or {}
        question = str(payload.get("question", "")).strip()
        if not question:
            return jsonify({"error": "Field 'question' is required."}), 400

        employee = db.session.get(Employee, payload.get("employeeId") or "")
        answer = build_policy_answer(employee.to_dict() if employee else None, question)
        if not answer:
            return jsonify({"error": "No policy matched."}), 404
        return jsonify(answer)

    @app.post("/api/hr-requests")
    def create_hr_request():
        """Record something the employee asked AskIvy to raise with HR.

        The manager is copied from the employee record at creation time rather than looked up
        when the request is read, so the row still shows who was actually copied even if the
        employee changes department later.
        """
        payload = request.get_json(silent=True) or {}
        employee = db.session.get(Employee, payload.get("employeeId") or "")
        if not employee:
            return jsonify({"error": "Unknown employee."}), 404

        question = str(payload.get("question", "")).strip()
        if not question:
            return jsonify({"error": "Field 'question' is required."}), 400

        hr_request = HRRequest(
            employee_id=employee.id,
            topic=str(payload.get("topic") or "General HR question")[:160],
            policy_id=payload.get("policyId"),
            question=question,
            situation=payload.get("situation"),
            manager_email=employee.manager_email,
            # Auto-assigned to the support/HR account rather than left unowned. With one
            # working HR persona in this demo, that's not a placeholder -- it's actually who
            # picks this up. A real multi-person HR team would need a real assignment step.
            assigned_to=SUPPORT_ACCOUNT_ID,
        )
        db.session.add(hr_request)
        db.session.commit()
        return jsonify(hr_request.to_dict()), 201

    @app.get("/api/admin/hr-requests")
    def admin_hr_requests():
        """Every raised request, for the support view. Same admin gate as the chat log."""
        requester_id = request.args.get("requesterId")
        requester = db.session.get(Employee, requester_id) if requester_id else None
        if not requester or not requester.is_admin:
            return jsonify({"error": "Admin access required."}), 403

        rows = HRRequest.query.order_by(HRRequest.created_at.desc()).all()
        return jsonify([row.to_dict() for row in rows])

    @app.patch("/api/admin/hr-requests/<int:request_id>")
    def admin_update_hr_request_status(request_id):
        """3.2.5 -- the other half of 3.2.2: without this, HRRequest.status was written once
        at creation and never touched again, so "checking progress" always showed Open."""
        _, error = _require_admin()
        if error:
            return error

        hr_request = db.session.get(HRRequest, request_id)
        if not hr_request:
            return jsonify({"error": "Unknown request."}), 404

        payload = request.get_json(silent=True) or {}
        status = payload.get("status")
        if status not in HR_REQUEST_STATUSES:
            return jsonify({"error": f"status must be one of {HR_REQUEST_STATUSES}."}), 400

        hr_request.status = status
        db.session.commit()
        return jsonify(hr_request.to_dict())

    @app.post("/api/chat-messages/<int:message_id>/feedback")
    def rate_chat_message(message_id):
        """Thumbs up/down on one bot reply. No admin gate -- any employee rates their own
        conversation, and there are no passwords anywhere in this app to check ownership
        against anyway."""
        payload = request.get_json(silent=True) or {}
        feedback = payload.get("feedback")
        if feedback not in ("up", "down", None):
            return jsonify({"error": "feedback must be 'up', 'down', or null to clear it."}), 400

        message = db.session.get(ChatMessage, message_id)
        if not message:
            return jsonify({"error": "Unknown message."}), 404

        message.feedback = feedback
        db.session.commit()
        return jsonify(message.to_dict())

    @app.get("/api/admin/analytics")
    def admin_analytics():
        """Aggregated usage signal for the Support tab -- most-asked topics, how often the
        bot couldn't answer, and the feedback split. Nothing here is new data; it's all
        already sitting in chat_messages and hr_requests, just never summarised anywhere.
        """
        _, error = _require_admin()
        if error:
            return error

        total = ChatMessage.query.count()
        unanswered = ChatMessage.query.filter_by(unanswered=True).count()

        source_counts = {}
        for (source,) in db.session.query(ChatMessage.policy_used).filter(
            ChatMessage.policy_used.isnot(None), ChatMessage.policy_used != ""
        ):
            # policy_used can be "Title A | Title B" (top-2 citation) -- count each title
            # separately, since "most-asked topics" means per-policy, not per-combination.
            for title in source.split(" | "):
                source_counts[title] = source_counts.get(title, 0) + 1
        top_topics = sorted(source_counts.items(), key=lambda item: item[1], reverse=True)[:10]

        hr_topic_counts = {}
        for (topic,) in db.session.query(HRRequest.topic):
            hr_topic_counts[topic] = hr_topic_counts.get(topic, 0) + 1
        hr_topics = sorted(hr_topic_counts.items(), key=lambda item: item[1], reverse=True)

        feedback_up = ChatMessage.query.filter_by(feedback="up").count()
        feedback_down = ChatMessage.query.filter_by(feedback="down").count()

        return jsonify({
            "totalMessages": total,
            "unansweredCount": unanswered,
            "unansweredRate": round(unanswered / total, 3) if total else 0,
            "topTopics": [{"topic": t, "count": c} for t, c in top_topics],
            "hrRequestsByTopic": [{"topic": t, "count": c} for t, c in hr_topics],
            "feedback": {"up": feedback_up, "down": feedback_down, "rated": feedback_up + feedback_down},
            "openHrRequests": HRRequest.query.filter_by(status="Open").count(),
        })

    @app.get("/api/admin/policies")
    def admin_list_policies():
        """Policies for the admin editor, plus which source is actually live.

        Deliberately a different shape from the public GET /api/policies (which stays a
        bare array so existing callers don't break) -- the editor needs to know whether it
        would be editing the source currently being read from POLICY_SOURCE=database
        (the default) or a database nobody's reading because POLICY_SOURCE=json is set for
        a rollback. Editing is still allowed either way; the banner just stops it being a
        silent surprise.
        """
        _, error = _require_admin()
        if error:
            return error
        rows = Policy.query.order_by(Policy.sort_order, Policy.id).all()
        return jsonify({"source": active_source(), "policies": [row.to_dict() for row in rows]})

    def _policy_payload_errors(payload):
        for field in ("title", "category", "summary"):
            if not str(payload.get(field, "")).strip():
                return f"Field '{field}' is required."
        rules = payload.get("rules", [])
        if not isinstance(rules, list) or not all(isinstance(r, str) for r in rules):
            return "Field 'rules' must be a list of strings."
        return None

    @app.post("/api/admin/policies")
    def admin_create_policy():
        """New policy (or FAQ entry -- same table, same retrieval, same admin screen; see
        userstories.md on why 3.4.3 doesn't get a second content store of its own)."""
        _, error = _require_admin()
        if error:
            return error

        payload = request.get_json(silent=True) or {}
        policy_id = str(payload.get("id", "")).strip().upper()
        if not policy_id:
            return jsonify({"error": "Field 'id' is required, e.g. 'FAQ-01'."}), 400
        if db.session.get(Policy, policy_id):
            return jsonify({"error": f"Policy '{policy_id}' already exists."}), 409

        bad_field = _policy_payload_errors(payload)
        if bad_field:
            return jsonify({"error": bad_field}), 400

        max_order = db.session.query(db.func.max(Policy.sort_order)).scalar() or 0
        policy = Policy(
            id=policy_id,
            title=payload["title"].strip(),
            category=payload["category"].strip(),
            summary=payload["summary"].strip(),
            rules=json.dumps(payload.get("rules", [])),
            sort_order=max_order + 1,
        )
        db.session.add(policy)
        db.session.commit()
        return jsonify(policy.to_dict()), 201

    @app.put("/api/admin/policies/<policy_id>")
    def admin_update_policy(policy_id):
        """Full replace of one policy's editable fields. Saving through this route is what
        invalidates the cached generated opener (policy_explainer.py keys its cache on
        Policy.updated_at, which the ORM bumps on this commit automatically)."""
        _, error = _require_admin()
        if error:
            return error

        policy = db.session.get(Policy, policy_id)
        if not policy:
            return jsonify({"error": "Unknown policy."}), 404

        payload = request.get_json(silent=True) or {}
        bad_field = _policy_payload_errors(payload)
        if bad_field:
            return jsonify({"error": bad_field}), 400

        policy.title = payload["title"].strip()
        policy.category = payload["category"].strip()
        policy.summary = payload["summary"].strip()
        policy.rules = json.dumps(payload.get("rules", []))
        db.session.commit()
        return jsonify(policy.to_dict())

    @app.delete("/api/admin/policies/<policy_id>")
    def admin_delete_policy(policy_id):
        _, error = _require_admin()
        if error:
            return error

        policy = db.session.get(Policy, policy_id)
        if not policy:
            return jsonify({"error": "Unknown policy."}), 404

        db.session.delete(policy)
        db.session.commit()
        return "", 204

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
        # Most branches never set this key at all, so it would otherwise serialise as
        # JSON null rather than false -- normalise it once here so both the DB row and
        # the response the widget reads always carry an explicit boolean.
        answer["unanswered"] = bool(answer.get("unanswered", False))

        chat = ChatMessage(
            employee_id=employee.id,
            question=question,
            response=answer["text"],
            policy_used=answer.get("source"),
            unanswered=answer["unanswered"],
        )
        db.session.add(chat)
        db.session.commit()

        # The id only exists after commit, and the widget needs it to attach feedback
        # (thumbs up/down) to the right row.
        answer["chatMessageId"] = chat.id
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

    for column, ddl in (
        ("manager_name", "ALTER TABLE employees ADD COLUMN manager_name VARCHAR(120)"),
        ("manager_email", "ALTER TABLE employees ADD COLUMN manager_email VARCHAR(160)"),
    ):
        if column not in columns:
            # Nullable with no default, so this is valid on both dialects and needs no
            # backfill statement -- ensure_managers() populates it afterwards via the ORM.
            db.session.execute(db.text(ddl))
            db.session.commit()

    if "policies" in inspector.get_table_names():
        policy_columns = {c["name"] for c in inspector.get_columns("policies")}
        if "sort_order" not in policy_columns:
            db.session.execute(db.text(
                "ALTER TABLE policies ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0"
            ))
            db.session.commit()

    if "chat_messages" in inspector.get_table_names():
        chat_columns = {c["name"] for c in inspector.get_columns("chat_messages")}
        if "unanswered" not in chat_columns:
            db.session.execute(db.text(
                "ALTER TABLE chat_messages ADD COLUMN unanswered BOOLEAN NOT NULL DEFAULT FALSE"
            ))
            db.session.commit()
        if "feedback" not in chat_columns:
            db.session.execute(db.text(
                "ALTER TABLE chat_messages ADD COLUMN feedback VARCHAR(10)"
            ))
            db.session.commit()

    if "hr_requests" in inspector.get_table_names():
        hr_columns = {c["name"] for c in inspector.get_columns("hr_requests")}
        if "assigned_to" not in hr_columns:
            db.session.execute(db.text(
                "ALTER TABLE hr_requests ADD COLUMN assigned_to VARCHAR(32)"
            ))
            db.session.commit()


def ensure_admin_accounts():
    """Make sure the support account exists and ADMIN_EMPLOYEE_IDS is applied.

    Runs AFTER seed_demo_data(), because seeding bails out the moment any employee exists
    and this function creates one.
    """
    if Employee.query.first() and not db.session.get(Employee, SUPPORT_ACCOUNT_ID):
        db.session.add(support_account())
        db.session.commit()

    for employee in Employee.query.all():
        should_be_admin = employee.id in ADMIN_EMPLOYEE_IDS
        if employee.is_admin != should_be_admin:
            employee.is_admin = should_be_admin
    db.session.commit()


# Department heads, used to fill in each employee's manager. Picked as the longest-serving
# person in each department so the demo data stays internally consistent.
DEPARTMENT_MANAGERS = {
    "Engineering": "david",
    "Product": "ethan",
    "Design": "meiling",
    "Operations": "weijian",
    "Sales": "rachel",
    "Human Resources": "nadia",
}


def ensure_managers():
    """Fill in manager_name / manager_email from DEPARTMENT_MANAGERS.

    Runs after seeding, like ensure_admin_accounts(), because it reads employee rows.

    A department head gets no manager rather than being made their own -- the offer to "cc
    your manager" then correctly degrades to an HR-only handoff instead of copying someone
    to their own request.
    """
    employees = {employee.id: employee for employee in Employee.query.all()}

    for employee in employees.values():
        manager_id = DEPARTMENT_MANAGERS.get(employee.department)
        manager = employees.get(manager_id) if manager_id else None

        if not manager or manager.id == employee.id:
            employee.manager_name = None
            employee.manager_email = None
            continue

        employee.manager_name = manager.name
        employee.manager_email = f"{manager.id}@lumenvale.com"

    db.session.commit()


def seed_policies():
    """Copy hr_policies.json into the policies table, once, on an empty table only.

    THIS IS THE CUTOVER the earlier docstring here warned about. Policies are now edited
    through the admin UI (`/api/admin/policies`), so the database is independently
    authoritative from this point on -- re-syncing from the file on every boot would silently
    discard every admin edit the next time the server restarts.

    Consequence for the file: `hr_policies.json` stops being a live source after the first
    boot on a given database. It still matters for two things -- seeding a brand-new database,
    and as what `POLICY_SOURCE=json` reads if the database is ever rolled back to -- but adding
    or editing a policy going forward means using the admin UI, not hand-editing this file.

    Consequence for tests/policy_parity.py: it was written as the cutover gate, proving the
    mirror matched before this switch happened. Ongoing drift between the file and the
    database is now expected and correct, not a bug -- see that file's own docstring.

    sort_order preserves the file's ordering for the initial seed. score_policies() sorts by
    score and Python's sort is stable, so equal-scoring policies fall back to input order --
    meaning the row order here decided what a low-signal question got told, once, at seed time.
    New policies added via the admin UI append after everything already seeded.
    """
    if Policy.query.first():
        return

    for index, entry in enumerate(load_policies_from_file()):
        policy = Policy(id=entry["id"])
        policy.title = entry["title"]
        policy.category = entry["category"]
        policy.summary = entry["summary"]
        policy.rules = json.dumps(entry.get("rules", []))
        policy.sort_order = index
        db.session.add(policy)

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
