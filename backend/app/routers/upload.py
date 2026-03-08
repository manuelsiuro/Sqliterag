import logging
import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Ensure upload directory exists
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Allowed image mime types
ALLOWED_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

@router.post("/upload/image")
async def upload_image(file: UploadFile = File(...)):
    """Accept an image file, save it to disk, and return the relative path."""
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type: {file.content_type}. Allowed: {', '.join(ALLOWED_MIME_TYPES.keys())}"
        )

    ext = ALLOWED_MIME_TYPES[file.content_type]
    filename = f"{uuid.uuid4()}{ext}"
    file_path = UPLOAD_DIR / filename
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to save uploaded image: {e}")
        raise HTTPException(status_code=500, detail="Failed to save image file on server.")
        
    return {"path": str(file_path)}
