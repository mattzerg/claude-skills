"""Slug helpers."""
from __future__ import annotations

import re
import unicodedata


def slugify(text: str, max_len: int = 60) -> str:
    """Lowercase, ASCII, hyphen-separated. Truncated cleanly at word boundary."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[-\s]+", "-", text)
    if len(text) > max_len:
        cut = text[:max_len].rsplit("-", 1)[0]
        text = cut if len(cut) >= 20 else text[:max_len].rstrip("-")
    return text or "idea"
