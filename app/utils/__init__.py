"""Input validation helpers."""

from decimal import Decimal, InvalidOperation


def validate_required_fields(data: dict, required: list[str]) -> list[str]:
    """Return list of missing field names."""
    return [f for f in required if f not in data or data[f] is None]


def parse_positive_decimal(value) -> tuple[Decimal | None, str | None]:
    """
    Parse a value as a positive Decimal.
    Returns (decimal_value, None) on success or (None, error_message) on failure.
    """
    try:
        d = Decimal(str(value))
        if d <= 0:
            return None, "Value must be a positive number"
        return d, None
    except (InvalidOperation, ValueError, TypeError):
        return None, "Invalid number format"


def parse_non_negative_int(value) -> tuple[int | None, str | None]:
    """
    Parse a value as a non-negative integer.
    Returns (int_value, None) on success or (None, error_message) on failure.
    """
    try:
        i = int(value)
        if i < 0:
            return None, "Value cannot be negative"
        return i, None
    except (ValueError, TypeError):
        return None, "Value must be an integer"
