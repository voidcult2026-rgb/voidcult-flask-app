"""
utils/images.py — drag-and-drop image upload handling with automatic
compression, used by both the product editor and the site media library.
"""
import os
import uuid
from PIL import Image
from flask import current_app

def allowed_file(filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in current_app.config['ALLOWED_EXTENSIONS']

def save_and_compress_image(file_storage, folder):
    """
    Save an uploaded image, downscale it to a max dimension, and re-encode
    at a fixed quality to keep file sizes small automatically — no manual
    editing required by the admin.
    Returns the saved filename (not the full path).
    """
    if not file_storage or not file_storage.filename or not allowed_file(file_storage.filename):
        return None

    ext = file_storage.filename.rsplit('.', 1)[-1].lower()
    if ext == 'jpg':
        ext = 'jpeg'
    filename = f"{uuid.uuid4().hex}.{ext if ext != 'gif' else 'gif'}"
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, filename)

    if ext == 'gif':
        # Don't recompress animated GIFs — save as-is.
        file_storage.save(filepath)
        return filename

    img = Image.open(file_storage.stream)
    if img.mode in ('RGBA', 'P') and ext == 'jpeg':
        img = img.convert('RGB')

    max_dim = current_app.config['IMAGE_MAX_DIMENSION']
    if max(img.size) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)

    save_kwargs = {}
    if ext in ('jpeg', 'webp'):
        save_kwargs['quality'] = current_app.config['IMAGE_QUALITY']
        save_kwargs['optimize'] = True

    img.save(filepath, **save_kwargs)
    return filename

def delete_image(folder, filename):
    if not filename:
        return
    path = os.path.join(folder, filename)
    if os.path.exists(path):
        os.remove(path)
