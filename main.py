from fastapi import Body, FastAPI, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
import os
import requests
from urllib.parse import urlencode
from datetime import datetime, timedelta
from token_manager import get_access_token


app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SESSION_SECRET", "supersecret"))

CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
REDIRECT_URI = os.environ["REDIRECT_URI"]
SCOPES = "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/calendar"

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
    access_token = get_access_token()

    if not access_token:
        return {"error": "Not authorized. Please visit /authorize."}

    calendar_id = os.environ.get("TARGET_CALENDAR_ID", "primary")
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
    access_token = get_access_token()
    
    if not access_token:
        print("❌ No access token found")
        return {"error": "Not authorized. Please visit /authorize."}

    data = await request.json()

    print("\n📥 Incoming request data:")
    print(json.dumps(data, indent=2))
    
    calendar_id = os.environ.get("TARGET_CALENDAR_ID", "primary")
    print(f"📛 Using calendar ID: {calendar_id}")
    attendee_objs = []
    for entry in data.get("attendees", []):
        if isinstance(entry, str):
            attendee_objs.append({"email": entry})
        elif isinstance(entry, dict) and "email" in entry:
            attendee_objs.append(entry)

    event_data = {
        "summary": data.get("summary", "Meeting"),
        "start": {
            "dateTime": data["start"],
            "timeZone": data.get("timezone", "UTC")
        },
        "end": {
            "dateTime": data["end"],
            "timeZone": data.get("timezone", "UTC")
        },
        "attendees": attendee_objs
    }

    print("\n📤 Sending event data to Google:")
    print(json.dumps(event_data, indent=2))
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
    response = requests.post(url, headers=headers, json=event_data)
    return response.json()

@app.get("/mcp/manifest")
def manifest():
    return {
        "name": "gcal_mcp_wrapper",
        "description": "Assistant tool that can check calendar availability and schedule meetings.",
        "tools": [
            {
                "name": "check_availability",
                "description": "Returns a list of upcoming events in the calendar for the next 24 hours.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "create_event",
                "description": "Creates a new calendar event.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "start": {"type": "string", "description": "RFC3339 datetime string"},
                        "end": {"type": "string", "description": "RFC3339 datetime string"},
                        "attendees": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "List of attendees with optional email and responseStatus"
                        },
                        "timezone": {"type": "string"}
                    },
                    "required": ["summary", "start", "end"]
                }
            }
        ]
    }

@app.post("/mcp/query")
async def mcp_query(request: Request, payload: dict = Body(...)):
    tool = payload.get("tool")
    input_data = payload.get("input", {})

    access_token = get_access_token()
    
    if not access_token:
        return {"error": "Not authorized. Please visit /authorize."}

    calendar_id = os.environ.get("TARGET_CALENDAR_ID", "primary")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    if tool == "check_availability":
        now = datetime.utcnow().isoformat() + 'Z'
        later = (datetime.utcnow() + timedelta(days=1)).isoformat() + 'Z'
        params = {
            "timeMin": now,
            "timeMax": later,
            "singleEvents": True,
            "orderBy": "startTime"
        }
        url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
        response = requests.get(url, headers=headers, params=params)
        return response.json()

    elif tool == "create_event":
        attendee_objs = []
        for entry in input_data.get("attendees", []):
            if isinstance(entry, str):
                attendee_objs.append({"email": entry})
            elif isinstance(entry, dict) and "email" in entry:
                attendee_objs.append(entry)

        event_data = {
            "summary": input_data.get("summary", "Meeting"),
            "start": {
                "dateTime": input_data["start"],
                "timeZone": input_data.get("timezone", "UTC")
            },
            "end": {
                "dateTime": input_data["end"],
                "timeZone": input_data.get("timezone", "UTC")
            },
            "attendees": attendee_objs
        }
        url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
        response = requests.post(url, headers=headers, json=event_data)
        return response.json()

    else:
        return {"error": f"Tool '{tool}' not recognized"}
