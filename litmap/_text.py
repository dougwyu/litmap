"""Shared text helpers for litmap."""
from __future__ import annotations


def last_name(author: str) -> str:
    """Return the surname portion of a 'Last, First' author string.

    If the string has no comma, return it unchanged (after stripping).
    """
    return author.split(",")[0].strip() if "," in author else author.strip()
