# backend/resume/textract.py
import boto3
import os
import time
import pdfminer.high_level
from dotenv import load_dotenv
from fastapi import UploadFile
import tempfile
from processing.normalize import normalize_textract_resume  # 🧠 new import

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
S3_BUCKET = os.getenv("S3_BUCKET", "skilllens-resumes")

textract = boto3.client(
    "textract",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

async def extract_text_from_pdf(file: UploadFile):
    """
    Upload PDF to S3 → extract text using Textract (sync/async) → fallback to PDFMiner if needed.
    Returns normalized text payload ready for MongoDB.
    """
    tmp_path = None
    try:
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name

        s3_key = f"uploads/{file.filename}"
        s3_client.upload_file(tmp_path, S3_BUCKET, s3_key)

        try:
            response = textract.detect_document_text(
                Document={"S3Object": {"Bucket": S3_BUCKET, "Name": s3_key}}
            )
            text = " ".join([block["Text"] for block in response["Blocks"] if block["BlockType"] == "LINE"])
            source = "textract_sync"

        except textract.exceptions.UnsupportedDocumentException:
            print("[INFO] Falling back to async Textract...")
            job = textract.start_document_text_detection(
                DocumentLocation={"S3Object": {"Bucket": S3_BUCKET, "Name": s3_key}}
            )
            job_id = job["JobId"]

            while True:
                status = textract.get_document_text_detection(JobId=job_id)
                job_status = status["JobStatus"]
                if job_status in ["SUCCEEDED", "FAILED"]:
                    break
                time.sleep(2)

            if job_status != "SUCCEEDED":
                raise Exception("Async Textract job failed.")

            pages, next_token = [], None
            while True:
                if next_token:
                    response = textract.get_document_text_detection(JobId=job_id, NextToken=next_token)
                else:
                    response = textract.get_document_text_detection(JobId=job_id)

                pages.extend(
                    [block["Text"] for block in response["Blocks"] if block["BlockType"] == "LINE"]
                )

                next_token = response.get("NextToken")
                if not next_token:
                    break

            text = " ".join(pages)
            source = "textract_async"

        # 🧩 Normalize here — consistent schema for MongoDB
        normalized = normalize_textract_resume(text)
        normalized["text"] = text
        normalized["source"] = source
        normalized["s3_path"] = f"s3://{S3_BUCKET}/{s3_key}"

        return normalized

    except Exception as e:
        print(f"[WARN] Textract failed: {e}")
        try:
            text = pdfminer.high_level.extract_text(tmp_path)
            normalized = normalize_textract_resume(text)
            normalized["text"] = text
            normalized["source"] = "pdfminer"
            return normalized
        except Exception as e2:
            return {"error": f"Both Textract and PDFMiner failed: {e2}"}

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
