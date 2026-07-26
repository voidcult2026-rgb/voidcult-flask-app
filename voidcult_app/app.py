"""
app.py — VOID CULT Flask application entry point.

Run locally:
    pip install flask pillow requests
    python app.py
Then visit http://127.0.0.1:5000
Admin panel: http://127.0.0.1:5000/admin/login  (admin@voidcult.com / ChangeMe123!)

CHANGE THE ADMIN PASSWORD IMMEDIATELY — see README.md.
"""
from flask import Flask, session, request
from config import Config
from database import close_db, init_db, get_db
from utils.security import generate_csrf_token, current_user
from utils.helpers import get_setting

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    with app.app_context():
        init_db(app)

    app.teardown_appcontext(close_db)

    # Blueprints
    from routes.main import bp as main_bp
    from routes.auth import bp as auth_bp
    from routes.cart import bp as cart_bp
    from admin.routes import bp as admin_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(admin_bp)

    @app.context_processor
    def inject_globals():
        """Available in every template: csrf token, cart count, logged-in user,
        and site-wide settings for navbar/footer/announcement bar."""
        cart = session.get('cart', [])
        return {
            'csrf_token_global': generate_csrf_token(),
            'cart_count': sum(i['qty'] for i in cart),
            'logged_in_user': current_user(),
            'preferred_gender': session.get('preferred_gender', 'Men'),
            'site_setting': get_setting,
        }

    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template('404.html'), 404

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
