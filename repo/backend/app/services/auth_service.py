from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    """Return a bcrypt hash of the given password."""
    return pwd_context.hash(password)


def create_access_token(data: dict) -> str:
    """Create a short-lived JWT access token.

    The token embeds all key/value pairs from *data* and adds standard
    ``exp`` and ``iat`` claims.  Lifetime is taken from
    ``settings.ACCESS_TOKEN_EXPIRE_MINUTES`` (default 30).
    """
    import uuid as _uuid
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 30),
    )
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
        "jti": str(_uuid.uuid4()),
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a long-lived JWT refresh token.

    Lifetime is taken from ``settings.REFRESH_TOKEN_EXPIRE_MINUTES`` (default 1440 = 24h).
    """
    import uuid as _uuid
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES,
    )
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
        "jti": str(_uuid.uuid4()),
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token, returning the payload dict.

    Raises ``jose.JWTError`` on invalid or expired tokens.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
