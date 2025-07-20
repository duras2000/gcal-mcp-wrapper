# token_manager.py
import os
import requests
from datetime import datetime, timedelta

CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["REFRESH_TOKEN"]

# Internal cache
_cached_token = None
_cached_expiry = None

def get_access_token():
    global _cached_token, _cached_expiry

    if _cached_token and _cached_expiry and datetime.utcnow() < _cached_expiry:
        return _cached_token

    # Token expired or not yet fetched, get a new one
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": REFRESH_TOKEN,
            "grant_type": "refresh_token",
        }
    )

    token_data = response.json()

    if "access_token" not in token_data:
        raise Exception(f"Failed to refresh token: {token_data}")

    _cached_token = token_data["access_token"]
    _cached_expiry = datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600) - 60)

    return _cached_token
