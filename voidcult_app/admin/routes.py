"""
admin/routes.py — the full VOID CULT admin dashboard: auth, dashboard
stats, product/category/collection/coupon/order management, and the
site_settings-backed CMS that lets the owner edit homepage content,
colors, nav, footer, and policy pages without touching any template.
"""
import os
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from werkzeug.security import check_password_hash
from database import get_db
from utils.security import csrf_protect, generate_csrf_token, admin_required
from utils.helpers import slugify, unique_slug, get_settings, set_setting, inr
from utils.images import save_and_compress_image, delete_image

bp = Blueprint('admin', __name__, url_prefix='/admin')

# ---------------------------------------------------------------- AUTH
@bp.route('/login', methods=['GET', 'POST'])
@csrf_protect
def login():
    if request.method == 'POST':
        db = get_db()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = db.execute("SELECT * FROM users WHERE email=? AND is_admin=1", (email,)).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['is_admin'] = True
            return redirect(url_for('admin.dashboard'))
        flash('Invalid admin credentials.', 'error')
        return redirect(url_for('admin.login'))
    return render_template('admin/login.html', csrf_token=generate_csrf_token())

@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('admin.login'))

# ---------------------------------------------------------------- DASHBOARD
@bp.route('/')
@admin_required
def dashboard():
    db = get_db()
    today_sales = db.execute("SELECT COALESCE(SUM(total),0) as t FROM orders WHERE date(created_at)=date('now')").fetchone()['t']
    month_revenue = db.execute("SELECT COALESCE(SUM(total),0) as t FROM orders WHERE strftime('%Y-%m',created_at)=strftime('%Y-%m','now')").fetchone()['t']
    total_orders = db.execute("SELECT COUNT(*) as c FROM orders").fetchone()['c']
    pending_orders = db.execute("SELECT * FROM orders WHERE status='Pending' ORDER BY created_at DESC LIMIT 6").fetchall()
    low_stock = db.execute("SELECT * FROM products WHERE stock<=5 AND is_active=1 ORDER BY stock ASC LIMIT 6").fetchall()
    top_products = db.execute(
        """SELECT product_name, SUM(qty) as units, SUM(qty*price) as revenue
           FROM order_items GROUP BY product_name ORDER BY units DESC LIMIT 5"""
    ).fetchall()
    total_customers = db.execute("SELECT COUNT(*) as c FROM users WHERE is_admin=0").fetchone()['c']
    daily = db.execute(
        """SELECT date(created_at) as d, SUM(total) as t FROM orders
           WHERE created_at >= date('now','-13 days') GROUP BY d ORDER BY d"""
    ).fetchall()

    return render_template(
        'admin/dashboard.html',
        today_sales=today_sales, month_revenue=month_revenue, total_orders=total_orders,
        pending_orders=pending_orders, low_stock=low_stock, top_products=top_products,
        total_customers=total_customers, daily=daily, inr=inr,
    )

# ---------------------------------------------------------------- PRODUCTS
@bp.route('/products')
@admin_required
def products():
    db = get_db()
    q = request.args.get('q', '')
    rows = db.execute(
        "SELECT * FROM products WHERE name LIKE ? ORDER BY created_at DESC", (f"%{q}%",)
    ).fetchall()
    return render_template('admin/products.html', products=rows, q=q)

@bp.route('/products/new', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def product_new():
    db = get_db()
    if request.method == 'POST':
        return _save_product(db, None)
    categories = db.execute("SELECT * FROM categories").fetchall()
    collections = db.execute("SELECT * FROM collections").fetchall()
    return render_template('admin/product_form.html', product=None, images=[], sizes=[], colors=[],
                            categories=categories, collections=collections, csrf_token=generate_csrf_token())

@bp.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def product_edit(product_id):
    db = get_db()
    if request.method == 'POST':
        return _save_product(db, product_id)
    product = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    images = db.execute("SELECT * FROM product_images WHERE product_id=? ORDER BY sort_order", (product_id,)).fetchall()
    sizes = db.execute("SELECT * FROM product_sizes WHERE product_id=?", (product_id,)).fetchall()
    colors = db.execute("SELECT * FROM product_colors WHERE product_id=?", (product_id,)).fetchall()
    categories = db.execute("SELECT * FROM categories").fetchall()
    collections = db.execute("SELECT * FROM collections").fetchall()
    return render_template('admin/product_form.html', product=product, images=images, sizes=sizes, colors=colors,
                            categories=categories, collections=collections, csrf_token=generate_csrf_token())

def _save_product(db, product_id):
    f = request.form
    name = f['name'].strip()
    slug = unique_slug('products', slugify(name)) if not product_id else f.get('slug', slugify(name))
    fields = (
        name, slug, f.get('category_id') or None, f.get('collection_id') or None,
        f.get('gender', 'Unisex'), f.get('description', ''), float(f.get('price') or 0),
        float(f['discount_price']) if f.get('discount_price') else None,
        f.get('sku') or None, int(f.get('stock') or 0), f.get('fabric', ''), f.get('material', ''),
        f.get('care_instructions', ''), f.get('delivery_time', '3-5 business days'), f.get('tags', ''),
        1 if f.get('is_active') else 0,
    )
    if product_id:
        db.execute(
            """UPDATE products SET name=?, slug=?, category_id=?, collection_id=?, gender=?, description=?,
               price=?, discount_price=?, sku=?, stock=?, fabric=?, material=?, care_instructions=?,
               delivery_time=?, tags=?, is_active=? WHERE id=?""",
            fields + (product_id,)
        )
    else:
        cur = db.execute(
            """INSERT INTO products (name, slug, category_id, collection_id, gender, description, price,
               discount_price, sku, stock, fabric, material, care_instructions, delivery_time, tags, is_active)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            fields
        )
        product_id = cur.lastrowid

    # sizes: form sends size_name[] / size_stock[] parallel arrays
    db.execute("DELETE FROM product_sizes WHERE product_id=?", (product_id,))
    for sname, sstock in zip(f.getlist('size_name[]'), f.getlist('size_stock[]')):
        if sname.strip():
            db.execute("INSERT INTO product_sizes (product_id, size, stock) VALUES (?,?,?)", (product_id, sname.strip(), int(sstock or 0)))

    # colors: color_name[] / color_hex[]
    db.execute("DELETE FROM product_colors WHERE product_id=?", (product_id,))
    for cname, chex in zip(f.getlist('color_name[]'), f.getlist('color_hex[]')):
        if cname.strip():
            db.execute("INSERT INTO product_colors (product_id, color_name, hex_code) VALUES (?,?,?)", (product_id, cname.strip(), chex or '#1a1a1a'))

    # images: drag-and-drop uploaded files, auto-compressed, appended in order
    files = request.files.getlist('images[]')
    max_order = db.execute("SELECT COALESCE(MAX(sort_order),-1) as m FROM product_images WHERE product_id=?", (product_id,)).fetchone()['m']
    for i, file in enumerate(files):
        filename = save_and_compress_image(file, current_app.config['UPLOAD_FOLDER'])
        if filename:
            max_order += 1
            db.execute("INSERT INTO product_images (product_id, filename, sort_order) VALUES (?,?,?)", (product_id, filename, max_order))

    db.commit()
    flash('Product saved — live on the website now.', 'success')
    return redirect(url_for('admin.product_edit', product_id=product_id))

@bp.route('/products/<int:product_id>/delete', methods=['POST'])
@admin_required
@csrf_protect
def product_delete(product_id):
    db = get_db()
    images = db.execute("SELECT filename FROM product_images WHERE product_id=?", (product_id,)).fetchall()
    for img in images:
        delete_image(current_app.config['UPLOAD_FOLDER'], img['filename'])
    db.execute("DELETE FROM products WHERE id=?", (product_id,))
    db.commit()
    flash('Product deleted.', 'success')
    return redirect(url_for('admin.products'))

@bp.route('/products/<int:product_id>/duplicate', methods=['POST'])
@admin_required
@csrf_protect
def product_duplicate(product_id):
    db = get_db()
    p = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not p:
        return redirect(url_for('admin.products'))
    new_slug = unique_slug('products', slugify(p['name'] + '-copy'))
    cur = db.execute(
        """INSERT INTO products (name, slug, category_id, collection_id, gender, description, price,
           discount_price, sku, stock, fabric, material, care_instructions, delivery_time, tags, is_active)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
        (p['name'] + ' (Copy)', new_slug, p['category_id'], p['collection_id'], p['gender'], p['description'],
         p['price'], p['discount_price'], None, p['stock'], p['fabric'], p['material'],
         p['care_instructions'], p['delivery_time'], p['tags'])
    )
    new_id = cur.lastrowid
    for row in db.execute("SELECT * FROM product_sizes WHERE product_id=?", (product_id,)).fetchall():
        db.execute("INSERT INTO product_sizes (product_id, size, stock) VALUES (?,?,?)", (new_id, row['size'], row['stock']))
    for row in db.execute("SELECT * FROM product_colors WHERE product_id=?", (product_id,)).fetchall():
        db.execute("INSERT INTO product_colors (product_id, color_name, hex_code) VALUES (?,?,?)", (new_id, row['color_name'], row['hex_code']))
    db.commit()
    flash('Product duplicated as a draft.', 'success')
    return redirect(url_for('admin.product_edit', product_id=new_id))

@bp.route('/products/bulk-delete', methods=['POST'])
@admin_required
@csrf_protect
def products_bulk_delete():
    ids = request.form.getlist('product_ids[]')
    db = get_db()
    for pid in ids:
        db.execute("DELETE FROM products WHERE id=?", (pid,))
    db.commit()
    flash(f'{len(ids)} product(s) deleted.', 'success')
    return redirect(url_for('admin.products'))

@bp.route('/products/image/<int:image_id>/delete', methods=['POST'])
@admin_required
@csrf_protect
def product_image_delete(image_id):
    db = get_db()
    img = db.execute("SELECT * FROM product_images WHERE id=?", (image_id,)).fetchone()
    if img:
        delete_image(current_app.config['UPLOAD_FOLDER'], img['filename'])
        db.execute("DELETE FROM product_images WHERE id=?", (image_id,))
        db.commit()
    return jsonify({'ok': True})

@bp.route('/products/image/reorder', methods=['POST'])
@admin_required
@csrf_protect
def product_image_reorder():
    db = get_db()
    order = request.json.get('order', [])  # list of image ids in new order
    for i, image_id in enumerate(order):
        db.execute("UPDATE product_images SET sort_order=? WHERE id=?", (i, image_id))
    db.commit()
    return jsonify({'ok': True})

# ---------------------------------------------------------------- CATEGORIES
@bp.route('/categories', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def categories():
    db = get_db()
    if request.method == 'POST':
        name = request.form['name'].strip()
        db.execute("INSERT INTO categories (name, slug, gender) VALUES (?,?,?)",
                   (name, unique_slug('categories', slugify(name)), request.form.get('gender', 'Unisex')))
        db.commit()
        flash('Category added.', 'success')
        return redirect(url_for('admin.categories'))
    rows = db.execute(
        "SELECT c.*, (SELECT COUNT(*) FROM products WHERE category_id=c.id) as product_count FROM categories c"
    ).fetchall()
    return render_template('admin/categories.html', categories=rows, csrf_token=generate_csrf_token())

@bp.route('/categories/<int:cat_id>/delete', methods=['POST'])
@admin_required
@csrf_protect
def category_delete(cat_id):
    db = get_db()
    db.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    db.commit()
    flash('Category deleted.', 'success')
    return redirect(url_for('admin.categories'))

# ---------------------------------------------------------------- COLLECTIONS
@bp.route('/collections', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def collections():
    db = get_db()
    if request.method == 'POST':
        name = request.form['name'].strip()
        db.execute(
            "INSERT INTO collections (name, slug, type, description, is_featured, is_active, scheduled_at) VALUES (?,?,?,?,?,?,?)",
            (name, unique_slug('collections', slugify(name)), request.form.get('type', 'Featured'),
             request.form.get('description', ''), 1 if request.form.get('is_featured') else 0,
             1 if request.form.get('is_active') else 0, request.form.get('scheduled_at') or None)
        )
        db.commit()
        flash('Collection created.', 'success')
        return redirect(url_for('admin.collections'))
    rows = db.execute(
        "SELECT c.*, (SELECT COUNT(*) FROM products WHERE collection_id=c.id) as product_count FROM collections c"
    ).fetchall()
    return render_template('admin/collections.html', collections=rows, csrf_token=generate_csrf_token())

@bp.route('/collections/<int:coll_id>/toggle', methods=['POST'])
@admin_required
@csrf_protect
def collection_toggle(coll_id):
    db = get_db()
    db.execute("UPDATE collections SET is_active = 1 - is_active WHERE id=?", (coll_id,))
    db.commit()
    return redirect(url_for('admin.collections'))

@bp.route('/collections/<int:coll_id>/delete', methods=['POST'])
@admin_required
@csrf_protect
def collection_delete(coll_id):
    db = get_db()
    db.execute("DELETE FROM collections WHERE id=?", (coll_id,))
    db.commit()
    flash('Collection deleted.', 'success')
    return redirect(url_for('admin.collections'))

# ---------------------------------------------------------------- ORDERS
@bp.route('/orders')
@admin_required
def orders():
    db = get_db()
    status = request.args.get('status', '')
    query = "SELECT * FROM orders"
    params = []
    if status:
        query += " WHERE status=?"
        params.append(status)
    query += " ORDER BY created_at DESC"
    rows = db.execute(query, params).fetchall()
    return render_template('admin/orders.html', orders=rows, status=status, inr=inr)

@bp.route('/orders/<int:order_id>')
@admin_required
def order_detail(order_id):
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    items = db.execute("SELECT * FROM order_items WHERE order_id=?", (order_id,)).fetchall()
    return render_template('admin/order_detail.html', order=order, items=items, csrf_token=generate_csrf_token(), inr=inr)

@bp.route('/orders/<int:order_id>/update', methods=['POST'])
@admin_required
@csrf_protect
def order_update(order_id):
    db = get_db()
    db.execute(
        "UPDATE orders SET status=?, tracking_number=? WHERE id=?",
        (request.form.get('status'), request.form.get('tracking_number', ''), order_id)
    )
    db.commit()
    flash('Order updated.', 'success')
    return redirect(url_for('admin.order_detail', order_id=order_id))

@bp.route('/orders/<int:order_id>/invoice')
@admin_required
def order_invoice(order_id):
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    items = db.execute("SELECT * FROM order_items WHERE order_id=?", (order_id,)).fetchall()
    return render_template('admin/invoice.html', order=order, items=items, inr=inr)

# ---------------------------------------------------------------- CUSTOMERS
@bp.route('/customers')
@admin_required
def customers():
    db = get_db()
    rows = db.execute(
        """SELECT u.*, COUNT(o.id) as order_count, COALESCE(SUM(o.total),0) as total_spent
           FROM users u LEFT JOIN orders o ON o.user_id=u.id
           WHERE u.is_admin=0 GROUP BY u.id ORDER BY u.created_at DESC"""
    ).fetchall()
    return render_template('admin/customers.html', customers=rows, inr=inr)

# ---------------------------------------------------------------- COUPONS
@bp.route('/coupons', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def coupons():
    db = get_db()
    if request.method == 'POST':
        db.execute(
            "INSERT INTO coupons (code, type, value, min_order, usage_limit, expiry) VALUES (?,?,?,?,?,?)",
            (request.form['code'].upper(), request.form.get('type', 'percentage'), float(request.form['value']),
             float(request.form.get('min_order') or 0), request.form.get('usage_limit') or None,
             request.form.get('expiry') or None)
        )
        db.commit()
        flash('Coupon created.', 'success')
        return redirect(url_for('admin.coupons'))
    rows = db.execute("SELECT * FROM coupons ORDER BY id DESC").fetchall()
    return render_template('admin/coupons.html', coupons=rows, csrf_token=generate_csrf_token(), inr=inr)

@bp.route('/coupons/<int:coupon_id>/toggle', methods=['POST'])
@admin_required
@csrf_protect
def coupon_toggle(coupon_id):
    db = get_db()
    db.execute("UPDATE coupons SET active = 1 - active WHERE id=?", (coupon_id,))
    db.commit()
    return redirect(url_for('admin.coupons'))

@bp.route('/coupons/<int:coupon_id>/delete', methods=['POST'])
@admin_required
@csrf_protect
def coupon_delete(coupon_id):
    db = get_db()
    db.execute("DELETE FROM coupons WHERE id=?", (coupon_id,))
    db.commit()
    return redirect(url_for('admin.coupons'))

# ---------------------------------------------------------------- REVIEWS
@bp.route('/reviews')
@admin_required
def reviews():
    db = get_db()
    rows = db.execute(
        "SELECT r.*, p.name as product_name FROM reviews r JOIN products p ON p.id=r.product_id ORDER BY r.created_at DESC"
    ).fetchall()
    return render_template('admin/reviews.html', reviews=rows, csrf_token=generate_csrf_token())

@bp.route('/reviews/<int:review_id>/approve', methods=['POST'])
@admin_required
@csrf_protect
def review_approve(review_id):
    db = get_db()
    db.execute("UPDATE reviews SET approved=1 WHERE id=?", (review_id,))
    db.commit()
    return redirect(url_for('admin.reviews'))

@bp.route('/reviews/<int:review_id>/delete', methods=['POST'])
@admin_required
@csrf_protect
def review_delete(review_id):
    db = get_db()
    db.execute("DELETE FROM reviews WHERE id=?", (review_id,))
    db.commit()
    return redirect(url_for('admin.reviews'))

# ---------------------------------------------------------------- MEDIA LIBRARY
@bp.route('/media', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def media():
    folder = request.args.get('folder', 'hero')
    upload_dir = os.path.join(current_app.config['SITE_UPLOAD_FOLDER'], folder)
    if request.method == 'POST':
        files = request.files.getlist('files[]')
        for file in files:
            save_and_compress_image(file, upload_dir)
        flash(f'{len(files)} file(s) uploaded and compressed.', 'success')
        return redirect(url_for('admin.media', folder=folder))
    os.makedirs(upload_dir, exist_ok=True)
    files = sorted(os.listdir(upload_dir))
    return render_template('admin/media.html', folder=folder, files=files, csrf_token=generate_csrf_token())

@bp.route('/media/<folder>/<filename>/delete', methods=['POST'])
@admin_required
@csrf_protect
def media_delete(folder, filename):
    path = os.path.join(current_app.config['SITE_UPLOAD_FOLDER'], folder, filename)
    if os.path.exists(path):
        os.remove(path)
    return redirect(url_for('admin.media', folder=folder))

# ---------------------------------------------------------------- SETTINGS / CMS
@bp.route('/settings', methods=['GET', 'POST'])
@admin_required
@csrf_protect
def settings():
    if request.method == 'POST':
        for key in request.form:
            if key != 'csrf_token':
                set_setting(key, request.form[key])
        flash('Settings saved — changes are live on the website now.', 'success')
        return redirect(url_for('admin.settings'))
    return render_template('admin/settings.html', settings=get_settings(), csrf_token=generate_csrf_token())

@bp.route('/staff')
@admin_required
def staff():
    db = get_db()
    rows = db.execute("SELECT * FROM users WHERE is_admin=1").fetchall()
    return render_template('admin/staff.html', staff=rows)
