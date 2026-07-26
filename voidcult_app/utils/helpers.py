"""utils/helpers.py — small shared helpers: slugs, order numbers, formatting."""
import re
import random
import string
from database import get_db

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

def unique_slug(table, base_slug):
    db = get_db()
    slug = base_slug
    i = 1
    while db.execute(f"SELECT id FROM {table} WHERE slug=?", (slug,)).fetchone():
        i += 1
        slug = f"{base_slug}-{i}"
    return slug

def generate_order_number():
    return "VC-" + ''.join(random.choices(string.digits, k=6))

def inr(amount):
    """Format a number as an Indian Rupee string, e.g. 184300 -> '1,84,300'."""
    amount = int(round(amount))
    s = str(amount)
    if len(s) <= 3:
        return s
    last3 = s[-3:]
    rest = s[:-3]
    parts = []
    while len(rest) > 2:
        parts.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        parts.insert(0, rest)
    return ','.join(parts) + ',' + last3

def get_settings():
    """Load all site_settings rows into a plain dict — used by templates for
    every editable piece of homepage/site content."""
    db = get_db()
    rows = db.execute("SELECT key, value FROM site_settings").fetchall()
    return {r['key']: r['value'] for r in rows}

def get_setting(key, default=''):
    db = get_db()
    row = db.execute("SELECT value FROM site_settings WHERE key=?", (key,)).fetchone()
    return row['value'] if row else default

def set_setting(key, value):
    db = get_db()
    db.execute(
        "INSERT INTO site_settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value)
    )
    db.commit()
