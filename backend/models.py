import json
from datetime import datetime, date, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utcnow():
    # Replaces the deprecated datetime.utcnow(); stays naive to match existing DateTime columns.
    return datetime.now(timezone.utc).replace(tzinfo=None)

class Employee(db.Model):
    __tablename__ = "employees"

    id = db.Column(db.String(32), primary_key=True)
    initials = db.Column(db.String(8), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(120), nullable=False)
    department = db.Column(db.String(80), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    tenure_years = db.Column(db.Integer, nullable=False, default=0)
    marital_status = db.Column(db.String(50), nullable=False)
    recent_event = db.Column(db.String(255), nullable=True)
    annual_leave_entitlement = db.Column(db.Integer, nullable=False, default=14)
    annual_leave_taken = db.Column(db.Integer, nullable=False, default=0)
    probation = db.Column(db.Boolean, nullable=False, default=False)
    salary_band = db.Column(db.String(30), nullable=False)
    # Gates the support/admin views. Demo-grade: there are no passwords anywhere in this
    # app, so this identifies a role, it does not authenticate one. See ensure_schema()
    # in app.py for how existing databases pick the column up.
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    # Who gets copied when AskIvy raises something with HR on this employee's behalf. Both
    # nullable: a department head has no manager in this data set, and the bot must then
    # offer an HR-only handoff rather than naming someone who doesn't exist.
    manager_name = db.Column(db.String(120), nullable=True)
    manager_email = db.Column(db.String(160), nullable=True)

    leave_requests = db.relationship("LeaveRequest", back_populates="employee", cascade="all, delete-orphan")
    chat_messages = db.relationship("ChatMessage", back_populates="employee", cascade="all, delete-orphan")
    hr_requests = db.relationship(
        "HRRequest", back_populates="employee", cascade="all, delete-orphan",
        foreign_keys="HRRequest.employee_id",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "initials": self.initials,
            "name": self.name,
            "role": self.role,
            "department": self.department,
            "startDate": self.start_date.isoformat(),
            "tenureYears": self.tenure_years,
            "maritalStatus": self.marital_status,
            "recentEvent": self.recent_event,
            "annualLeaveEntitlement": self.annual_leave_entitlement,
            "annualLeaveTaken": self.annual_leave_taken,
            "probation": self.probation,
            "salaryBand": self.salary_band,
            "isAdmin": self.is_admin,
            "managerName": self.manager_name,
            "managerEmail": self.manager_email,
        }

class LeaveRequest(db.Model):
    __tablename__ = "leave_requests"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(32), db.ForeignKey("employees.id"), nullable=False)
    leave_type = db.Column(db.String(50), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    number_of_days = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="Pending")
    submitted_via = db.Column(db.String(30), nullable=False, default="Portal")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    employee = db.relationship("Employee", back_populates="leave_requests")

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.leave_type,
            "from": self.start_date.isoformat(),
            "to": self.end_date.isoformat(),
            "days": self.number_of_days,
            "reason": self.reason,
            "status": self.status,
            "submittedVia": self.submitted_via,
            "createdAt": self.created_at.isoformat(),
        }

class Policy(db.Model):
    """Database-backed HR policies.

    Mirrors backend/data/hr_policies.json during the migration -- seeded from it, validated
    against it, and only later made the live source. Nothing reads this yet; see
    services/policy_repository_db.py.

    `rules` is a JSON array stored as text rather than a native array or JSONB column: the
    same DDL then works on both SQLite locally and Postgres on Render, with no dialect
    branching for the sake of a list of strings.
    """

    __tablename__ = "policies"

    id = db.Column(db.String(32), primary_key=True)          # e.g. "LEAVE-01"
    title = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    rules = db.Column(db.Text, nullable=False, default="[]")
    # Position in the original hr_policies.json. Not cosmetic: score_policies() sorts by
    # score and Python's sort is stable, so equal-scoring policies fall back to input order.
    # Ordering by id instead would silently change which policies a low-signal query returns
    # -- caught by tests/policy_parity.py, which is the whole reason it exists.
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    def to_dict(self):
        """Shaped exactly like an entry in hr_policies.json, so callers can't tell them apart."""
        try:
            rules = json.loads(self.rules)
        except (TypeError, ValueError):
            rules = []
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "summary": self.summary,
            "rules": rules,
        }


class PolicyExplanation(db.Model):
    """Cache of generated policy prose, keyed by policy and situation.

    The generated layer of a policy answer depends only on the policy's rules and which
    situation applies -- never on who is asking. So every employee in probation asking about
    hybrid working can share one generated paragraph, and the space is (10 policies x a few
    situations), which converges after a handful of questions.

    WHAT MUST NEVER BE CACHED: the tailored line. It carries live figures -- LEAVE-01 quotes
    the employee's remaining balance -- so it is recomputed on every request and appended
    after the cached prose. Caching it would show one employee another's leave balance.

    policy_updated_at is the invalidation key. It holds the Policy.updated_at the prose was
    generated from; when a policy is edited in the admin editor its timestamp moves and the
    stale entry is ignored. Without this, editing a policy would leave the old explanation in
    front of users indefinitely while the verbatim rules underneath it changed.
    """

    __tablename__ = "policy_explanations"

    policy_id = db.Column(db.String(32), db.ForeignKey("policies.id"), primary_key=True)
    situation_key = db.Column(db.String(48), primary_key=True)
    text = db.Column(db.Text, nullable=False)
    policy_updated_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class HRRequest(db.Model):
    """Something the employee asked AskIvy to raise with HR.

    Exists because the bot now offers to raise things. An offer that leads nowhere is worse
    than no offer, so accepting one writes a row that support can actually see in the admin
    view -- the same reasoning that put chat history there.
    """

    __tablename__ = "hr_requests"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(32), db.ForeignKey("employees.id"), nullable=False)
    topic = db.Column(db.String(160), nullable=False)          # human-readable, e.g. "Work From Home / Hybrid"
    policy_id = db.Column(db.String(32), nullable=True)        # not a FK: the policy may be deleted later
    question = db.Column(db.Text, nullable=False)              # what the employee actually asked
    situation = db.Column(db.String(48), nullable=True)        # resolved situation, so HR sees what the bot concluded
    # Copied at creation, not looked up later: if the employee changes manager afterwards,
    # the record should still show who was actually copied at the time.
    manager_email = db.Column(db.String(160), nullable=True)
    # Who on the support/HR side owns this. Set at creation (app.py defaults it to the
    # support account) rather than left to be claimed later -- with one working HR/support
    # persona in this demo, "assigned" would otherwise be a UI promise nothing backs.
    assigned_to = db.Column(db.String(32), db.ForeignKey("employees.id"), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="Open")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    employee = db.relationship("Employee", back_populates="hr_requests", foreign_keys=[employee_id])
    assignee = db.relationship("Employee", foreign_keys=[assigned_to])

    def to_dict(self):
        return {
            "id": self.id,
            "employeeId": self.employee_id,
            "employeeName": self.employee.name if self.employee else None,
            "topic": self.topic,
            "policyId": self.policy_id,
            "question": self.question,
            "situation": self.situation,
            "managerEmail": self.manager_email,
            "assignedTo": self.assigned_to,
            "assignedToName": self.assignee.name if self.assignee else None,
            "status": self.status,
            "createdAt": self.created_at.isoformat(),
        }


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(32), db.ForeignKey("employees.id"), nullable=False)
    question = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    policy_used = db.Column(db.String(255), nullable=True)
    # True only at genuine "couldn't answer" branches -- HRMS/career-library unreachable,
    # no career path on file for the requested pair. NOT true for a fuzzy policy match or a
    # chitchat deflection; both of those are complete, honest answers, not gaps. Set by the
    # engine that produced the reply, not inferred here from the response text.
    unanswered = db.Column(db.Boolean, nullable=False, default=False)
    # "up" / "down" / NULL (no feedback given). A free column rather than a linked table --
    # one reaction per message is all the story asks for, and it keeps the read side a plain
    # column instead of a join.
    feedback = db.Column(db.String(10), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    employee = db.relationship("Employee", back_populates="chat_messages")

    def to_dict(self):
        return {
            "id": self.id,
            "question": self.question,
            "response": self.response,
            "policyUsed": self.policy_used,
            "unanswered": self.unanswered,
            "feedback": self.feedback,
            "createdAt": self.created_at.isoformat(),
        }
