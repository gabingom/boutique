import os, json, uuid
from datetime import datetime
from urllib.parse import quote, quote_plus
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, flash)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()  # lit le fichier .env (local)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-change-me")
# Sur Render : DATABASE_URL est fournie automatiquement (PostgreSQL).
# En local : on utilise les variables DB_* (même format que Laravel).
db_url = os.getenv("DATABASE_URL")
if not db_url:
    driver = {"mysql": "mysql+pymysql", "pgsql": "postgresql"}.get(
        os.getenv("DB_CONNECTION", "mysql"), "mysql+pymysql")
    db_url = "{}://{}:{}@{}:{}/{}".format(
        driver,
        quote_plus(os.getenv("DB_USERNAME", "root")),
        quote_plus(os.getenv("DB_PASSWORD", "")),
        os.getenv("DB_HOST", "127.0.0.1"),
        os.getenv("DB_PORT", "3306"),
        os.getenv("DB_DATABASE", "boutique"))
    if driver.startswith("mysql"):
        db_url += "?charset=utf8mb4"
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024
db = SQLAlchemy(app)
UPLOAD_DIR = os.path.join(app.root_path, "static", "uploads")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    sizes = db.Column(db.String(200), default="")
    description = db.Column(db.Text, default="")
    image_url = db.Column(db.String(500))
    audio_url = db.Column(db.String(500))
    available = db.Column(db.Boolean, default=True)
    created = db.Column(db.DateTime, default=datetime.utcnow)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    phone = db.Column(db.String(40))
    address = db.Column(db.String(300))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    payment = db.Column(db.String(40), default="Paiement à la livraison")
    items = db.Column(db.Text)
    total = db.Column(db.Integer)
    status = db.Column(db.String(30), default="Nouvelle")
    created = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def items_list(self):
        return json.loads(self.items or "[]")


class Setting(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(300))


DEFAULTS = {"shop_name": "Ma Boutique", "whatsapp": "", "phone": "",
            "address": "", "currency": "FCFA"}


def get_settings():
    s = dict(DEFAULTS)
    s.update({x.key: x.value for x in Setting.query.all()})
    return s


def digits(v):
    return "".join(c for c in (v or "") if c.isdigit())


def save_file(f, kind):
    if not f or not f.filename:
        return None
    if os.getenv("CLOUDINARY_URL"):
        import cloudinary.uploader
        r = cloudinary.uploader.upload(
            f, resource_type="image" if kind == "image" else "video")
        return r["secure_url"]
    ext = os.path.splitext(secure_filename(f.filename))[1] or \
        (".webm" if kind == "audio" else ".jpg")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    name = uuid.uuid4().hex + ext
    f.save(os.path.join(UPLOAD_DIR, name))
    return url_for("static", filename="uploads/" + name)


def admin_required(fn):
    @wraps(fn)
    def w(*a, **k):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return fn(*a, **k)
    return w


# ---------- Côté acheteur ----------
@app.route("/")
def index():
    products = Product.query.filter_by(available=True)\
        .order_by(Product.created.desc()).all()
    return render_template("index.html", products=products, s=get_settings())


@app.route("/order", methods=["POST"])
def order():
    d = request.get_json(force=True)
    s = get_settings()
    items, total = [], 0
    for it in d.get("items", []):
        p = db.session.get(Product, int(it["id"]))
        if not p or not p.available:
            continue
        qty = max(1, int(it.get("qty", 1)))
        items.append({"name": p.name, "size": it.get("size", ""),
                      "qty": qty, "price": p.price})
        total += p.price * qty
    if not items or not d.get("name") or not d.get("phone"):
        return jsonify(ok=False, error="Panier ou coordonnées manquants"), 400
    o = Order(name=d["name"][:120], phone=d["phone"][:40],
              address=(d.get("address") or "")[:300],
              lat=d.get("lat"), lng=d.get("lng"),
              items=json.dumps(items, ensure_ascii=False), total=total)
    db.session.add(o)
    db.session.commit()
    lines = [f"Nouvelle commande #{o.id}"]
    lines += [f"- {i['name']} {('(' + i['size'] + ')') if i['size'] else ''}"
              f" x{i['qty']} = {i['price'] * i['qty']} {s['currency']}"
              for i in items]
    lines += [f"Total : {total} {s['currency']} (paiement à la livraison)",
              f"Client : {o.name} - {o.phone}", f"Adresse : {o.address}"]
    if o.lat and o.lng:
        lines.append(f"Position : https://maps.google.com/?q={o.lat},{o.lng}")
    wa = f"https://wa.me/{digits(s['whatsapp'])}?text={quote(chr(10).join(lines))}"
    return jsonify(ok=True, id=o.id, whatsapp=wa)


# ---------- Côté admin ----------
@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin"))
        flash("Mot de passe incorrect")
    return render_template("login.html", s=get_settings())


@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def admin():
    return render_template("admin.html", s=get_settings(),
                           products=Product.query.order_by(Product.created.desc()).all())


@app.route("/admin/product", methods=["POST"])
@admin_required
def add_product():
    f = request.form
    p = Product(name=f["name"], price=int(f["price"] or 0), sizes=f.get("sizes", ""),
                description=f.get("description", ""),
                image_url=save_file(request.files.get("image"), "image"),
                audio_url=save_file(request.files.get("audio"), "audio"))
    db.session.add(p)
    db.session.commit()
    return redirect(url_for("admin"))


@app.route("/admin/product/<int:pid>/delete", methods=["POST"])
@admin_required
def delete_product(pid):
    p = db.session.get(Product, pid)
    if p:
        db.session.delete(p)
        db.session.commit()
    return redirect(url_for("admin"))


@app.route("/admin/product/<int:pid>/toggle", methods=["POST"])
@admin_required
def toggle_product(pid):
    p = db.session.get(Product, pid)
    if p:
        p.available = not p.available
        db.session.commit()
    return redirect(url_for("admin"))


@app.route("/admin/settings", methods=["POST"])
@admin_required
def save_settings():
    for k in DEFAULTS:
        v = request.form.get(k, "").strip()
        row = db.session.get(Setting, k)
        if row:
            row.value = v
        else:
            db.session.add(Setting(key=k, value=v))
    db.session.commit()
    return redirect(url_for("admin"))


@app.route("/admin/orders")
@admin_required
def orders():
    return render_template("orders.html", s=get_settings(),
                           orders=Order.query.order_by(Order.created.desc()).all())


@app.route("/admin/orders/<int:oid>/status", methods=["POST"])
@admin_required
def order_status(oid):
    o = db.session.get(Order, oid)
    if o:
        o.status = request.form.get("status", o.status)
        db.session.commit()
    return redirect(url_for("orders"))


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)