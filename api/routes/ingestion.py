import os
import uuid
import httpx
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

router = APIRouter(prefix="/ingestion", tags=["ingestion"])

class IngestionRequest(BaseModel):
    pdf_url: str
    subject: str
    grade: int

async def _download_and_ingest(url: str, subject: str, grade: int):
    tmp_path = f"/tmp/{uuid.uuid4()}.pdf"
    try:
        print(f"Starting ingestion background task for {subject} Grade {grade}")
        # Download file
        async with httpx.AsyncClient() as client:
            # We follow redirects in case Cloudinary redirects
            response = await client.get(url, timeout=300.0, follow_redirects=True)
            response.raise_for_status()
            with open(tmp_path, "wb") as f:
                for chunk in response.aiter_bytes():
                    f.write(chunk)
        
        print(f"Downloaded PDF to {tmp_path}, starting script...")
        # Run ingestion
        from scripts.ingest_textbook import run
        await run(tmp_path, subject, grade, dry_run=False, no_content=False)
        print(f"Ingestion background task completed for {subject} Grade {grade}")
        
    except Exception as e:
        print(f"Ingestion background task failed: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

@router.post("/trigger")
async def trigger_ingestion(body: IngestionRequest, background_tasks: BackgroundTasks):
    """
    Trigger an asynchronous textbook ingestion pipeline.
    Downloads the PDF from Cloudinary, extracts text, detects topics, seeds the DB,
    generates embeddings, and generates AI lessons/questions in the background.
    """
    background_tasks.add_task(_download_and_ingest, body.pdf_url, body.subject, body.grade)
    return {"status": "accepted", "message": "Textbook ingestion started in the background."}
