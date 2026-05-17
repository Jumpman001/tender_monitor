"""
Дедупликатор тендеров — SHA256 хэш для проверки новизны.
"""

import hashlib


def compute_hash(source: str, title: str, url: str) -> str:
    """
    Вычисляет SHA256 хэш из source + title + url.
    Используется для дедупликации тендеров.
    """
    raw = f"{source.strip().lower()}|{title.strip().lower()}|{url.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
