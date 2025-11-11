# backend/analytics/export_to_dw.py
import os
import pandas as pd
import pymongo
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

# MongoDB connection
mongo_client = pymongo.MongoClient(os.getenv("MONGO_URI"))
mdb = mongo_client[os.getenv("MONGO_DB", "skilllens")]
candidates = mdb["candidates"]

# Example aggregation (adjust if needed)
pipeline = [
    {"$unwind": "$skills"},
    {"$group": {"_id": "$skills", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}}
]
data = list(candidates.aggregate(pipeline))
df = pd.DataFrame(data)
df.rename(columns={"_id": "skill"}, inplace=True)

if df.empty:
    print("⚠️ No data found for export, skipping PostgreSQL export.")
else:
    pg_pooler = os.getenv("POSTGRES_URI")   # pooler connection
    pg_direct = os.getenv("POSTGRES_DIRECT")  # direct connection

    def try_export(uri):
        try:
            print(f"Trying export with: {uri}")
            engine = create_engine(uri)
            df.to_sql("skills_aggregate", engine, if_exists="replace", index=False)
            print("✅ Exported to Postgres successfully")
            return True
        except Exception as e:
            print(f"❌ Failed with {uri}: {e}")
            return False

    # First try Pooler → then fallback to Direct
    if not try_export(pg_pooler):
        if pg_direct:
            print("🔄 Falling back to direct connection...")
            if not try_export(pg_direct):
                print("❌ Both pooler and direct failed")
        else:
            print("⚠️ No direct connection URI set in .env")
