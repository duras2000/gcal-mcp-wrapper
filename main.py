from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
import os
import requests
from urllib.parse import urlencode
from datetime import datetime, timedelta

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SESSION_SECRET", "supersecret"))

CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
REDIRECT_URI = os.environ["REDIRECT_URI"]
SCOPES = "https://www.googleapis.com/auth/calendar"

@app.get("/")
def home():
    return {"message": "Assistant Calendar Wrapper is live."}

@app.get("/authorize")
def authorize():
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent"
    }
    return RedirectResponse(url=f"https://accounts.google.com/o/oauth2/auth?{urlencode(params)}")

@app.get("/callback")
def callback(request: Request, code: str):
    data = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    token_resp = requests.post("https://oauth2.googleapis.com/token", data=data)
    token_json = token_resp.json()
    request.session["access_token"] = token_json["access_token"]
    return {"access_token": token_json["access_token"]}

@app.get("/tools/check_availability")
def check_availability(request: Request):
    access_token = request.session.get("access_token")
    if not access_token:
        return {"error": "Not authorized. Please visit /authorize."}

    calendar_id = os.environ.get("TARGET_CALENDAR_ID")
    now = datetime.utcnow().isoformat() + 'Z'
    later = (datetime.utcnow() + timedelta(days=1)).isoformat() + 'Z'
    url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
    params = {
        "timeMin": now,
        "timeMax": later,
        "singleEvents": True,
        "orderBy": "startTime"
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers, params=params)
    return response.json()

@app.post("/tools/create_event")
async def create_event(request: Request):
    access_token = request.session.get("access_token")
    if not access_token:
        return {"error": "Not authorized. Please visit /authorize."}

    data = await request.json()
    calendar_id = os.environ.get("TARGET_CALENDAR_ID")
    event_data = {
        "summary": data.get("summary", "Meeting"),
        "start": {
            "dateTime": data["start"],
            "timeZone": "UTC"
        },
        "end": {
            "dateTime": data["end"],
            "timeZone": "UTC"
        },
        "attendees": [{"email": email} for email in data.get("attendees", [])]
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
    response = requests.post(url, headers=headers, json=event_data)
    return response.json()
