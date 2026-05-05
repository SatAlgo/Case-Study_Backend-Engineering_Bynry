"""Supplier models — suppliers, company-supplier and product-supplier relationships."""

from datetime import datetime, timezone
from app import db


class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    contact_email = db.Column(db.String(255), nullable=True)
    contact_phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Supplier {self.name}>"


class CompanySupplier(db.Model):
    """Many-to-many: which companies work with which suppliers."""

    __tablename__ = "company_suppliers"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(
        db.Integer, db.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    supplier_id = db.Column(
        db.Integer, db.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint("company_id", "supplier_id", name="uq_company_supplier"),
    )


class ProductSupplier(db.Model):
    """
    Many-to-many: which suppliers provide which products.
    Includes cost, lead time, and preferred supplier flag.
    """

    __tablename__ = "product_suppliers"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    supplier_id = db.Column(
        db.Integer, db.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False
    )
    unit_cost = db.Column(db.Numeric(12, 2), nullable=True)
    lead_time_days = db.Column(db.Integer, nullable=True)
    is_preferred = db.Column(db.Boolean, default=False)

    # Relationships
    product = db.relationship("Product", backref="suppliers")
    supplier = db.relationship("Supplier", backref="products_supplied")

    __table_args__ = (
        db.UniqueConstraint("product_id", "supplier_id", name="uq_product_supplier"),
    )

    def __repr__(self):
        return f"<ProductSupplier Product:{self.product_id} Supplier:{self.supplier_id}>"
