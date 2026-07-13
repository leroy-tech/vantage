"""
Config helper: reads settings from Streamlit's secrets manager when running
on Streamlit Community Cloud, and falls back to environment variables /
.env when running locally (CLI, price_tracker cron job, etc).

This lets the exact same code work in both places without changes.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def get_secret(key: str, default=None):
    """
    Look up a config value, preferring Streamlit secrets (for cloud
    deployment) and falling back to environment variables (for local/CLI use).
    """
    try:
        import streamlit as st
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        # Not running under Streamlit, or no secrets.toml configured — that's fine
        pass

    return os.getenv(key, default)
