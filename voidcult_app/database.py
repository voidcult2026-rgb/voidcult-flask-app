"""
database.py — SQLite connection handling + initialization for VOID CULT.

Uses Python's built-in sqlite3 (no external DB driver needed). Every query
in this project goes through get_db(), so migrating to MySQL later means
swapping this one file for a PyMySQL/mysql-connector equivalent — the SQL
itself is written to be portable.
"""
import sqlite3
import os
from flask import g, current_app

def get_db():
    """Return a request-scoped SQLite connection with row access by column name."""
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE_PATH'])
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db(app):
    """Create tables (if missing) and seed default content. Called once at startup."""
    db_path = app.config['DATABASE_PATH']
    first_run = not os.path.exists(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    with open(os.path.join(os.path.dirname(__file__), 'schema.sql')) as f:
        conn.executescript(f.read())
    conn.commit()

    if first_run:
        _seed(conn)
        conn.commit()
    conn.close()

def _seed(conn):
    """Populate first-run demo data: admin account, settings, categories, sample products."""
    from werkzeug.security import generate_password_hash

    # --- default admin account ---
    conn.execute(
        "INSERT INTO users (name, email, password_hash, is_admin, email_verified) VALUES (?,?,?,1,1)",
        ("VOID CULT Admin", "admin@voidcult.com", generate_password_hash("ChangeMe123!"))
    )

    # --- site settings (everything the admin CMS can edit) ---
    defaults = {
        "site_name": "VOID CULT",
        "hero_eyebrow": "Chapter 04 — Luxury Streetwear",
        "hero_title": "ENTER THE VOID",
        "hero_subtitle": "Streetwear stripped down to structure and shadow. No color. No noise.",
        "hero_cta_text": "Shop Now",
        "hero_image": "",
        "announcement_text": "FREE SHIPPING OVER ₹4000 — NEW DROP CHAPTER 04 — NO RESTOCKS",
        "color_primary": "#000000",
        "color_purple_dark": "#1A0826",
        "color_purple_glow": "#6A0DAD",
        "color_white": "#FFFFFF",
        "color_gray": "#A9A9A9",
        "footer_text": "VOID CULT is luxury streetwear built in black and dark violet — one limited drop at a time.",
        "contact_email": "support@voidcult.com",
        "contact_phone": "+91 90000 00000",
        "instagram_url": "https://instagram.com",
        "about_content": "VOID CULT was founded on the idea that restraint is its own kind of loud. We design in black and negative space, run limited drops, and never restock a sold-out pattern.",
        "shipping_policy": "Orders ship within 24-48 hours. Delivery in 3-5 business days across India. Free shipping over ₹4000.",
        "return_policy": "Returns accepted within 7 days of delivery, unworn and with tags attached. Refunds processed within 5-7 business days.",
        "privacy_policy": "We collect only what's needed to process your order and never sell your data to third parties.",
        "terms_of_service": "By using this site you agree to our standard terms of sale, including our shipping and return policies.",
        "faqs": "Q: How long does delivery take?\nA: 3-5 business days across India.\n\nQ: Do you restock sold-out items?\nA: No — every VOID CULT drop is limited and final.",
        "razorpay_key_id": "",
        "razorpay_key_secret": "",
        "stripe_publishable_key": "",
        "stripe_secret_key": "",
    }
    for k, v in defaults.items():
        conn.execute("INSERT OR IGNORE INTO site_settings (key, value) VALUES (?,?)", (k, v))

    # --- categories ---
    categories = [
        ("Hoodies", "hoodies", "Unisex"), ("T-Shirts", "t-shirts", "Unisex"),
        ("Cargo", "cargo", "Men"), ("Pants", "pants", "Unisex"),
        ("Shirts", "shirts", "Unisex"), ("Oversized", "oversized", "Unisex"),
        ("Accessories", "accessories", "Unisex"), ("Outerwear", "outerwear", "Unisex"),
    ]
    for name, slug, gender in categories:
        conn.execute("INSERT OR IGNORE INTO categories (name, slug, gender) VALUES (?,?,?)", (name, slug, gender))

    # --- collections ---
    collections = [
        ("Heavyweight Outerwear", "heavyweight-outerwear", "Featured", "14 pieces built for cold weather.", 1),
        ("Cargo & Utility", "cargo-utility", "Season", "Utilitarian silhouettes for Men.", 1),
        ("Chapter 04 — Limited", "chapter-04-limited", "Limited Edition", "6 pieces. No restock.", 1),
        ("Oversized Tailoring", "oversized-tailoring", "Featured", "Sharp cuts in negative space for Women.", 1),
    ]
    for name, slug, ctype, desc, feat in collections:
        conn.execute(
            "INSERT OR IGNORE INTO collections (name, slug, type, description, is_featured) VALUES (?,?,?,?,?)",
            (name, slug, ctype, desc, feat)
        )

    # --- sample products ---
    products = [
        ("Oversized Void Hoodie", "oversized-void-hoodie", 1, 1, "Men", 3400, 4200, "VC-HD-001", 12,
         "100% Cotton Fleece", "Heavyweight Fleece", "Cold wash, do not tumble dry", "streetwear,hoodie,bestseller",
         "19oz brushed cotton fleece, cut for an oversized drape. Ribbed cuffs and hem, kangaroo pocket, garment-dyed for a worn-in tone from day one."),
        ("Structured Cargo Pant", "structured-cargo-pant", 3, 2, "Men", 2800, None, "VC-CG-002", 48,
         "Cotton Twill", "Heavy Twill", "Machine wash cold", "cargo,utility",
         "Six-pocket cargo trouser in heavy cotton twill, tapered leg, adjustable ankle cuffs."),
        ("Oversized Blazer", "oversized-blazer", 5, 4, "Women", 4800, 5800, "VC-BZ-010", 9,
         "Wool Blend", "Structured Wool Blend", "Dry clean only", "tailoring,blazer",
         "Sharp-shouldered oversized blazer, fully lined, single-button close."),
        ("Ribbed Merino Crewneck", "ribbed-merino-crewneck", 1, 1, "Unisex", 2100, None, "VC-KN-003", 30,
         "100% Merino Wool", "Fine Knit", "Hand wash cold, dry flat", "knitwear,essentials",
         "Fine-gauge merino crewneck with a ribbed trim. Sits close without clinging."),
        ("Wool Trench", "wool-trench", 8, 1, "Men", 7200, None, "VC-WT-004", 0,
         "Wool Blend", "Heavyweight Wool", "Dry clean only", "outerwear,limited",
         "Floor-sweeping wool trench, belted waist, storm flap. Limited run of 20."),
        ("Ribbed Slip Dress", "ribbed-slip-dress", 2, 4, "Women", 3200, None, "VC-DR-004", 15,
         "Viscose Rib Knit", "Rib Knit", "Hand wash cold", "dress,essentials",
         "Bias-cut slip dress in ribbed viscose, adjustable straps."),
    ]
    for (name, slug, cat_id, coll_id, gender, price, discount, sku, stock, fabric, material, care, tags, desc) in products:
        cur = conn.execute(
            """INSERT OR IGNORE INTO products
               (name, slug, category_id, collection_id, gender, description, price, discount_price,
                sku, stock, fabric, material, care_instructions, tags)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (name, slug, cat_id, coll_id, gender, desc, price, discount, sku, stock, fabric, material, care, tags)
        )
        pid = cur.lastrowid
        if pid:
            for size in ["S", "M", "L", "XL"]:
                conn.execute("INSERT INTO product_sizes (product_id, size, stock) VALUES (?,?,?)", (pid, size, stock // 4 + 3))
            conn.execute("INSERT INTO product_colors (product_id, color_name, hex_code) VALUES (?,?,?)", (pid, "Jet Black", "#141414"))
            conn.execute("INSERT INTO product_colors (product_id, color_name, hex_code) VALUES (?,?,?)", (pid, "Void Purple", "#6A0DAD"))

    # --- a couple of coupons ---
    conn.execute("INSERT OR IGNORE INTO coupons (code, type, value, min_order) VALUES ('VOID20','percentage',20,2000)")
    conn.execute("INSERT OR IGNORE INTO coupons (code, type, value, min_order) VALUES ('WELCOME300','flat',300,1500)")
