from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.exceptions import ValidationException


ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


async def save_profile_photo(file: UploadFile, category: str) -> str:
    """Store an uploaded profile photo and return its public URL."""
    extension = ALLOWED_IMAGE_TYPES.get(file.content_type or "")
    if not extension:
        await file.close()
        raise ValidationException(
            code="INVALID_IMAGE_TYPE",
            message="Foto harus berformat JPG, PNG, atau WebP",
        )

    settings = get_settings()
    max_size = settings.PROFILE_PHOTO_MAX_SIZE_BYTES
    content = await file.read(max_size + 1)
    await file.close()
    if not content:
        raise ValidationException(code="EMPTY_IMAGE", message="File foto tidak boleh kosong")
    if len(content) > max_size:
        raise ValidationException(
            code="IMAGE_TOO_LARGE",
            message=f"Ukuran foto maksimal {max_size // (1024 * 1024)} MB",
        )

    target_dir = Path(settings.UPLOAD_DIR).resolve() / category
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4()}{extension}"
    (target_dir / filename).write_bytes(content)
    return f"{settings.UPLOAD_URL_PREFIX}/{category}/{filename}"


def delete_uploaded_file(public_url: str) -> bool:
    """Delete only files located below the configured public upload root."""
    settings = get_settings()
    prefix = settings.UPLOAD_URL_PREFIX.rstrip("/") + "/"
    if not public_url.startswith(prefix):
        return False
    relative_path = public_url.removeprefix(prefix)
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    target = (upload_root / relative_path).resolve()
    if target == upload_root or upload_root not in target.parents:
        return False
    try:
        if target.is_file():
            target.unlink()
            return True
    except OSError:
        return False
    return False
