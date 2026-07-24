from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_base_url: str = "http://llm-gateway.internal/v1"
    llm_api_key: str = "not-needed"
    llm_model: str = "qwen2.5-32b-instruct"
    llm_temperature: float = 0.2
    llm_timeout_seconds: int = 120

    # Эмбеддинги: пустой base_url/api_key = использовать llm_base_url/llm_api_key.
    # По имени модели выбираются retrieval-префиксы (см. rag/embeddings.py):
    # "frida" → search_document:/search_query:, "e5" → passage:/query:
    embeddings_model: str = "frida"
    embeddings_base_url: str = ""
    embeddings_api_key: str = ""

    # Qdrant: http(s)://host:port, ":memory:" или локальный путь (dev без сервера)
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "tz_examples"
    rag_top_k: int = 4
    # Минимальный косинусный score, чтобы фрагмент считался релевантным примером:
    # без порога на нетематический запрос («привет, продолжим») в промпт всё
    # равно попадали бы случайные чанки. Порог зависит от модели эмбеддингов
    # (распределения score у FRIDA и e5 разные) — откалибруйте по своей базе:
    # ретривер пишет score кандидатов в лог, посмотрите значения релевантных
    # и нерелевантных выдач и подвиньте порог. Дефолт консервативный, чтобы
    # порог не «съел» все примеры на незнакомой модели.
    rag_min_score: float = 0.5
    # Максимум примеров с одного документа: 3 примера из разных ТЗ передают
    # стиль лучше, чем 4 куска одного и того же
    rag_max_per_doc: int = 2
    # Общий бюджет символов на блок примеров (примеры теперь целые разделы
    # до 8000 символов — без потолка они вытеснили бы из контекста остальное)
    examples_max_chars: int = 12000

    # Документ ТЗ хранится как список разделов (не одной строкой) — иначе
    # документ на 200 000 слов не влезает ни в контекст LLM, ни в лимит
    # генерации при переписывании целиком. Разделы крупнее потолка
    # переразбиваются эвристиками/фиксированным окном (см. app/spec_doc.py).
    spec_max_section_chars: int = 20000
    # Сколько разделов рабочего документа подгружать в промпт целиком на
    # каждом ходу (ретривал по самому документу, а не только по примерам)
    spec_rag_top_k: int = 4
    # Потолок супершагов графа на один ход пользователя. У LangGraph по
    # умолчанию 25 — на большом документе агент упирается в него, пока
    # читает разделы. Один раунд «LLM → инструменты» = 2 шага.
    graph_recursion_limit: int = 100
    # Максимум символов, которые один вызов get_sections вернёт в контекст —
    # защита от чтения десятков разделов разом (не поместившиеся id агенту
    # предлагается запросить следующим вызовом)
    spec_read_max_chars: int = 60000
    # Бюджет блока <relevant_sections> в системном промпте: top_k разделов по
    # 20 000 символов иначе могут съесть весь контекст LLM ещё до истории
    spec_relevant_max_chars: int = 24000

    # Бюджеты истории диалога, передаваемой LLM (сама история в чекпоинте не
    # обрезается — только то, что уходит в промпт, см. app/graph/history.py):
    # общий потолок символов; старые ходы отбрасываются целиком
    history_max_chars: int = 60000
    # результаты инструментов из прошлых ходов длиннее этого — заменяются
    # заглушкой (чтение раздела на 20 000 символов не должно жить в истории вечно)
    history_tool_result_keep_chars: int = 1500
    # строковые аргументы tool_calls из прошлых ходов (например, new_text
    # update_section) обрезаются до этого размера
    history_tool_arg_keep_chars: int = 500

    # Сколько последних чекпоинтов LangGraph держать на сессию: каждый хранит
    # полную копию состояния (для большого ТЗ — мегабайты), без подрезки файл
    # растёт на десятки МБ за ход
    checkpoint_keep_last: int = 20

    # Оригиналы загруженных .docx + карты «раздел → блоки» (app/originals.py):
    # экспорт патчит оригинал, сохраняя шаблон/картинки/стили нетронутых разделов
    originals_dir: str = "./data/originals"

    # Кэш эмбеддингов разделов рабочего документа. Лежит в отдельном SQLite,
    # а не в состоянии графа: векторы (~9 КБ на раздел) иначе копируются в
    # каждый чекпоинт каждого супершага
    section_index_db_path: str = "./data/section_index.sqlite3"

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
