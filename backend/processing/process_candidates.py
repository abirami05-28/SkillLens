# backend/processing/process_candidates.py
import os, sys, argparse
import pymongo
import json
from dotenv import load_dotenv

# Import NLP + regex utilities
from processing.nlp_processor import (
    extract_text_fields,
    extract_entities,
    parse_years_of_experience,
    extract_emails,
    extract_phone_numbers,
)

# Import embedding function
from processing.embedder import text_to_embedding

# Load environment variables
load_dotenv()  # loads .env from backend/

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "skilllens")

if not MONGO_URI:
    print("ERROR: MONGO_URI missing in .env")
    sys.exit(1)

# MongoDB connection
client = pymongo.MongoClient(MONGO_URI)
db = client[MONGO_DB]
candidates = db["candidates"]

def process(limit=None, skip=0):
    """
    Process candidate documents:
    - Build embeddings
    - Run NER (Named Entity Recognition)
    - Extract regex-based fields (emails, phones, years of experience)
    - Store back into MongoDB
    """
    cursor = candidates.find({}).skip(skip)
    count = 0
    for doc in cursor:
        try:
            # Build text blob for NLP
            text = extract_text_fields(doc)

            # Embeddings
            emb = text_to_embedding(text)

            # NLP processing
            entities = extract_entities(text)
            years = parse_years_of_experience(text) or doc.get("experience") or 0
            emails = extract_emails(text)
            phones = extract_phone_numbers(text)

            # Prepare update fields
            update = {
                "embedding": emb,
                "parsed_experience": int(years),
                "ner_entities": entities,
                "emails_found": emails,
                "phones_found": phones,
            }

            # Save results back to MongoDB
            candidates.update_one({"_id": doc["_id"]}, {"$set": update})
            count += 1

            # Stop after reaching limit
            if limit and count >= limit:
                break

            # Progress log
            if count % 50 == 0:
                print("Processed:", count)

        except Exception as e:
            print("Error processing", doc.get("_id"), str(e))

    print("Done. Processed:", count)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="limit number of docs to process")
    parser.add_argument("--skip", type=int, default=0, help="skip docs")
    args = parser.parse_args()
    process(limit=args.limit, skip=args.skip)
