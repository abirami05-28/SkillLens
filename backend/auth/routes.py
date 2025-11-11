# --- add at the top of auth/routes.py ---
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
import os, time, secrets
import requests as pyrequests
from datetime import datetime, timedelta
import jwt as pyjwt  # match your main.py which uses PyJWT
from google.oauth2 import id_token
from google.auth.transport import requests as grequests

from dotenv import load_dotenv
load_dotenv()  # ensure .env is read before getenv below

from db import mongo  # your existing async Motor client
auth_router = APIRouter()

# --- Google Sign-In env ---
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_SIGNIN_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_SIGNIN_CLIENT_SECRET")
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_SIGNIN_REDIRECT_URI")
FRONTEND_BASE_URL    = os.getenv("FRONTEND_BASE_URL", "http://127.0.0.1:5500/frontend")
JWT_SECRET           = os.getenv("JWT_SECRET", "replace_this_in_env")

# Simple in-memory state for CSRF (dev only). Use Redis in prod.
STATE_STORE: dict[str, float] = {}  # state -> expiry epoch

def _build_google_auth_url(state: str) -> str:
    base = "https://accounts.google.com/o/oauth2/v2/auth"
    scope = "openid email profile"  # login-only scopes
    params = (
        f"client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={scope}"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&state={state}"
    )
    return f"{base}?{params}"

@auth_router.get("/google/start")
def google_start():
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI):
        raise HTTPException(status_code=500, detail="Google Sign-In not configured")
    state = secrets.token_urlsafe(32)
    STATE_STORE[state] = time.time() + 600  # 10-minute TTL
    return RedirectResponse(_build_google_auth_url(state))

@auth_router.get("/google/callback")
async def google_callback(request: Request, code: str | None = None, state: str | None = None):
    # 1) Validate state
    if not state or state not in STATE_STORE or STATE_STORE[state] < time.time():
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    STATE_STORE.pop(state, None)

    if not code:
        raise HTTPException(status_code=400, detail="Missing code")

    # 2) Exchange code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    body = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    resp = pyrequests.post(token_url, data=body, timeout=15)
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {resp.text}")
    tokens = resp.json()
    id_tok = tokens.get("id_token")
    if not id_tok:
        raise HTTPException(status_code=400, detail="No id_token returned")

    # 3) Verify ID token
    try:
        idinfo = id_token.verify_oauth2_token(id_tok, grequests.Request(), GOOGLE_CLIENT_ID)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google ID token: {e}")

    email = idinfo.get("email")
    email_verified = idinfo.get("email_verified", False)
    username = idinfo.get("name") or (email.split("@")[0] if email else "user")
    picture = idinfo.get("picture", "")

    if not email or not email_verified:
        raise HTTPException(status_code=401, detail="Google email not verified")

    # 4) Upsert user (async Motor)
    users = mongo.users_collection
    db_user = await users.find_one({"email": email})
    if not db_user:
        await users.insert_one({
            "email": email,
            "username": username,
            "password": None,     # passwordless Google user
            "orgname": "",
            "contact": "",
            "address": "",
            "provider": "google",
            "picture": picture,
            "createdAt": datetime.utcnow()
        })
        db_user = await users.find_one({"email": email})

    # 5) Mint JWT same as /auth/login uses (PyJWT + HS256)
    payload = {
        "sub": str(db_user["_id"]),
        "email": db_user["email"],
        "username": db_user.get("username", email.split("@")[0]),
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    token = pyjwt.encode(payload, JWT_SECRET, algorithm="HS256")

    # 6) Redirect back to frontend handoff to store token and jump to dashboard
    redirect_url = f"{FRONTEND_BASE_URL}/oauth_finish.html#token={token}&email={email}"
    return RedirectResponse(redirect_url, status_code=302)
