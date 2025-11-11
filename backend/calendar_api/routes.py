# backend/calendar_api/routes.py
from fastapi import APIRouter, HTTPException
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import os, json
from bson import ObjectId 
from db.mongo import get_database
calendar_router = APIRouter(prefix="/calendar", tags=["Google Calendar"])

# Environment vars
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

# Scopes
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

# Temporary token store (for dev use only)
TOKENS_FILE = "google_tokens.json"


@calendar_router.get("/auth-url")
async def get_auth_url():
    """Generate Google OAuth2 authorization URL."""
    try:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uris": [GOOGLE_REDIRECT_URI],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            },
            scopes=SCOPES
        )
        flow.redirect_uri = GOOGLE_REDIRECT_URI
        auth_url, _ = flow.authorization_url(prompt="consent", include_granted_scopes="true")
        return {"auth_url": auth_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating auth URL: {e}")


@calendar_router.get("/oauth2callback")
async def oauth2callback(code: str):
    """Exchange auth code for tokens."""
    try:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uris": [GOOGLE_REDIRECT_URI],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            },
            scopes=SCOPES
        )
        flow.redirect_uri = GOOGLE_REDIRECT_URI
        flow.fetch_token(code=code)
        creds = flow.credentials

        # Save token for later use
        with open(TOKENS_FILE, "w") as f:
            f.write(creds.to_json())

        return {"message": "✅ Google Calendar linked successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth callback failed: {e}")

@calendar_router.post("/schedule_meeting")
async def schedule_meeting(payload: dict):
    # --- Step 1: Ensure Google linked ---
    if not os.path.exists(TOKENS_FILE):
        raise HTTPException(status_code=400, detail="Google not linked. Visit /calendar/auth-url first.")

    creds = Credentials.from_authorized_user_file(TOKENS_FILE, SCOPES)
    service = build("calendar", "v3", credentials=creds)

    # --- Step 2: Extract required fields ---
    candidate_id = payload.get("candidate_id")
    candidate_name = payload.get("candidate_name")  # ✅ include candidate_name from frontend
    recruiter_email = payload.get("recruiter_email")
    date = payload.get("date")
    start_time = payload.get("start_time")
    end_time = payload.get("end_time")

    if not all([candidate_id, recruiter_email, date, start_time, end_time]):
        raise HTTPException(status_code=400, detail="Missing required fields in payload.")

    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="MongoDB not initialized")

    # --- Step 3: Fetch candidate details if not passed ---
    candidate = None
    try:
        candidate = await db["candidates"].find_one({"_id": ObjectId(candidate_id)})
    except Exception:
        pass
    if not candidate:
        candidate = await db["candidates"].find_one({"_id": candidate_id})

    candidate_email = candidate.get("email") if candidate else None
    if not candidate_email:
        candidate_email = "placeholder@example.com"  # fallback for missing email

    candidate_name = candidate_name or candidate.get("name", "Candidate")

    # --- Step 4: Create event on Google Calendar ---
    start = f"{date}T{start_time}:00+05:30"
    end = f"{date}T{end_time}:00+05:30"

    event = {
        "summary": f"Interview with {candidate_name}",
        "description": f"Interview scheduled for {candidate_name}",
        "start": {"dateTime": start, "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end, "timeZone": "Asia/Kolkata"},
        "attendees": [
            {"email": recruiter_email},
            {"email": candidate_email},
        ],
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 30},
                {"method": "popup", "minutes": 10},
            ],
        },
    }

    event_result = service.events().insert(
        calendarId="primary", body=event, sendUpdates="all"
    ).execute()

    # --- Step 5: Save to MongoDB for persistence ---
    interview_data = {
        "candidate_id": candidate_id,
        "candidate_name": candidate_name,
        "recruiter_email": recruiter_email,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "event_link": event_result.get("htmlLink"),
    }

    await db["interviews"].insert_one(interview_data)

    return {
        "message": f"✅ Meeting scheduled successfully for {candidate_name}!",
        "event_link": event_result.get("htmlLink"),
    }

@calendar_router.get("/get_interviews")
async def get_interviews():
    """Fetch all scheduled interviews from MongoDB."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="MongoDB not initialized")

    interviews = []
    async for i in db["interviews"].find({}):
        i["_id"] = str(i["_id"])
        interviews.append(i)
    return {"interviews": interviews}
