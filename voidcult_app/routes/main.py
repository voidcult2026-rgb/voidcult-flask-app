"""routes/main.py — storefront: home, shop listing, product detail, search, static pages."""
from flask import Blueprint, render_template, request, session, jsonify
from database import get_db
from utils.helpers import get_settings, get_setting
from utils.security import current_user

bp = Blueprint('main', __name__)

def _product_card_data(db, rows):
    """Attach primary image + color swatches to a list of product rows."""
    products = []
    for p in rows:
        img = db.execute(
            "SELECT filename FROM product_images WHERE product_id=? ORDER BY sort_order LIMIT 1", (p['id'],)
        ).fetchone()
        colors = db.execute("SELECT hex_code FROM product_colors WHERE product_id=?", (p['id'],)).fetchall()
        products.append({
            'row': p,
            'image': img['filename'] if img else None,
            'colors': [c['hex_code'] for c in colors],
        })
    return products

@bp.route('/')
def home():
    db = get_db()
    gender = session.get('preferred_gender', 'Men')
    featured_collections = db.execute(
        "SELECT * FROM collections WHERE is_active=1 AND is_featured=1 LIMIT 4"
    ).fetchall()
    bestsellers = db.execute(
        "SELECT * FROM products WHERE is_active=1 AND (gender=? OR gender='Unisex') ORDER BY created_at DESC LIMIT 8",
        (gender,)
    ).fetchall()
    categories = db.execute("SELECT * FROM categories LIMIT 6").fetchall()
    reviews = db.execute(
        "SELECT r.*, p.name as product_name FROM reviews r JOIN products p ON p.id=r.product_id "
        "WHERE r.approved=1 ORDER BY r.created_at DESC LIMIT 6"
    ).fetchall()
    return render_template(
        'index.html',
        settings=get_settings(),
        gender=gender,
        collections=featured_collections,
        products=_product_card_data(db, bestsellers),
        categories=categories,
        reviews=reviews,
    )

@bp.route('/set-gender/<gender>')
def set_gender(gender):
    if gender in ('Men', 'Women'):
        session['preferred_gender'] = gender
    return jsonify({'ok': True, 'gender': session.get('preferred_gender', 'Men')})

@bp.route('/shop')
def shop():
    db = get_db()
    gender = request.args.get('gender', '')
    category = request.args.get('category', '')
    collection = request.args.get('collection', '')
    color = request.args.get('color', '')
    size = request.args.get('size', '')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    q = request.args.get('q', '').strip()
    sort = request.args.get('sort', 'newest')

    query = "SELECT DISTINCT p.* FROM products p"
    joins = []
    where = ["p.is_active=1"]
    params = []

    if color:
        joins.append("JOIN product_colors pc ON pc.product_id=p.id")
        where.append("pc.color_name=?")
        params.append(color)
    if size:
        joins.append("JOIN product_sizes ps ON ps.product_id=p.id")
        where.append("ps.size=? AND ps.stock>0")
        params.append(size)
    if gender:
        where.append("(p.gender=? OR p.gender='Unisex')")
        params.append(gender)
    if category:
        where.append("p.category_id=(SELECT id FROM categories WHERE slug=?)")
        params.append(category)
    if collection:
        where.append("p.collection_id=(SELECT id FROM collections WHERE slug=?)")
        params.append(collection)
    if min_price is not None:
        where.append("COALESCE(p.discount_price,p.price)>=?")
        params.append(min_price)
    if max_price is not None:
        where.append("COALESCE(p.discount_price,p.price)<=?")
        params.append(max_price)
    if q:
        where.append("(p.name LIKE ? OR p.tags LIKE ?)")
        params.append(f"%{q}%"); params.append(f"%{q}%")

    query += " " + " ".join(joins)
    query += " WHERE " + " AND ".join(where)
    if sort == 'price_low':
        query += " ORDER BY COALESCE(p.discount_price,p.price) ASC"
    elif sort == 'price_high':
        query += " ORDER BY COALESCE(p.discount_price,p.price) DESC"
    elif sort == 'newest':
        query += " ORDER BY p.created_at DESC"

    rows = db.execute(query, params).fetchall()
    categories = db.execute("SELECT * FROM categories").fetchall()
    collections = db.execute("SELECT * FROM collections WHERE is_active=1").fetchall()

    return render_template(
        'shop.html',
        settings=get_settings(),
        products=_product_card_data(db, rows),
        categories=categories,
        collections=collections,
        filters=request.args,
    )

@bp.route('/product/<slug>')
def product_detail(slug):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE slug=? AND is_active=1", (slug,)).fetchone()
    if not product:
        return render_template('404.html'), 404
    images = db.execute("SELECT * FROM product_images WHERE product_id=? ORDER BY sort_order", (product['id'],)).fetchall()
    sizes = db.execute("SELECT * FROM product_sizes WHERE product_id=?", (product['id'],)).fetchall()
    colors = db.execute("SELECT * FROM product_colors WHERE product_id=?", (product['id'],)).fetchall()
    reviews = db.execute(
        "SELECT * FROM reviews WHERE product_id=? AND approved=1 ORDER BY created_at DESC", (product['id'],)
    ).fetchall()
    related = db.execute(
        "SELECT * FROM products WHERE category_id=? AND id!=? AND is_active=1 LIMIT 4",
        (product['category_id'], product['id'])
    ).fetchall()

    # recently viewed (session-based)
    viewed = session.get('recently_viewed', [])
    if product['id'] in viewed:
        viewed.remove(product['id'])
    viewed.insert(0, product['id'])
    session['recently_viewed'] = viewed[:8]

    avg_rating = None
    if reviews:
        avg_rating = round(sum(r['rating'] for r in reviews) / len(reviews), 1)

    return render_template(
        'product_detail.html',
        settings=get_settings(),
        product=product, images=images, sizes=sizes, colors=colors,
        reviews=reviews, avg_rating=avg_rating,
        related=_product_card_data(db, related),
    )

@bp.route('/api/search-suggest')
def search_suggest():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    db = get_db()
    rows = db.execute(
        "SELECT name, slug FROM products WHERE is_active=1 AND name LIKE ? LIMIT 6", (f"%{q}%",)
    ).fetchall()
    return jsonify([{'name': r['name'], 'slug': r['slug']} for r in rows])

@bp.route('/wishlist/toggle/<int:product_id>', methods=['POST'])
def wishlist_toggle(product_id):
    user = current_user()
    if not user:
        return jsonify({'ok': False, 'error': 'login_required'}), 401
    db = get_db()
    existing = db.execute("SELECT id FROM wishlist WHERE user_id=? AND product_id=?", (user['id'], product_id)).fetchone()
    if existing:
        db.execute("DELETE FROM wishlist WHERE id=?", (existing['id'],))
        db.commit()
        return jsonify({'ok': True, 'active': False})
    db.execute("INSERT INTO wishlist (user_id, product_id) VALUES (?,?)", (user['id'], product_id))
    db.commit()
    return jsonify({'ok': True, 'active': True})

@bp.route('/about')
def about():
    return render_template('page_static.html', settings=get_settings(), title='About', content_key='about_content')

@bp.route('/contact')
def contact():
    return render_template('page_static.html', settings=get_settings(), title='Contact', content_key=None)

@bp.route('/faqs')
def faqs():
    return render_template('page_static.html', settings=get_settings(), title='FAQs', content_key='faqs')

@bp.route('/shipping-policy')
def shipping_policy():
    return render_template('page_static.html', settings=get_settings(), title='Shipping Policy', content_key='shipping_policy')

@bp.route('/return-policy')
def return_policy():
    return render_template('page_static.html', settings=get_settings(), title='Return Policy', content_key='return_policy')

@bp.route('/privacy-policy')
def privacy_policy():
    return render_template('page_static.html', settings=get_settings(), title='Privacy Policy', content_key='privacy_policy')

@bp.route('/terms')
def terms():
    return render_template('page_static.html', settings=get_settings(), title='Terms of Service', content_key='terms_of_service')
