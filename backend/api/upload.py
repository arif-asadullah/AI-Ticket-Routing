"""Upload API — file upload with OCR processing."""

import json
import logging
import os
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from backend.core.auth import require_any_authenticated

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/upload", tags=["upload"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}


@router.post("")
async def upload_file(
    file: UploadFile,
    request: Request,
    user: dict = Depends(require_any_authenticated),
):
    """Upload a screenshot, run OCR, return extracted text and entities."""
    # Validate content type
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"File type '{file.content_type}' not allowed. Use PNG, JPG, GIF, or WEBP.")

    # Read and validate size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large ({len(contents)} bytes). Max 5MB.")

    # Generate unique filename
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "png"
    file_id = str(uuid4())
    filename = f"{file_id}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    # Ensure upload directory exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Save file
    with open(filepath, "wb") as f:
        f.write(contents)

    # Run OCR
    db = getattr(request.app.state, "arango_db", None)
    from backend.services.ocr_engine import extract_from_image
    ocr_result = extract_from_image(filepath, db=db)

    # Cache OCR result as sidecar JSON
    meta = {
        "file_id": file_id,
        "file_url": f"/api/upload/{file_id}",
        "filename": file.filename,
        "ocr_result": ocr_result,
    }
    with open(os.path.join(UPLOAD_DIR, f"{file_id}.json"), "w") as f:
        json.dump(meta, f)

    logger.info("Upload: %s → OCR type=%s, text_len=%d",
                file.filename, ocr_result["screenshot_type"], len(ocr_result["raw_text"]))

    return meta


@router.get("/{file_id}")
async def serve_file(file_id: str, user: dict = Depends(require_any_authenticated)):
    """Serve an uploaded file. Requires authentication."""
    # Match the file id exactly (filename without extension), not a loose prefix.
    for fname in os.listdir(UPLOAD_DIR):
        if fname.endswith(".json"):
            continue
        if fname.rsplit(".", 1)[0] == file_id:
            return FileResponse(os.path.join(UPLOAD_DIR, fname))
    raise HTTPException(404, "File not found")
