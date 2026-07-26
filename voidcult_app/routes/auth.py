"""routes/auth.py — customer registration, login, logout, password reset, profile."""
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db
from utils.security import csrf_protect, generate_csrf_token, login_required, current_user

bp = Blueprint('auth', __name__)

@bp.route('/register', methods=['GET', 'POST'])
@csrf_protect
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        db = get_db()

        if not name or not email or len(password) < 6:
            flash('Please fill all fields — password must be at least 6 characters.', 'error')
            return redirect(url_for('auth.register'))
        if db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
            flash('An account with that email already exists.', 'error')
            return redirect(url_for('auth.register'))

        token = secrets.token_urlsafe(24)
        db.execute(
            "INSERT INTO users (name, email, password_hash, verify_token) VALUES (?,?,?,?)",
            (name, email, generate_password_hash(password), token)
        )
        db.commit()
        # In production this link is emailed via SMTP (see config.py). Without
        # SMTP configured, we surface it directly so the flow is testable.
        verify_link = url_for('auth.verify_email', token=token, _external=True)
        flash(f'Account created! Verify your email: {verify_link}', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html', csrf_token=generate_csrf_token())

@bp.route('/verify/<token>')
def verify_email(token):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE verify_token=?", (token,)).fetchone()
    if user:
        db.execute("UPDATE users SET email_verified=1, verify_token=NULL WHERE id=?", (user['id'],))
        db.commit()
        flash('Email verified — you can now log in.', 'success')
    else:
        flash('Invalid or expired verification link.', 'error')
    return redirect(url_for('auth.login'))

@bp.route('/login', methods=['GET', 'POST'])
@csrf_protect
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['is_admin'] = bool(user['is_admin'])
            flash(f"Welcome back, {user['name']}.", 'success')
            next_url = request.args.get('next') or url_for('main.home')
            return redirect(next_url)
        flash('Incorrect email or password.', 'error')
        return redirect(url_for('auth.login'))

    return render_template('login.html', csrf_token=generate_csrf_token())

@bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.home'))

@bp.route('/forgot-password', methods=['GET', 'POST'])
@csrf_protect
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user:
            token = secrets.token_urlsafe(24)
            db.execute("UPDATE users SET verify_token=? WHERE id=?", (token, user['id']))
            db.commit()
            reset_link = url_for('auth.reset_password', token=token, _external=True)
            flash(f'Password reset link (would be emailed): {reset_link}', 'success')
        else:
            flash('If that email exists, a reset link has been sent.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('forgot_password.html', csrf_token=generate_csrf_token())

@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
@csrf_protect
def reset_password(token):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE verify_token=?", (token,)).fetchone()
    if not user:
        flash('Invalid or expired reset link.', 'error')
        return redirect(url_for('auth.forgot_password'))
    if request.method == 'POST':
        password = request.form.get('password', '')
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return redirect(request.path)
        db.execute("UPDATE users SET password_hash=?, verify_token=NULL WHERE id=?", (generate_password_hash(password), user['id']))
        db.commit()
        flash('Password updated — please log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('reset_password.html', csrf_token=generate_csrf_token(), token=token)

@bp.route('/profile')
@login_required
def profile():
    user = current_user()
    db = get_db()
    addresses = db.execute("SELECT * FROM addresses WHERE user_id=?", (user['id'],)).fetchall()
    orders = db.execute("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC", (user['id'],)).fetchall()
    wishlist = db.execute(
        "SELECT p.* FROM wishlist w JOIN products p ON p.id=w.product_id WHERE w.user_id=?", (user['id'],)
    ).fetchall()
    return render_template('profile.html', user=user, addresses=addresses, orders=orders, wishlist=wishlist, csrf_token=generate_csrf_token())

@bp.route('/profile/address', methods=['POST'])
@login_required
@csrf_protect
def add_address():
    user = current_user()
    db = get_db()
    db.execute(
        """INSERT INTO addresses (user_id, full_name, line1, city, state, pincode, phone, is_default)
           VALUES (?,?,?,?,?,?,?,?)""",
        (user['id'], request.form['full_name'], request.form['line1'], request.form['city'],
         request.form['state'], request.form['pincode'], request.form['phone'],
         1 if request.form.get('is_default') else 0)
    )
    db.commit()
    flash('Address saved.', 'success')
    return redirect(url_for('auth.profile'))

@bp.route('/order/<order_number>')
@login_required
def track_order(order_number):
    user = current_user()
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE order_number=? AND user_id=?", (order_number, user['id'])).fetchone()
    if not order:
        return render_template('404.html'), 404
    items = db.execute("SELECT * FROM order_items WHERE order_id=?", (order['id'],)).fetchall()
    return render_template('order_track.html', order=order, items=items)
