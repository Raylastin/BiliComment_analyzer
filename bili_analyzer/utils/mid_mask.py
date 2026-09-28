"""User mid masking for privacy-preserving display."""

from __future__ import annotations


def mask_mid(mid: int | str | None) -> str:
    """Mask a numeric mid, e.g. 1234567 -> 123****67."""
    if mid is None:
        return ""
    text = str(mid).strip()
    if not text:
        return ""
    if len(text) <= 4:
        return text[0] + "*" * (len(text) - 1)
    return f"{text[:3]}****{text[-2:]}"

