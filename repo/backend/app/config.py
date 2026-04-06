from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://harborview:harborview_secret@db:5432/harborview"
    DATABASE_URL_SYNC: str = "postgresql://harborview:harborview_secret@db:5432/harborview"

    # Security
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    ALGORITHM: str = "HS256"
    BCRYPT_ROUNDS: int = 12

    # Encryption
    ENCRYPTION_KEY: str = ""

    # File storage
    UPLOAD_DIR: str = "/data/uploads"
    MAX_IMAGE_SIZE: int = 10 * 1024 * 1024       # 10 MB
    MAX_VIDEO_SIZE: int = 200 * 1024 * 1024       # 200 MB
    ALLOWED_IMAGE_TYPES: list[str] = ["image/jpeg", "image/png"]
    ALLOWED_VIDEO_TYPES: list[str] = ["video/mp4"]

    # Backup
    BACKUP_DIR: str = "/data/backups"
    BACKUP_PASSPHRASE: str = "backup-default-passphrase"
    BACKUP_RETENTION_DAYS: int = 30

    # Application
    APP_NAME: str = "HarborView Property Operations Portal"
    API_V1_PREFIX: str = "/api/v1"

    # Default admin seed
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "Admin@Harbor2026"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
