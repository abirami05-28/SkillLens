from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"))
db = client["skilllens"]
cand = db.candidates.find_one({"embedding": {"$exists": True}})
print(cand.get("embedding"))
