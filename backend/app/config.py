from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_base_url: str = "http://llm-gateway.internal/v1"
    llm_api_key: str = "not-needed"
    llm_model: str = "qwen2.5-32b-instruct"
    llm_temperature: float = 0.2
    llm_timeout_seconds: int = 120

    # Эмбеддинги: пустой base_url/api_key = использовать llm_base_url/llm_api_key
    embeddings_base_url: str = ""
    embeddings_api_key: str = ""
    embeddings_model: str = "multilingual-e5-large"

    # Qdrant: http(s)://host:port, ":memory:" или локальный путь (dev без сервера)
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "tz_examples"
    rag_top_k: int = 4

    # Документ ТЗ хранится как список разделов (не одной строкой) — иначе
    # документ на 200 000 слов не влезает ни в контекст LLM, ни в лимит
    # генерации при переписывании целиком. Разделы крупнее потолка
    # переразбиваются эвристиками/фиксированным окном (см. app/spec_doc.py).
    spec_max_section_chars: int = 20000
    # Сколько разделов рабочего документа подгружать в промпт целиком на
    # каждом ходу (ретривал по самому документу, а не только по примерам)
    spec_rag_top_k: int = 4

    # Папка с примерами реальных ТЗ; фоновое задание синхронизирует её с Qdrant
    examples_dir: str = "./data/examples"
    examples_scan_interval_seconds: int = 60

    # Персистентное хранилище сессий (чекпоинты LangGraph + метаданные сессий:
    # владелец/заголовок/время). SQLite-файл — сессии переживают перезапуск
    # бэкенда и доступны пользователю при повторном входе (см. app/sessions.py).
    checkpoint_db_path: str = "./data/checkpoints.sqlite3"

    # MCP-сервер ADT tools (чтение объектов SAP); пустой URL = без SAP-инструментов
    mcp_server_url: str = ""
    mcp_transport: str = "streamable_http"
    mcp_auth_token: str = ""

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Авторизация через LDAP. auth_enabled=False снимает требование логина
    # (для локальной разработки без LDAP-сервера под рукой).
    auth_enabled: bool = True

    # host[:port] или ldap(s)://host:port — сервер каталога
    ldap_server: str = ""
    ldap_use_ssl: bool = True
    ldap_base_dn: str = ""
    # Прямой bind: логин подставляется в шаблон DN, например
    # "uid={username},ou=people,dc=example,dc=com" (типично для OpenLDAP).
    # Оставить пустым, если используется сервисный аккаунт ниже.
    ldap_user_dn_template: str = ""
    # Сервисный аккаунт для режима search+bind — нужен для Active Directory,
    # где DN пользователя заранее не известен: сервисный аккаунт ищет
    # пользователя по ldap_search_filter, затем бинд выполняется под найденным
    # DN с паролем пользователя. Пусто = прямой bind по шаблону выше.
    ldap_bind_dn: str = ""
    ldap_bind_password: str = ""
    ldap_search_filter: str = "(uid={username})"

    jwt_secret: str = "CHANGE_ME_JWT_SECRET"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480
    # True в проде за HTTPS — cookie сессии не уйдёт по обычному http
    auth_cookie_secure: bool = False


settings = Settings()
