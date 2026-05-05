-- ============================================================
-- StockFlow — Database Schema (PostgreSQL)
-- Part 2: Database Design
--
-- Design Decisions:
--   1. NUMERIC(12,2) for all monetary values — avoids float precision errors
--   2. UNIQUE(product_id, warehouse_id) on inventory — same product in multiple warehouses
--   3. Append-only inventory_logs — full audit trail for compliance & debugging
--   4. Junction table for bundles — supports quantity-per-component
--   5. is_preferred flag on product_suppliers — quick reorder lookups
--   6. Indexes on FKs and filtered columns — optimizes alert queries
--   7. Soft deletes via is_active — preserves referential integrity for historical data
-- ============================================================

-- 1. Companies (tenants)
CREATE TABLE companies (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    phone           VARCHAR(20),
    address         TEXT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Warehouses (belong to companies)
CREATE TABLE warehouses (
    id              SERIAL PRIMARY KEY,
    company_id      INT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    location        TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_warehouses_company ON warehouses(company_id);

-- 3. Products (belong to companies, SKU globally unique)
CREATE TABLE products (
    id                  SERIAL PRIMARY KEY,
    company_id          INT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name                VARCHAR(255) NOT NULL,
    sku                 VARCHAR(100) UNIQUE NOT NULL,
    description         TEXT,
    price               NUMERIC(12, 2) NOT NULL CHECK (price >= 0),
    product_type        VARCHAR(50) DEFAULT 'standard',    -- 'standard', 'bundle', 'perishable'
    low_stock_threshold INT DEFAULT 10,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_products_company ON products(company_id);
CREATE INDEX idx_products_sku ON products(sku);

-- 4. Product Bundles (self-referencing many-to-many)
--    A "bundle" product contains other products with specified quantities.
--    Example: 'Starter Kit' = 2x Widget A + 1x Widget B
CREATE TABLE product_bundles (
    id              SERIAL PRIMARY KEY,
    bundle_id       INT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    component_id    INT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity        INT NOT NULL DEFAULT 1 CHECK (quantity > 0),
    UNIQUE(bundle_id, component_id),
    CHECK (bundle_id != component_id)    -- Prevent self-reference
);

-- 5. Suppliers
CREATE TABLE suppliers (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    contact_email   VARCHAR(255),
    contact_phone   VARCHAR(20),
    address         TEXT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. Company-Supplier relationship (many-to-many)
CREATE TABLE company_suppliers (
    id              SERIAL PRIMARY KEY,
    company_id      INT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    supplier_id     INT NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    UNIQUE(company_id, supplier_id)
);

-- 7. Product-Supplier mapping (which supplier provides which product)
--    Includes unit cost, lead time, and preferred supplier flag.
CREATE TABLE product_suppliers (
    id              SERIAL PRIMARY KEY,
    product_id      INT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    supplier_id     INT NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    unit_cost       NUMERIC(12, 2),
    lead_time_days  INT,               -- Delivery lead time in days
    is_preferred    BOOLEAN DEFAULT FALSE,
    UNIQUE(product_id, supplier_id)
);

-- 8. Inventory (current stock per product per warehouse)
CREATE TABLE inventory (
    id              SERIAL PRIMARY KEY,
    product_id      INT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    warehouse_id    INT NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    quantity        INT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    last_updated    TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(product_id, warehouse_id)
);
CREATE INDEX idx_inventory_product ON inventory(product_id);
CREATE INDEX idx_inventory_warehouse ON inventory(warehouse_id);

-- 9. Inventory Change Log (append-only audit trail)
--    Records every stock change with who, when, why, and resulting quantity.
--    change_type: 'sale', 'restock', 'transfer', 'adjustment', 'initial'
--    quantity_change: positive for additions, negative for removals
CREATE TABLE inventory_logs (
    id              SERIAL PRIMARY KEY,
    inventory_id    INT NOT NULL REFERENCES inventory(id),
    product_id      INT NOT NULL REFERENCES products(id),
    warehouse_id    INT NOT NULL REFERENCES warehouses(id),
    change_type     VARCHAR(50) NOT NULL,
    quantity_change INT NOT NULL,
    quantity_after  INT NOT NULL,
    reference_id    VARCHAR(100),      -- Order ID, PO number, etc.
    notes           TEXT,
    created_by      INT,               -- User ID who made the change
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_inv_logs_product ON inventory_logs(product_id);
CREATE INDEX idx_inv_logs_warehouse ON inventory_logs(warehouse_id);
CREATE INDEX idx_inv_logs_created ON inventory_logs(created_at);
CREATE INDEX idx_inv_logs_change_type ON inventory_logs(change_type);

-- 10. Users (for authentication — referenced by created_by in logs)
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    company_id      INT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_users_company ON users(company_id);
CREATE INDEX idx_users_email ON users(email);
