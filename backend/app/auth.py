"""LDAP-авторизация: логин/пароль проверяются в каталоге, сессия — JWT в cookie."""

import logging
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Cookie, HTTPException, status
from ldap3 import Connection, Server
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars
from ldap3.utils.dn import escape_rdn

from app.config import settings

logger = logging.getLogger(__name__)

COOKIE_NAME = "tza_session"


class LdapAuthError(Exception):
    """Неверные учётные данные, пользователь не найден или LDAP недоступен."""


def _search_user_dn(conn: Connection, username: str) -> str:
    """search+bind: сервисный аккаунт ищет DN пользователя в каталоге."""
    filter_ = settings.ldap_search_filter.format(username=escape_filter_chars(username))
    conn.search(settings.ldap_base_dn, filter_, attributes=[])
    if not conn.entries:
        raise LdapAuthError("Пользователь не найден в LDAP")
    return conn.entries[0].entry_dn


def _template_user_dn(username: str) -> str:
    """Прямой bind: DN пользователя собирается из ldap_user_dn_template."""
    if not settings.ldap_user_dn_template:
        raise LdapAuthError("LDAP_USER_DN_TEMPLATE не настроен")
    return settings.ldap_user_dn_template.format(
        username=escape_rdn(username), base_dn=settings.ldap_base_dn
    )


def authenticate(username: str, password: str) -> str:
    """Проверяет логин/пароль в LDAP. Возвращает DN аутентифицированного пользователя.

    Два режима, выбираются настройками (см. app/config.py):
    - прямой bind по ldap_user_dn_template;
    - search+bind сервисным аккаунтом ldap_bind_dn (нужен для Active Directory).
    """
    if not settings.ldap_server:
        raise LdapAuthError("LDAP не настроен (LDAP_SERVER пуст)")
    if not username or not password:
        raise LdapAuthError("Пустой логин или пароль")

    server = Server(settings.ldap_server, use_ssl=settings.ldap_use_ssl)
    try:
        if settings.ldap_bind_dn:
            with Connection(
                server,
                user=settings.ldap_bind_dn,
                password=settings.ldap_bind_password,
                auto_bind=True,
            ) as search_conn:
                user_dn = _search_user_dn(search_conn, username)
        else:
            user_dn = _template_user_dn(username)

        with Connection(server, user=user_dn, password=password, auto_bind=True):
            pass
    except LdapAuthError:
        raise
    except LDAPException as exc:
        logger.warning("LDAP-аутентификация не удалась для %s: %s", username, exc)
        raise LdapAuthError("Неверный логин или пароль") from exc

    return user_dn


def create_access_token(username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Сессия недействительна"
        ) from exc
    return payload["sub"]


def require_user(session: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> str:
    """FastAPI-зависимость: текущий пользователь или 401."""
    if not settings.auth_enabled:
        return "dev"
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация"
        )
    return _decode_access_token(session)
