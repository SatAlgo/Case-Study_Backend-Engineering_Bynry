"""
Tests for the low-stock alerts endpoint (Part 3).
Validates filtering, pagination, edge cases, and supplier info enrichment.
"""

import pytest
from datetime import datetime, timedelta, timezone

from app import create_app, db
from app.config import TestConfig
from app.models import (
    Company, Warehouse, Product, Supplier, ProductSupplier,
    Inventory, InventoryLog, User,
)


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def setup_alerts_data(app):
    """Create a full test scenario for low-stock alerts."""
    with app.app_context():
        # Company
        company = Company(name="Test Corp", email="test@corp.com")
        db.session.add(company)
        db.session.flush()

        # User
        user = User(
            email="user@corp.com", password_hash="h", name="Tester",
            company_id=company.id,
        )
        db.session.add(user)

        # Warehouse
        wh = Warehouse(company_id=company.id, name="Main Warehouse")
        db.session.add(wh)
        db.session.flush()

        # Product: low stock (below threshold)
        low_product = Product(
            company_id=company.id, name="Widget A", sku="WID-001",
            price=9.99, low_stock_threshold=20,
        )
        db.session.add(low_product)
        db.session.flush()

        # Product: well stocked (above threshold)
        ok_product = Product(
            company_id=company.id, name="Widget B", sku="WID-002",
            price=14.99, low_stock_threshold=5,
        )
        db.session.add(ok_product)
        db.session.flush()

        # Product: low stock but NO recent sales
        stale_product = Product(
            company_id=company.id, name="Widget C", sku="WID-003",
            price=4.99, low_stock_threshold=15,
        )
        db.session.add(stale_product)
        db.session.flush()

        # Inventory records
        inv_low = Inventory(product_id=low_product.id, warehouse_id=wh.id, quantity=5)
        inv_ok = Inventory(product_id=ok_product.id, warehouse_id=wh.id, quantity=50)
        inv_stale = Inventory(product_id=stale_product.id, warehouse_id=wh.id, quantity=3)
        db.session.add_all([inv_low, inv_ok, inv_stale])
        db.session.flush()

        # Recent sale log for low_product (should trigger alert)
        log1 = InventoryLog(
            inventory_id=inv_low.id, product_id=low_product.id,
            warehouse_id=wh.id, change_type="sale",
            quantity_change=-2, quantity_after=5,
            created_at=datetime.now(timezone.utc) - timedelta(days=5),
        )
        db.session.add(log1)

        # Old sale log for stale_product (>30 days ago, should NOT trigger)
        log2 = InventoryLog(
            inventory_id=inv_stale.id, product_id=stale_product.id,
            warehouse_id=wh.id, change_type="sale",
            quantity_change=-1, quantity_after=3,
            created_at=datetime.now(timezone.utc) - timedelta(days=60),
        )
        db.session.add(log2)

        # Supplier for low_product
        supplier = Supplier(name="Supplier Corp", contact_email="orders@supplier.com")
        db.session.add(supplier)
        db.session.flush()

        ps = ProductSupplier(
            product_id=low_product.id, supplier_id=supplier.id,
            unit_cost=5.00, lead_time_days=7, is_preferred=True,
        )
        db.session.add(ps)
        db.session.commit()

        return {
            "company_id": company.id,
            "user_id": user.id,
            "warehouse_id": wh.id,
            "low_product_id": low_product.id,
            "ok_product_id": ok_product.id,
            "stale_product_id": stale_product.id,
        }


class TestLowStockAlerts:
    """Test cases for GET /api/companies/{id}/alerts/low-stock."""

    def test_returns_only_low_stock_with_recent_sales(self, client, setup_alerts_data):
        cid = setup_alerts_data["company_id"]
        response = client.get(f"/api/companies/{cid}/alerts/low-stock")
        assert response.status_code == 200
        data = response.get_json()

        # Should include Widget A (low stock + recent sale)
        # Should NOT include Widget B (stock above threshold)
        # Should NOT include Widget C (low stock but no recent sales)
        assert data["total_alerts"] == 1
        assert data["alerts"][0]["sku"] == "WID-001"

    def test_includes_supplier_info(self, client, setup_alerts_data):
        cid = setup_alerts_data["company_id"]
        response = client.get(f"/api/companies/{cid}/alerts/low-stock")
        data = response.get_json()

        supplier = data["alerts"][0]["supplier"]
        assert supplier is not None
        assert supplier["name"] == "Supplier Corp"
        assert supplier["contact_email"] == "orders@supplier.com"
        assert supplier["lead_time_days"] == 7

    def test_includes_days_until_stockout(self, client, setup_alerts_data):
        cid = setup_alerts_data["company_id"]
        response = client.get(f"/api/companies/{cid}/alerts/low-stock")
        data = response.get_json()

        alert = data["alerts"][0]
        assert "days_until_stockout" in alert
        assert "daily_sales_rate" in alert
        assert alert["current_stock"] == 5
        assert alert["threshold"] == 20

    def test_nonexistent_company_returns_404(self, client, setup_alerts_data):
        response = client.get("/api/companies/99999/alerts/low-stock")
        assert response.status_code in (404, 403)

    def test_empty_company_returns_empty_alerts(self, client, app):
        """Company with no products should return empty alerts."""
        with app.app_context():
            company = Company(name="Empty Corp", email="empty@corp.com")
            db.session.add(company)
            db.session.flush()
            user = User(
                email="e@empty.com", password_hash="h", name="E",
                company_id=company.id,
            )
            db.session.add(user)
            db.session.commit()
            cid = company.id

        response = client.get(f"/api/companies/{cid}/alerts/low-stock")
        assert response.status_code == 200
        data = response.get_json()
        assert data["total_alerts"] == 0
        assert data["alerts"] == []

    def test_pagination_parameters(self, client, setup_alerts_data):
        cid = setup_alerts_data["company_id"]
        response = client.get(
            f"/api/companies/{cid}/alerts/low-stock?page=1&per_page=5"
        )
        data = response.get_json()
        assert data["page"] == 1
        assert data["per_page"] == 5
        assert "total_pages" in data
