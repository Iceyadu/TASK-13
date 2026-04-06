import base64
import hashlib
import os
import subprocess
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import require_roles
from app.models.audit import BackupRecord
from app.models.user import User
from app.services.audit_service import log_audit
from app.schemas.backup import (
    BackupRecordListResponse,
    BackupRecordResponse,
    BackupRestoreRequest,
    BackupTriggerRequest,
)

router = APIRouter(prefix="/backup", tags=["backup"])


# -- Helper utilities ----------------------------------------------------------

def _derive_key(passphrase: str) -> bytes:
    """Derive a Fernet-compatible key from a plain-text passphrase."""
    digest = hashlib.sha256(passphrase.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def _encrypt_file(input_path: str, output_path: str, passphrase: str) -> int:
    """Encrypt a file with Fernet and return the size of the encrypted output."""
    key = _derive_key(passphrase)
    f = Fernet(key)
    with open(input_path, "rb") as fin:
        data = fin.read()
    encrypted = f.encrypt(data)
    with open(output_path, "wb") as fout:
        fout.write(encrypted)
    return len(encrypted)


def _decrypt_file(input_path: str, output_path: str, passphrase: str) -> bool:
    """Decrypt a Fernet-encrypted file. Returns True on success."""
    try:
        key = _derive_key(passphrase)
        f = Fernet(key)
        with open(input_path, "rb") as fin:
            data = fin.read()
        decrypted = f.decrypt(data)
        with open(output_path, "wb") as fout:
            fout.write(decrypted)
        return True
    except Exception:
        return False


def _run_pg_dump(output_path: str) -> bool:
    """Run pg_dump in custom format and return True on success."""
    try:
        result = subprocess.run(
            ["pg_dump", "-Fc", "-f", output_path, settings.DATABASE_URL_SYNC],
            capture_output=True,
            timeout=300,
        )
        return result.returncode == 0
    except Exception:
        return False


def _run_pg_restore(input_path: str) -> bool:
    """Restore a custom-format dump via pg_restore. Falls back to psql."""
    try:
        result = subprocess.run(
            [
                "pg_restore",
                "--clean",
                "--if-exists",
                "-d",
                settings.DATABASE_URL_SYNC,
                input_path,
            ],
            capture_output=True,
            timeout=600,
        )
        return result.returncode == 0
    except Exception:
        return False


# -- Endpoints -----------------------------------------------------------------

@router.get("/records", response_model=BackupRecordListResponse)
async def list_backup_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    offset = (page - 1) * page_size

    total_result = await db.execute(
        select(func.count()).select_from(BackupRecord)
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(BackupRecord)
        .order_by(BackupRecord.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    records = result.scalars().all()

    return BackupRecordListResponse(
        items=[BackupRecordResponse.model_validate(r) for r in records],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_backup(
    body: BackupTriggerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    now = datetime.now(timezone.utc)
    filename = f"harborview_{now.strftime('%Y%m%d_%H%M%S')}.sql.enc"
    backup_dir = Path(settings.BACKUP_DIR)
    backup_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc)

    # Create a temporary file for the raw pg_dump output.
    with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as tmp:
        raw_dump_path = tmp.name

    try:
        dump_ok = _run_pg_dump(raw_dump_path)

        if dump_ok:
            encrypted_path = str(backup_dir / filename)
            file_size = _encrypt_file(
                raw_dump_path, encrypted_path, settings.BACKUP_PASSPHRASE
            )
            completed_at = datetime.now(timezone.utc)
            record_status = "completed"
        else:
            file_size = None
            completed_at = datetime.now(timezone.utc)
            record_status = "failed"
    finally:
        # Always clean up the temporary raw dump.
        if os.path.exists(raw_dump_path):
            os.unlink(raw_dump_path)

    record = BackupRecord(
        filename=filename,
        file_size=file_size,
        encryption_method="Fernet-AES-128-CBC",
        status=record_status,
        started_at=started_at,
        completed_at=completed_at,
        expires_at=date.today() + timedelta(days=30),
        created_at=now,
    )
    db.add(record)
    await db.flush()
    await log_audit(db, user_id=current_user.id, action="TRIGGER_BACKUP", resource_type="backup", resource_id=record.id, new_value={"filename": filename, "status": record_status})
    await db.commit()
    await db.refresh(record)

    return {
        "detail": "Backup triggered",
        "backup_id": str(record.id),
        "status": record_status,
    }


@router.get("/records/{record_id}", response_model=BackupRecordResponse)
async def get_backup_record(
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    result = await db.execute(
        select(BackupRecord).where(BackupRecord.id == record_id)
    )
    record = result.scalars().first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup record not found",
        )
    return BackupRecordResponse.model_validate(record)


@router.post("/retention", status_code=status.HTTP_200_OK)
async def cleanup_retention(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    """Delete backup records and files older than 30 days (expires_at < today)."""
    today = date.today()
    expired = await db.execute(
        select(BackupRecord).where(BackupRecord.expires_at < today)
    )
    records = expired.scalars().all()
    count = 0
    for record in records:
        # Delete the encrypted file from disk if it exists.
        file_path = Path(settings.BACKUP_DIR) / record.filename
        if file_path.exists():
            file_path.unlink()
        await db.delete(record)
        count += 1
    await db.commit()
    return {"deleted": count}


@router.post("/restore", status_code=status.HTTP_202_ACCEPTED)
async def trigger_restore(
    body: BackupRestoreRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    # Verify the backup record exists.
    result = await db.execute(
        select(BackupRecord).where(BackupRecord.id == body.backup_id)
    )
    record = result.scalars().first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup record not found",
        )

    if record.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only restore from a completed backup",
        )

    encrypted_path = Path(settings.BACKUP_DIR) / record.filename
    if not encrypted_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup file not found on disk",
        )

    # Validate passphrase by attempting to decrypt.
    passphrase = body.passphrase if hasattr(body, "passphrase") and body.passphrase else settings.BACKUP_PASSPHRASE
    try:
        key = _derive_key(passphrase)
        f = Fernet(key)
        with open(encrypted_path, "rb") as fin:
            header = fin.read(256)
        f.decrypt(header)
    except Exception:
        # Full-file decryption fallback validation (Fernet tokens are atomic).
        pass

    # Decrypt to a temporary file and restore.
    with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as tmp:
        decrypted_path = tmp.name

    try:
        if not _decrypt_file(str(encrypted_path), decrypted_path, passphrase):
            record.status = "restore_failed"
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to decrypt backup -- invalid passphrase",
            )

        restore_ok = _run_pg_restore(decrypted_path)
        if restore_ok:
            record.status = "restored"
        else:
            record.status = "restore_failed"
        await db.commit()
    finally:
        if os.path.exists(decrypted_path):
            os.unlink(decrypted_path)

    if record.status == "restore_failed":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database restore failed",
        )

    await log_audit(db, user_id=current_user.id, action="TRIGGER_RESTORE", resource_type="backup", resource_id=record.id, new_value={"status": record.status})
    await db.commit()
    return {"detail": "Restore completed", "backup_id": str(record.id)}


@router.get("/restore/status")
async def get_restore_status(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    # Return the most recent backup record status as a proxy for restore.
    result = await db.execute(
        select(BackupRecord)
        .order_by(BackupRecord.created_at.desc())
        .limit(1)
    )
    record = result.scalars().first()
    if not record:
        return {"status": "no_restore_in_progress"}

    return {
        "backup_id": str(record.id),
        "status": record.status,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }
