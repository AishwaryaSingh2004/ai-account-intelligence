from src.schema import AccountIntel
from pydantic import ValidationError


def validate_intel(raw: dict):
    """Returns (parsed_object, None) on success, or (None, error) on failure."""
    try:
        parsed = AccountIntel(**raw)
        return parsed, None
    except ValidationError as e:
        return None, str(e)