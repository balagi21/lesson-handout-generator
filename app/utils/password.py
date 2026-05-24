import bcrypt

from .const import PASSWORD_MAX_LENGTH


def hash_password(password: str) -> str:
    """Хеширует пароль, обрезая до 72 символов (ограничение bcrypt)"""
    password_bytes = password.encode('utf-8')[:PASSWORD_MAX_LENGTH]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет пароль"""
    plain_bytes = plain_password.encode('utf-8')[:PASSWORD_MAX_LENGTH]
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(plain_bytes, hashed_bytes)
