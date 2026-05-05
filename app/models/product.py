"""Product models — catalog items and bundle relationships."""

from datetime import datetime, timezone
from app import db


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(
        db.Integer, db.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    name = db.Column(db.String(255), nullable=False)
    sku = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(12, 2), nullable=False)
    product_type = db.Column(db.String(50), default="standard")  # standard, bundle, perishable
    low_stock_threshold = db.Column(db.Integer, default=10)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    inventory_items = db.relationship("Inventory", backref="product", lazy="dynamic")
    inventory_logs = db.relationship("InventoryLog", backref="product", lazy="dynamic")

    # Indexes
    __table_args__ = (
        db.Index("idx_products_company", "company_id"),
        db.Index("idx_products_sku", "sku"),
        db.CheckConstraint("price >= 0", name="ck_products_price_positive"),
    )

    def __repr__(self):
        return f"<Product {self.sku}: {self.name}>"


class ProductBundle(db.Model):
    """
    Self-referencing many-to-many: a 'bundle' product contains other products.
    Example: 'Starter Kit' bundle contains 2x Widget A + 1x Widget B.
    """

    __tablename__ = "product_bundles"

    id = db.Column(db.Integer, primary_key=True)
    bundle_id = db.Column(
        db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    component_id = db.Column(
        db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    quantity = db.Column(db.Integer, nullable=False, default=1)

    # Relationships
    bundle = db.relationship("Product", foreign_keys=[bundle_id], backref="bundle_components")
    component = db.relationship("Product", foreign_keys=[component_id], backref="part_of_bundles")

    __table_args__ = (
        db.UniqueConstraint("bundle_id", "component_id", name="uq_bundle_component"),
        db.CheckConstraint("bundle_id != component_id", name="ck_no_self_bundle"),
        db.CheckConstraint("quantity > 0", name="ck_bundle_qty_positive"),
    )

    def __repr__(self):
        return f"<Bundle {self.bundle_id} contains {self.quantity}x Product {self.component_id}>"
