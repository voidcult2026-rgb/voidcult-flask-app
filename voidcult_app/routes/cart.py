"""
routes/cart.py — session-based shopping cart, coupon application, and
checkout (Cash on Delivery fully functional; Razorpay/Stripe wired to real
REST APIs but require live keys entered in Admin > Settings to activate).
"""
import requests
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from database import get_db
from utils.security import csrf_protect, generate_csrf_token, current_user
from utils.helpers import generate_order_number, get_setting, inr

bp = Blueprint('cart', __name__)

def _cart():
    return session.setdefault('cart', [])

def _cart_totals(cart):
    subtotal = sum(item['price'] * item['qty'] for item in cart)
    discount = session.get('coupon_discount', 0)
    shipping = 0 if subtotal >= 4000 or subtotal == 0 else 150
    total = max(subtotal - discount + shipping, 0)
    return subtotal, discount, shipping, total

@bp.route('/cart')
def view_cart():
    cart = _cart()
    subtotal, discount, shipping, total = _cart_totals(cart)
    return render_template(
        'cart.html', cart=cart, subtotal=subtotal, discount=discount, shipping=shipping, total=total,
        coupon_code=session.get('coupon_code'), csrf_token=generate_csrf_token(), inr=inr
    )

@bp.route('/cart/add', methods=['POST'])
@csrf_protect
def add_to_cart():
    db = get_db()
    product_id = int(request.form['product_id'])
    size = request.form.get('size', '')
    color = request.form.get('color', '')
    qty = max(int(request.form.get('qty', 1)), 1)

    product = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not product:
        return jsonify({'ok': False, 'error': 'Product not found'}), 404

    image = db.execute("SELECT filename FROM product_images WHERE product_id=? ORDER BY sort_order LIMIT 1", (product_id,)).fetchone()
    price = product['discount_price'] or product['price']

    cart = _cart()
    for item in cart:
        if item['product_id'] == product_id and item['size'] == size and item['color'] == color:
            item['qty'] += qty
            break
    else:
        cart.append({
            'product_id': product_id, 'name': product['name'], 'price': price,
            'qty': qty, 'size': size, 'color': color,
            'image': image['filename'] if image else None,
        })
    session['cart'] = cart
    session.modified = True
    return jsonify({'ok': True, 'cart_count': sum(i['qty'] for i in cart)})

@bp.route('/cart/update', methods=['POST'])
@csrf_protect
def update_cart():
    idx = int(request.form['index'])
    qty = max(int(request.form.get('qty', 1)), 0)
    cart = _cart()
    if 0 <= idx < len(cart):
        if qty == 0:
            cart.pop(idx)
        else:
            cart[idx]['qty'] = qty
    session['cart'] = cart
    session.modified = True
    return redirect(url_for('cart.view_cart'))

@bp.route('/cart/apply-coupon', methods=['POST'])
@csrf_protect
def apply_coupon():
    code = request.form.get('code', '').strip().upper()
    db = get_db()
    cart = _cart()
    subtotal, _, _, _ = _cart_totals(cart)
    coupon = db.execute("SELECT * FROM coupons WHERE code=? AND active=1", (code,)).fetchone()

    if not coupon:
        flash('Invalid coupon code.', 'error')
    elif subtotal < coupon['min_order']:
        flash(f"This coupon needs a minimum order of ₹{inr(coupon['min_order'])}.", 'error')
    elif coupon['usage_limit'] and coupon['used_count'] >= coupon['usage_limit']:
        flash('This coupon has reached its usage limit.', 'error')
    else:
        discount = subtotal * (coupon['value'] / 100) if coupon['type'] == 'percentage' else coupon['value']
        session['coupon_code'] = code
        session['coupon_discount'] = round(min(discount, subtotal), 2)
        flash(f'Coupon {code} applied.', 'success')
    return redirect(url_for('cart.view_cart'))

@bp.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart = _cart()
    if not cart:
        flash('Your bag is empty.', 'error')
        return redirect(url_for('cart.view_cart'))
    subtotal, discount, shipping, total = _cart_totals(cart)
    user = current_user()

    razorpay_enabled = bool(get_setting('razorpay_key_id') and get_setting('razorpay_key_secret'))
    stripe_enabled = bool(get_setting('stripe_secret_key'))

    if request.method == 'POST':
        payment_method = request.form.get('payment_method', 'COD')
        db = get_db()
        order_number = generate_order_number()

        db.execute(
            """INSERT INTO orders (order_number, user_id, status, payment_method, payment_status,
               subtotal, discount, shipping, total, coupon_code,
               address_name, address_line1, address_city, address_state, address_pincode, address_phone)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (order_number, user['id'] if user else None, 'Pending', payment_method,
             'Paid' if payment_method != 'COD' else 'Unpaid',
             subtotal, discount, shipping, total, session.get('coupon_code'),
             request.form.get('full_name'), request.form.get('line1'), request.form.get('city'),
             request.form.get('state'), request.form.get('pincode'), request.form.get('phone'))
        )
        order_id = db.execute("SELECT id FROM orders WHERE order_number=?", (order_number,)).fetchone()['id']

        for item in cart:
            db.execute(
                "INSERT INTO order_items (order_id, product_id, product_name, price, qty, size, color) VALUES (?,?,?,?,?,?,?)",
                (order_id, item['product_id'], item['name'], item['price'], item['qty'], item['size'], item['color'])
            )
            db.execute("UPDATE products SET stock = MAX(stock - ?, 0) WHERE id=?", (item['qty'], item['product_id']))

        if session.get('coupon_code'):
            db.execute("UPDATE coupons SET used_count = used_count + 1 WHERE code=?", (session['coupon_code'],))

        db.commit()
        session['cart'] = []
        session.pop('coupon_code', None)
        session.pop('coupon_discount', None)
        return redirect(url_for('cart.order_success', order_number=order_number))

    return render_template(
        'checkout.html', cart=cart, subtotal=subtotal, discount=discount, shipping=shipping, total=total,
        user=user, csrf_token=generate_csrf_token(), inr=inr,
        razorpay_enabled=razorpay_enabled, stripe_enabled=stripe_enabled,
        razorpay_key_id=get_setting('razorpay_key_id'),
    )

@bp.route('/checkout/create-razorpay-order', methods=['POST'])
@csrf_protect
def create_razorpay_order():
    """
    Creates a real Razorpay order via their REST API. Only works once you've
    entered live razorpay_key_id / razorpay_key_secret in Admin > Settings —
    without those, this route returns a clear error instead of failing silently.
    """
    key_id, key_secret = get_setting('razorpay_key_id'), get_setting('razorpay_key_secret')
    if not (key_id and key_secret):
        return jsonify({'ok': False, 'error': 'Razorpay is not configured yet. Add your keys in Admin > Settings.'}), 400

    cart = _cart()
    _, _, _, total = _cart_totals(cart)
    try:
        resp = requests.post(
            'https://api.razorpay.com/v1/orders',
            auth=(key_id, key_secret),
            json={'amount': int(total * 100), 'currency': 'INR', 'payment_capture': 1},
            timeout=10,
        )
        resp.raise_for_status()
        return jsonify({'ok': True, 'order': resp.json(), 'key_id': key_id})
    except requests.RequestException as e:
        return jsonify({'ok': False, 'error': str(e)}), 502

@bp.route('/checkout/create-stripe-session', methods=['POST'])
@csrf_protect
def create_stripe_session():
    """Creates a real Stripe Checkout Session via their REST API — same
    activation rule as Razorpay above: needs a live secret key to function."""
    secret_key = get_setting('stripe_secret_key')
    if not secret_key:
        return jsonify({'ok': False, 'error': 'Stripe is not configured yet. Add your secret key in Admin > Settings.'}), 400

    cart = _cart()
    _, _, _, total = _cart_totals(cart)
    try:
        resp = requests.post(
            'https://api.stripe.com/v1/checkout/sessions',
            auth=(secret_key, ''),
            data={
                'mode': 'payment',
                'success_url': url_for('cart.order_success', order_number='pending', _external=True),
                'cancel_url': url_for('cart.checkout', _external=True),
                'line_items[0][price_data][currency]': 'inr',
                'line_items[0][price_data][product_data][name]': 'VOID CULT Order',
                'line_items[0][price_data][unit_amount]': int(total * 100),
                'line_items[0][quantity]': 1,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return jsonify({'ok': True, 'session': resp.json()})
    except requests.RequestException as e:
        return jsonify({'ok': False, 'error': str(e)}), 502

@bp.route('/order-success/<order_number>')
def order_success(order_number):
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE order_number=?", (order_number,)).fetchone()
    items = db.execute("SELECT * FROM order_items WHERE order_id=?", (order['id'],)).fetchall() if order else []
    return render_template('order_success.html', order=order, items=items, inr=inr)
