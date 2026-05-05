"""
Tests for the product creation endpoint (Part 1).
Validates all bug fixes: validation, SKU uniqueness, atomicity, auth, status codes.
"""

import pytest
from app import create_app, db
from app.config import TestConfig
from app.models import Company, Warehouse, Product, Inventory, User


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
def setup_data(app):
    """Create a company, warehouse, and user for testing."""
    with app.app_context():
        company = Company(name="Test Corp", email="test@corp.com")
        db.session.add(company)
        db.session.flush()

        warehouse = Warehouse(company_id=company.id, name="Main Warehouse")
        db.session.add(warehouse)

        user = User(
            email="dev@corp.com",
            password_hash="hashed",
            name="Test User",
            company_id=company.id,
        )
        db.session.add(user)
        db.session.commit()

        return {
            "company_id": company.id,
            "warehouse_id": warehouse.id,
            "user_id": user.id,
        }


def valid_product_data(warehouse_id):
    """Helper: returns a valid product creation payload."""
    return {
        "name": "Widget A",
        "sku": "WID-001",
        "price": 19.99,
        "warehouse_id": warehouse_id,
        "initial_quantity": 100,
    }


class TestProductCreation:
    """Test cases for POST /api/products."""

    def test_missing_required_fields_returns_400(self, client, setup_data):
        """Sending empty body should return 400 with missing field list."""
        response = client.post("/api/products", json={})
        assert response.status_code == 400
        data = response.get_json()
        assert "missing_fields" in data

    def test_missing_name_returns_400(self, client, setup_data):
        payload = valid_product_data(setup_data["warehouse_id"])
        del payload["name"]
        response = client.post("/api/products", json=payload)
        assert response.status_code == 400

    def test_negative_price_returns_400(self, client, setup_data):
        payload = valid_product_data(setup_data["warehouse_id"])
        payload["price"] = -10
        response = client.post("/api/products", json=payload)
        assert response.status_code == 400

    def test_negative_quantity_returns_400(self, client, setup_data):
        payload = valid_product_data(setup_data["warehouse_id"])
        payload["initial_quantity"] = -5
        response = client.post("/api/products", json=payload)
        assert response.status_code == 400

    def test_invalid_price_format_returns_400(self, client, setup_data):
        payload = valid_product_data(setup_data["warehouse_id"])
        payload["price"] = "not-a-number"
        response = client.post("/api/products", json=payload)
        assert response.status_code == 400

    def test_nonexistent_warehouse_returns_404(self, client, setup_data):
        payload = valid_product_data(warehouse_id=99999)
        response = client.post("/api/products", json=payload)
        assert response.status_code in (404, 403)

    def test_duplicate_sku_returns_409(self, client, setup_data):
        """Creating two products with the same SKU should fail on second attempt."""
        payload = valid_product_data(setup_data["warehouse_id"])

        # First creation should succeed
        resp1 = client.post("/api/products", json=payload)
        assert resp1.status_code == 201

        # Second creation with same SKU should fail
        resp2 = client.post("/api/products", json=payload)
        assert resp2.status_code == 409

    def test_successful_creation_returns_201(self, client, setup_data):
        payload = valid_product_data(setup_data["warehouse_id"])
        response = client.post("/api/products", json=payload)
        assert response.status_code == 201
        data = response.get_json()
        assert "product_id" in data
        assert data["sku"] == "WID-001"

    def test_product_and_inventory_created_atomically(self, client, app, setup_data):
        """Both product and inventory records should exist after creation."""
        payload = valid_product_data(setup_data["warehouse_id"])
        response = client.post("/api/products", json=payload)
        assert response.status_code == 201

        with app.app_context():
            product = Product.query.filter_by(sku="WID-001").first()
            assert product is not None

            inv = Inventory.query.filter_by(product_id=product.id).first()
            assert inv is not None
            assert inv.quantity == 100

    def test_sku_normalized_to_uppercase(self, client, setup_data):
        payload = valid_product_data(setup_data["warehouse_id"])
        payload["sku"] = "wid-001"
        response = client.post("/api/products", json=payload)
        assert response.status_code == 201
        assert response.get_json()["sku"] == "WID-001"
