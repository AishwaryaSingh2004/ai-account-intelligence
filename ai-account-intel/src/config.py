import os
from dotenv import load_dotenv

load_dotenv()


def _get_secret(key: str, default: str = None):
    """Reads a setting from environment variables first (local dev via .env),
    falling back to Streamlit secrets (when deployed). Returns `default` if
    found in neither, so the app never crashes on a missing optional setting."""
    value = os.environ.get(key)
    if value is not None:
        return value
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default


GEMINI_API_KEY = _get_secret("GEMINI_API_KEY")
GEMINI_MODEL = _get_secret("GEMINI_MODEL", "gemini-3.1-flash-lite")
GEMINI_FALLBACK_MODEL = _get_secret("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash")
MAX_RETRIES = int(_get_secret("MAX_RETRIES", "3"))
RETRY_BASE_WAIT_SECONDS = int(_get_secret("RETRY_BASE_WAIT_SECONDS", "5"))
BATCH_DELAY_SECONDS = int(_get_secret("BATCH_DELAY_SECONDS", "3"))
MAX_OUTPUT_TOKENS = int(_get_secret("MAX_OUTPUT_TOKENS", "1024"))


def has_valid_key() -> bool:
    return bool(GEMINI_API_KEY)
