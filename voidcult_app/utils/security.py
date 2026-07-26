"""
utils/security.py — auth helpers, CSRF protection, and access-control
decorators for VOID CULT.

We don't use Flask-Login/Flask-WTF here (sandboxed environment with no
package installs available), so this file re-implements the same patterns
by hand using Flask's built-in signed session cookies:

- Login state lives in session['user_id'] / session['is_admin'].
- CSRF tokens are random strings stored in session and compared against
  a hidden form field on every POST. This is the same core mechanism
  Flask-WTF uses under the hood.
"""
import secrets
from functools import wraps
from flask import session, redirect, url_for, request, abort, flash
from database import get_db

def generate_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def validate_csrf(form_token):
    return form_token is not None and secrets.compare_digest(form_token, session.get('csrf_token', ''))

def csrf_protect(view):
    """Apply to any POST route to require a valid csrf_token form field."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if request.method == 'POST':
            token = request.form.get('csrf_token')
            if not validate_csrf(token):
                abort(400, description="Invalid or missing CSRF token.")
        return view(*args, **kwargs)
    return wrapped

def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to continue.', 'error')
            return redirect(url_for('auth.login', next=request.path))
        return view(*args, **kwargs)
    return wrapped

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('user_id') or not session.get('is_admin'):
            return redirect(url_for('admin.login'))
        return view(*args, **kwargs)
    return wrapped
