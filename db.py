"""Database layer for MealSync. Plain sqlite3, no ORM."""
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Asia/Kuala_Lumpur")
except Exception:  # tzdata missing (some Windows setups)
    _TZ = None

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "canteen.db")
TP_PATTERN = re.compile(r"^TP\d{6}$")
ACTIVE_STATUSES = ("Pending", "Preparing", "Ready")
CATEGORIES = ["Rice", "Noodles", "Western", "Snacks", "Drinks", "Dessert", "Other"]

# new status -> statuses it can move from (used by the vendor side)
ALLOWED_FROM = {
    "Preparing": ("Pending",),
    "Ready": ("Preparing",),
    "Completed": ("Ready",),
    "Cancelled": ("Pending", "Preparing", "Ready"),
}


def now():
    return datetime.now(_TZ).strftime("%Y-%m-%d %H:%M:%S")


def today():
    return datetime.now(_TZ).date()


@contextmanager
def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch(sql, params=()):
    with _db() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def execute(sql, params=()):
    """Returns (lastrowid, rowcount)."""
    with _db() as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid, cur.rowcount


def init_db():
    with _db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                tp_number TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                password TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS vendors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS menu_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor_id INTEGER NOT NULL REFERENCES vendors(id),
                name TEXT NOT NULL,
                price REAL NOT NULL,
                available INTEGER NOT NULL DEFAULT 1,
                category TEXT NOT NULL DEFAULT 'Other',
                image TEXT
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tp_number TEXT NOT NULL REFERENCES students(tp_number),
                vendor_id INTEGER NOT NULL REFERENCES vendors(id),
                status TEXT NOT NULL DEFAULT 'Pending',
                total REAL NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL REFERENCES orders(id),
                name TEXT NOT NULL,
                price REAL NOT NULL,
                qty INTEGER NOT NULL
            );
            """
        )
        # older databases from the Streamlit version don't have these two columns
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(menu_items)")}
        if "category" not in cols:
            conn.execute("ALTER TABLE menu_items ADD COLUMN category TEXT NOT NULL DEFAULT 'Other'")
        if "image" not in cols:
            conn.execute("ALTER TABLE menu_items ADD COLUMN image TEXT")


# ---------- accounts ----------

def _hash(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 120_000)
    return f"{salt}${digest.hex()}"


def _check(password, stored):
    try:
        salt, digest = stored.split("$")
    except ValueError:
        return False
    test = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 120_000)
    return hmac.compare_digest(test.hex(), digest)


def register_student(tp, name, password):
    tp = tp.strip().upper()
    name = name.strip()
    if not TP_PATTERN.match(tp):
        return False, "TP number should look like TP012345."
    if not name:
        return False, "Please enter your name."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    try:
        execute("INSERT INTO students (tp_number, name, password) VALUES (?, ?, ?)",
                (tp, name, _hash(password)))
    except sqlite3.IntegrityError:
        return False, "That TP number is already registered."
    return True, "Account created."


def register_vendor(shop_name, username, password):
    shop_name = shop_name.strip()
    username = username.strip()
    if not shop_name or not username:
        return False, "Shop name and username are required."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    try:
        execute("INSERT INTO vendors (shop_name, username, password) VALUES (?, ?, ?)",
                (shop_name, username, _hash(password)))
    except sqlite3.IntegrityError:
        return False, "That shop name or username is already taken."
    return True, "Account created."


def login_student(tp, password):
    rows = fetch("SELECT * FROM students WHERE tp_number = ?", (tp.strip().upper(),))
    if rows and _check(password, rows[0]["password"]):
        return {"tp_number": rows[0]["tp_number"], "name": rows[0]["name"]}
    return None


def login_vendor(vendor_id, password):
    rows = fetch("SELECT * FROM vendors WHERE id = ?", (vendor_id,))
    if rows and _check(password, rows[0]["password"]):
        r = rows[0]
        return {"id": r["id"], "shop_name": r["shop_name"], "username": r["username"]}
    return None


def get_vendor(vendor_id):
    rows = fetch("SELECT id, shop_name FROM vendors WHERE id = ?", (vendor_id,))
    return rows[0] if rows else None


def list_vendors():
    return fetch(
        """SELECT v.id, v.shop_name,
                  (SELECT COUNT(*) FROM menu_items m
                    WHERE m.vendor_id = v.id AND m.available = 1) AS item_count,
                  (SELECT m.image FROM menu_items m
                    WHERE m.vendor_id = v.id AND m.image IS NOT NULL AND m.image != ''
                    ORDER BY m.id LIMIT 1) AS cover
             FROM vendors v ORDER BY v.shop_name"""
    )


# ---------- menu ----------

def get_menu(vendor_id):
    return fetch("SELECT * FROM menu_items WHERE vendor_id = ? ORDER BY category, name", (vendor_id,))


def get_menu_item(item_id, vendor_id):
    rows = fetch("SELECT * FROM menu_items WHERE id = ? AND vendor_id = ?", (item_id, vendor_id))
    return rows[0] if rows else None


def get_items(ids):
    """Menu items by id, with the stall name. Used to build the cart from current prices."""
    ids = list(ids)
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    return fetch(
        f"""SELECT m.*, v.shop_name FROM menu_items m
              JOIN vendors v ON v.id = m.vendor_id
             WHERE m.id IN ({marks})""",
        ids,
    )


def add_menu_item(vendor_id, name, price, category="Other", image=None):
    name = name.strip()
    if not name:
        return False, "Item name is required."
    if price <= 0:
        return False, "Price must be more than 0."
    if category not in CATEGORIES:
        category = "Other"
    execute(
        "INSERT INTO menu_items (vendor_id, name, price, category, image) VALUES (?, ?, ?, ?, ?)",
        (vendor_id, name, round(price, 2), category, image),
    )
    return True, "Item added."


def update_menu_item(item_id, vendor_id, name, price, available, category="Other", image=None):
    """image=None keeps the current photo."""
    name = name.strip()
    if not name or price <= 0:
        return False, "Name and a positive price are required."
    if category not in CATEGORIES:
        category = "Other"
    if image is None:
        execute(
            "UPDATE menu_items SET name = ?, price = ?, available = ?, category = ? "
            "WHERE id = ? AND vendor_id = ?",
            (name, round(price, 2), 1 if available else 0, category, item_id, vendor_id),
        )
    else:
        execute(
            "UPDATE menu_items SET name = ?, price = ?, available = ?, category = ?, image = ? "
            "WHERE id = ? AND vendor_id = ?",
            (name, round(price, 2), 1 if available else 0, category, image, item_id, vendor_id),
        )
    return True, "Saved."


def delete_menu_item(item_id, vendor_id):
    execute("DELETE FROM menu_items WHERE id = ? AND vendor_id = ?", (item_id, vendor_id))


# ---------- orders ----------

def place_order(tp, vendor_id, cart, note=""):
    """cart is {menu_item_id: qty}. Prices are read from the DB, not the browser."""
    if not cart:
        return None, "Your cart is empty."
    ids = list(cart.keys())
    marks = ",".join("?" * len(ids))
    with _db() as conn:
        rows = conn.execute(
            f"SELECT * FROM menu_items WHERE id IN ({marks}) AND vendor_id = ? AND available = 1",
            ids + [vendor_id],
        ).fetchall()
        if len(rows) != len(ids):
            return None, "Some items are no longer available. Please check your cart."
        total = round(sum(r["price"] * cart[r["id"]] for r in rows), 2)
        cur = conn.execute(
            "INSERT INTO orders (tp_number, vendor_id, status, total, note, created_at) "
            "VALUES (?, ?, 'Pending', ?, ?, ?)",
            (tp, vendor_id, total, note.strip(), now()),
        )
        order_id = cur.lastrowid
        for r in rows:
            conn.execute(
                "INSERT INTO order_items (order_id, name, price, qty) VALUES (?, ?, ?, ?)",
                (order_id, r["name"], r["price"], cart[r["id"]]),
            )
    return order_id, "Order placed."


def get_orders(tp=None, vendor_id=None, statuses=None, start=None, end=None):
    sql = """SELECT o.*, v.shop_name, s.name AS student_name
               FROM orders o
               JOIN vendors v ON v.id = o.vendor_id
               JOIN students s ON s.tp_number = o.tp_number
              WHERE 1 = 1"""
    params = []
    if tp:
        sql += " AND o.tp_number = ?"
        params.append(tp)
    if vendor_id:
        sql += " AND o.vendor_id = ?"
        params.append(vendor_id)
    if statuses:
        sql += f" AND o.status IN ({','.join('?' * len(statuses))})"
        params += list(statuses)
    if start:
        sql += " AND date(o.created_at) >= ?"
        params.append(str(start))
    if end:
        sql += " AND date(o.created_at) <= ?"
        params.append(str(end))
    sql += " ORDER BY o.created_at DESC, o.id DESC"
    orders = fetch(sql, params)
    if orders:
        ids = [o["id"] for o in orders]
        items = fetch(
            f"SELECT * FROM order_items WHERE order_id IN ({','.join('?' * len(ids))})", ids
        )
        grouped = {}
        for it in items:
            grouped.setdefault(it["order_id"], []).append(it)
        for o in orders:
            o["items"] = grouped.get(o["id"], [])
    return orders


def cancel_order_student(order_id, tp):
    """Students can only cancel while the stall hasn't started on it."""
    _, n = execute(
        "UPDATE orders SET status = 'Cancelled' "
        "WHERE id = ? AND tp_number = ? AND status = 'Pending'",
        (order_id, tp),
    )
    return n == 1


def vendor_set_status(order_id, vendor_id, new_status):
    allowed = ALLOWED_FROM.get(new_status)
    if not allowed:
        return False
    marks = ",".join("?" * len(allowed))
    _, n = execute(
        f"UPDATE orders SET status = ? WHERE id = ? AND vendor_id = ? AND status IN ({marks})",
        [new_status, order_id, vendor_id, *allowed],
    )
    return n == 1
