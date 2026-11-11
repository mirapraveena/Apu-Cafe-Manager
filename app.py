import os
import uuid
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)

import db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

app = Flask(__name__)
# fine for a hackathon demo; set SECRET_KEY in the environment for anything real
app.secret_key = os.environ.get("SECRET_KEY", "mealsync-hackathon-key")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB per upload

os.makedirs(UPLOAD_DIR, exist_ok=True)
db.init_db()


# ---------- template helpers ----------

@app.template_filter("money")
def money(x):
    return f"RM {x:,.2f}"


@app.template_filter("when")
def when(ts):
    try:
        d = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return ts
    hour = d.hour % 12 or 12
    return f"{d.day} {d.strftime('%b')}, {hour}:{d.minute:02d} {'AM' if d.hour < 12 else 'PM'}"


def short_day(iso):
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b')}"


def bars(pairs):
    """[(label, value)] -> rows with a width percentage for the CSS bar charts."""
    top = max((v for _, v in pairs), default=0) or 1
    return [{"label": l, "value": round(v, 2), "pct": max(3, round(v / top * 100))} for l, v in pairs]


def parse_date(text, default):
    try:
        return date.fromisoformat(text)
    except (TypeError, ValueError):
        return default


# ---------- auth ----------

def login_required(role):
    def deco(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = session.get("user")
            if not user:
                return redirect(url_for("login"))
            if user["role"] != role:
                return redirect(url_for("home"))
            return view(*args, **kwargs)
        return wrapper
    return deco


@app.route("/")
def home():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    if user["role"] == "student":
        return redirect(url_for("stalls"))
    return redirect(url_for("vendor_orders"))


@app.route("/login", methods=["GET", "POST"])
def login():
    role = request.values.get("role", "student")
    if role not in ("student", "vendor"):
        role = "student"
    if request.method == "POST":
        pw = request.form.get("password", "")
        if role == "student":
            u = db.login_student(request.form.get("tp_number", ""), pw)
            if u:
                session.clear()
                session["user"] = {"role": "student", **u}
                return redirect(url_for("stalls"))
        else:
            try:
                vendor_id = int(request.form.get("vendor_id", 0))
            except ValueError:
                vendor_id = 0
            u = db.login_vendor(vendor_id, pw)
            if u:
                session.clear()
                session["user"] = {"role": "vendor", **u}
                # brand-new stalls start on the menu page
                return redirect(url_for("vendor_menu" if not db.get_menu(u["id"]) else "vendor_orders"))
        flash("Wrong login details.", "error")
    return render_template("login.html", role=role, vendors=db.list_vendors())


@app.route("/register", methods=["GET", "POST"])
def register():
    role = request.values.get("role", "student")
    if role not in ("student", "vendor"):
        role = "student"
    if request.method == "POST":
        pw = request.form.get("password", "")
        if pw != request.form.get("confirm", ""):
            flash("Passwords don't match.", "error")
        else:
            if role == "student":
                ok, msg = db.register_student(request.form.get("tp_number", ""),
                                              request.form.get("name", ""), pw)
            else:
                ok, msg = db.register_vendor(request.form.get("shop_name", ""),
                                             request.form.get("username", ""), pw)
            if ok:
                flash("Account created. You can log in now.", "success")
                return redirect(url_for("login", role=role))
            flash(msg, "error")
    return render_template("register.html", role=role, form=request.form)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- cart helpers (kept in the session) ----------

def get_cart():
    return session.get("cart") or {"vendor_id": None, "items": {}}


def cart_lines():
    cart = get_cart()
    rows = {r["id"]: r for r in db.get_items([int(i) for i in cart["items"]])}
    lines = []
    for sid, qty in cart["items"].items():
        r = rows.get(int(sid))
        if r and r["available"]:
            lines.append({**r, "qty": qty, "line_total": round(r["price"] * qty, 2)})
    return lines


def cart_summary():
    lines = cart_lines()
    return sum(l["qty"] for l in lines), round(sum(l["line_total"] for l in lines), 2)


@app.context_processor
def inject_globals():
    user = session.get("user")
    count, total = 0, 0.0
    if user and user["role"] == "student":
        count, total = cart_summary()
    return {"user": user, "cart_count": count, "cart_total": total, "CATEGORIES": db.CATEGORIES}


# ---------- student: browse + cart ----------

@app.route("/stalls")
@login_required("student")
def stalls():
    return render_template("stalls.html", vendors=db.list_vendors())


@app.route("/stalls/<int:vendor_id>")
@login_required("student")
def stall_menu(vendor_id):
    vendor = db.get_vendor(vendor_id)
    if not vendor:
        abort(404)
    items = db.get_menu(vendor_id)
    cats = []
    for it in items:
        if it["category"] not in cats:
            cats.append(it["category"])
    return render_template("menu.html", vendor=vendor, items=items, cats=cats)


@app.post("/cart/add")
@login_required("student")
def cart_add():
    try:
        item_id = int(request.form["item_id"])
        qty = max(1, min(20, int(request.form.get("qty", 1))))
    except (KeyError, ValueError):
        abort(400)
    as_json = request.headers.get("X-Requested-With") == "fetch"

    def reply(ok, msg):
        if as_json:
            count, total = cart_summary()
            return jsonify(ok=ok, message=msg, count=count, total=money(total)), (200 if ok else 409)
        flash(msg, "success" if ok else "error")
        return redirect(request.referrer or url_for("cart"))

    rows = db.get_items([item_id])
    if not rows or not rows[0]["available"]:
        return reply(False, "That item isn't available right now.")
    item = rows[0]
    cart = get_cart()
    if cart["items"] and cart["vendor_id"] != item["vendor_id"]:
        return reply(False, "Your cart has items from another stall. Check out or clear it first.")
    cart["vendor_id"] = item["vendor_id"]
    cart["items"][str(item_id)] = min(20, cart["items"].get(str(item_id), 0) + qty)
    session["cart"] = cart
    return reply(True, f"Added {qty} x {item['name']}")


@app.route("/cart")
@login_required("student")
def cart():
    lines = cart_lines()
    vendor = db.get_vendor(get_cart()["vendor_id"]) if lines else None
    return render_template("cart.html", lines=lines, vendor=vendor,
                           total=round(sum(l["line_total"] for l in lines), 2))


@app.post("/cart/update")
@login_required("student")
def cart_update():
    cart = get_cart()
    key = request.form.get("item_id", "")
    try:
        delta = int(request.form.get("delta", 0))
    except ValueError:
        delta = 0
    if key in cart["items"]:
        qty = cart["items"][key] + delta
        if qty <= 0:
            del cart["items"][key]
        else:
            cart["items"][key] = min(20, qty)
        if not cart["items"]:
            cart["vendor_id"] = None
        session["cart"] = cart
    return redirect(url_for("cart"))


@app.post("/cart/remove")
@login_required("student")
def cart_remove():
    cart = get_cart()
    cart["items"].pop(request.form.get("item_id", ""), None)
    if not cart["items"]:
        cart["vendor_id"] = None
    session["cart"] = cart
    return redirect(url_for("cart"))


@app.post("/cart/clear")
@login_required("student")
def cart_clear():
    session.pop("cart", None)
    return redirect(url_for("cart"))


@app.post("/checkout")
@login_required("student")
def checkout():
    cart = get_cart()
    lines = cart_lines()
    if not lines:
        flash("Your cart is empty.", "error")
        return redirect(url_for("cart"))
    if len(lines) != len(cart["items"]):
        # something sold out or was removed by the stall since it was added
        cart["items"] = {str(l["id"]): l["qty"] for l in lines}
        session["cart"] = cart
        flash("Some items are no longer available and were taken out. Check your cart.", "error")
        return redirect(url_for("cart"))
    order_id, msg = db.place_order(
        session["user"]["tp_number"], cart["vendor_id"],
        {l["id"]: l["qty"] for l in lines}, request.form.get("note", ""),
    )
    if order_id:
        session.pop("cart", None)
        flash(f"Order #{order_id} placed. The stall will start on it soon.", "success")
        return redirect(url_for("my_orders"))
    flash(msg, "error")
    return redirect(url_for("cart"))


# ---------- student: orders, history, spending ----------

@app.route("/orders")
@login_required("student")
def my_orders():
    orders = db.get_orders(tp=session["user"]["tp_number"], statuses=db.ACTIVE_STATUSES)
    return render_template("orders.html", orders=orders)


@app.post("/orders/<int:order_id>/cancel")
@login_required("student")
def cancel_order(order_id):
    if db.cancel_order_student(order_id, session["user"]["tp_number"]):
        flash(f"Order #{order_id} cancelled.", "success")
    else:
        flash("The stall already started on this order, so it can't be cancelled.", "error")
    return redirect(url_for("my_orders"))


@app.route("/history")
@login_required("student")
def history():
    orders = db.get_orders(tp=session["user"]["tp_number"])
    chosen = request.args.get("status", "all")
    if chosen != "all":
        orders = [o for o in orders if o["status"] == chosen]
    return render_template("history.html", orders=orders, chosen=chosen,
                           statuses=["Pending", "Preparing", "Ready", "Completed", "Cancelled"])


@app.route("/spending")
@login_required("student")
def spending():
    end = parse_date(request.args.get("to"), db.today())
    start = parse_date(request.args.get("from"), end - timedelta(days=30))
    orders = [o for o in db.get_orders(tp=session["user"]["tp_number"], start=start, end=end)
              if o["status"] != "Cancelled"]
    all_stalls = sorted({o["shop_name"] for o in orders})
    picked = request.args.getlist("stall") or all_stalls
    orders = [o for o in orders if o["shop_name"] in picked]

    by_day, by_stall = {}, {}
    for o in orders:
        day = o["created_at"][:10]
        by_day[day] = by_day.get(day, 0) + o["total"]
        by_stall[o["shop_name"]] = by_stall.get(o["shop_name"], 0) + o["total"]
    total = round(sum(o["total"] for o in orders), 2)
    return render_template(
        "spending.html", start=start, end=end, all_stalls=all_stalls, picked=picked,
        total=total, count=len(orders), average=(total / len(orders) if orders else 0),
        daily=bars([(short_day(d), v) for d, v in sorted(by_day.items())]),
        per_stall=bars(sorted(by_stall.items(), key=lambda kv: -kv[1])),
    )


# ---------- vendor ----------

def save_image(file):
    """Saves an uploaded photo and returns its stored name, or None if nothing was chosen."""
    if not file or not file.filename:
        return None
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        raise ValueError("Photos must be PNG, JPG, WEBP or GIF.")
    name = uuid.uuid4().hex + ext
    file.save(os.path.join(UPLOAD_DIR, name))
    return name


def remove_image(name):
    # seed images are shared between items, so only uploaded (random-named) files are deleted
    if name and not name.startswith("seed-"):
        try:
            os.remove(os.path.join(UPLOAD_DIR, os.path.basename(name)))
        except OSError:
            pass


def read_price():
    try:
        return float(request.form.get("price", "0") or 0)
    except ValueError:
        return 0.0


@app.route("/vendor/orders")
@login_required("vendor")
def vendor_orders():
    vendor = session["user"]
    orders = db.get_orders(vendor_id=vendor["id"], statuses=db.ACTIVE_STATUSES)
    board = {"Pending": [], "Preparing": [], "Ready": []}
    for o in reversed(orders):  # oldest first
        board[o["status"]].append(o)
    return render_template("vendor_orders.html", board=board, has_menu=bool(db.get_menu(vendor["id"])))


@app.post("/vendor/orders/<int:order_id>/status")
@login_required("vendor")
def vendor_status(order_id):
    new_status = request.form.get("status", "")
    if not db.vendor_set_status(order_id, session["user"]["id"], new_status):
        flash("That order was already changed. Refreshing the board.", "error")
    return redirect(url_for("vendor_orders"))


@app.route("/vendor/menu")
@login_required("vendor")
def vendor_menu():
    return render_template("vendor_menu.html", items=db.get_menu(session["user"]["id"]))


@app.post("/vendor/menu/add")
@login_required("vendor")
def vendor_menu_add():
    try:
        image = save_image(request.files.get("image"))
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("vendor_menu"))
    ok, msg = db.add_menu_item(session["user"]["id"], request.form.get("name", ""), read_price(),
                               request.form.get("category", "Other"), image)
    if not ok:
        remove_image(image)
    flash(msg, "success" if ok else "error")
    return redirect(url_for("vendor_menu"))


@app.post("/vendor/menu/<int:item_id>/edit")
@login_required("vendor")
def vendor_menu_edit(item_id):
    vendor_id = session["user"]["id"]
    old = db.get_menu_item(item_id, vendor_id)
    if not old:
        abort(404)
    try:
        image = save_image(request.files.get("image"))
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("vendor_menu"))
    ok, msg = db.update_menu_item(
        item_id, vendor_id, request.form.get("name", ""), read_price(),
        request.form.get("available") == "on", request.form.get("category", "Other"), image,
    )
    if ok and image:
        remove_image(old["image"])
    elif not ok:
        remove_image(image)
    flash(msg, "success" if ok else "error")
    return redirect(url_for("vendor_menu"))


@app.post("/vendor/menu/<int:item_id>/delete")
@login_required("vendor")
def vendor_menu_delete(item_id):
    vendor_id = session["user"]["id"]
    old = db.get_menu_item(item_id, vendor_id)
    if old:
        db.delete_menu_item(item_id, vendor_id)
        remove_image(old["image"])
        flash(f"Deleted {old['name']}.", "success")
    return redirect(url_for("vendor_menu"))


@app.route("/vendor/report")
@login_required("vendor")
def vendor_report():
    end = parse_date(request.args.get("to"), db.today())
    start = parse_date(request.args.get("from"), end - timedelta(days=30))
    orders = db.get_orders(vendor_id=session["user"]["id"], start=start, end=end)
    done = [o for o in orders if o["status"] == "Completed"]
    revenue = round(sum(o["total"] for o in done), 2)

    by_day, sold = {}, {}
    for o in done:
        day = o["created_at"][:10]
        by_day[day] = by_day.get(day, 0) + o["total"]
        for i in o["items"]:
            row = sold.setdefault(i["name"], {"qty": 0, "revenue": 0})
            row["qty"] += i["qty"]
            row["revenue"] += i["qty"] * i["price"]
    top_items = sorted(sold.items(), key=lambda kv: -kv[1]["qty"])[:8]

    return render_template(
        "vendor_report.html", start=start, end=end, orders=orders, revenue=revenue,
        done=len(done), cancelled=sum(1 for o in orders if o["status"] == "Cancelled"),
        average=(revenue / len(done) if done else 0),
        daily=bars([(short_day(d), v) for d, v in sorted(by_day.items())]),
        top=bars([(name, v["qty"]) for name, v in top_items]),
        top_rows=top_items,
    )


@app.errorhandler(413)
def too_large(_):
    flash("That photo is too big. Keep it under 8 MB.", "error")
    return redirect(request.referrer or url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
