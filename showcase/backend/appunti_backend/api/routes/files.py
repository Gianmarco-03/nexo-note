from __future__ import annotations

import hashlib
import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from appunti_backend.api.deps import get_current_user, get_db
from appunti_backend.core.config import settings
from appunti_backend.db.models import StoredFile, User
from appunti_backend.schemas.files import StoredFileResponse


router = APIRouter()

CHUNK_SIZE = 4 * 1024 * 1024
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(filename: str) -> str:
    trimmed = filename.strip() or "upload.bin"
    return SAFE_FILENAME_RE.sub("_", trimmed)[:180] or "upload.bin"


def _owned_file(db: Session, user_id: str, file_id: str) -> StoredFile | None:
    return db.scalar(
        select(StoredFile).where(StoredFile.id == file_id, StoredFile.user_id == user_id)
    )


@router.post("/upload", response_model=StoredFileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StoredFileResponse:
    original_name = _safe_filename(file.filename or "upload.bin")
    user_dir = settings.upload_dir / current_user.id
    user_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid4().hex}_{original_name}"
    target_path = user_dir / stored_name
    sha256 = hashlib.sha256()
    size_bytes = 0
    max_size_bytes = settings.max_upload_size_mb * 1024 * 1024

    try:
        with target_path.open("wb") as output:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > max_size_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File oltre il limite di {settings.max_upload_size_mb} MB.",
                    )
                sha256.update(chunk)
                output.write(chunk)
    except Exception:
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    stored_file = StoredFile(
        user_id=current_user.id,
        original_name=original_name,
        stored_name=stored_name,
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=size_bytes,
        sha256=sha256.hexdigest(),
        storage_path=str(target_path),
    )
    db.add(stored_file)
    db.commit()
    db.refresh(stored_file)
    return StoredFileResponse.model_validate(stored_file)


@router.get("", response_model=list[StoredFileResponse])
def list_files(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[StoredFileResponse]:
    files = db.scalars(
        select(StoredFile)
        .where(StoredFile.user_id == current_user.id)
        .order_by(StoredFile.created_at.desc())
    ).all()
    return [StoredFileResponse.model_validate(file) for file in files]


@router.get("/{file_id}", response_model=StoredFileResponse)
def get_file_metadata(
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StoredFileResponse:
    stored_file = _owned_file(db, current_user.id, file_id)
    if not stored_file:
        raise HTTPException(status_code=404, detail="File non trovato.")
    return StoredFileResponse.model_validate(stored_file)


@router.get("/{file_id}/download")
def download_file(
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stored_file = _owned_file(db, current_user.id, file_id)
    if not stored_file:
        raise HTTPException(status_code=404, detail="File non trovato.")

    target_path = Path(stored_file.storage_path)
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Contenuto file non presente su disco.")

    return FileResponse(
        path=target_path,
        media_type=stored_file.mime_type,
        filename=stored_file.original_name,
    )


@router.delete("/{file_id}")
def delete_file(
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, bool]:
    stored_file = _owned_file(db, current_user.id, file_id)
    if not stored_file:
        raise HTTPException(status_code=404, detail="File non trovato.")

    target_path = Path(stored_file.storage_path)
    db.delete(stored_file)
    db.commit()
    target_path.unlink(missing_ok=True)
    return {"deleted": True}
