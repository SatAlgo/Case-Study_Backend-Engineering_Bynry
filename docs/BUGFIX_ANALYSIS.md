# Part 1: Detailed Bug Analysis

## Original Code (As Provided)

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

---

## Issue 1: No Input Validation

**What's wrong:** The code directly accesses `data['name']`, `data['sku']`, `data['price']`, etc. using dictionary key access without any checks.

**What happens in production:**
- If a client sends `{}` or omits any field → `KeyError` → unhandled 500 error
- If `data` itself is `None` (non-JSON request body) → `TypeError`
- No type checking: `price` could be `"hello"`, `quantity` could be `-5`
- No length/format validation: SKU could be empty string, name could be 10,000 characters

**Fix:** Validate all required fields exist, check data types, enforce business rules (positive price, non-negative quantity), and return 400 with descriptive error messages.

---

## Issue 2: No SKU Uniqueness Check

**What's wrong:** The requirements state "SKUs must be unique across the platform," but the code never checks for duplicates before insertion.

**What happens in production:**
- **If DB has UNIQUE constraint:** An unhandled `IntegrityError` crashes the endpoint with a 500 error. The error message is a raw database error, potentially leaking schema details.
- **If DB lacks UNIQUE constraint:** Duplicate products are silently created. Inventory lookups by SKU return multiple results, breaking search, reports, and barcode scanning.

**Fix:** Query for existing SKU before insert. Handle `IntegrityError` as a safety net.

---

## Issue 3: Non-Atomic Transaction (Two Commits)

**What's wrong:** The code calls `db.session.commit()` after creating the product, then calls it again after creating the inventory. These are two separate transactions.

**What happens in production:**
- If the first `commit()` succeeds but the second fails (DB error, constraint violation, connection drop), the product exists in the database but has no inventory record.
- This is a **data consistency** problem: the warehouse shows a product but no stock information.
- Cleaning up requires manual database intervention or a separate repair job.

**Fix:** Use `db.session.flush()` after the product (to get `product.id` without committing) and a single `db.session.commit()` at the end. If anything fails, `db.session.rollback()` undoes everything.

---

## Issue 4: No Error Handling

**What's wrong:** Zero `try/except` blocks. Any exception propagates as an unhandled 500 error.

**What happens in production:**
- Database connection timeouts → 500 with stack trace
- Constraint violations → 500 with raw SQL error
- Stack traces may expose: table names, column names, database type, ORM version
- No logging: failures are invisible to the operations team
- No rollback: failed operations may leave the session in a dirty state, affecting subsequent requests

**Fix:** Wrap the database operations in `try/except`, rollback on failure, log errors, return clean JSON error responses.

---

## Issue 5: No Authentication or Authorization

**What's wrong:** The endpoint has no `@login_required` decorator or any form of authentication check. There's no verification that the warehouse belongs to the requesting user's company.

**What happens in production:**
- Any unauthenticated user can create products (even without logging in)
- A user from Company A can insert products into Company B's warehouse by guessing a `warehouse_id`
- In a multi-tenant B2B SaaS, this is a **critical security vulnerability**
- There's no audit trail of who created what

**Fix:** Add authentication decorator, verify `current_user.company_id` matches the warehouse's company, and log the creating user.

---

## Issue 6: Wrong HTTP Status Codes

**What's wrong:** The endpoint returns the default 200 OK status for a resource creation, and has no error-specific status codes.

**What happens in production:**
- API consumers (frontend, mobile apps, integrations) can't distinguish between "found existing data" (200) and "created new data" (201)
- Error cases all return 200 or unhandled 500, making it impossible to build proper error handling on the client side
- Breaks RESTful API conventions that integrators expect

**Fix:** Return 201 for successful creation, 400 for validation errors, 404 for missing resources, 409 for conflicts, 403 for unauthorized access.

---

## Issue 7: Float Precision for Price

**What's wrong:** If `data['price']` is stored as a Python `float` and the database column is `FLOAT` or `REAL`, floating-point arithmetic introduces precision errors.

**What happens in production:**
- `19.99` may be stored as `19.989999999999998`
- Rounding errors accumulate across thousands of transactions
- Invoice totals don't match expected values
- Revenue reports show discrepancies

**Fix:** Use Python's `Decimal` type and PostgreSQL's `NUMERIC(12, 2)` column type for exact decimal arithmetic.
