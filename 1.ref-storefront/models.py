from extensions import db
from flask_login import UserMixin
from datetime import datetime

class Admin(UserMixin, db.Model):
    __tablename__ = "admins"

    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email         = db.Column(db.String,  unique=True, nullable=False)
    password_hash = db.Column(db.String,  nullable=False)
    name          = db.Column(db.String,  nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    last_login    = db.Column(db.DateTime, nullable=True)

    def get_id(self):
        return f"a-{self.id}"

    def to_dict(self):
        return {
            "id":         self.id,
            "email":      self.email,
            "name":       self.name,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None
        }


class Order(db.Model):
    __tablename__ = "orders"

    order_id           = db.Column(db.String,  primary_key=True)
    customer_email     = db.Column(db.String,  nullable=False)
    customer_name      = db.Column(db.String,  nullable=False)
    status             = db.Column(db.String,  nullable=False)
    estimated_delivery = db.Column(db.String,  nullable=False)
    courier            = db.Column(db.String,  nullable=False)
    delivery_address   = db.Column(db.String,  nullable=False)
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at         = db.Column(db.DateTime, default=datetime.utcnow,
                                   onupdate=datetime.utcnow)

    tickets = db.relationship("Ticket", backref="order", lazy=True)

    def to_dict(self):
        return {
            "order_id":           self.order_id,
            "customer_email":     self.customer_email,
            "customer_name":      self.customer_name,
            "status":             self.status,
            "estimated_delivery": self.estimated_delivery,
            "courier":            self.courier,
            "delivery_address":   self.delivery_address,
            "created_at":         self.created_at.isoformat(),
            "updated_at":         self.updated_at.isoformat(),
        }


class Ticket(db.Model):
    __tablename__ = "tickets"

    ticket_id      = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id       = db.Column(db.String,  db.ForeignKey("orders.order_id"), nullable=False)
    customer_email = db.Column(db.String,  nullable=False)
    issue_type     = db.Column(db.String,  nullable=False)
    description    = db.Column(db.String,  nullable=False)
    status         = db.Column(db.String,  default="open")
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow,
                                onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "ticket_id":      self.ticket_id,
            "order_id":       self.order_id,
            "customer_email": self.customer_email,
            "issue_type":     self.issue_type,
            "description":    self.description,
            "status":         self.status,
            "created_at":     self.created_at.isoformat(),
            "updated_at":     self.updated_at.isoformat(),
        }


class Customer(UserMixin, db.Model):
    __tablename__ = "customers"

    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email         = db.Column(db.String,  unique=True, nullable=False)
    password_hash = db.Column(db.String,  nullable=False)
    name          = db.Column(db.String,  nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    last_login    = db.Column(db.DateTime, nullable=True)

    orders = db.relationship(
        "Order", backref="customer", lazy=True,
        foreign_keys="Order.customer_email",
        primaryjoin="Customer.email == Order.customer_email"
    )

    def get_id(self):
        return f"c-{self.id}"

    def to_dict(self):
        return {
            "id":         self.id,
            "email":      self.email,
            "name":       self.name,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None
        }
