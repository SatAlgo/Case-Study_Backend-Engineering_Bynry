"""
Part 1: Code Review & Debugging — Fixed Product Creation Endpoint

Original Issues Fixed:
  1. No input validation           → Comprehensive field & type checks
  2. No SKU uniqueness check       → Pre-check before insertion
  3. Non-atomic transaction        → flush() + single commit()
  4. No error handling             → try/except with rollback
  5. No authentication/auth        → @login_required + ownership check
  6. Wrong HTTP status codes       → 201 for success, proper 4xx/5xx
  7. Float precision for price     → Decimal type
"""

from decimal import Decimal, InvalidOperation
import logging

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Product, Inventory, InventoryLog, Warehouse

logger = logging.getLogger(__name__)

products_bp = Blueprint("products", __name__)


@products_bp.route("/products", methods=["POST"])
@login_required
def create_product():
    """
    Create a new product and initialize its inventory in a warehouse.

    Request Body (JSON):
        name (str):              Product name (required)
        sku (str):               Unique SKU identifier (required)
        price (number):          Product price, must be positive (required)
        warehouse_id (int):      Target warehouse ID (required)
        initial_quantity (int):  Starting inventory count, >= 0 (required)
        description (str):       Product description (optional)
        product_type (str):      'standard', 'bundle', 'perishable' (optional, default: 'standard')
        low_stock_threshold (int): Alert threshold (optional, default: 10)

    Returns:
        201: Product created successfully
        400: Validation error
        404: Warehouse not found
        409: SKU already exists
        500: Internal server error
    """
    data = request.get_json()

    # ------------------------------------------------------------------
    # 1. Validate request body exists
    # ------------------------------------------------------------------
    if not data:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    # ------------------------------------------------------------------
    # 2. Check required fields
    # ------------------------------------------------------------------
    required_fields = ["name", "sku", "price", "warehouse_id", "initial_quantity"]
    missing = [f for f in required_fields if f not in data or data[f] is None]
    if missing:
        return jsonify({
            "error": "Missing required fields",
            "missing_fields": missing,
        }), 400

    # ------------------------------------------------------------------
    # 3. Validate data types and business rules
    # ------------------------------------------------------------------

    # Name: non-empty string
    name = str(data["name"]).strip()
    if not name:
        return jsonify({"error": "Product name cannot be empty"}), 400

    # SKU: non-empty string, normalized to uppercase
    sku = str(data["sku"]).strip().upper()
    if not sku:
        return jsonify({"error": "SKU cannot be empty"}), 400

    # Price: must be a positive decimal
    try:
        price = Decimal(str(data["price"]))
        if price <= 0:
            return jsonify({"error": "Price must be a positive number"}), 400
    except (InvalidOperation, ValueError, TypeError):
        return jsonify({"error": "Invalid price format — must be a number"}), 400

    # Quantity: must be a non-negative integer
    try:
        initial_quantity = int(data["initial_quantity"])
        if initial_quantity < 0:
            return jsonify({"error": "Initial quantity cannot be negative"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Initial quantity must be an integer"}), 400

    # Warehouse ID: must be an integer
    try:
        warehouse_id = int(data["warehouse_id"])
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid warehouse_id"}), 400

    # ------------------------------------------------------------------
    # 4. Verify warehouse exists AND belongs to the user's company
    # ------------------------------------------------------------------
    warehouse = Warehouse.query.get(warehouse_id)
    if not warehouse:
        return jsonify({"error": "Warehouse not found"}), 404
    if warehouse.company_id != current_user.company_id:
        return jsonify({"error": "Unauthorized — warehouse belongs to another company"}), 403

    # ------------------------------------------------------------------
    # 5. Check SKU uniqueness
    # ------------------------------------------------------------------
    existing_product = Product.query.filter_by(sku=sku).first()
    if existing_product:
        return jsonify({
            "error": f"A product with SKU '{sku}' already exists",
            "existing_product_id": existing_product.id,
        }), 409

    # ------------------------------------------------------------------
    # 6. Create product + inventory in a single atomic transaction
    # ------------------------------------------------------------------
    try:
        # Create product
        product = Product(
            name=name,
            sku=sku,
            price=price,
            company_id=current_user.company_id,
            description=data.get("description", ""),
            product_type=data.get("product_type", "standard"),
            low_stock_threshold=data.get("low_stock_threshold", 10),
        )
        db.session.add(product)
        db.session.flush()  # Get product.id WITHOUT committing

        # Create inventory record
        inventory = Inventory(
            product_id=product.id,
            warehouse_id=warehouse_id,
            quantity=initial_quantity,
        )
        db.session.add(inventory)
        db.session.flush()  # Get inventory.id for the log

        # Record the initial inventory in the audit log
        log_entry = InventoryLog(
            inventory_id=inventory.id,
            product_id=product.id,
            warehouse_id=warehouse_id,
            change_type="initial",
            quantity_change=initial_quantity,
            quantity_after=initial_quantity,
            notes="Initial stock on product creation",
            created_by=current_user.id,
        )
        db.session.add(log_entry)

        # Single commit — all three records succeed or all fail
        db.session.commit()

        logger.info(
            "Product created: id=%d, sku=%s, warehouse=%d, qty=%d, by user=%d",
            product.id, product.sku, warehouse_id, initial_quantity, current_user.id,
        )

        return jsonify({
            "message": "Product created successfully",
            "product_id": product.id,
            "sku": product.sku,
        }), 201

    except IntegrityError:
        db.session.rollback()
        logger.error("IntegrityError creating product SKU: %s", sku)
        return jsonify({"error": "Product could not be created — duplicate entry"}), 409

    except Exception as e:
        db.session.rollback()
        logger.exception("Unexpected error creating product: %s", str(e))
        return jsonify({"error": "Internal server error"}), 500
