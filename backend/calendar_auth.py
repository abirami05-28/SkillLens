# backend/calendar_auth.py
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import os, json, base64
from pydantic import BaseModel
from typing import List, Optional

calendar_router = APIRouter()

# For local testing only (do NOT use in production)
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

CLIENT_SECRETS_FILE = "credentials.json"   # adjust path if needed
SCOPES = ["https://www.googleapis.com/auth/calendar"]
REDIRECT_URI = "http://127.0.0.1:8000/google/callback"  # must match Google Console exactly

# Simple in-memory store for demo. Replace with per-user DB/Redis in production.
user_credentials: dict[str, dict] = {}

# Helper to encode a small JSON state into a base64 string
def encode_state(obj: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode()

def decode_state(s: str) -> dict:
    try:
        return json.loads(base64.urlsafe_b64decode(s.encode()).decode())
    except Exception:
        return {}

# Step 1: Redirect the user to Google's OAuth page
@calendar_router.get("/authorize")
async def authorize(user_email: Optional[str] = None):
    """
    Open this endpoint from the frontend as:
      /google/authorize?user_email=alice%40example.com

    The handler encodes the user_email into the OAuth 'state' so the callback can map tokens to the user.
    """
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    state_payload = {"user_email": user_email} if user_email else {}
    state = encode_state(state_payload)

    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=state
    )
    return RedirectResponse(authorization_url)

# Step 2: Google redirects back here
@calendar_router.get("/callback")
async def callback(request: Request):
    """
    Google will redirect to this endpoint. We exchange the code for tokens,
    store them keyed by user_email (from state), and return a small HTML page
    that posts a message back to the opener window and closes the popup.
    """
    # re-create Flow with same redirect_uri
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    # Exchange code for tokens
    flow.fetch_token(authorization_response=str(request.url))
    credentials = flow.credentials

    # get state from query params, decode to find user_email
    state_param = request.query_params.get("state", "")
    state_obj = decode_state(state_param) if state_param else {}
    user_email = state_obj.get("user_email") or "default"

    # store credentials for that user (demo: in-memory). Persist in DB in real apps.
    user_credentials[user_email] = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes
    }

    # Return a tiny page that sends a message back to the opener and closes itself.
    # The opener should listen to window.message events.
    html = f"""
    <!doctype html>
    <html>
    <head><meta charset="utf-8"></head>
    <body>
      <script>
        try {{
          window.opener.postMessage({{type: 'google_auth', status: 'success', user_email: {json.dumps(user_email)}}}, '*');
        }} catch(e) {{
          console.log('postMessage failed', e);
        }}
        // close popup
        window.close();
      </script>
      <p>Authorization successful. You can close this window.</p>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

# Pydantic model for event creation
class EventIn(BaseModel):
    user_email: Optional[str] = None   # which user account to use (must match the one used in authorize)
    summary: str
    start_datetime: str  # ISO string: 2025-09-20T10:00:00Z or with offset
    end_datetime: str
    timezone: Optional[str] = "UTC"
    attendees: Optional[List[str]] = []

# Step 3: create event using stored credentials
@calendar_router.post("/create_event")
async def create_event(event: EventIn):
    creds_dict = user_credentials.get(event.user_email or "default")
    if not creds_dict:
        raise HTTPException(status_code=401, detail="User not authenticated with Google Calendar. Visit /google/authorize first.")

    creds = Credentials(**creds_dict)
    service = build("calendar", "v3", credentials=creds)

    body = {
        "summary": event.summary,
        "start": {"dateTime": event.start_datetime, "timeZone": event.timezone},
        "end": {"dateTime": event.end_datetime, "timeZone": event.timezone},
        "attendees": [{"email": e} for e in (event.attendees or [])]
    }

    created_event = service.events().insert(calendarId="primary", body=body).execute()
    return JSONResponse({"event": created_event})
