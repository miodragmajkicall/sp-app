from __future__ import annotations

import unicodedata


def csv_safe_text(value: str) -> str:
    """Protect free-text CSV cells without changing stored values."""
    if not value:
        return value

    # Skip leading whitespace and invisible formatting characters.
    # A leading control character is itself considered unsafe.
    index = 0
    has_control = False
    while index < len(value):
        char = value[index]
        kind = unicodedata.category(char)
        if not char.isspace() and kind not in {"Cc", "Cf"}:
            break
        if kind == "Cc":
            has_control = True
        index += 1

    first = value[index:index + 1]
    formula_starts = "=+-@\uff1d\uff0b\uff0d\uff20"
    if has_control or (first and first in formula_starts):
        return "\t" + value
    return value
