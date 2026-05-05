# StockFlow — Backend Engineering Intern Case Study

> **Inventory Management System for B2B SaaS**  
> Submitted by: **Satyam Gaikwad**  
> Position: Backend Engineering Intern — Bynry Inc.  
> Date: 5th May 2026

---

## Table of Contents

- [Project Overview](#project-overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Part 1: Code Review & Debugging](#part-1-code-review--debugging)
- [Part 2: Database Design](#part-2-database-design)
- [Part 3: API Implementation — Low-Stock Alerts](#part-3-api-implementation--low-stock-alerts)
- [Assumptions](#assumptions)
- [Alternative Approaches Considered](#alternative-approaches-considered)

---

## Project Overview

StockFlow is a B2B inventory management platform that allows small businesses to track products across multiple warehouses and manage supplier relationships. This repository contains my solutions to all three parts of the backend engineering case study.

---

## Tech Stack

| Component       | Technology                     |
|-----------------|--------------------------------|
| Language        | Python 3.10+                   |
| Framework       | Flask                          |
| ORM             | SQLAlchemy (Flask-SQLAlchemy)  |
| Database        | PostgreSQL                     |
| Migrations      | Flask-Migrate (Alembic)        |
| Validation      | Marshmallow                    |
| Auth            | Flask-Login                    |
| Testing         | pytest                         |

---

## Project Structure

```
stockflow/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Configuration settings
│   ├── models/
│   │   ├── __init__.py          # Model exports
│   │   ├── company.py           # Company model
│   │   ├── warehouse.py         # Warehouse model
│   │   ├── product.py           # Product & ProductBundle models
│   │   ├── supplier.py          # Supplier & junction table models
│   │   ├── inventory.py         # Inventory & InventoryLog models
│   │   └── user.py              # User model (for auth)
│   ├── routes/
│   │   ├── __init__.py          # Blueprint registration
│   │   ├── products.py          # Part 1: Fixed product creation endpoint
│   │   └── alerts.py            # Part 3: Low-stock alerts endpoint
│   └── utils/
│       ├── __init__.py
│       ├── validators.py        # Input validation helpers
│       └── errors.py            # Error handler utilities
├── migrations/
│   └── schema.sql               # Part 2: Full DDL schema
├── tests/
│   ├── __init__.py
│   ├── test_products.py         # Tests for product creation
│   └── test_alerts.py           # Tests for low-stock alerts
├── docs/
│   └── BUGFIX_ANALYSIS.md       # Part 1: Detailed bug analysis
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Setup & Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/stockflow-case-study.git
cd stockflow-case-study

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your database credentials

# Initialize database
flask db upgrade
# OR run the DDL directly:
psql -U postgres -d stockflow -f migrations/schema.sql

# Run the application
flask run

# Run tests
pytest tests/ -v
```

---

## Part 1: Code Review & Debugging

### Original Buggy Code

```python
@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.json
    product = Product(
        name=data['name'],
        sku=data['sku'],
        price=data['price'],
        warehouse_id=data['warehouse_id']
    )
    db.session.add(product)
    db.session.commit()

    inventory = Inventory(
        product_id=product.id,
        warehouse_id=data['warehouse_id'],
        quantity=data['initial_quantity']
    )
    db.session.add(inventory)
    db.session.commit()
    return {"message": "Product created", "product_id": product.id}
```

### Issues Identified

| # | Issue | Production Impact | Severity |
|---|-------|-------------------|----------|
| 1 | **No input validation** — Directly accesses `data['name']` etc. without checking existence or types | `KeyError` → 500 crash on malformed requests; negative prices/quantities corrupt data | 🔴 Critical |
| 2 | **No SKU uniqueness check** — Doesn't verify if SKU already exists | Duplicate SKUs break inventory lookups; unhandled `IntegrityError` if DB has constraint | 🔴 Critical |
| 3 | **Non-atomic transaction** — Two separate `db.session.commit()` calls | If 2nd commit fails, orphaned product exists without inventory record; inconsistent state | 🔴 Critical |
| 4 | **No error handling** — Zero try/except blocks | Unhandled exceptions leak stack traces with DB schema info; no graceful degradation | 🔴 Critical |
| 5 | **No authentication/authorization** — Anyone can create products in any warehouse | Complete security vulnerability; Company A can write to Company B's warehouses | 🔴 Critical |
| 6 | **Wrong HTTP status code** — Returns 200 instead of 201 for resource creation | Breaks RESTful conventions; API consumers can't reliably determine outcome | 🟡 Medium |
| 7 | **Float precision for price** — If price is stored as float, decimal errors accumulate | `19.99` becomes `19.989999...`; rounding errors in invoicing/revenue | 🟡 Medium |

### Fixed Code

See: [`app/routes/products.py`](app/routes/products.py)

**Key fixes applied:**
- Comprehensive input validation with clear error messages
- SKU uniqueness pre-check before insertion
- `db.session.flush()` + single `db.session.commit()` for atomicity
- `try/except` with `db.session.rollback()` on failure
- `@login_required` decorator + warehouse ownership verification
- `Decimal` type for price precision
- Proper HTTP status codes (201, 400, 404, 409, 500)

For detailed analysis, see: [`docs/BUGFIX_ANALYSIS.md`](docs/BUGFIX_ANALYSIS.md)

---

## Part 2: Database Design

### Entity-Relationship Overview

```
Companies ─────< Warehouses
    │                 │
    │                 │
    ├───< Products ───┤
    │        │        │
    │        │     Inventory ───< InventoryLogs
    │        │
    │   ProductBundles (self-referencing)
    │        │
    └───< CompanySuppliers >─── Suppliers
                                    │
                          ProductSuppliers
```

### Schema Design

Full DDL: [`migrations/schema.sql`](migrations/schema.sql)

**9 tables designed:**

| Table | Purpose |
|-------|---------|
| `companies` | Multi-tenant company accounts |
| `warehouses` | Physical locations belonging to companies |
| `products` | Product catalog with per-product low-stock thresholds |
| `product_bundles` | Self-referencing junction table for bundle products |
| `suppliers` | Supplier directory |
| `company_suppliers` | Many-to-many: which companies work with which suppliers |
| `product_suppliers` | Many-to-many: which suppliers provide which products (with cost & lead time) |
| `inventory` | Current stock levels per product per warehouse |
| `inventory_logs` | Append-only audit trail of all inventory changes |

### Design Decisions

1. **`NUMERIC(12,2)` for price** — Avoids floating-point precision errors for financial data
2. **`UNIQUE(product_id, warehouse_id)` on inventory** — Same product in multiple warehouses with independent quantities
3. **Append-only `inventory_logs`** — Full audit trail with who/when/why/resulting-quantity for compliance
4. **Junction table for bundles** — `product_bundles` with quantity-per-component; `CHECK` prevents self-reference
5. **`is_preferred` flag on `product_suppliers`** — Quick lookup for reordering alerts
6. **Strategic indexes** — On all foreign keys, SKU, and `created_at` on logs for alert query performance
7. **Soft deletes via `is_active`** — Preserves referential integrity for historical log entries

### Questions for the Product Team (Identified Gaps)

1. Should bundles auto-deduct component inventory when sold, or are they tracked independently?
2. Do we need to support inter-warehouse transfers? (I've included `'transfer'` as a change_type assuming yes.)
3. Is there a concept of "reserved" or "committed" stock (e.g., items in pending orders)?
4. Should `low_stock_threshold` be per-product or per-product-per-warehouse?
5. Do suppliers serve the entire platform or are they company-specific?
6. Are there different user roles (admin, warehouse manager, viewer) that need RBAC?
7. Do we need to support multiple currencies for international suppliers?
8. Is there a maximum number of warehouses per company? Any plan/tier limits?

---

## Part 3: API Implementation — Low-Stock Alerts

### Endpoint

```
GET /api/companies/{company_id}/alerts/low-stock
```

### Query Parameters

| Parameter  | Type | Default | Description |
|------------|------|---------|-------------|
| `page`     | int  | 1       | Page number |
| `per_page` | int  | 20      | Results per page (max 100) |

### Response Format

```json
{
    "alerts": [
        {
            "product_id": 123,
            "product_name": "Widget A",
            "sku": "WID-001",
            "warehouse_id": 456,
            "warehouse_name": "Main Warehouse",
            "current_stock": 5,
            "threshold": 20,
            "days_until_stockout": 12,
            "daily_sales_rate": 0.42,
            "supplier": {
                "id": 789,
                "name": "Supplier Corp",
                "contact_email": "orders@supplier.com",
                "lead_time_days": 7
            }
        }
    ],
    "total_alerts": 1,
    "page": 1,
    "per_page": 20,
    "total_pages": 1
}
```

### Implementation

See: [`app/routes/alerts.py`](app/routes/alerts.py)

### Algorithm

1. **Authorization** — Verify user belongs to the requested company
2. **Filter** — Query inventory where `quantity <= low_stock_threshold` for active products/warehouses
3. **Recent Activity** — Only include products with at least one `'sale'` entry in `inventory_logs` in the last 30 days
4. **Stockout Estimate** — `days_until_stockout = current_stock / (total_sold_30d / 30)`
5. **Supplier Lookup** — Attach preferred supplier info (fallback to any linked supplier)
6. **Paginate** — Return paginated results sorted by most critical (lowest stock) first

### Edge Cases Handled

| Edge Case | Handling |
|-----------|----------|
| Company doesn't exist | 404 with clear error message |
| User from different company | 403 Unauthorized (multi-tenant security) |
| No warehouses / no products | Empty alerts array, `total_alerts: 0` |
| Product has no sales in 30 days | Excluded from alerts (not "active") |
| Zero daily sales rate | `days_until_stockout` set to `null` |
| No supplier linked to product | `supplier` field is `null` |
| Very large result sets | Pagination, capped at 100 per page |
| Inactive products/warehouses | Excluded via `is_active = True` filter |

### Performance Considerations

- `recent_sales_subquery` executes once and is reused (avoids N+1)
- Results sorted by `quantity ASC` — most critical alerts first
- Pagination prevents loading thousands of records
- **Future optimization:** pre-compute `daily_sales_rate` via scheduled jobs and cache results

---

## Assumptions

1. "Recent sales activity" = at least one sale-type log entry in the last **30 days**
2. `low_stock_threshold` is a **per-product** setting (stored in products table)
3. `days_until_stockout` uses a **simple average** (total sold ÷ 30); a weighted moving average could be used for better accuracy
4. The **preferred supplier** (`is_preferred = True`) is returned; falls back to first available
5. Auth is handled via **Flask-Login** patterns (`@login_required`, `current_user`)
6. Database is **PostgreSQL** (DDL uses SERIAL, NUMERIC, BOOLEAN)
7. All timestamps are stored in **UTC**

---

## Alternative Approaches Considered

### Part 1 — Code Review
- **Marshmallow/Pydantic for validation** — More scalable but adds dependency; chose manual validation for clarity
- **DB constraint-only SKU check** — Simpler but produces cryptic error messages; chose pre-check for UX

### Part 2 — Database Design
- **Adjacency list for bundles** (`parent_id` on products) — Simpler but can't store quantity-per-component; chose junction table
- **Event sourcing** (derive inventory from logs only) — Better audit trail but complex read queries; chose current-state + change log

### Part 3 — API
- **Single complex SQL query** with all JOINs — More efficient but harder to maintain; chose hybrid SQL + Python for readability
- **Redis caching** for alert data — Great for production but premature for initial implementation; noted as future optimization

---

## License

This project is submitted as part of the Bynry Inc. hiring process and is not intended for production use.
