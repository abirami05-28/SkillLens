import asyncio
from db.mongo import init_mongo, get_database

async def clear_collections():
    await init_mongo()
    db = get_database()

    collections_to_clear = [
        "candidates",
        "bias_metrics",
        "analytics",
        "matches"
    ]

    for coll_name in collections_to_clear:
        coll = db[coll_name]
        result = await coll.delete_many({})
        print(f"🧹 Cleared {coll_name} → {result.deleted_count} documents deleted")

    print("✅ All specified collections cleared successfully.")

if __name__ == "__main__":
    asyncio.run(clear_collections())
