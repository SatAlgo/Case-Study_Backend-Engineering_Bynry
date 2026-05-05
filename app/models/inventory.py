"""Inventory models — current stock levels and change audit trail."""

from datetime import datetime, timezone
from app import db


class Inventory(db.Model):
    """
    Current stock level for a product in a specific warehouse.
    The UNIQUE constraint on (product_id, warehouse_id) ensures one record
    per product-warehouse combination.
    """

    __tablename__ = "inventory"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    warehouse_id = db.Column(
        db.Integer, db.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False
    )
    quantity = db.Column(db.Integer, nullable=False, default=0)
    last_updated = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.UniqueConstraint("product_id", "warehouse_id", name="uq_product_warehouse"),
        db.Index("idx_inventory_product", "product_id"),
        db.Index("idx_inventory_warehouse", "warehouse_id"),
        db.CheckConstraint("quantity >= 0", name="ck_inventory_qty_non_negative"),
    )

    def __repr__(self):
        return f"<Inventory Product:{self.product_id} Warehouse:{self.warehouse_id} Qty:{self.quantity}>"


class InventoryLog(db.Model):
    """
    Append-only audit trail for every inventory change.
    Records who changed what, when, why, and the resulting quantity.

    change_type values: 'sale', 'restock', 'transfer', 'adjustment', 'initial'
    quantity_change: positive for additions, negative for removals
    """

    __tablename__ = "inventory_logs"

    id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(
        db.Integer, db.ForeignKey("inventory.id"), nullable=False
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id"), nullable=False
    )
    warehouse_id = db.Column(
        db.Integer, db.ForeignKey("warehouses.id"), nullable=False
    )
    change_type = db.Column(db.String(50), nullable=False)
    quantity_change = db.Column(db.Integer, nullable=False)
    quantity_after = db.Column(db.Integer, nullable=False)
    reference_id = db.Column(db.String(100), nullable=True)  # Order ID, PO number, etc.
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, nullable=True)  # User ID
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.Index("idx_inv_logs_product", "product_id"),
        db.Index("idx_inv_logs_created", "created_at"),
        db.Index("idx_inv_logs_change_type", "change_type"),
    )

    def __repr__(self):
        return (
            f"<InventoryLog {self.change_type}: {self.quantity_change:+d} "
            f"Product:{self.product_id} Warehouse:{self.warehouse_id}>"
        )
