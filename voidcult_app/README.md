# VOID CULT — Flask E-Commerce Platform

## Quick Start
```bash
pip install -r requirements.txt
python app.py
```
Visit http://127.0.0.1:5000

**Admin panel:** http://127.0.0.1:5000/admin/login
Default login: `admin@voidcult.com` / `ChangeMe123!`
**Change this password immediately** — go to a Python shell and run:
```python
from app import create_app
from database import get_db
from werkzeug.security import generate_password_hash
app = create_app()
with app.app_context():
    db = get_db()
    db.execute("UPDATE users SET password_hash=? WHERE email='admin@voidcult.com'",
               (generate_password_hash('YOUR-NEW-PASSWORD'),))
    db.commit()
```

## What's real vs. what needs your credentials

**Fully working out of the box:**
- Product catalog, categories, collections, search & filters
- Cart, Cash on Delivery checkout, coupons, stock deduction
- Customer accounts (register/login/logout), profile, addresses, order history
- Full admin dashboard: products (with drag-drop image upload + automatic
  compression), categories, collections, orders, coupons, customers, reviews
- CMS (site_settings table): hero text, announcement bar, footer, About,
  FAQs, Shipping/Return/Privacy/Terms — all editable from Admin > CMS &
  Settings with zero code changes
- CSRF protection, password hashing (scrypt via Werkzeug), session-based auth

**Needs your credentials to fully activate:**
- **Razorpay / Stripe** — the checkout page and `/checkout/create-razorpay-order`
  and `/checkout/create-stripe-session` routes call the real REST APIs, but
  need live keys entered in Admin > CMS & Settings > Payment Gateway Keys.
  Without them, checkout works fine via Cash on Delivery.
- **Email** (verification links, order confirmations) — `config.py` has SMTP
  settings; without them, verification/reset links are shown directly in the
  UI (via flash messages) instead of emailed, so the flow is still testable.
- **Logo** — no logo file was provided when this was built. Drop your logo
  into `static/uploads/site/branding/` and set the `logo_image` setting
  (via the database or a small admin field) to have it appear top-left.

## Project Structure
```
voidcult_app/
├── app.py                 # Flask app factory + entry point
├── config.py               # All configuration (SECRET_KEY, upload limits, SMTP)
├── database.py             # SQLite connection + schema init + demo seed data
├── schema.sql               # Full database schema
├── requirements.txt
├── routes/
│   ├── main.py             # Storefront: home, shop, product detail, search
│   ├── auth.py              # Register, login, logout, password reset, profile
│   └── cart.py               # Cart, coupons, checkout, payment gateway calls
├── admin/
│   └── routes.py             # Full admin dashboard (products/orders/CMS/etc)
├── utils/
│   ├── security.py           # CSRF, login_required/admin_required, password checks
│   ├── images.py              # Drag-drop upload + automatic Pillow compression
│   └── helpers.py              # Slugs, order numbers, INR formatting, settings
├── templates/                  # Jinja2 templates (storefront + templates/admin/)
└── static/
    ├── css/                     # style.css (storefront) + admin.css
    ├── js/                       # smoke.js (animated bg), main.js, admin.js
    └── uploads/                   # product images + site media library
```

## Why raw sqlite3 instead of SQLAlchemy?
This was built in a sandboxed environment with no package-install access
beyond what ships with Flask (Werkzeug, Jinja2) plus Pillow and requests,
which were already present. Every query lives in `routes/` and `admin/routes.py`
using plain parameterized SQL — there's no ORM lock-in, so swapping to
Flask-SQLAlchemy + MySQL later means replacing `database.py`'s connection
logic and translating `schema.sql`; the query logic itself barely changes.

## Security notes
- Change `SECRET_KEY` in `config.py` (or set the `SECRET_KEY` env var) before
  deploying — it signs both the session cookie and CSRF tokens.
- All forms are CSRF-protected via `utils/security.py`.
- Passwords are hashed with Werkzeug's `scrypt`-based hasher — never stored
  in plain text.
- All SQL uses parameterized queries (`?` placeholders) — no string-formatted
  SQL anywhere, which is what prevents SQL injection.

## Known gaps to be aware of
- Email verification is generated correctly but only actually emailed once
  you wire up real SMTP credentials in `config.py`.
- The "brand colors" fields in Admin > Settings save to the database but
  aren't yet wired to override `style.css` at runtime — that's a short next
  step (inject them as CSS custom properties in `base.html`'s `<head>`).
- No automated tests yet — recommend adding `pytest` + a test SQLite DB
  before going to production.
