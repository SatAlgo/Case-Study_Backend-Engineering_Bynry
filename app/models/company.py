"""Company model — represents a tenant in the multi-tenant system."""

from datetime import datetime, timezone
from app import db


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    warehouses = db.relationship("Warehouse", backref="company", lazy="dynamic")
    products = db.relationship("Product", backref="company", lazy="dynamic")
    users = db.relationship("User", backref="company", lazy="dynamic")

    def __repr__(self):
        return f"<Company {self.name}>"
