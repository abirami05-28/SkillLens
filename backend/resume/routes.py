# backend/resume/routes.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from .textract import extract_text_from_pdf
from db.mongo import get_database
from resume.textract import textract, s3_client, S3_BUCKET  # ✅ already has working clients
from processing.normalize import normalize_textract_resume
import uuid
import time
import tempfile
import pdfminer.high_level
import os
from processing.hf_router import embed_text
from processing.hf_router import embed_text_direct

router = APIRouter(tags=["Resume"])
# ----------------------------------------------------------
# 1️⃣ Upload a Single Resume → Extract → Normalize → Store
# ----------------------------------------------------------
@router.post("/upload_resume")
async def upload_resume(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    try:
        # Step 1: Extract text
        result = await extract_text_from_pdf(file)
        if "error" in result:
            raise Exception(result["error"])

       
        # Step 2: Normalize for schema consistency
        normalized = normalize_textract_resume(result.get("text", ""))
        
        # Step 3: Prepare final candidate document
        candidate_doc = {
            "_id": str(uuid.uuid4()),
            "filename": file.filename,
            "text": result.get("text", ""),
            "source": result.get("source"),
            **normalized,
        }
        # ✅ Step 4: Generate embedding (local SBERT)
        text_for_embedding = candidate_doc.get("text", "")
        if text_for_embedding.strip():
            embedding = await embed_text_direct(text_for_embedding)
            candidate_doc["embedding"] = embedding
        else:
            candidate_doc["embedding"] = []

        # Step 5: Save to MongoDB
        db = get_database()
        if db is None:
            raise HTTPException(status_code=500, detail="MongoDB not initialized")

        await db["candidates"].insert_one(candidate_doc)

        return {
            "msg": f"Resume {file.filename} processed successfully.",
            "mongo_id": candidate_doc["_id"],
            "source": result.get("source"),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing resume: {e}")


# ------------------------------------------------------------------------
# 2️⃣ Process All Resumes from AWS S3 Bucket → Handles All Formats
# ------------------------------------------------------------------------
@router.post("/process_all")
async def process_all_resumes():
    try:
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET)
        if "Contents" not in response:
            raise HTTPException(status_code=404, detail="No files found in S3 bucket.")

        pdf_files = [obj["Key"] for obj in response["Contents"] if obj["Key"].lower().endswith(".pdf")]
        if not pdf_files:
            raise HTTPException(status_code=404, detail="No PDF files found in S3 bucket.")

        db = get_database()
        if db is None:
            raise HTTPException(status_code=500, detail="MongoDB not initialized")

        results = []
        for pdf_key in pdf_files:
            try:
                print(f"📄 Processing: {pdf_key}")
                text = None
                source = None

                # Step 1️⃣ Try Sync Textract
                try:
                    response = textract.detect_document_text(
                        Document={"S3Object": {"Bucket": S3_BUCKET, "Name": pdf_key}}
                    )
                    text = " ".join([block["Text"] for block in response["Blocks"] if block["BlockType"] == "LINE"])
                    source = "textract_sync"

                # Step 2️⃣ Fallback to Async Textract for scanned/image PDFs
                except textract.exceptions.UnsupportedDocumentException:
                    print(f"[INFO] Falling back to async Textract for {pdf_key}...")
                    job = textract.start_document_text_detection(
                        DocumentLocation={"S3Object": {"Bucket": S3_BUCKET, "Name": pdf_key}}
                    )
                    job_id = job["JobId"]

                    while True:
                        status = textract.get_document_text_detection(JobId=job_id)
                        job_status = status["JobStatus"]
                        if job_status in ["SUCCEEDED", "FAILED"]:
                            break
                        time.sleep(2)

                    if job_status == "SUCCEEDED":
                        pages = []
                        next_token = None
                        while True:
                            if next_token:
                                response = textract.get_document_text_detection(JobId=job_id, NextToken=next_token)
                            else:
                                response = textract.get_document_text_detection(JobId=job_id)

                            pages.extend([block["Text"] for block in response["Blocks"] if block["BlockType"] == "LINE"])
                            next_token = response.get("NextToken")
                            if not next_token:
                                break

                        text = " ".join(pages)
                        source = "textract_async"
                    else:
                        raise Exception("Async Textract job failed.")

                # Step 3️⃣ Final fallback to PDFMiner
                except Exception as textract_error:
                    print(f"[WARN] Textract failed for {pdf_key}: {textract_error}")
                    print("[INFO] Falling back to PDFMiner...")
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        s3_client.download_file(S3_BUCKET, pdf_key, tmp.name)
                        text = pdfminer.high_level.extract_text(tmp.name)
                    source = "pdfminer"

                if not text:
                    raise Exception("No text extracted")

                # Step 4️⃣ Normalize extracted data for consistency
                normalized = normalize_textract_resume(text)

                # ✅ Step 5️⃣ Generate embeddings using local SBERT
                from processing.hf_router import embed_text_direct
                embedding = await embed_text_direct(text)
                if not embedding:
                    embedding = []
                # Step 6️⃣ Build final candidate document
                candidate_doc = {
                    "_id": str(uuid.uuid4()),
                    "filename": pdf_key.split("/")[-1],
                    "s3_path": f"s3://{S3_BUCKET}/{pdf_key}",
                    "text": text,
                    "source": source,
                    "embedding": embedding,
                    **normalized,
                }

                # Step 7️⃣ Save in MongoDB
                await db["candidates"].insert_one(candidate_doc)
                results.append({"filename": pdf_key, "status": "success", "source": source})

            except Exception as e:
                results.append({"filename": pdf_key, "status": "failed", "error": str(e)})

        return {"processed": len(results), "results": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing resumes: {e}")


# ------------------------------------------------------------------------
# 3️⃣ Upload Resume(s) to S3 Without Processing (For Bulk Upload Mode)
# ------------------------------------------------------------------------
@router.post("/upload_resume_s3")
async def upload_resume_s3(file: UploadFile = File(...)):
    """
    Upload a single resume directly to S3 and store its parsed details with embeddings in MongoDB.
    """
    try:
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported.")

        # Step 1️⃣ Upload to S3
        s3_key = f"uploads/{file.filename}"
        s3_client.upload_fileobj(file.file, S3_BUCKET, s3_key)
        print(f"✅ Uploaded {file.filename} to S3 bucket {S3_BUCKET}")

        # Step 2️⃣ Extract text using Textract (sync)
        try:
            textract_res = textract.detect_document_text(
                Document={"S3Object": {"Bucket": S3_BUCKET, "Name": s3_key}}
            )
            text = " ".join([b["Text"] for b in textract_res["Blocks"] if b["BlockType"] == "LINE"])
            source = "textract_sync"
        except Exception as textract_err:
            print(f"[WARN] Textract sync failed: {textract_err}")
            # Fallback → PDFMiner extraction
            import tempfile, pdfminer.high_level
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                s3_client.download_file(S3_BUCKET, s3_key, tmp.name)
                text = pdfminer.high_level.extract_text(tmp.name)
            source = "pdfminer"

        # Step 3️⃣ Normalize text
        from processing.normalize import normalize_textract_resume
        normalized = normalize_textract_resume(text)

        # ✅ Step 4️⃣ Generate embeddings
        from processing.hf_router import embed_text_direct
        embedding = await embed_text_direct(text)
        if not embedding:
            embedding = []

        # Step 5️⃣ Build final candidate document
        db = get_database()
        if db is None:
            raise HTTPException(status_code=500, detail="MongoDB not initialized")

        candidate_doc = {
            "_id": str(uuid.uuid4()),
            "filename": file.filename,
            "s3_path": f"s3://{S3_BUCKET}/{s3_key}",
            "text": text,
            "source": source,
            "embedding": embedding,
            **normalized,
        }

        await db["candidates"].insert_one(candidate_doc)

        return {
            "msg": f"{file.filename} uploaded to S3 and processed successfully.",
            "s3_path": f"s3://{S3_BUCKET}/{s3_key}",
            "mongo_id": candidate_doc["_id"],
            "embedding_len": len(embedding),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload and process: {e}")

    





