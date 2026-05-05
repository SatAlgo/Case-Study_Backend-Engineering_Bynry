"""Warehouse model — physical storage locations belonging to companies."""

from datetime import datetime, timezone
from app import db


class Warehouse(db.Model):
    __tablename__ = "warehouses"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(
        db.Integer, db.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    name = db.Column(db.String(255), nullable=False)
    location = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    inventory_items = db.relationship("Inventory", backref="warehouse", lazy="dynamic")

    # Indexes
    __table_args__ = (
        db.Index("idx_warehouses_company", "company_id"),
    )

    def __repr__(self):
        return f"<Warehouse {self.name} (Company: {self.company_id})>"
