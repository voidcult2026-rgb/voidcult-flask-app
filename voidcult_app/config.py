"""
config.py — central configuration for VOID CULT.

IMPORTANT (read before going live):
- Change SECRET_KEY to a long random value in production (used to sign
  session cookies and CSRF tokens).
- Fill in RAZORPAY / STRIPE keys via the Admin > Settings page (stored in
  the site_settings table) once you have live merchant accounts. Without
  real keys, checkout falls back to Cash on Delivery only.
- Set up real SMTP credentials below to enable email verification and
  order confirmation emails. Without them, verification tokens are still
  generated and logged to the console so you can test the flow locally.
"""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-this-in-production-4f8a2e1c9b')
    DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(BASE_DIR, 'voidcult.db'))
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(BASE_DIR, 'static', 'uploads', 'products'))
    SITE_UPLOAD_FOLDER = os.environ.get('SITE_UPLOAD_FOLDER', os.path.join(BASE_DIR, 'static', 'uploads', 'site'))
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
    IMAGE_MAX_DIMENSION = 1600      # px — images are downscaled to this before saving
    IMAGE_QUALITY = 82              # JPEG/WEBP compression quality

    # --- SMTP (fill in to enable real emails) ---
    SMTP_HOST = os.environ.get('SMTP_HOST', '')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USER = os.environ.get('SMTP_USER', '')
    SMTP_PASS = os.environ.get('SMTP_PASS', '')

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
