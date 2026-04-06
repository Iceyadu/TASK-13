import os
import uuid as uuid_mod
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models.media import Media
from app.models.user import User
from app.schemas.media import MediaResponse

router = APIRouter(tags=["media"])

UPLOAD_DIR = Path(settings.UPLOAD_DIR)

ALLOWED_IMAGE_MIME = {"image/jpeg", "image/png"}
ALLOWED_VIDEO_MIME = {"video/mp4"}
ALL_ALLOWED_MIME = ALLOWED_IMAGE_MIME | ALLOWED_VIDEO_MIME

MAX_IMAGE_SIZE = settings.MAX_IMAGE_SIZE       # 10 MB
MAX_VIDEO_SIZE = settings.MAX_VIDEO_SIZE       # 200 MB

# Magic byte signatures for real file-type detection
MAGIC_JPEG = b"\xff\xd8\xff"
MAGIC_PNG = b"\x89PNG\r\n\x1a\n"
MAGIC_MP4_FTYP = b"ftyp"  # appears at offset 4 in MP4 files

MIME_BY_MAGIC = {
    "image/jpeg": lambda data: data[:3] == MAGIC_JPEG,
    "image/png": lambda data: data[:8] == MAGIC_PNG,
    "video/mp4": lambda data: len(data) >= 8 and data[4:8] == MAGIC_MP4_FTYP,
}


async def _validate_and_read(file: UploadFile) -> tuple[bytes, str]:
    """Read file content, validate type by magic bytes and size. Returns (content, mime_type)."""
    content = await file.read()
    declared_mime = (file.content_type or "").lower()

    # Determine actual MIME from magic bytes
    detected_mime: str | None = None
    for mime, checker in MIME_BY_MAGIC.items():
        if checker(content):
            detected_mime = mime
            break

    # If declared type is an allowed type, magic bytes MUST match
    if declared_mime in ALL_ALLOWED_MIME and detected_mime is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File content does not match declared type '{declared_mime}'. "
                   f"Allowed: JPG, PNG, MP4",
        )

    # Use detected MIME if available, fall back to declared
    actual_mime = detected_mime or declared_mime

    if actual_mime not in ALL_ALLOWED_MIME:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type. Allowed: JPG, PNG, MP4. "
                   f"Detected: {actual_mime or 'unknown'}",
        )

    file_size = len(content)

    # Size limits by type
    if actual_mime in ALLOWED_IMAGE_MIME:
        if file_size > MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Image file exceeds 10 MB limit ({file_size:,} bytes)",
            )
    elif actual_mime in ALLOWED_VIDEO_MIME:
        if file_size > MAX_VIDEO_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Video file exceeds 200 MB limit ({file_size:,} bytes)",
            )

    return content, actual_mime


def _save_to_disk(content: bytes, ext: str) -> tuple[str, str]:
    """Write content to UPLOAD_DIR. Returns (uuid_filename, full_path_str)."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    uuid_filename = f"{uuid_mod.uuid4()}{ext}"
    full_path = UPLOAD_DIR / uuid_filename
    with open(full_path, "wb") as f:
        f.write(content)
    return uuid_filename, str(full_path)


# -- General media upload ------------------------------------------------------

@router.post(
    "/media/upload", response_model=MediaResponse, status_code=status.HTTP_201_CREATED
)
async def upload_media(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content, actual_mime = await _validate_and_read(file)
    ext = os.path.splitext(file.filename or "")[1] or _ext_for_mime(actual_mime)
    uuid_filename, full_path = _save_to_disk(content, ext)

    media = Media(
        filename=uuid_filename,
        original_name=file.filename or "unknown",
        mime_type=actual_mime,
        file_size=len(content),
        storage_path=full_path,
        uploaded_by=current_user.id,
    )
    db.add(media)
    await db.commit()
    await db.refresh(media)
    return MediaResponse.model_validate(media)


@router.get("/media/{media_id}", response_model=MediaResponse)
async def get_media(
    media_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    media = await _get_media_or_404(db, media_id)
    await _enforce_media_access(db, current_user, media)
    return MediaResponse.model_validate(media)


@router.get("/media/{media_id}/file")
async def get_media_file(
    media_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    media = await _get_media_or_404(db, media_id)
    await _enforce_media_access(db, current_user, media)
    file_path = Path(media.storage_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk"
        )
    return FileResponse(
        path=str(file_path),
        media_type=media.mime_type,
        filename=media.original_name,
    )


@router.delete("/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media(
    media_id: UUID,
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(require_roles("admin", "property_manager")),
):
    media = await _get_media_or_404(db, media_id)
    _delete_file_on_disk(media.storage_path)
    await db.delete(media)
    await db.commit()
    return None


# -- Listing media -------------------------------------------------------------

@router.post(
    "/listings/{listing_id}/media",
    response_model=MediaResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_listing_media(
    listing_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "property_manager")),
):
    from app.models.listing import Listing, ListingMedia

    listing_result = await db.execute(
        select(Listing).where(Listing.id == listing_id)
    )
    if not listing_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found"
        )

    content, actual_mime = await _validate_and_read(file)
    ext = os.path.splitext(file.filename or "")[1] or _ext_for_mime(actual_mime)
    uuid_filename, full_path = _save_to_disk(content, ext)

    media = Media(
        filename=uuid_filename,
        original_name=file.filename or "unknown",
        mime_type=actual_mime,
        file_size=len(content),
        storage_path=full_path,
        uploaded_by=current_user.id,
    )
    db.add(media)
    await db.flush()

    link = ListingMedia(
        listing_id=listing_id,
        media_id=media.id,
    )
    db.add(link)
    await db.commit()
    await db.refresh(media)
    return MediaResponse.model_validate(media)


@router.delete(
    "/listings/{listing_id}/media/{media_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_listing_media(
    listing_id: UUID,
    media_id: UUID,
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(require_roles("admin", "property_manager")),
):
    from app.models.listing import ListingMedia

    result = await db.execute(
        select(ListingMedia).where(
            ListingMedia.listing_id == listing_id,
            ListingMedia.media_id == media_id,
        )
    )
    link = result.scalars().first()
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found for this listing",
        )

    await db.delete(link)

    media = await _get_media_or_404(db, media_id)
    _delete_file_on_disk(media.storage_path)
    await db.delete(media)

    await db.commit()
    return None


# -- Helpers -------------------------------------------------------------------

async def _get_media_or_404(db: AsyncSession, media_id: UUID) -> Media:
    result = await db.execute(select(Media).where(Media.id == media_id))
    media = result.scalars().first()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Media not found"
        )
    return media


def _delete_file_on_disk(storage_path: str) -> None:
    file_path = Path(storage_path)
    if file_path.exists():
        file_path.unlink()


async def _enforce_media_access(db: AsyncSession, current_user: User, media: Media) -> None:
    """Residents can only access media they uploaded or media linked to published listings."""
    if current_user.role != "resident":
        return
    if media.uploaded_by == current_user.id:
        return
    # Check if media is linked to a published listing
    from app.models.listing import Listing, ListingMedia
    link_result = await db.execute(
        select(ListingMedia).where(ListingMedia.media_id == media.id)
    )
    link = link_result.scalars().first()
    if link:
        listing_result = await db.execute(
            select(Listing).where(Listing.id == link.listing_id)
        )
        listing = listing_result.scalars().first()
        if listing and listing.status == "published":
            return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
    )


def _ext_for_mime(mime: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "video/mp4": ".mp4",
    }.get(mime, ".bin")
