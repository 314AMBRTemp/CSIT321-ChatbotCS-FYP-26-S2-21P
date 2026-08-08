from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

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

    leave_requests = db.relationship("LeaveRequest", back_populates="employee", cascade="all, delete-orphan")
    chat_messages = db.relationship("ChatMessage", back_populates="employee", cascade="all, delete-orphan")

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
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

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

class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(32), db.ForeignKey("employees.id"), nullable=False)
    question = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    policy_used = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    employee = db.relationship("Employee", back_populates="chat_messages")

    def to_dict(self):
        return {
            "id": self.id,
            "question": self.question,
            "response": self.response,
            "policyUsed": self.policy_used,
            "createdAt": self.created_at.isoformat(),
        }
