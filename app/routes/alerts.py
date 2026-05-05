"""
Part 3: API Implementation — Low-Stock Alerts Endpoint

Business Rules:
  - Low stock threshold varies by product (stored in products.low_stock_threshold)
  - Only alert for products with recent sales activity (last 30 days)
  - Handles multiple warehouses per company
  - Includes supplier information for reordering
  - Estimates days until stockout based on average daily sales rate

Assumptions:
  - "Recent sales activity" = at least one 'sale' type log entry in last 30 days
  - days_until_stockout = current_stock / avg_daily_sales_rate
  - Preferred supplier (is_preferred=True) is returned first; fallback to any linked supplier
  - Results paginated; sorted by current_stock ASC (most critical first)
"""

import math
import logging
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func

from app import db
from app.models import (
    Company, Product, Warehouse, Inventory, InventoryLog,
    ProductSupplier, Supplier,
)

logger = logging.getLogger(__name__)

alerts_bp = Blueprint("alerts", __name__)

# Configurable: how far back to look for "recent" sales activity
RECENT_ACTIVITY_DAYS = 30


@alerts_bp.route("/companies/<int:company_id>/alerts/low-stock", methods=["GET"])
@login_required
def get_low_stock_alerts(company_id):
    """
    Returns low-stock alerts for all warehouses belonging to a company.
    Only includes products with recent sales activity.

    Path Parameters:
        company_id (int): The company to fetch alerts for

    Query Parameters:
        page (int):     Page number (default: 1)
        per_page (int): Results per page (default: 20, max: 100)

    Returns:
        200: List of low-stock alerts with supplier info
        403: User not authorized for this company
        404: Company not found
    """

    # ------------------------------------------------------------------
    # 1. Authorization: user must belong to the requested company
    # ------------------------------------------------------------------
    if current_user.company_id != company_id:
        return jsonify({"error": "Unauthorized — you do not belong to this company"}), 403

    # ------------------------------------------------------------------
    # 2. Validate company exists
    # ------------------------------------------------------------------
    company = Company.query.get(company_id)
    if not company:
        return jsonify({"error": "Company not found"}), 404

    # ------------------------------------------------------------------
    # 3. Parse pagination parameters
    # ------------------------------------------------------------------
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(max(per_page, 1), 100)  # Clamp between 1 and 100

    if page < 1:
        page = 1

    # ------------------------------------------------------------------
    # 4. Define time window for "recent activity"
    # ------------------------------------------------------------------
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=RECENT_ACTIVITY_DAYS)

    # ------------------------------------------------------------------
    # 5. Subquery: product IDs with at least one sale in the last 30 days
    # ------------------------------------------------------------------
    recent_sales_subquery = (
        db.session.query(InventoryLog.product_id)
        .filter(
            InventoryLog.change_type == "sale",
            InventoryLog.created_at >= cutoff_date,
        )
        .distinct()
        .subquery()
    )

    # ------------------------------------------------------------------
    # 6. Main query: inventory below threshold + recent sales + active only
    # ------------------------------------------------------------------
    low_stock_query = (
        db.session.query(Inventory, Product, Warehouse)
        .join(Product, Inventory.product_id == Product.id)
        .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
        .filter(
            Warehouse.company_id == company_id,
            Warehouse.is_active.is_(True),
            Product.is_active.is_(True),
            Inventory.quantity <= Product.low_stock_threshold,
            Product.id.in_(recent_sales_subquery),
        )
        .order_by(Inventory.quantity.asc())  # Most critical (lowest stock) first
    )

    # ------------------------------------------------------------------
    # 7. Get total count before pagination
    # ------------------------------------------------------------------
    total_alerts = low_stock_query.count()

    # ------------------------------------------------------------------
    # 8. Apply pagination
    # ------------------------------------------------------------------
    results = (
        low_stock_query
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    # ------------------------------------------------------------------
    # 9. Build response: enrich each alert with sales rate & supplier info
    # ------------------------------------------------------------------
    alerts = []

    for inventory, product, warehouse in results:
        # Calculate average daily sales rate (last 30 days) for this product+warehouse
        total_sold = (
            db.session.query(
                func.coalesce(func.sum(func.abs(InventoryLog.quantity_change)), 0)
            )
            .filter(
                InventoryLog.product_id == product.id,
                InventoryLog.warehouse_id == warehouse.id,
                InventoryLog.change_type == "sale",
                InventoryLog.created_at >= cutoff_date,
            )
            .scalar()
        )

        daily_sales_rate = total_sold / RECENT_ACTIVITY_DAYS if total_sold > 0 else 0

        # Estimate days until stockout
        if daily_sales_rate > 0:
            days_until_stockout = math.floor(inventory.quantity / daily_sales_rate)
        else:
            days_until_stockout = None  # Can't estimate without sales data

        # Get preferred supplier (or fallback to any linked supplier)
        supplier_link = (
            ProductSupplier.query
            .filter_by(product_id=product.id)
            .order_by(ProductSupplier.is_preferred.desc())  # Preferred first
            .first()
        )

        supplier_info = None
        if supplier_link:
            supplier = Supplier.query.get(supplier_link.supplier_id)
            if supplier:
                supplier_info = {
                    "id": supplier.id,
                    "name": supplier.name,
                    "contact_email": supplier.contact_email,
                    "lead_time_days": supplier_link.lead_time_days,
                }

        alerts.append({
            "product_id": product.id,
            "product_name": product.name,
            "sku": product.sku,
            "warehouse_id": warehouse.id,
            "warehouse_name": warehouse.name,
            "current_stock": inventory.quantity,
            "threshold": product.low_stock_threshold,
            "days_until_stockout": days_until_stockout,
            "daily_sales_rate": round(daily_sales_rate, 2),
            "supplier": supplier_info,
        })

    # ------------------------------------------------------------------
    # 10. Return paginated response
    # ------------------------------------------------------------------
    total_pages = math.ceil(total_alerts / per_page) if total_alerts > 0 else 0

    return jsonify({
        "alerts": alerts,
        "total_alerts": total_alerts,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
    }), 200
