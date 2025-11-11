
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
import requests
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta

load_dotenv()
auth_router = APIRouter()

# ========== AUTH0 CONFIG (kept from your old code) ==========
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")  # e.g., "your-tenant.us.auth0.com"
API_AUDIENCE = os.getenv("AUTH0_AUDIENCE")  # e.g., "https://skilllens-api"
ALGORITHMS = ["RS256"]

bearer_scheme = HTTPBearer()

def get_jwks():
    jwks_url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
    response = requests.get(jwks_url)
    response.raise_for_status()
    return response.json()

jwks = get_jwks()

def verify_jwt(token: str):
    """Verify JWT issued by Auth0"""
    unverified_header = jwt.get_unverified_header(token)
    rsa_key = {}
    for key in jwks["keys"]:
        if key["kid"] == unverified_header["kid"]:
            rsa_key = {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"]
            }
    if not rsa_key:
        raise HTTPException(status_code=401, detail="Unable to find appropriate key")

    try:
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=ALGORITHMS,
            audience=API_AUDIENCE,
            issuer=f"https://{AUTH0_DOMAIN}/"
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTClaimsError:
        raise HTTPException(status_code=401, detail="Invalid claims")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token = credentials.credentials
    return verify_jwt(token)

@auth_router.get("/profile")
async def profile(user=Depends(get_current_user)):
    return {"msg": "You are logged in with Auth0!", "user": user}


# ========== LOCAL MONGODB + JWT AUTH (new part) ==========
MONGO_URI = os.getenv("MONGO_URI")
SECRET_KEY = os.getenv("JWT_SECRET", "mysecret")  # generate with openssl rand -hex 32
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

client = MongoClient(MONGO_URI)
db = client["skilllens"]
users_collection = db["users"]

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserSignup(BaseModel):
    email: EmailStr
    username: str
    password: str
    orgname: str
    contact: str
    address: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@auth_router.post("/signup")
async def signup(user: UserSignup):
    if users_collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = pwd_context.hash(user.password)
    users_collection.insert_one({
        "email": user.email,
        "username": user.username,
        "password": hashed_password,
        "orgname": user.orgname,
        "contact": user.contact,
        "address": user.address
    })

    return {"message": "User registered successfully"}

@auth_router.post("/login")
async def login(user: UserLogin):
    db_user = users_collection.find_one({"email": user.email})
    if not db_user or not pwd_context.verify(user.password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token_data = {
        "sub": str(db_user["_id"]),
        "email": db_user["email"],
        "username": db_user.get("username", db_user["email"].split("@")[0])  # <--
    }
    token = create_access_token(token_data)
    return {"access_token": token, "token_type": "bearer"}

# Example protected route using local JWTs
@auth_router.get("/me")
async def read_me(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        user_info = {
            "id": payload.get("sub"),
            "email": payload.get("email"),
            "username": payload.get("username") or payload.get("email").split("@")[0]
        }

        return {"user": user_info}

    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
