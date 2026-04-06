import os
import aiofiles
from pathlib import Path
from app.config import settings

async def save_file(content: bytes, relative_path: str) -> str:
    full_path = Path(settings.UPLOAD_DIR) / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(full_path, "wb") as f:
        await f.write(content)
    return relative_path

async def get_file_stream(relative_path: str):
    full_path = Path(settings.UPLOAD_DIR) / relative_path
    if not full_path.exists():
        raise FileNotFoundError(f"File not found: {relative_path}")
    async def _stream():
        async with aiofiles.open(full_path, "rb") as f:
            while chunk := await f.read(8192):
                yield chunk
    return _stream()

async def delete_file(relative_path: str) -> None:
    full_path = Path(settings.UPLOAD_DIR) / relative_path
    if full_path.exists():
        os.remove(full_path)
